"""Verify review_required is non-success and preserves the failed source evidence."""
from pathlib import Path
import argparse,json,subprocess,sys
from run_matrix import classify_status
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--source-root',type=Path);a=p.parse_args();r=a.root.resolve();s=(a.source_root or r/'work/reproduce_clean_01').resolve();out=r/'qa/native_followup';out.mkdir(parents=True,exist_ok=True)
base=dict(scientific_guardrails=True,nonwind_physics_exact=True,bitwise_physics_exact=True,same_build_repeats_bitwise_exact=True)
probes=[('all_exact',{},'pass'),('crossbuild_wind_only',{'bitwise_physics_exact':False},'review_required'),('samebuild_wind_only',{'same_build_repeats_bitwise_exact':False},'review_required'),('class_guardrail_damage',{'scientific_guardrails':False},'fail'),('nonwind_physics_damage',{'nonwind_physics_exact':False},'fail'),('samebuild_nonwind_damage',{'nonwind_physics_exact':False,'same_build_repeats_bitwise_exact':False},'fail')]
results=[{'name':n,'expected':e,'observed':classify_status(**(base|x))} for n,x,e in probes];assert all(x['expected']==x['observed'] for x in results)
failed=s/'qa/native/native_matrix_results.json';before=failed.read_bytes();q=subprocess.run([sys.executable,'-X','utf8','-B',str(r/'tests/native/run_matrix.py'),'--root',str(s),'--results-dir',str(out/'reanalysis')],capture_output=True,text=True)
assert q.returncode==2,(q.returncode,q.stdout,q.stderr);assert failed.read_bytes()==before
analysis=json.loads((out/'reanalysis/native_matrix_results.json').read_text());assert analysis['status']=='review_required' and analysis['nonwind_physics_bitwise_identical'] and analysis['scientific_guardrails_pass']
result={'status':'pass','gate_probes':results,'existing_failed_results_preserved':True,'reanalysis_exit_code':q.returncode,'reanalysis_status':analysis['status'],'reanalysis_native_run_count':analysis['native_run_count'],'fresh_solver_runs':0};(out/'gate_status_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
