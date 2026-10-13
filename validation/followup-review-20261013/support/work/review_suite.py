import os
from pathlib import Path
import sys,json,subprocess,statistics,hashlib,os,time
from full_tests import *
from fidelity_suite import compare
sys.path.insert(0,str(JOB/'qa/pressure'))
from native_console_runner import run_hidden_console
VARIANTS=os.environ.get('GRAMM_TEST_VARIANTS','baseline,radiation_column,uvw_sources').split(',')
PLAN={
 'neutral_1':dict(nx=48,ny=36,nz=24,dx=250,duration=3600,threads=1),
 'convective_4':dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True),
 'stable_coast_8':dict(nx=64,ny=48,nz=24,dx=500,sc=7,wind=1,duration=600,threads=8,coast=True,turbulence=True),
 'large_neutral_14':dict(nx=96,ny=64,nz=28,dx=500,duration=3600,threads=14),
 'frequent_radiation_4':dict(nx=24,ny=20,nz=16,dx=100,sc=3,wind=2,duration=180,threads=4,irad=1),
}
FIDELITY={
 'neutral_1':dict(nx=48,ny=36,nz=24,dx=250,duration=600,threads=1),
 'convective_4':PLAN['convective_4'],
 'stable_coast_8':PLAN['stable_coast_8'],
 'frequent_radiation_4':PLAN['frequent_radiation_4'],
 'sequential_custom_4':dict(nx=32,ny=24,nz=20,dx=250,duration=360,threads=4,coast=True,multi=True,custom=True),
 'calm_convective_8':dict(nx=32,ny=24,nz=20,dx=500,sc=2,wind=.4,duration=180,dt=10,threads=8,coast=True),
 'radiation_off_1':dict(nx=24,ny=20,nz=16,dx=250,sc=6,wind=1,duration=180,threads=1,radiation=False),
 'radiation_refresh_1':dict(nx=24,ny=20,nz=16,dx=250,sc=2,duration=2100,threads=1),
}
def dump(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2))
def native(case,variant,config,rep):
 folder=JOB/'runs/native'/case/(f'r{rep:02d}_'+variant)
 c=make_case(folder,**config)
 r=run_hidden_console(JOB/'build'/variant/'GRAMM.dll',folder,timeout=300,last=c['situations'])
 if r['status']!='pass':raise RuntimeError(str(r))
 payload=outputs(folder,c['situations'])
 rec={**r,'case':case,'variant':variant,'rep':rep,'measured':rep>0,'config':c,'payloads':payload}
 dump(folder/'benchmark_result.json',rec)
 print(f"NATIVE {case} r{rep} {variant} {r['lifetime_seconds']:.4f}s",flush=True)
 return rec
def native_suite():
 path=JOB/'qa/native/results.json'; records=json.loads(path.read_text()) if path.exists() else []
 done={(r['case'],r['variant'],r['rep']) for r in records}
 dump(JOB/'qa/native/plan.json',dict(cases=PLAN,variants=VARIANTS,measured_pairs=5,warmups=1,order='rotated by replicate'))
 for case,config in PLAN.items():
  for rep in range(6):
   order=VARIANTS[rep%len(VARIANTS):]+VARIANTS[:rep%len(VARIANTS)]
   for variant in order:
    if (case,variant,rep) in done:continue
    records.append(native(case,variant,config,rep));dump(path,records)
 summary=[]
 for case in PLAN:
  base={r['rep']:r for r in records if r['case']==case and r['variant']=='baseline' and r['measured']}
  for variant in VARIANTS[1:]:
   rows=[r for r in records if r['case']==case and r['variant']==variant and r['measured']]
   pct=[100*(1-r['lifetime_seconds']/base[r['rep']]['lifetime_seconds']) for r in rows]
   summary.append(dict(case=case,variant=variant,pairs=len(pct),saved_percent=pct,median_saved_percent=statistics.median(pct),faster_pairs=sum(x>0 for x in pct),baseline_seconds=statistics.median(r['lifetime_seconds'] for r in base.values()),patched_seconds=statistics.median(r['lifetime_seconds'] for r in rows)))
 dump(JOB/'qa/native/summary.json',summary)
 print('NATIVE PASS',len(records),flush=True)
def fidelity_suite(variants):
 path=JOB/'qa/fidelity/results.json';records=json.loads(path.read_text()) if path.exists() else []
 done={(r['case'],r['variant']) for r in records}
 dump(JOB/'qa/fidelity/plan.json',FIDELITY)
 for case,config in FIDELITY.items():
  folder=JOB/'runs'/('fidelity_'+case)/'baseline'
  base=json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists() else run_instrumented('fidelity_'+case,'baseline',config)
  for variant in variants:
   if (case,variant) in done:continue
   result=run_instrumented('fidelity_'+case,variant,config)
   comp=compare(base,result);comp.update(case=case,variant=variant)
   records.append(comp);dump(path,records)
   if comp['status']!='pass':raise RuntimeError('Fidelity failed '+case+' '+variant)
 print('FIDELITY PASS',len(records),flush=True)
if __name__=='__main__':
 mode=sys.argv[1]
 lock=JOB/'tests/TIMING.lock'
 with lock.open('x') as f:f.write(str(os.getpid()))
 try:
  if mode=='native':native_suite()
  elif mode=='fidelity':fidelity_suite(sys.argv[2:] or VARIANTS[1:])
 finally:lock.unlink()
