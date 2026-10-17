from pathlib import Path
import argparse,csv,itertools,json,sys,time
from run_matrix import analyze,compare,sha,write_json
from fixture import make_case
from native_console_runner import run_hidden_console
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--source-root',type=Path);p.add_argument('--repeats',type=int,default=6);a=p.parse_args()
r=a.root.resolve();s=(a.source_root or r/'work/reproduce_clean_01').resolve();out=r/'qa/native_followup';out.mkdir(parents=True,exist_ok=True);raw=out/'runs';raw.mkdir(exist_ok=True)
prior=json.loads((s/'qa/native/native_matrix_results.json').read_text()); names=['cool_day_40x32x20_500m_t2','warm_day_40x32x20_500m_t8','land_day_40x32x20_500m_t2'];specs={x['name']:x['configuration'] for x in prior['comparisons'] if x['name'] in names}
builds={k:s/f'build/{k}/GRAMM.dll' for k in ('baseline','candidate')};started=time.perf_counter();records=[];data={};rows=[];comparisons=[]
for name in names:
 cfg=specs[name]
 for rep in range(a.repeats):
  for build,assembly in builds.items():
   if time.perf_counter()-started>150: raise TimeoutError('followup 150s cap')
   case=raw/name/f'{build}_{rep:02d}'
   if not case.exists():
    make_case(case,**{k:cfg[k] for k in ('nx','ny','nz','dx','threads','sc','wind','coast')},duration=360,dt=5,irad=30)
    (case/'CustomInit.txt').write_text('Synthetic custom initial conditions\nheader\n'+f"27,{cfg['wind']},{cfg['sc']},1,1000000,293.15,303.15,293.15,{cfg['delta']},0.6,5000,-0.0065,0.01,-0.005\n")
    write_json(case/'native_config.json',cfg);rr=run_hidden_console(assembly,case,timeout=90)
   else:rr=json.loads((case/'native_run_result.json').read_text())
   assert rr['status']=='pass' and rr['assembly_sha256']==sha(assembly.read_bytes())
   d=analyze(case,cfg);data[name,build,rep]=d;records.append({'name':name,'build':build,'repeat':rep,'run':rr,**d[0]});write_json(out/'progress.json',{'run_count':len(records),'runs':records})
   print(f'[FOLLOWUP] {name} {build} {rep} {rr["elapsed_seconds"]:.2f}s',flush=True)
for name in names:
 for mode in ('baseline_repeat','candidate_repeat','cross_build'):
  pairs=list(itertools.combinations(range(a.repeats),2)) if mode!='cross_build' else list(itertools.product(range(a.repeats),repeat=2))
  per=[]
  for x,y in pairs:
   first='baseline' if mode in ('baseline_repeat','cross_build') else 'candidate';second='candidate' if mode=='cross_build' else first
   c=compare(data[name,first,x],data[name,second,y],apply_expected_patch=mode=='cross_build');q=c['physical_files']['00001.wnd']
   row={'name':name,'mode':mode,'rep_a':x,'rep_b':y,'wnd_different_values':q['different_values'],'wnd_max_abs_raw_delta':q['max_abs_raw_delta'],'wnd_rms_raw_delta':q['rms_raw_delta'],'class_expected_mismatches':c.get('baseline_formula_expected_mismatches',c.get('same_build_expected_class_mismatches')),'changed_land_cells':c['changed_land_cells'],'ust_identical':c['decoded_zip_members']['.ust']['byte_identical'],'ol_identical':c['decoded_zip_members']['.obl']['byte_identical'],'other_physical_identical':all(v['byte_identical'] for k,v in c['physical_files'].items() if k!='00001.wnd')};rows.append(row);per.append(row)
  comparisons.append({'name':name,'mode':mode,'comparison_count':len(per),'wnd_nonidentical_comparisons':sum(x['wnd_different_values']>0 for x in per),'wnd_different_values_min':min(x['wnd_different_values'] for x in per),'wnd_different_values_max':max(x['wnd_different_values'] for x in per),'wnd_max_abs_raw_delta':max(x['wnd_max_abs_raw_delta'] for x in per),'class_expected_mismatches':sum(x['class_expected_mismatches'] for x in per),'changed_land_cells':sum(x['changed_land_cells'] for x in per),'ust_all_identical':all(x['ust_identical'] for x in per),'ol_all_identical':all(x['ol_identical'] for x in per),'other_physical_all_identical':all(x['other_physical_identical'] for x in per)})
semantic=all(x['class_expected_mismatches']==0 and x['changed_land_cells']==0 and x['ust_identical'] and x['ol_identical'] and x['other_physical_identical'] for x in rows)
violations=sum(x['interior_water_positive_ol_unstable_cells'] for x in records if x['build']=='candidate');exact=all(x['wnd_different_values']==0 for x in rows)
result={'status':'fail' if not semantic or violations else ('pass' if exact else 'review_required'),'native_run_count':len(records),'same_build_comparisons':sum(x['mode']!='cross_build' for x in rows),'cross_build_comparisons':sum(x['mode']=='cross_build' for x in rows),'prior_failed_results_preserved':str(s/'qa/native/native_matrix_results.json'),'source_root':str(s),'build_hashes':{k:sha(v.read_bytes()) for k,v in builds.items()},'semantic_and_nonwind_physics_exact':semantic,'candidate_positive_ol_water_unstable_violations':violations,'bitwise_wind_equivalence':exact,'comparison_tolerance':'none; no numeric acceptance threshold introduced','wind_encoding':'Int16 units 0.01 m/s; reported raw delta 1 is 0.01 m/s','parallelism_semantics':'Max_Proc requested settings, not measured thread counts','native_process_elapsed_sum_seconds':sum(x['run']['elapsed_seconds'] for x in records),'analysis_and_new_execution_elapsed_seconds':time.perf_counter()-started,'summaries':comparisons,'pairwise_comparisons':rows,'runs':records}
write_json(out/'native_followup_results.json',result)
for filename,items in [('native_followup_summary.csv',comparisons),('native_followup_pairwise.csv',rows)]:
 with (out/filename).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
print(json.dumps({k:v for k,v in result.items() if k not in ('runs','pairwise_comparisons')},indent=2),flush=True)
raise SystemExit(1 if result['status']=='fail' else 2 if result['status']=='review_required' else 0)
