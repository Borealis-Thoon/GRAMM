from pathlib import Path
import argparse,json,shutil,subprocess,hashlib
parser=argparse.ArgumentParser();parser.add_argument('--job-root',type=Path,default=Path(__file__).resolve().parents[2]);parser.add_argument('--gral-source',type=Path,required=True);args=parser.parse_args()
R=args.job_root;src=args.gral_source;dst=R/'work/coupling/diagnostic_src';dst.mkdir(parents=True,exist_ok=True)
for p in src.iterdir():
 if p.is_file():shutil.copy2(p,dst/p.name)
p=dst/'Program.cs';s=p.read_text(encoding='utf-8-sig');needle='                    ReadMeteoData();';assert s.count(needle)==1
insert='''                    ReadMeteoData();
                    // Test-only readout; official concentration runs use the unmodified GRAL.dll.
                    using (var diagnostic = new System.IO.StreamWriter("imported_meteo.csv"))
                    {
                        diagnostic.WriteLine("x_m,y_m,SC,OL_m,ustar_m_s,z0_m,u_first_m_s,v_first_m_s");
                        for (int ix=1;ix<=NX;ix++) for(int iy=1;iy<=NY;iy++)
                            diagnostic.WriteLine(System.FormattableString.Invariant($"{GrammWest+(ix-0.5)*DDX[1]},{GrammSouth+(iy-0.5)*DDY[1]},{SC_Gral[ix][iy]},{Ob[ix][iy]},{Ustern[ix][iy]},{Z0Gramm[ix][iy]},{UWIN[ix][iy][1]},{VWIN[ix][iy][1]}"));
                    }
                    Environment.Exit(0);
'''
p.write_text(s.replace(needle,insert),encoding='utf-8')
build=R/'work/coupling/diagnostic_build';out=subprocess.run(['dotnet','build',str(dst/'GRAL.csproj'),'-c','Release','-o',str(build),'--nologo','-v','minimal'],capture_output=True,text=True,timeout=90);(R/'qa/coupling/diagnostic_build.log').write_text(out.stdout+out.stderr);assert out.returncode==0,out.stdout+out.stderr
for v in ['A','B']:
 source=R/f'runs/coupling/cool_main_{v}';target=R/f'runs/coupling/diagnostic_{v}';target.mkdir(exist_ok=False)
 manifest=json.loads((source/'input_manifest.json').read_text())
 for name in manifest:shutil.copy2(source/name,target/name)
 with (target/'console.log').open('wb') as log:
  p=subprocess.run(['dotnet',str(build/'GRAL.dll'),str(target)],cwd=target,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=30);assert p.returncode==0
 assert (target/'imported_meteo.csv').exists()
 shutil.copy2(target/'imported_meteo.csv',R/f'qa/coupling/imported_meteo_{v}.csv')
print('diagnostic done',flush=True)
