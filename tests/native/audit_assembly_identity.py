"""Compare source bytes and method bodies between original and reproduced builds."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--source-root',type=Path);p.add_argument('--dotnet',default=shutil.which('dotnet'));a=p.parse_args();r=a.root.resolve();s=(a.source_root or r/'work/reproduce_clean_01').resolve();out=r/'qa/native_followup';out.mkdir(parents=True,exist_ok=True);d=Path(__file__).resolve().parent/'assembly_audit'
build=subprocess.run([a.dotnet,'build',str(d/'assembly_audit.csproj'),'-c','Release','--nologo','-v','quiet','-p:OutputPath='+str(d/'bin')+'\\'],capture_output=True,text=True);assert build.returncode==0,(build.stdout,build.stderr)
results={}
for k,folder in [('baseline','upstream'),('candidate','candidate')]:
 x=r/'work'/folder/'src';y=s/'work'/folder/'src';names=set(p.name for p in x.glob('*.cs'))|set(p.name for p in y.glob('*.cs'));diff=[n for n in names if not (x/n).exists() or not (y/n).exists() or (x/n).read_bytes()!=(y/n).read_bytes()]
 q=subprocess.run([a.dotnet,str(d/'bin/assembly_audit.dll'),str(r/f'build/{k}/GRAMM.dll'),str(s/f'build/{k}/GRAMM.dll')],capture_output=True,text=True);assert q.returncode==0,(q.stdout,q.stderr)
 results[k]={'source_files_checked':len(names),'source_differences':diff,'original_sha256':hashlib.sha256((r/f'build/{k}/GRAMM.dll').read_bytes()).hexdigest(),'reproduced_sha256':hashlib.sha256((s/f'build/{k}/GRAMM.dll').read_bytes()).hexdigest(),'il_audit':json.loads(q.stdout)}
assert all(not v['source_differences'] and v['il_audit']['method_bodies_identical'] for v in results.values())
result={'status':'pass','scope':'C# source bytes and IL method bodies/locals/exception clauses. Whole DLL hashes also contain embedded symbols and source-path metadata.','builds':results};(out/'assembly_identity_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
