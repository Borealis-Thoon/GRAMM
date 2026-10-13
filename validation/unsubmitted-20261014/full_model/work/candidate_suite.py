from pathlib import Path
import sys,json,subprocess,statistics,hashlib,os,time,argparse
from full_tests import *
from fidelity_suite import compare
sys.path.insert(0,str(JOB/'qa/pressure'))
from native_console_runner import run_hidden_console
VARIANTS=['baseline','surface_radiation','store_height','terminal_diagnostics']
SOURCES={v:'gramm_'+v for v in VARIANTS}
SOURCES.update({v:'gramm_'+v for v in ['combined','pressure_products','pressure_recurrence','selected_combined']})
NATIVE={
 'small_neutral_1':dict(nx=24,ny=20,nz=16,dx=100,duration=3600,threads=1),
 'medium_neutral_4':dict(nx=48,ny=36,nz=24,dx=250,duration=3600,threads=4),
 'stable_coast_8':dict(nx=64,ny=48,nz=24,dx=500,sc=7,wind=1,duration=600,threads=8,coast=True),
 'convective_tke_4':dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True),
 'large_neutral_14':dict(nx=96,ny=64,nz=28,dx=500,duration=3600,threads=14),
 'frequent_radiation_4':dict(nx=24,ny=20,nz=16,dx=100,sc=3,wind=2,duration=180,threads=4,irad=1),
}
FIDELITY={**NATIVE,
 'sequential_custom_4':dict(nx=32,ny=24,nz=20,dx=250,duration=360,threads=4,coast=True,multi=True,custom=True),
 'calm_convective_8':dict(nx=32,ny=24,nz=20,dx=500,sc=2,wind=.4,duration=180,dt=10,threads=8,coast=True),
 'radiation_off_1':dict(nx=24,ny=20,nz=16,dx=250,sc=6,wind=1,duration=180,threads=1,radiation=False),
 'radiation_refresh_1':dict(nx=24,ny=20,nz=16,dx=250,sc=2,duration=2100,threads=1),
}
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def build(variants):
 records=[]
 for v in variants:
  source=JOB.parent/'work'/SOURCES[v];dest=JOB/'build'/v;obj=JOB/'build'/(v+'_obj')
  cmd=[DOTNET,'build',str(source/'src/GRAMM.csproj'),'-c','Release','-p:TreatWarningsAsErrors=true','-o',str(dest),'--nologo','--disable-build-servers']
  r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
  log=r.stdout+r.stderr;(JOB/'logs').mkdir(exist_ok=True);(JOB/'logs'/('build_'+v+'.log')).write_text(log,encoding='utf-8')
  assert r.returncode==0,log
  records.append(dict(variant=v,exit=r.returncode,source_commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()))
  save(JOB/'qa/builds.json',records);print('BUILD',v,flush=True)
def fidelity(variants,cases):
 records=[]
 plan={c:FIDELITY[c] for c in cases};save(JOB/'qa/fidelity/plan.json',plan)
 for c,config in plan.items():
  results={}
  for v in variants:
   saved=JOB/'runs'/('fidelity_'+c)/v/'result.json'
   results[v]=json.loads(saved.read_text()) if saved.exists() else run_instrumented('fidelity_'+c,v,config)
  for v in variants[1:]:
   rec=compare(results['baseline'],results[v]);rec.update(case=c,variant=v);records.append(rec)
   save(JOB/'qa/fidelity/results.json',records)
   assert rec['status']=='pass',(c,v)
 print('FIDELITY',len(records),flush=True)
def native(variants,cases,reps):
 path=JOB/'qa/native/results.json';records=json.loads(path.read_text()) if path.exists() else []
 done={(r['case'],r['variant'],r['rep']) for r in records}
 save(JOB/'qa/native/plan.json',dict(cases={c:NATIVE[c] for c in cases},variants=variants,measured_repetitions=reps,warmups=1))
 for c in cases:
  for rep in range(reps+1):
   shift=rep%len(variants);order=variants[shift:]+variants[:shift]
   for v in order:
    if (c,v,rep) in done:continue
    folder=JOB/'runs/native'/c/(f'r{rep:02d}_'+v)
    config=make_case(folder,**NATIVE[c])
    r=run_hidden_console(JOB/'build'/v/'GRAMM.dll',folder,timeout=300,last=config['situations'])
    assert r['status']=='pass',r
    rec={**r,'case':c,'variant':v,'rep':rep,'measured':rep>0,'config':config,'payloads':outputs(folder,config['situations'])}
    records.append(rec);save(folder/'benchmark_result.json',rec);save(path,records)
    print('NATIVE',c,v,rep,round(r['lifetime_seconds'],4),flush=True)
 summary=[]
 for c in cases:
  base={r['rep']:r for r in records if r['case']==c and r['variant']=='baseline' and r['measured']}
  for v in variants[1:]:
   rows=[r for r in records if r['case']==c and r['variant']==v and r['measured']]
   pct=[100*(1-r['lifetime_seconds']/base[r['rep']]['lifetime_seconds']) for r in rows]
   summary.append(dict(case=c,variant=v,pairs=len(pct),saved_percent=pct,median_saved_percent=statistics.median(pct),faster_pairs=sum(x>0 for x in pct),baseline_seconds=statistics.median(base[r['rep']]['lifetime_seconds'] for r in rows),patched_seconds=statistics.median(r['lifetime_seconds'] for r in rows)))
 save(JOB/'qa/native/summary.json',summary)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['build','fidelity','native']);p.add_argument('--variants',nargs='+',default=VARIANTS);p.add_argument('--cases',nargs='+');p.add_argument('--reps',type=int,default=5);a=p.parse_args()
 lock=JOB.parent/'tests/TIMING.lock';lock.parent.mkdir(exist_ok=True)
 with lock.open('x') as f:f.write(str(os.getpid()))
 try:
  if a.mode=='build':build(a.variants)
  elif a.mode=='fidelity':fidelity(a.variants,a.cases or list(FIDELITY))
  else:native(a.variants,a.cases or list(NATIVE),a.reps)
 finally:lock.unlink()
