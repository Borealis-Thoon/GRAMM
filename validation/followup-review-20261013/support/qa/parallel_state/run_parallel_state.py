"""Run actual GRAMM native-dispatch state repeats. Do not run beside timing work.

The model equations and configured 300-second integration are unchanged.
Raw state binaries stay local; only numerical comparisons are publication inputs.
"""
from pathlib import Path
import json,sys

JOB=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(JOB/'work'))
from full_tests import run_instrumented

VARIANTS=('baseline','radiation_column','combined')
THREADS=(1,4,8)
REPEATS=3
CONFIG=dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=300,dt=5,irad=30,coast=True,turbulence=True)


def main():
    qa=JOB/'qa/parallel_state'
    qa.mkdir(parents=True,exist_ok=True)
    plan={'job':str(JOB),'config':CONFIG,'threads':list(THREADS),'repeats':REPEATS,'variants':list(VARIANTS),
          'serial':False,'snapshot':True,'binary':True,'expected_runs':len(VARIANTS)*len(THREADS)*REPEATS,'run_order':[]}
    for ti,threads in enumerate(THREADS):
        for repeat in range(1,REPEATS+1):
            shift=(ti+repeat-1)%len(VARIANTS)
            for variant in VARIANTS[shift:]+VARIANTS[:shift]:
                plan['run_order'].append({'case':f'parallel_t{threads}_r{repeat}','threads':threads,'repeat':repeat,'variant':variant})
    (qa/'plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    completed=[]
    try:
        for item in plan['run_order']:
            config={**CONFIG,'threads':item['threads']}
            result=run_instrumented(item['case'],item['variant'],config,serial=False,snapshot=True,binary=True)
            completed.append({**item,'folder':str(JOB/'runs'/item['case']/item['variant']),'integration':result['integration']})
            (qa/'run_progress.json').write_text(json.dumps({'status':'running','completed':completed},indent=2)+'\n',encoding='utf-8')
    except Exception as error:
        (qa/'run_progress.json').write_text(json.dumps({'status':'failed','completed':completed,'error':str(error)},indent=2)+'\n',encoding='utf-8')
        raise
    (qa/'run_progress.json').write_text(json.dumps({'status':'complete','completed':completed},indent=2)+'\n',encoding='utf-8')
    print(f'parallel_runs={len(completed)} complete=true',flush=True)
    return 0

if __name__=='__main__': raise SystemExit(main())
