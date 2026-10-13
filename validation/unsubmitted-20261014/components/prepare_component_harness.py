from pathlib import Path
import hashlib,json,re
import argparse
ap=argparse.ArgumentParser(description='Extract the tested GRAMM methods and build a component-check project.')
ap.add_argument('--source-root',type=Path,required=True,help='Directory containing gramm_baseline and the three candidate source directories')
ap.add_argument('--output',type=Path,required=True,help='New directory for the generated C# project')
a=ap.parse_args()
O=a.output.resolve();O.mkdir(parents=True,exist_ok=False)
locks=json.loads(Path(__file__).with_name('source_lock.json').read_text(encoding='utf-8'))['sources']
def read(folder,file):
 p=a.source_root/folder/'src'/file
 raw=p.read_bytes();s=raw.decode('utf-8-sig').replace('\r\n','\n')
 expected=locks[folder]['files']['src/'+file]['utf8_lf_sha256']
 actual=hashlib.sha256(s.encode('utf-8')).hexdigest()
 if actual!=expected:raise ValueError(f'Source hash mismatch: {folder}/src/{file}')
 return s

def method(s,sig):
 masked=re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"',lambda m:' '*len(m.group()),s)
 st=s.index(sig);p=masked.index('{',st)+1;n=1
 while n:
  n+=(masked[p]=='{')-(masked[p]=='}');p+=1
 return s[st:p]
