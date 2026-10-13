from pathlib import Path
from array import array
from itertools import combinations
import csv,json,hashlib,math,struct,sys,statistics
ROOT=Path(__file__).resolve().parents[2]
QA=ROOT/'qa/benefit_review'

def require(ok,why):
    if not ok: raise ValueError(why)

def load(thread,repeat,variant):
    folder=ROOT/'runs'/f'parallel_t{thread}_r{repeat}'/variant
    data=(folder/'00001.wnd').read_bytes()
    header,nx,ny,nz,dx=struct.unpack('<iiiif',data[:20])
    require((header,nx,ny,nz,dx)==(-1,48,36,24,250.0),'Wrong wnd header '+str(folder))
    require(len(data)==20+nx*ny*nz*3*2,'Wrong wnd size '+str(folder))
    payload=array('h');payload.frombytes(data[20:])
    if sys.byteorder!='little':payload.byteswap()
    snap=json.loads((folder/'harness_snapshot_00001.json').read_text())
    fields={r['name']:r for r in snap['fields']}
    values={}
    for name in ('U','V','W'):
        blob=(folder/fields[name]['binary_file']).read_bytes()
        require(hashlib.sha256(blob).hexdigest()==fields[name]['sha256'],'Wrong snapshot hash')
        values[name]=array('d');values[name].frombytes(blob)
        if sys.byteorder!='little':values[name].byteswap()
    mismatch=0
    for index,tick in enumerate(payload):
        cell,axis=divmod(index,3);cell,k=divmod(cell,nz);i,j=divmod(cell,ny);i+=1;j+=1;k+=1
        value=values['UVW'[axis]][(i*(ny+1)+j)*(nz+1)+k]
        require(math.isfinite(value),'Nonfinite field')
        mismatch+=int(round(max(-32768,min(32767,value*100))))!=tick
    require(mismatch==0,'WND payload differs from rounded final snapshot '+str(folder))
    return {'thread':thread,'repeat':repeat,'variant':variant,'folder':folder,'header':data[:20],'payload':payload,'sha256':hashlib.sha256(data).hexdigest(),'fields':values,'rounding_mismatch_count':mismatch}

def compare(a,b,kind):
    require(a['header']==b['header'],'Header mismatch')
    n=len(a['payload']);nx,ny,nz=48,36,24
    changed=[];axis_metrics={}
    for axis,name in enumerate('UVW'):
        deltas=[int(b['payload'][i])-int(a['payload'][i]) for i in range(axis,n,3)]
        count=sum(d!=0 for d in deltas)
        axis_metrics[name]={'count':len(deltas),'changed_count':count,'max_abs_ticks':max(abs(d) for d in deltas),'mean_abs_ticks':sum(abs(d) for d in deltas)/len(deltas),'mean_signed_ticks':sum(deltas)/len(deltas)}
    all_deltas=[int(y)-int(x) for x,y in zip(a['payload'],b['payload'])]
    for index,d in enumerate(all_deltas):
        if not d:continue
        cell,axis=divmod(index,3);cell,k=divmod(cell,nz);i,j=divmod(cell,ny);i+=1;j+=1;k+=1
        offset=(i*(ny+1)+j)*(nz+1)+k;field='UVW'[axis]
        ref=a['fields'][field][offset];cand=b['fields'][field][offset]
        changed.append({'i':i,'j':j,'k':k,'component':field,'reference_tick':a['payload'][index],'candidate_tick':b['payload'][index],'difference_ticks':d,'reference_full_precision_ms':ref,'candidate_full_precision_ms':cand,'full_precision_difference_ms':cand-ref,'rounding_boundary_ms':(a['payload'][index]+b['payload'][index])/200})
    return {'threads':a['thread'],'kind':kind,'reference_repeat':a['repeat'],'candidate_repeat':b['repeat'],'reference_variant':a['variant'],'candidate_variant':b['variant'],'payload_component_values':n,'header_identical':True,'wnd_sha256_identical':a['sha256']==b['sha256'],'changed_count':len(changed),'changed_fraction':len(changed)/n,'max_abs_ticks':max(abs(d) for d in all_deltas),'mean_abs_ticks':sum(abs(d) for d in all_deltas)/n,'mean_signed_ticks':sum(all_deltas)/n,'max_abs_ms':max(abs(d) for d in all_deltas)*.01,'mean_abs_ms':sum(abs(d) for d in all_deltas)*.01/n,'largest_full_precision_change_at_changed_output_ms':max((abs(r['full_precision_difference_ms']) for r in changed),default=0),'rounding_from_final_full_precision_state_verified':True,'axis_metrics':axis_metrics,'changed_locations':changed}

