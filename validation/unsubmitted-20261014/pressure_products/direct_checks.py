"""Prepare or run source-extracted pressure-product checks; no performance timing."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, encoding='utf-8', capture_output=True).stdout


def extract(s, pattern):
    m = re.search(pattern, s, re.S)
    if not m:
        raise ValueError('Source contract missing: ' + pattern)
    return m.group(0)


def engine(name, expressions, fields, cutoff, guard=''):
    declarations = '\n'.join(f'    public static {t}[] {n} = new {t}[8];' for n,t in sorted(fields.items()))
    methods = '\n'.join(f'    public static double E{i}(int k, int kn) {{ return {e}; }}' for i,e in enumerate(expressions))
    cases = '\n'.join(f'        case {i}: return E{i}(k, kn);' for i in range(len(expressions)))
    doubles = '\n'.join(f'        for (int q=0; q<8; q++) {n}[q] = (seed + {i+1} * 0.0625 + q * 0.25) * (q % 2 == 0 ? -1 : 1);' for i,(n,t) in enumerate(sorted(fields.items())) if t=='double')
    return f'''
static class {name}
{{
{declarations}
    public static void Setup(float s, float sxyz, float area, float areaxyz, double seed)
    {{
        for (int q=0; q<8; q++) {{ SUZ_L[q]=s; SUXYZ_L[q]=sxyz; AREAZ_L[q]=area; AREAXYZ_L[q]=areaxyz; }}
{doubles}
    }}
    public static void Clip(int k)
    {{
{cutoff}
    }}
    public static void Prepare(int i, int j, int k, int NI, int NJ_P, int NK_P)
    {{
{guard}
    }}
{methods}
    public static double Evaluate(int expression, int k, int kn)
    {{
        switch (expression) {{
{cases}
        default: throw new ArgumentOutOfRangeException(nameof(expression));
        }}
    }}
}}
'''

HARNESS = r'''
static class Program { public static bool ICPN; }
static class Harness
{
    static long expressionCases, finiteCases, nonfiniteCases, expressionMismatches, floatCases, floatMismatches, guardCases;
    static List<string> failures = new();
    static void Failure(string text) { if (failures.Count < 12) failures.Add(text); }
    static void SameFloat(float before, float after, string label)
    {
        floatCases++;
        if (BitConverter.SingleToInt32Bits(before) != BitConverter.SingleToInt32Bits(after)) { floatMismatches++; Failure(label); }
    }
    static void ExpressionCase(float s, float sxyz, float a, float axyz, double seed)
    {
        Baseline.Setup(s,sxyz,a,axyz,seed); Candidate.Setup(s,sxyz,a,axyz,seed);
        Baseline.Clip(2); Candidate.Clip(2);
        Program.ICPN=true;
        Candidate.Prepare(2,2,2,5,6,4);
        SameFloat(Baseline.SUZ_L[2]*Baseline.AREAZ_L[2],Candidate.SUZ_L[2],"SUZ product");
        SameFloat(Baseline.SUXYZ_L[2]*Baseline.AREAXYZ_L[2],Candidate.SUXYZ_L[2],"SUXYZ product");
        for (int e=0;e<16;e++)
        {
            double expected=Baseline.Evaluate(e,2,4), actual=Candidate.Evaluate(e,2,4);
            expressionCases++;
            if (double.IsFinite(expected)) finiteCases++; else nonfiniteCases++;
            if (BitConverter.DoubleToInt64Bits(expected)!=BitConverter.DoubleToInt64Bits(actual))
            { expressionMismatches++; Failure($"expression {e}; s={s:R}; a={a:R}"); }
        }
    }
    static void GuardCase(bool pressure, float s, float a)
    {
        const int ni=5,nj=6,nk=4;
        Program.ICPN=pressure;
        for (int i=0;i<=ni;i++) for (int j=0;j<=nj;j++) for (int k=0;k<=nk;k++)
        {
            Candidate.Setup(s,-s,a,-a,0.0);
            // This is the existing CALCPR producer loop domain; its guard runs only here.
            if (i>=1 && j>=2 && k>=1) Candidate.Prepare(i,j,k,ni,nj,nk);
            bool weighted=pressure && i>=2 && i<ni && j>=2 && j<nj && k>=1 && k<nk;
            for(int q=0;q<8;q++)
            {
                float z=weighted && q==k ? s*a : s;
                float xyz=weighted && q==k ? (-s)*(-a) : -s;
                SameFloat(z,Candidate.SUZ_L[q],$"SUZ guard {pressure}/{i}/{j}/{k}/{q}");
                SameFloat(xyz,Candidate.SUXYZ_L[q],$"SUXYZ guard {pressure}/{i}/{j}/{k}/{q}");
            }
            guardCases++;
        }
    }
    public static int Main(string[] args)
    {
        float cut=0.00001f;
        float[] sources={0f,-0f,MathF.BitDecrement(cut),cut,MathF.BitIncrement(cut),-MathF.BitDecrement(cut),-cut,-MathF.BitIncrement(cut),float.Epsilon,-float.Epsilon,1f,-1f,0.1234567f,-7912.123f,float.MaxValue,float.MinValue,float.PositiveInfinity,float.NegativeInfinity,float.NaN,BitConverter.Int32BitsToSingle(unchecked((int)0x7fc12345)),BitConverter.Int32BitsToSingle(unchecked((int)0xffc12345))};
        float[] areas={0f,-0f,float.Epsilon,-float.Epsilon,0.125f,-0.125f,1f,-1f,19.7f,-431.125f,float.MaxValue,float.PositiveInfinity,float.NegativeInfinity,float.NaN};
        for(int n=0;n<sources.Length;n++) for(int q=0;q<areas.Length;q++) for(int mix=0;mix<3;mix++)
            ExpressionCase(sources[n],sources[(n+mix+1)%sources.Length],areas[q],areas[(q+mix+1)%areas.Length],mix*0.37-0.5);
        Random rng=new(80431);
        for(int n=0;n<20000;n++)
        {
            float s=BitConverter.Int32BitsToSingle((int)rng.NextInt64(int.MinValue,(long)int.MaxValue+1));
            float sx=BitConverter.Int32BitsToSingle((int)rng.NextInt64(int.MinValue,(long)int.MaxValue+1));
            float a=BitConverter.Int32BitsToSingle((int)rng.NextInt64(int.MinValue,(long)int.MaxValue+1));
            float ax=BitConverter.Int32BitsToSingle((int)rng.NextInt64(int.MinValue,(long)int.MaxValue+1));
            ExpressionCase(s,sx,a,ax,(rng.NextDouble()-0.5)*1e4);
        }
        foreach(bool pressure in new[]{false,true}) foreach(float s in new[]{0f,-0f,2.37f,float.NaN,float.PositiveInfinity}) foreach(float a in new[]{0f,4.25f,-2f}) GuardCase(pressure,s,a);
        var result=new {status=expressionMismatches==0 && floatMismatches==0 ? "pass" : "fail",expressionCases,finiteCases,nonfiniteCases,expressionMismatches,floatCases,floatMismatches,guardCases,failures,coverage="16 extracted DIM expressions; source cutoff boundary; signed zero; finite random bit patterns; NaN and infinities; positive/negative/zero face areas; pressure off; lateral/level-zero/top sentinels",scope="Component checks only. Full CALCPR restoration and model outputs are validated separately."};
        string json=JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true});
        if(args.Length>0) System.IO.File.WriteAllText(args[0],json+"\n");
        Console.WriteLine(json);
        return result.status=="pass" ? 0 : 1;
    }
}
'''

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-root',type=Path,required=True,help='Candidate checkout or extracted source tree.')
    p.add_argument('--baseline-source-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--run',action='store_true',help='Build and execute the extracted component checks.')
    p.add_argument('--dotnet',default='dotnet')
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    lock=json.loads((Path(__file__).parent/'source_lock.json').read_text(encoding='utf-8'))
    old={f:(a.baseline_source_root/'src'/f).read_text(encoding='utf-8-sig') for f in ('CALCPR.cs','PRIMP.cs')}
    new={f:(a.source_root/'src'/f).read_text(encoding='utf-8-sig') for f in old}
    for label,root in [('baseline',a.baseline_source_root),('candidate',a.source_root)]:
        for relative,expected in lock['source_hashes'][label].items():
            text=(root/relative).read_text(encoding='utf-8-sig')
            assert hashlib.sha256(text.encode()).hexdigest()==expected,(label,relative,'source hash mismatch')
    pattern=r'\bDIM\s*=\s*((?:SUZ|SUXYZ)_L\[k\].*?);'
    be=re.findall(pattern,old['PRIMP.cs'],re.S)
    ce=re.findall(pattern,new['PRIMP.cs'],re.S)
    assert len(be)==len(ce)==16
    for b,c in zip(be,ce):
        assert c==b.replace('SUZ_L[k] * AREAZ_L[k]','SUZ_L[k]').replace('SUXYZ_L[k] * AREAXYZ_L[k]','SUXYZ_L[k]')
    fields={n:t for t,n in re.findall(r'ReadOnlySpan<(float|double)>\s+(\w+)',old['PRIMP.cs'])}
    fields.update({n:t for t,n in re.findall(r'\b(float|double)\[\]\s+(\w+)',old['PRIMP.cs'])})
    names=set(re.findall(r'\b(\w+_L)\[','\n'.join(be)))|{'SUZ_L','SUXYZ_L','AREAZ_L','AREAXYZ_L'}
    fields={n:fields[n] for n in names}
    assert fields['SUZ_L']==fields['AREAZ_L']==fields['SUXYZ_L']==fields['AREAXYZ_L']=='float'
    cutoffs=[]
    for src in (old['CALCPR.cs'],new['CALCPR.cs']):
        cutoffs.append('\n'.join(extract(src,rf'if \(Math.Abs\({n}_L\[k\]\) < 0.00001\)\s*\{{\s*{n}_L\[k\] = 0;\s*\}}') for n in ('SUZ','SUXYZ')))
    guard=extract(new['CALCPR.cs'],r'if \(Program.ICPN && i > 1 && i < NI && j < NJ_P && k < NK_P\)\s*\{\s*SUZ_L\[k\] = SUZ_L\[k\] \* AREAZ_L\[k\];\s*SUXYZ_L\[k\] = SUXYZ_L\[k\] \* AREAXYZ_L\[k\];\s*\}')
    source='using System;\nusing System.Collections.Generic;\nusing System.Text.Json;\n'+engine('Baseline',be,fields,cutoffs[0])+engine('Candidate',ce,fields,cutoffs[1],guard)+HARNESS
    (a.output/'Harness.cs').write_text(source,encoding='utf-8',newline='\n')
    target=re.search(r'<TargetFramework>([^<]+)</TargetFramework>',(a.source_root/'src/GRAMM.csproj').read_text(encoding='utf-8')).group(1)
    project=f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>{target}</TargetFramework><Optimize>true</Optimize><TreatWarningsAsErrors>true</TreatWarningsAsErrors><EnableNETAnalyzers>false</EnableNETAnalyzers><ImplicitUsings>disable</ImplicitUsings><Nullable>disable</Nullable></PropertyGroup></Project>\n'
    (a.output/'PressureProducts.csproj').write_text(project,encoding='utf-8')
    manifest={'baseline':lock['baseline'],'head':lock['candidate'],'expressions':len(be),'fields':fields,'sources':{variant:{f:hashlib.sha256(s.encode()).hexdigest() for f,s in d.items()} for variant,d in [('base',old),('candidate',new)]},'hash_convention':'UTF-8 source text, BOM removed and universal LF line endings','harness_sha256':hashlib.sha256(source.encode()).hexdigest(),'tests_run':False}
    if a.run:
        build=run([a.dotnet,'build',str(a.output/'PressureProducts.csproj'),'-c','Release','--nologo','-warnaserror'])
        (a.output/'build.log').write_text(build,encoding='utf-8')
        result=run([a.dotnet,str(a.output/'bin/Release'/target/'PressureProducts.dll'),str(a.output/'result.json')])
        (a.output/'run.log').write_text(result,encoding='utf-8')
        manifest['tests_run']=True
        manifest['result']=json.loads(result)
    (a.output/'source_extraction.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'prepared':str(a.output),'tests_run':a.run,'expressions':len(be)}))

if __name__=='__main__':
    main()
