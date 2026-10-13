from pathlib import Path
import json,argparse,subprocess,sys
import candidate_suite as suite
from full_tests import run_instrumented
from fidelity_suite import compare
EXTRA={
 'confirmation_neutral_4':suite.NATIVE['medium_neutral_4'],
 'confirmation_stable_8':suite.NATIVE['stable_coast_8'],
 'radiation_medium_4':dict(nx=48,ny=36,nz=24,dx=250,sc=3,wind=2,duration=600,threads=4,irad=1),
}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['native','fidelity']);a=p.parse_args()
 if a.mode=='native':
  suite.NATIVE.update(EXTRA)
  suite.native(['baseline','surface_radiation'],list(EXTRA),5)
 else:
  results={}
  for v in ['baseline','surface_radiation','combined']:
   results[v]=run_instrumented('extra_radiation_medium_4',v,EXTRA['radiation_medium_4'])
  rows=[dict(variant=v,**compare(results['baseline'],results[v])) for v in ['surface_radiation','combined']]
  assert all(r['status']=='pass' for r in rows)
  suite.save(suite.JOB/'qa/surface_followup/fidelity.json',dict(case=EXTRA['radiation_medium_4'],comparisons=rows))

  plan=suite.JOB/'qa/surface_followup/fidelity_plan.json'
  suite.save(plan,{'radiation_medium_4':EXTRA['radiation_medium_4']})
  subprocess.run([sys.executable,'-B',str(suite.JOB/'qa/test_review/validate_completed.py'),'--job',str(suite.JOB),'--cases',str(plan),'--case-prefix','extra_','--variants','baseline','surface_radiation','combined','--output',str(suite.JOB/'qa/surface_followup/strict_validation.json')],check=True)
