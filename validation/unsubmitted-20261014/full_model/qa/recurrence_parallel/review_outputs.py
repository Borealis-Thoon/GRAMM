"""Review native wind rounding, decoded surface outputs and completed integration."""
from pathlib import Path
from array import array
from itertools import combinations
import argparse,csv,hashlib,json,math,struct,sys,zipfile
from analyze_parallel_state import load_run, VARIANTS


def require(ok,message):
    if not ok: raise ValueError(message)


def digest(data): return hashlib.sha256(data).hexdigest()


def decode(data,header,count,label):
    require(len(data)==20+2*count,'Wrong payload size: '+label)
    require(struct.unpack('<iiiif',data[:20])==header,'Wrong payload header: '+label)
    values=array('h');values.frombytes(data[20:])
    if sys.byteorder!='little':values.byteswap()
    return values


def load(job,plan,thread,repeat,variant):
    run=load_run(job,plan,thread,repeat,variant)
    folder=Path(run['folder']); result=json.loads((folder/'result.json').read_text())
    nx,ny,nz=(plan['config'][key] for key in ('nx','ny','nz'))
    expected=(-1,nx,ny,nz,float(plan['config']['dx']))
    wind_data=(folder/'00001.wnd').read_bytes()
    wind=decode(wind_data,expected,nx*ny*nz*3,str(folder/'00001.wnd'))
    require(result['payloads']['00001.wnd']=={'sha256':digest(wind_data),'size':len(wind_data)},'Saved WND result differs')
    fields={}
    for name in 'UVW':
        data=run['binary_files'][name].read_bytes(); fields[name]=array('d');fields[name].frombytes(data)
        if sys.byteorder!='little':fields[name].byteswap()
    for index,tick in enumerate(wind):
        cell,axis=divmod(index,3);cell,k=divmod(cell,nz);i,j=divmod(cell,ny)
        value=fields['UVW'[axis]][((i+1)*(ny+1)+(j+1))*(nz+1)+(k+1)]
        require(math.isfinite(value),'Non-finite wind snapshot')
        predicted=round(max(-32768,min(32767,value*100)))
        require(predicted==tick,'Saved wind differs from final snapshot rounding')
    surface={};surface_hashes={}
    with zipfile.ZipFile(folder/'00001.scl') as archive:
        names=archive.namelist()
        require(len(names)==3 and set(names)=={'00001.ust','00001.obl','00001.scl'},'Missing/duplicate SCL payload')
        require(archive.testzip() is None,'SCL CRC failure')
        for name in sorted(names):
            data=archive.read(name);surface[name]=decode(data,expected,nx*ny,name)
            surface_hashes[name]=digest(data)
            require(result['payloads']['00001.scl/'+name]=={'sha256':digest(data),'size':len(data)},'Saved surface result differs')
    steady=(folder/'00001_steady_state.txt').read_bytes()
    require(result['payloads']['00001_steady_state.txt']=={'sha256':digest(steady),'size':len(steady)},'Saved steady-state result differs')
    return dict(threads=thread,repeat=repeat,variant=variant,wind=wind,fields=fields,wind_sha256=digest(wind_data),surface=surface,surface_hashes=surface_hashes,steady_sha256=digest(steady),integration=run['integration'],shape=(nx,ny,nz),rounding_values_verified=len(wind),full_precision_fields_checked=9,numerical_retries=0)


