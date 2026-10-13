import os
from pathlib import Path
import sys,subprocess,json,hashlib
JOB=Path(__file__).resolve().parents[1]
SOURCES={'baseline':'warnings','radiation_column':'radiation_column','uvw_sources':'uvw_sources','scalar_tdma':'scalar_tdma','combined':'combined'}
records=[]
for variant in sys.argv[1:]:
 source=JOB/'work'/SOURCES[variant]
 cmd=[os.environ.get('DOTNET_EXE','dotnet'),'build',str(source/'src/GRAMM.csproj'),'-c','Release','-p:TreatWarningsAsErrors=true','-p:BaseIntermediateOutputPath='+str(JOB/'build'/(variant+'_obj'))+os.sep,'-o',str(JOB/'build'/variant),'--nologo']
 r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
 (JOB/'logs'/('build_'+variant+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:print(r.stdout,r.stderr);raise SystemExit(r.returncode)
 dll=JOB/'build'/variant/'GRAMM.dll'
 rec=dict(variant=variant,commit=json.loads((source/'source_receipt.json').read_text())['commit'],exit_code=r.returncode,command=cmd,assembly_sha256=hashlib.sha256(dll.read_bytes()).hexdigest())
 records.append(rec);print('BUILD PASS',variant,flush=True)
 path=JOB/'qa'/('build_'+variant+'.json');path.write_text(json.dumps(rec,indent=2))
