from pathlib import Path
import argparse,json,subprocess,sys
import candidate_suite as suite
from full_tests import run_instrumented
from fidelity_suite import compare
CASES=list(suite.FIDELITY)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['fidelity','native']);a=p.parse_args()
 if a.mode=='fidelity':
  rows=[]
  for c in CASES:
   base=json.loads((suite.JOB/'runs'/('fidelity_'+c)/'baseline/result.json').read_text())
   saved=suite.JOB/'runs'/('fidelity_'+c)/'pressure_recurrence/result.json'
   result=json.loads(saved.read_text()) if saved.exists() else run_instrumented('fidelity_'+c,'pressure_recurrence',suite.FIDELITY[c])
   row=dict(case=c,variant='pressure_recurrence',**compare(base,result));rows.append(row)
   suite.save(suite.JOB/'qa/pressure_recurrence/fidelity.json',rows)
   assert row['status']=='pass',c
  subprocess.run([sys.executable,'-B',str(suite.JOB/'qa/test_review/validate_completed.py'),'--job',str(suite.JOB),'--cases',str(suite.JOB/'qa/fidelity/plan.json'),'--variants','baseline','pressure_recurrence','--output',str(suite.JOB/'qa/pressure_recurrence/strict_validation.json')],check=True)
 else:
  selected=['small_neutral_1','medium_neutral_4','stable_coast_8','convective_tke_4']
  mapping={'recurrence_'+c:suite.NATIVE[c] for c in selected};suite.NATIVE.update(mapping)
  suite.native(['baseline','pressure_recurrence'],list(mapping),5)
  name='products_confirmation_large_14';suite.NATIVE[name]=suite.NATIVE['large_neutral_14']
  suite.native(['baseline','pressure_products','pressure_recurrence'],[name],5)