meta={}
common='''using System; using System.Linq; using System.Collections.Concurrent; using System.Threading.Tasks; using System.Collections.Generic; using System.Collections.Immutable;
'''
store_support='''
public static ParallelOptions pOptions=new(); public static bool ICTE; public static double FN=.0001,RELAXT=.7; public const double CK=.35,VISEL=.05;
public static double[][] UST=Array.Empty<double[]>(),ZI=Array.Empty<double[]>(); public static ImmutableArray<float>[] AHImm=Array.Empty<ImmutableArray<float>>();
public static double[][][] U=Array.Empty<double[][]>(),V=Array.Empty<double[][]>(),VISV=Array.Empty<double[][]>(),RITSCH=Array.Empty<double[][]>(),TE=Array.Empty<double[][]>(),TEN=Array.Empty<double[][]>(),DISSN=Array.Empty<double[][]>();
public static ImmutableArray<float>[][] ZSPImm=Array.Empty<ImmutableArray<float>[]>();
static double Pow2(double x)=>x*x;
public static void Init(int ni,int nj,int nk,int worker,bool tke,int profile){
 pOptions.MaxDegreeOfParallelism=worker;ICTE=tke;FN=profile==7?0:-.0001;
 UST=H.A2(ni,nj,(i,j)=>profile==0?0:profile==1?1e-12:.15+.05*((i+j)%6));AHImm=H.F2(ni,nj,(i,j)=>20+i*2+j).Select(r=>r.ToImmutableArray()).ToArray();ZI=H.A2(ni,nj,(i,j)=>-7);
 ZSPImm=H.F3(ni,nj,nk,(i,j,k)=>AHImm[i][j]+3+8*k+.5*k*k).Select(r=>r.Select(c=>c.ToImmutableArray()).ToArray()).ToArray();
 U=H.A3(ni,nj,nk,(i,j,k)=>1+i*.01+k*k*.005);V=H.A3(ni,nj,nk,(i,j,k)=>-2+j*.02-k*.02);
 VISV=H.A3(ni,nj,nk,(i,j,k)=>-.123);TE=H.A3(ni,nj,nk,(i,j,k)=>k%2==0?-1:.4);TEN=H.A3(ni,nj,nk,(i,j,k)=>.4+.01*k);DISSN=H.A3(ni,nj,nk,(i,j,k)=>.2+.01*k);
 double[] ri={Math.BitDecrement(-.048),-.048,Math.BitIncrement(-.048),Math.BitDecrement(0),0,Math.BitIncrement(0),Math.BitDecrement(.33),.33,Math.BitIncrement(.33),double.NaN,double.PositiveInfinity,double.NegativeInfinity};
 RITSCH=H.A3(ni,nj,nk,(i,j,k)=>ri[(i+j+k+profile)%ri.Length]);
}
public static double[] Fields()=>H.Flat(VISV).Concat(H.Flat(TE)).Concat(ZI.SelectMany(r=>r)).ToArray();
'''
calctb_support='''
public static ParallelOptions pOptions=new();public static int TerminalOut,TerminalThreshold,NZB;
public const double SIGMA=5.6697e-8,ALW=2500000;public const float CPBOD=900; public static double DT=1.5,RELAXV=.4,RELAXT=.7;
public static ImmutableArray<float> DDXImm,DDYImm;public static float[] DWB=Array.Empty<float>(),DZB=Array.Empty<float>();
public static double[][] WQU=Array.Empty<double[]>(),RSOLG=Array.Empty<double[]>(),RL=Array.Empty<double[]>(),EPSG=Array.Empty<double[]>(),FW=Array.Empty<double[]>(),QUG=Array.Empty<double[]>(),UST=Array.Empty<double[]>();public static float[][] ALAMBDA=Array.Empty<float[]>(),XWQ=Array.Empty<float[]>(),AWQ=Array.Empty<float[]>(),RHOB=Array.Empty<float[]>();
public static double[][][] TB=Array.Empty<double[][]>(),TBN=Array.Empty<double[][]>(),QU=Array.Empty<double[][]>();public static float[][][] RHO=Array.Empty<float[][]>();public static ImmutableArray<float>[][] AREAImm=Array.Empty<ImmutableArray<float>[]>(),VOLImm=Array.Empty<ImmutableArray<float>[]>();
static double Pow4(double x){return x*x*x*x;}
public static void Init(int ni,int nj,int nzb,int worker,int threshold,int counter,int profile){
 pOptions.MaxDegreeOfParallelism=worker;NZB=nzb;TerminalThreshold=threshold;TerminalOut=counter;
 DDXImm=Enumerable.Repeat(250f,ni+2).ToImmutableArray();DDYImm=Enumerable.Repeat(300f,nj+2).ToImmutableArray();DWB=Enumerable.Range(0,nzb+2).Select(k=>(float)(.1+.03*k)).ToArray();DZB=Enumerable.Range(0,nzb+2).Select(k=>(float)(.2+.03*k)).ToArray();
 TB=H.A3(ni,nj,nzb,(i,j,k)=>280+i*.1+j*.2-k*.3);TBN=H.A3(ni,nj,nzb,(i,j,k)=>-9);QU=H.A3(ni,nj,2,(i,j,k)=>5+i*.01);RHO=H.F3(ni,nj,2,(i,j,k)=>1.2);AREAImm=H.F3(ni,nj,2,(i,j,k)=>75000).Select(r=>r.Select(c=>c.ToImmutableArray()).ToArray()).ToArray();VOLImm=H.F3(ni,nj,2,(i,j,k)=>750000).Select(r=>r.Select(c=>c.ToImmutableArray()).ToArray()).ToArray();
 WQU=H.A2(ni,nj,(i,j)=>75000*(10+i*.2));RSOLG=H.A2(ni,nj,(i,j)=>50+j*.3);RL=H.A2(ni,nj,(i,j)=>300+i*.1);EPSG=H.A2(ni,nj,(i,j)=>.95);ALAMBDA=H.F2(ni,nj,(i,j)=>.6);FW=H.A2(ni,nj,(i,j)=>profile==0?0:profile==1?1:(i+j)%2);QUG=H.A2(ni,nj,(i,j)=>-1);XWQ=H.F2(ni,nj,(i,j)=>.02);UST=H.A2(ni,nj,(i,j)=>.2);AWQ=H.F2(ni,nj,(i,j)=>.1);RHOB=H.F2(ni,nj,(i,j)=>1800);
}
public static double[] Fields()=>H.Flat(TB).Concat(H.Flat(TBN)).Concat(H.Flat(QU)).Concat(QUG.SelectMany(r=>r)).Append(TerminalOut).ToArray();
'''
rad_support='''
public static class Program {public static ParallelOptions pOptions=new();public static int NZ;public const double SIGMA=5.6697e-8;public static double[] RHOBZZ=Array.Empty<double>();public static int[][] KST=Array.Empty<int[]>();public static double[][] CLOUDS=Array.Empty<double[]>(),RL=Array.Empty<double[]>(),EPSG=Array.Empty<double[]>(),TG=Array.Empty<double[]>();public static double[][][] TABS=Array.Empty<double[][]>(),DT_TERR=Array.Empty<double[][]>();}
public partial class RadiationCalculation {
 const double Wcrit=.03,Cp=1004;
 double[][] Wrad=Array.Empty<double[]>(),CGp=Array.Empty<double[]>(),Rp=Array.Empty<double[]>(),Q=Array.Empty<double[]>(),RTerrG=Array.Empty<double[]>();float[][] Alfa=Array.Empty<float[]>();
 double[] Dz1=Array.Empty<double>(),Dz2=Array.Empty<double>(),LStrich=Array.Empty<double>();
 double[][][] EpsAp=Array.Empty<double[][]>(),EpsAm=Array.Empty<double[][]>(),Eab=Array.Empty<double[][]>(),Tab=Array.Empty<double[][]>();
 public void Init(int ni,int nj,int nk,int worker,int profile,int phase){
 Program.pOptions.MaxDegreeOfParallelism=worker;Program.NZ=nk;
 Program.KST=Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>phase==0?2:2+(i+j)%Math.Min(5,nk-1)).ToArray()).ToArray();
 Program.RHOBZZ=Enumerable.Range(0,nk+2).Select(k=>1.3-.005*k).ToArray();
 Program.CLOUDS=H.A2(ni,nj,(i,j)=>(i+j+phase)%11/10d);Program.RL=H.A2(ni,nj,(i,j)=>-9);Program.EPSG=H.A2(ni,nj,(i,j)=>.9+.001*(i+j)%30);Program.TG=H.A2(ni,nj,(i,j)=>280+phase+i*.1-j*.07);
 Program.TABS=H.A3(ni,nj,Math.Max(10,nk),(i,j,k)=>280+phase+i*.03-j*.04-k*.3);Program.DT_TERR=H.A3(ni,nj,nk,(i,j,k)=>-99);
 Q=H.A2(ni,nj,(i,j)=>.4+(i+j)%5*.1);RTerrG=H.A2(ni,nj,(i,j)=>-19);Alfa=H.A2(ni,nj,(i,j)=>.01*i-.02*j).Select(r=>r.Select(x=>(float)x).ToArray()).ToArray();
 Dz1=Enumerable.Range(0,nk+2).Select(k=>5d+15*k+.5*k*k-7).ToArray();Dz2=Dz1.Select(x=>x+14).ToArray();LStrich=Enumerable.Range(0,nk+2).Select(k=>300d-k).ToArray();
 Wrad=Enumerable.Range(0,nk+2).Select(k=>new double[]{0,0,profile switch {0=>0,1=>.004,2=>.03,3=>.06,_=>k%3==0?.035:.0001},0}).ToArray();CGp=Enumerable.Range(0,nk+2).Select(k=>new double[]{0,0,.001+.0007*k,0}).ToArray();Rp=Enumerable.Range(0,nk+2).Select(k=>new double[]{0,0,.0008+.0005*k,0}).ToArray();
 EpsAp=H.A3(ni,nj,nk,(i,j,k)=>.2+.001*k);EpsAm=H.A3(ni,nj,nk,(i,j,k)=>.22+.001*k);Eab=H.A3(ni,nj,nk,(i,j,k)=>.3);Tab=H.A3(ni,nj,nk,(i,j,k)=>260-k*.2);
 }
 public double[] Fields()=>Program.RL.SelectMany(r=>r).Concat(RTerrG.SelectMany(r=>r)).Concat(H.Flat(Program.DT_TERR)).ToArray();
}
'''
for label,folder in [('Base','gramm_baseline'),('Patch','')]:
 store=read(folder or 'gramm_store_height','STORE.cs');block=store[store.index('            //Turbulent eddy viscosity model'):store.index('            //homogenous Von Neumann boundary-conditions')];
 (O/(label+'Store.cs')).write_text(common+'namespace '+label+'Store { public static partial class Program {\n'+store_support+'\npublic static void Run(int NI,int NJ,int NK){\n'+block+'\n}\n}}',encoding='utf-8')
 calctb=read(folder or 'gramm_terminal_diagnostics','CALCTB.cs');cm=method(calctb,'public static void Calctb_calculate(')
 (O/(label+'Soil.cs')).write_text(common+'namespace '+label+'Soil { public static partial class Program {\n'+calctb_support+cm+'\n}}',encoding='utf-8')
 rad=read(folder or 'gramm_surface_radiation','RADIAT.cs');methods=[method(rad,s) for s in ['private double Cl_Eps(','private void Cl_RterrG(','private void Cl_dTdtterr(','private double Cl_EpsB(']];loop=rad[rad.index('            //Terrestrial radiation'):rad.index('            //border values')]
 (O/(label+'Radiation.cs')).write_text(common+'namespace '+label+'Rad {\n'+rad_support+'public partial class RadiationCalculation {\n'+'\n'.join(methods)+'\npublic void Run(int NI,int NJ){\n'+loop+'\n}\n}}',encoding='utf-8')
 meta[label]={'STORE_block_sha256':hashlib.sha256(block.encode()).hexdigest(),'CALCTB_method_sha256':hashlib.sha256(cm.encode()).hexdigest(),'RADIAT_loop_sha256':hashlib.sha256(loop.encode()).hexdigest(),'source_edits':'none; actual method and loop text extracted verbatim'}
