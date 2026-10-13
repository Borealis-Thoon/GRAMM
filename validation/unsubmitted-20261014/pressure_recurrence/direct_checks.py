"""Extract and check all sixteen pressure recurrence blocks against the candidate."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess


def invoke(cmd):
    r=subprocess.run(cmd,text=True,encoding='utf-8',capture_output=True)
    if r.returncode:
        print(r.stdout+r.stderr)
        raise RuntimeError('Command failed: '+cmd[0])
    return r.stdout


def block(text,start):
    begin=text.index(start);opening=text.index('{',begin);depth=0
    for end in range(opening,len(text)):
        if text[end]=='{':depth+=1
        elif text[end]=='}':
            depth-=1
            if depth==0:return text[begin:end+1]
    raise ValueError('Unclosed source block')


def emit_class(name,blocks):
    methods=[]
    for i,formula in enumerate(blocks):
        methods.append(f'''    public static void E{i}(int NK, double[] AP_L, double[] AB_L, double[] AT_L, double[] source, double[] pResult, double[] qResult)
    {{
        int NK_P=NK;
        Span<double> PIM=stackalloc double[2*NK+2];
        Span<double> QIM=stackalloc double[2*NK+2];
        if (BitConverter.DoubleToInt64Bits(PIM[2*(NK-1)+1])!=0 || BitConverter.DoubleToInt64Bits(QIM[2*(NK-1)+1])!=0) throw new Exception("Nonzero stack top boundary");
        double TERMP, DIM;
        for(int kn=2*(NK_P-1);kn>=1;--kn)
        {{
            DIM=source[kn];
{formula}
        }}
        for(int k=1;k<=2*(NK-1);k++) {{pResult[k]=PIM[k];qResult[k]=QIM[k];}}
    }}''')
    cases='\n'.join(f'            case {i}: E{i}(NK,AP,AB,AT,source,p,q); break;' for i in range(len(blocks)))
    return 'static class '+name+'\n{\n'+'\n'.join(methods)+f'''\n    public static void Run(int id,int NK,double[] AP,double[] AB,double[] AT,double[] source,double[] p,double[] q)
    {{
        switch(id) {{
{cases}
            default: throw new ArgumentOutOfRangeException(nameof(id));
        }}
    }}
}}\n'''

HARNESS=r'''
static class Harness
{
    static long recurrenceCases, comparisons, finiteComparisons, nonfiniteComparisons, mismatches, boundaryCases, pressureOffCases;
    static readonly List<string> failures=new();
    static void Check(double expected,double actual,string label)
    {
        comparisons++;
        if(double.IsFinite(expected)) finiteComparisons++;else nonfiniteComparisons++;
        if(BitConverter.DoubleToInt64Bits(expected)!=BitConverter.DoubleToInt64Bits(actual))
        {mismatches++;if(failures.Count<12) failures.Add(label);}
    }
    static void One(int nk,int mode,int seed)
    {
        int n=2*nk+2,top=2*(nk-1);
        double[] ap=new double[n],ab=new double[n],at=new double[n],dim=new double[n];
        Random r=new(seed);
        for(int k=0;k<n;k++)
        {
            ap[k]=2+r.NextDouble()*8;ab[k]=r.NextDouble()*0.25;at[k]=r.NextDouble()*0.25;dim[k]=(r.NextDouble()-0.5)*100;
            switch(mode)
            {
                case 1: ap[k]=1e-240+r.NextDouble()*1e-240; ab[k]*=1e-250;at[k]*=1e-250;break;
                case 2: at[k]=0;break;
                case 3: ab[k]=0;break;
                case 4: ap[k]=0;at[k]=0;break;
                case 5: ap[k]=double.Epsilon;break;
                case 6: ap[k]=BitConverter.Int64BitsToDouble(unchecked((long)0x7ff8123456789012));break;
                case 7: at[k]=double.PositiveInfinity;break;
                case 8: ab[k]=double.NegativeInfinity;break;
                case 9: ap[k]=-ap[k];ab[k]=-ab[k];at[k]=-at[k];break;
                case 10: ap[k]=-0.0;ab[k]=0.0;at[k]=-0.0;break;
                case 11: ap[k]=1e250;ab[k]=(k%2==0?1:-1)*1e249;at[k]=1e249;break;
            }
        }
        double[] ca=(double[])ap.Clone(),cb=(double[])ab.Clone(),ct=(double[])at.Clone();
        Program.ICPN=false;Cache.Prepare(nk,ca,cb,ct);
        for(int k=0;k<n;k++){Check(ap[k],ca[k],"pressure off AP");Check(ab[k],cb[k],"pressure off AB");Check(at[k],ct[k],"pressure off AT");}
        pressureOffCases++;
        Program.ICPN=true;Cache.Prepare(nk,ca,cb,ct);
        for(int k=0;k<n;k++)
        {
            Check(at[k],ct[k],"AT unchanged");
            if(k==0 || k>top){Check(ap[k],ca[k],"AP boundary");Check(ab[k],cb[k],"AB boundary");boundaryCases++;}
        }
        for(int e=0;e<16;e++)
        {
            double[] bp=new double[n],bq=new double[n],cp=new double[n],cq=new double[n];
            Baseline.Run(e,nk,ap,ab,at,dim,bp,bq);Candidate.Run(e,nk,ca,cb,ct,dim,cp,cq);
            for(int k=1;k<=top;k++){Check(bp[k],cp[k],"P recurrence");Check(bq[k],cq[k],"Q recurrence");}
            recurrenceCases++;
        }
    }
    public static int Main(string[] args)
    {
        if(args.Length!=2) throw new ArgumentException("result path and compiled baseline assembly are required");
        var asm=Assembly.LoadFrom(args[1]);
        var locals=new List<object>();int lambdaCount=0;bool allInit=true;
        foreach(var type in asm.GetTypes()) foreach(var method in type.GetMethods(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static|BindingFlags.Instance))
        {
            if(!method.Name.Contains("<Primp_calculate>"))continue;
            var body=method.GetMethodBody();if(body==null)continue;
            lambdaCount++;allInit &= body.InitLocals;
            locals.Add(new {method=type.FullName+"."+method.Name,initLocals=body.InitLocals});
        }
        if(lambdaCount!=8 || !allInit)throw new Exception("Expected eight pressure lambdas with initialized locals");
        foreach(int nk in new[]{1,2,3,8,16,32}) for(int mode=0;mode<12;mode++) for(int seed=1;seed<=64;seed++) One(nk,mode,seed);
        var result=new {status=mismatches==0?"pass":"fail",recurrenceCases,comparisons,finiteComparisons,nonfiniteComparisons,mismatches,boundaryCases,pressureOffCases,baselinePressureLambdas=lambdaCount,baselineInitLocals=allInit,lambdaBodies=locals,failures,scope="16 source-extracted recurrence blocks, actual guarded TERMIP transform, P/Q bits, pressure-off arrays, AT preservation and top coefficient boundaries; compiled baseline locals and stackalloc +0 top checks"};
        string json=JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true});
        System.IO.File.WriteAllText(args[0],json+"\n");Console.WriteLine(json);return result.status=="pass"?0:1;
    }
}
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--baseline-source-root',type=Path);p.add_argument('--baseline-assembly',type=Path);p.add_argument('--run',action='store_true');p.add_argument('--dotnet',default='dotnet');a=p.parse_args()
    base='4da3b7c172860e3f9369c7d2fba56b2d82ffbefb'
    if a.run and not a.baseline_assembly:p.error('--run requires --baseline-assembly')
    old={f:(a.baseline_source_root/'src'/f).read_text(encoding='utf-8-sig') if a.baseline_source_root else invoke(['git','-C',str(a.source_root),'show',base+':src/'+f]).lstrip('\ufeff') for f in ('TERMIP.cs','PRIMP.cs')}
    new={f:(a.source_root/'src'/f).read_text(encoding='utf-8-sig') for f in old}
    lock=json.loads((Path(__file__).parent/'source_lock.json').read_text(encoding='utf-8'))
    for variant,sources in [('baseline',old),('candidate',new)]:
        for filename,text in sources.items():
            assert hashlib.sha256(text.encode()).hexdigest()==lock['source_hashes'][variant]['src/'+filename],(variant,filename,'source hash mismatch')
    pattern=r'TERMP\s*=\s*[^;]+;\s*PIM\[kn\]\s*=\s*[^;]+;\s*QIM\[kn\]\s*=\s*[^;]+;'
    b=re.findall(pattern,old['PRIMP.cs']);c=re.findall(pattern,new['PRIMP.cs']);assert len(b)==len(c)==16
    for before,after in zip(b,c):assert after==before.replace('1 / (AP_L[kn] - AT_L[kn] * PIM[kn + 1])','AP_L[kn]').replace('AB_L[kn] * TERMP','AB_L[kn]')
    producer=block(new['TERMIP.cs'],'if (Program.ICPN)')
    cache='static class Program { public static bool ICPN; }\nstatic class Cache { public static void Prepare(int NK,double[] AP_L,double[] AB_L,double[] AT_L) {\n'+producer+'\n} }\n'
    src='using System;\nusing System.Collections.Generic;\nusing System.Reflection;\nusing System.Text.Json;\n'+emit_class('Baseline',b)+emit_class('Candidate',c)+cache+HARNESS
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'Harness.cs').write_text(src,encoding='utf-8',newline='\n')
    framework=re.search(r'<TargetFramework>([^<]+)</TargetFramework>',(a.source_root/'src/GRAMM.csproj').read_text()).group(1)
    project=f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>{framework}</TargetFramework><Optimize>true</Optimize><TreatWarningsAsErrors>true</TreatWarningsAsErrors><EnableNETAnalyzers>false</EnableNETAnalyzers><ImplicitUsings>disable</ImplicitUsings><Nullable>disable</Nullable></PropertyGroup></Project>\n';(a.output/'PressureRecurrence.csproj').write_text(project,encoding='utf-8')
    meta={'baseline':base,'candidate':'44df730514c6ea9af235a5abd0c66a03ce62dded','recurrence_blocks':len(b),'source_hashes':{variant:{f:hashlib.sha256(text.encode()).hexdigest() for f,text in d.items()} for variant,d in [('baseline',old),('candidate',new)]},'harness_sha256':hashlib.sha256(src.encode()).hexdigest(),'tests_run':False}
    if a.run:
        log=invoke([a.dotnet,'build',str(a.output/'PressureRecurrence.csproj'),'-c','Release','--nologo','-warnaserror']);(a.output/'build.log').write_text(log,encoding='utf-8')
        result=invoke([a.dotnet,str(a.output/'bin/Release'/framework/'PressureRecurrence.dll'),str(a.output/'result.json'),str(a.baseline_assembly)]);(a.output/'run.log').write_text(result,encoding='utf-8')
        meta['tests_run']=True;meta['result']=json.loads(result);meta['baseline_assembly_sha256']=hashlib.sha256(a.baseline_assembly.read_bytes()).hexdigest()
    (a.output/'source_extraction.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8');print(json.dumps({'tests_run':a.run,'output':str(a.output),'recurrence_blocks':len(b)}))

if __name__=='__main__':main()