runs={(t,r,v):load(t,r,v) for t in (1,4,8) for r in (1,2,3) for v in ('baseline','scalar_tdma')}
rows=[]
for t in (1,4,8):
    for a,b in combinations((1,2,3),2):rows.append(compare(runs[t,a,'baseline'],runs[t,b,'baseline'],'baseline_repeat'))
    for r in (1,2,3):rows.append(compare(runs[t,r,'baseline'],runs[t,r,'scalar_tdma'],'matched_scalar'))
groups=[]
for t in (1,4,8):
    for kind in ('baseline_repeat','matched_scalar'):
        rr=[r for r in rows if r['threads']==t and r['kind']==kind]
        groups.append({'threads':t,'kind':kind,'pairs':len(rr),'identical_files':sum(r['wnd_sha256_identical'] for r in rr),'changed_counts':[r['changed_count'] for r in rr],'max_changed_count':max(r['changed_count'] for r in rr),'max_changed_fraction':max(r['changed_fraction'] for r in rr),'max_abs_ms':max(r['max_abs_ms'] for r in rr),'max_mean_abs_ms':max(r['mean_abs_ms'] for r in rr)})
full=json.loads((ROOT/'qa/parallel_state/analysis.json').read_text())
require(full['data_status']=='complete_and_finite' and not full['errors'],'Incomplete parallel-state review')
scalar_full=[r for r in full['comparisons'] if r['kind']=='matched_patch' and r['candidate_variant']=='scalar_tdma']
base_full=[r for r in full['comparisons'] if r['kind']=='baseline_repeat']
require(len(scalar_full)==81 and len(base_full)==81,'Unexpected full-precision pair count')
def extreme(records,names,metric='max_abs'):return max(r[metric] for r in records if r['field'] in names)
field_extrema={name:{'baseline_max_abs':extreme(base_full,[name]),'scalar_max_abs':extreme(scalar_full,[name]),'baseline_max_mae':extreme(base_full,[name],'mae'),'scalar_max_mae':extreme(scalar_full,[name],'mae'),'baseline_max_rmse':extreme(base_full,[name],'rmse'),'scalar_max_rmse':extreme(scalar_full,[name],'rmse')} for name in ('U','V','W','T','QU','PN','TE','DISS','RADIATION')}
result={'status':'complete','source':'AUSGABE.cs IOUT==0: int32 -1,NX,NY,NZ,float32 dx then int16 U,V,W, i/j/k order; Convert.ToInt16(value*100), clamped','quantum_ms':.01,'payload_components_per_file':124416,'read_only_model_output_analysis':True,'runs_read':len(runs),'pair_count':len(rows),'all_18_wnd_files_verified_against_final_double_snapshots':True,'native_scalar_pairs':9,'native_scalar_full_precision_field_pairs':len(scalar_full),'native_scalar_steps_identical_field_pairs':sum(r['steps_identical'] for r in scalar_full),'native_scalar_hash_identical_field_pairs':sum(r['hash_identical'] for r in scalar_full),'native_scalar_worker_setting_1_fields_all_bitwise_identical':all(r['hash_identical'] for r in scalar_full if r['threads']==1),'wind_component_max_abs_ms':{'baseline_repeat':extreme(base_full,list('UVW')),'matched_scalar':extreme(scalar_full,list('UVW'))},'temperature_max_abs_K':{'baseline_repeat':extreme(base_full,['T']),'matched_scalar':extreme(scalar_full,['T'])},'field_extrema':field_extrema,'groups':groups,'comparisons':rows,'interpretation_codes':['all_changed_int16_values_explained_by_rounding_final_double_state','rare_output_quantization_boundary_crossings','some_patch_metric_maxima_above_observed_baseline_maxima','no_claim_all_differences_within_baseline_envelope','no_downstream_dispersion_equivalence_claim'],'qa_recommendation':'eligible_for_draft_pr_with_exact_fixed_order_validation_and_measured_native_variation'}
(QA/'native_wnd_review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
flat=[{k:v for k,v in r.items() if k not in ('axis_metrics','changed_locations')} for r in rows]
with (QA/'native_wnd_comparisons.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
locations=[{**{k:r[k] for k in ('threads','kind','reference_repeat','candidate_repeat')},**v} for r in rows for v in r['changed_locations']]
with (QA/'native_wnd_changed_locations.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(locations[0]));w.writeheader();w.writerows(locations)
print(json.dumps({k:v for k,v in result.items() if k not in ('comparisons','field_extrema')},indent=2))