(O/'ComponentChecks.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><TreatWarningsAsErrors>true</TreatWarningsAsErrors></PropertyGroup></Project>')
(O/'provenance.json').write_text(json.dumps(meta,indent=2))
main=r'''
using System.Text.Json;
static class H {
 public static double[][] A2(int ni,int nj,Func<int,int,double> f)=>Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>f(i,j)).ToArray()).ToArray();
 public static double[][][] A3(int ni,int nj,int nk,Func<int,int,int,double> f)=>Enumerable.Range(0,ni+2).Select(i=>Enumerable.Range(0,nj+2).Select(j=>Enumerable.Range(0,nk+2).Select(k=>f(i,j,k)).ToArray()).ToArray()).ToArray();
 public static float[][] F2(int ni,int nj,Func<int,int,double> f)=>A2(ni,nj,f).Select(r=>r.Select(x=>(float)x).ToArray()).ToArray();
 public static float[][][] F3(int ni,int nj,int nk,Func<int,int,int,double> f)=>A3(ni,nj,nk,f).Select(r=>r.Select(c=>c.Select(x=>(float)x).ToArray()).ToArray()).ToArray();
 public static IEnumerable<double> Flat(double[][][] a)=>a.SelectMany(r=>r).SelectMany(c=>c);
 static long total=0,finite=0,nan=0;
 static void Equal(double[] a,double[] b,string key){if(a.Length!=b.Length)throw new Exception("Length "+key);for(int n=0;n<a.Length;n++){if(BitConverter.DoubleToInt64Bits(a[n])!=BitConverter.DoubleToInt64Bits(b[n]))throw new Exception($"Bits {key} {n} {a[n]} {b[n]}");total++;if(double.IsFinite(a[n]))finite++;else nan++;}}
 static string Capture(Action f){var old=Console.Out;var s=new System.IO.StringWriter(System.Globalization.CultureInfo.InvariantCulture);Console.SetOut(s);try{f();}finally{Console.SetOut(old);}return s.ToString();}
 static string Display(string s){if(s.Length==0)return s;var lines=s.Split('\n');return lines[0]+lines[1].Substring(0,14)+lines[1].Substring(28,28);}
 static void Main(string[] args){System.Globalization.CultureInfo.CurrentCulture=System.Globalization.CultureInfo.InvariantCulture;int store=0,soil=0,rad=0;var rows=new List<object>();
 foreach(int nk in new[]{0,1,2,3,8,28,65})foreach(int w in new[]{1,4,8})foreach(bool tke in new[]{false,true})foreach(int profile in Enumerable.Range(0,8)){
 const int ni=18,nj=13;BaseStore.Program.Init(ni,nj,nk,w,tke,profile);PatchStore.Program.Init(ni,nj,nk,w,tke,profile);BaseStore.Program.Run(ni,nj,nk);PatchStore.Program.Run(ni,nj,nk);Equal(BaseStore.Program.Fields(),PatchStore.Program.Fields(),$"store {nk} {w} {tke} {profile}");store++;}
 foreach(var g in new[]{(12,9),(24,17)})foreach(int nzb in new[]{2,3,5,8})foreach(int w in new[]{1,4,8})foreach(int th in new[]{1,6,12})foreach(int delta in new[]{-1,0,1})foreach(int p in new[]{0,1,2}){
 var(ni,nj)=g;BaseSoil.Program.Init(ni,nj,nzb,w,th,th+delta,p);PatchSoil.Program.Init(ni,nj,nzb,w,th,th+delta,p);
 for(int repeat=0;repeat<2;repeat++){string a=Capture(()=>BaseSoil.Program.Calctb_calculate(ni,nj,12)),b=Capture(()=>PatchSoil.Program.Calctb_calculate(ni,nj,12));Equal(BaseSoil.Program.Fields(),PatchSoil.Program.Fields(),$"soil {g} {nzb} {w} {th} {delta} {p} {repeat}");if(Display(a)!=Display(b))throw new Exception("Display");if(repeat==0 && delta<0 && (a.Length!=0||b.Length!=0))throw new Exception("Silent");BaseSoil.Program.TerminalOut=th;PatchSoil.Program.TerminalOut=th;soil++;}}
 foreach(var g in new[]{(4,4,12),(13,11,16),(48,36,24)})foreach(int w in new[]{1,2,4,8,14})foreach(int p in Enumerable.Range(0,5))foreach(int phase in new[]{0,1,2}){
 var(ni,nj,nk)=g;var a=new BaseRad.RadiationCalculation();var b=new PatchRad.RadiationCalculation();a.Init(ni,nj,nk,w,p,phase);b.Init(ni,nj,nk,w,p,phase);for(int repeat=0;repeat<2;repeat++){a.Run(ni,nj);b.Run(ni,nj);Equal(a.Fields(),b.Fields(),$"rad {g} {w} {p} {phase} {repeat}");rad++;}}
 var result=new{status="pass",store_cases=store,soil_cases=soil,radiation_cases=rad,total_cases=store+soil+rad,bitwise_equal_values=total,finite_bitwise_equal_values=finite,nonfinite_equal_values=nan,source_extraction=true,soil_display_note="Exact EINTRAG1/2/3 only. Existing parallel EINTRAG4/5 reductions excluded from console comparison.",store_scope="Actual ICTE true/false viscosity branches, including NK0/1/2; full STORE boundary checks belong to model runs.",radiation_scope="Actual terrestrial loop plus four actual methods; synthetic prepared radiation profiles and spatial KST. Full initialization belongs to model runs."};File.WriteAllText(args[0],JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(result));
 }
}
'''
(O/'Program.cs').write_text(main,encoding='utf-8')
print(O)