def compare(a,b,kind):
    require(a['shape']==b['shape'],'Shape mismatch')
    nx,ny,nz=a['shape']; n=len(a['wind']); delta=[int(y)-int(x) for x,y in zip(a['wind'],b['wind'])]
    locations=[]
    for index,d in enumerate(delta):
        if d==0:continue
        cell,axis=divmod(index,3);cell,k=divmod(cell,nz);i,j=divmod(cell,ny);i+=1;j+=1;k+=1
        field='UVW'[axis];offset=(i*(ny+1)+j)*(nz+1)+k
        av,bv=a['fields'][field][offset],b['fields'][field][offset]
        locations.append(dict(i=i,j=j,k=k,component=field,baseline_tick=a['wind'][index],candidate_tick=b['wind'][index],difference_ticks=d,baseline_full_precision_ms=av,candidate_full_precision_ms=bv,full_precision_difference_ms=bv-av))
    surfaces={}
    for name in a['surface']:
        dif=[int(y)-int(x) for x,y in zip(a['surface'][name],b['surface'][name])]
        surfaces[name]=dict(values=len(dif),changed_count=sum(x!=0 for x in dif),max_abs_ticks=max(abs(x) for x in dif),identical=a['surface_hashes'][name]==b['surface_hashes'][name])
    same_steps=all(a['integration'][key]==b['integration'][key] for key in ('itime','dt','realtime','tlimit','retries'))
    require(same_steps,'Integration differs between native comparison pair')
    return dict(threads=a['threads'],kind=kind,reference_variant=a['variant'],candidate_variant=b['variant'],reference_repeat=a['repeat'],candidate_repeat=b['repeat'],wind_values=n,wind_changed_count=len(locations),wind_changed_fraction=len(locations)/n,wind_max_abs_ticks=max(abs(x) for x in delta),wind_max_abs_ms=max(abs(x) for x in delta)*.01,wind_mae_ms=math.fsum(abs(x) for x in delta)*.01/n,wind_identical=a['wind_sha256']==b['wind_sha256'],surface=surfaces,surface_all_identical=all(x['identical'] for x in surfaces.values()),steady_state_identical=a['steady_sha256']==b['steady_sha256'],steps_identical=same_steps,all_wind_values_explained_by_final_snapshot_rounding=True,changed_locations=locations)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,default=Path(__file__).resolve().parents[2]);args=ap.parse_args()
    job=args.job.resolve();qa=job/'qa/recurrence_parallel'
    plan=json.loads((qa/'plan.json').read_text());analysis=json.loads((qa/'analysis.json').read_text())
    require(plan['variants']==list(VARIANTS) and plan['threads']==[1,4,8] and plan['repeats']==3,'Unexpected plan')
    expected_runs=len(plan['variants'])*len(plan['threads'])*plan['repeats']
    expected_pairs=len(plan['threads'])*(math.comb(plan['repeats'],2)+(len(plan['variants'])-1)*plan['repeats'])
    require(plan['expected_runs']==expected_runs,'Unexpected planned run count')
    require(analysis['data_status']=='complete_and_finite' and analysis['runs']==expected_runs and not analysis['errors'],'Incomplete precision-state analysis')
    runs={(t,r,v):load(job,plan,t,r,v) for t in plan['threads'] for r in (1,2,3) for v in plan['variants']}
    require(len(runs)==expected_runs,'Missing native run')
    rows=[]
    for t in plan['threads']:
        for a,b in combinations((1,2,3),2):rows.append(compare(runs[t,a,'baseline'],runs[t,b,'baseline'],'baseline_repeat'))
        for v in plan['variants'][1:]:
            for r in (1,2,3):rows.append(compare(runs[t,r,'baseline'],runs[t,r,v],'matched_patch'))
    require(len(rows)==expected_pairs,'Missing native pair')
    summary=[]
    for v in plan['variants']:
        rr=[r for r in rows if r['candidate_variant']==v]
        f=[r for r in analysis['comparisons'] if r['candidate_variant']==v]
        require(len(rr)==9 and len(f)==81,'Missing variant comparisons')
        summary.append(dict(variant=v,pairs=len(rr),wind_changed_counts=[r['wind_changed_count'] for r in rr],wind_identical_pairs=sum(r['wind_identical'] for r in rr),max_wind_changed_count=max(r['wind_changed_count'] for r in rr),max_wind_changed_fraction=max(r['wind_changed_fraction'] for r in rr),max_wind_tick_difference=max(r['wind_max_abs_ticks'] for r in rr),max_wind_mae_ms=max(r['wind_mae_ms'] for r in rr),all_surface_payload_pairs_identical=all(r['surface_all_identical'] for r in rr),steady_state_identical_pairs=sum(r['steady_state_identical'] for r in rr),integration_identical_pairs=sum(r['steps_identical'] for r in rr),full_precision_field_pairs=len(f),full_precision_identical_field_pairs=sum(r['hash_identical'] for r in f),setting_1_all_fields_bitwise_identical=all(r['hash_identical'] for r in f if r['threads']==1),max_wind_component_difference_ms=max(r['max_abs'] for r in f if r['field'] in 'UVW'),max_temperature_difference_K=max(r['max_abs'] for r in f if r['field']=='T')))
    record=dict(status='pass',scope='Completed native parallel runs; decoded integer outputs and final double snapshots',runs=len(runs),output_pairs=len(rows),wind_components_per_file=len(next(iter(runs.values()))['wind']),all_wind_component_rounding_checks=sum(r['rounding_values_verified'] for r in runs.values()),wind_quantum_ms=.01,all_rounding_checks_passed=True,surface_payloads_per_file=3,surface_storage_units={'ust':'.001 m/s','obl':'.1 m','scl':'stability-class integer'},numerical_retries=0,summary=summary,comparisons=rows,notes=['Paired wind differences are reported, including baseline-to-baseline repeat differences.','The exact fixed-order comparisons and native parallel comparisons have separate scopes.','ZIP container timestamps are excluded; decoded SCL payloads are compared.'])
    (qa/'output_review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    flat=[{k:v for k,v in r.items() if k not in ('surface','changed_locations')} for r in rows]
    with (qa/'output_comparisons.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    location_fields=['threads','kind','candidate_variant','reference_repeat','candidate_repeat','i','j','k','component','baseline_tick','candidate_tick','difference_ticks','baseline_full_precision_ms','candidate_full_precision_ms','full_precision_difference_ms']
    locations=[{**{k:r[k] for k in location_fields[:5]},**loc} for r in rows for loc in r['changed_locations']]
    with (qa/'output_changed_locations.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=location_fields);writer.writeheader();writer.writerows(locations)
    print(json.dumps({k:v for k,v in record.items() if k not in ('comparisons',)},indent=2))

if __name__=='__main__':main()
