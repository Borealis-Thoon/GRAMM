from pathlib import Path
import json,argparse,subprocess,sys
import candidate_suite as suite
from full_tests import run_instrumented
from fidelity_suite import compare
CASES=['small_neutral_1','medium_neutral_4','stable_coast_8','convective_tke_4','large_neutral_14','frequent_radiation_4','sequential_custom_4','calm_convective_8','radiation_off_1','radiation_refresh_1']
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['fidelity','native']);a=p.parse_args()
 if a.mode=='fidelity':
  rows=[]
  for c in CASES:
   old=suite.JOB/'runs'/('fidelity_'+c)/'baseline/result.json';base=json.loads(old.read_text())
   result=run_instrumented('fidelity_'+c,'pressure_products',suite.FIDELITY[c])
   row=dict(case=c,variant='pressure_products',**compare(base,result));rows.append(row)
   suite.save(suite.JOB/'qa/pressure_products/fidelity.json',rows)
   assert row['status']=='pass',c
  plan=suite.JOB/'qa/pressure_products/fidelity_plan.json'
  suite.save(plan,{c:suite.FIDELITY[c] for c in CASES})
  subprocess.run([sys.executable,'-B',str(suite.JOB/'qa/test_review/validate_completed.py'),'--job',str(suite.JOB),'--cases',str(plan),'--variants','baseline','pressure_products','--output',str(suite.JOB/'qa/pressure_products/strict_validation.json')],check=True)
 else:
  selected=['small_neutral_1','medium_neutral_4','stable_coast_8','convective_tke_4','large_neutral_14']
  mapping={'pressure_'+c:suite.NATIVE[c] for c in selected};suite.NATIVE.update(mapping)
  suite.native(['baseline','pressure_products'],list(mapping),5)
