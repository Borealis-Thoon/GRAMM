"""Compare full-precision GRAMM state against native baseline repeat variation.

No numerical tolerance is used to declare equivalence. Status refers only to
complete, finite, correctly sized data. Every observed difference is reported.
"""
from pathlib import Path
from array import array
from itertools import combinations
import argparse,csv,hashlib,json,math,re,statistics,struct,sys

FIELDS=('U','V','W','T','QU','PN','TE','DISS','RADIATION')
VARIANTS=('baseline','pressure_recurrence')
METRICS=('max_abs','mae','rmse','changed_fraction')
SHA=re.compile(r'^[a-f0-9]{64}$')


def require(condition,message):
    if not condition: raise ValueError(message)


def load_json(path):
    require(path.is_file(),f'Missing JSON: {path}')
    def reject(value): raise ValueError('Non-finite JSON literal: '+value)
    return json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=reject)


def sha(data): return hashlib.sha256(data).hexdigest()


def load_run(job,plan,threads,repeat,variant):
    folder=job/'runs'/f'recurrence_parallel_t{threads}_r{repeat}'/variant
    result=load_json(folder/'result.json'); c=load_json(folder/'fixture.json'); expected={**plan['config'],'threads':threads}
    require(result['serial'] is False and result['config']==c,'Run metadata differs')
    for key,value in expected.items():
        actual=c['grid'][key] if key in ('nx','ny','nz') else c['grid']['dx_m'] if key=='dx' else c[key]
        require(actual==value,f'Unexpected fixture {key}: {actual} != {value}')
    require(c['situations']==1 and c['sc']==2 and c['wind']==2 and c['duration']==300,'Expected one 300-second SC2 case')
    require(c['turbulence'] is True and c['coast'] is True and c['radiation'] is True,'Expected coastal turbulence/radiation case')
    iin=[line.split(':',1)[1].strip() for line in (folder/'IIN.dat').read_text().splitlines()]
    require(int(iin[17])==1110111,'Turbulence and radiation equations must be enabled')
    problem=folder/'Problemreport_GRAMM.txt';require(not problem.exists() or not problem.read_text(errors='replace').strip(),'Problemreport_GRAMM.txt contains an error')
    core=folder/'Logfile_GRAMMCore.txt';require(not core.exists() or 'GRAMM Error:' not in core.read_text(errors='replace'),'Core log contains an error')
    with (folder/'harness_integration.csv').open(encoding='utf-8-sig',newline='') as stream: rows=list(csv.DictReader(stream))
    require(len(rows)==1 and result['integration']==rows,'Missing or inconsistent integration metadata')
    row=rows[0]
    require(int(row['weather_start'])==1 and int(row['weather_end'])==1 and int(row['retries'])==0,'Wrong weather identifier or numerical retry')
    require(int(row['serial'])==0 and int(row['configured_threads'])==threads,'Wrong dispatch mode or configured threads')
    dt,rt,limit,elapsed=(float(row[k]) for k in ('dt','realtime','tlimit','elapsed_seconds'))
    require(all(math.isfinite(v) for v in (dt,rt,limit,elapsed)) and dt>0 and elapsed>0,'Non-finite or non-positive integration metadata')
    require(limit==300 and limit<=rt<=limit+dt+1e-6 and int(row['itime'])>=3,'Configured integration not completed')
    paths=list(folder.glob('harness_snapshot_*.json'));require(len(paths)==1 and paths[0].name=='harness_snapshot_00001.json','Missing or extra snapshot')
    snap=load_json(paths[0]);require(result['snapshots']==[snap],'Snapshot differs from result record')
    nx,ny,nz=(c['grid'][k] for k in ('nx','ny','nz'))
    require((snap['nx'],snap['ny'],snap['nz'])==(nx,ny,nz) and snap['itime']==int(row['itime']) and snap['realtime']==rt,'Snapshot does not match integration')
    require(snap['weather_start']==1 and snap['weather_end']==1 and snap['encoding']=='float64-le' and snap['order']=='i,j,k including allocated halo cells','Invalid snapshot identity/encoding/order')
    require(len(snap['fields'])==9 and {f['name'] for f in snap['fields']}==set(FIELDS),'Missing or duplicate fields')
    binary_files={};metadata={}
    for field in snap['fields']:
        name=field['name'];count=(nx+1)*(ny+1)*(nz if name=='RADIATION' else nz+1)
        require(field['count']==count and field['finite_count']==count and field['finite'] is True,'Non-finite or wrong field count: '+name)
        require(math.isfinite(field['min']) and math.isfinite(field['max']) and field['min']<=field['max'],'Invalid field extrema: '+name)
        require(SHA.fullmatch(field['sha256']),'Invalid field SHA256: '+name)
        filename=field['binary_file'];require(isinstance(filename,str) and Path(filename).name==filename,'Missing local binary filename: '+name)
        path=folder/filename;data=path.read_bytes();require(len(data)==count*8 and sha(data)==field['sha256'],'Binary size/hash mismatch: '+name)
        values=array('d');values.frombytes(data)
        if sys.byteorder!='little':values.byteswap()
        require(all(math.isfinite(v) for v in values),'Non-finite raw field: '+name)
        require(min(values)==field['min'] and max(values)==field['max'],'Raw field extrema mismatch: '+name)
        binary_files[name]=path;metadata[name]=field
    return {'folder':str(folder),'threads':threads,'repeat':repeat,'variant':variant,'integration':row,'fields':metadata,'binary_files':binary_files}


def read_values(path):
    values=array('d');values.frombytes(path.read_bytes())
    if sys.byteorder!='little':values.byteswap()
    return values


def compare_runs(a,b,kind):
    rows=[]
    same_steps=all(a['integration'][k]==b['integration'][k] for k in ('itime','dt','realtime','tlimit'))
    for name in FIELDS:
        av=read_values(a['binary_files'][name]);bv=read_values(b['binary_files'][name]);require(len(av)==len(bv),'Comparison count mismatch')
        n=len(av);diff=array('d',(y-x for x,y in zip(av,bv)));require(all(math.isfinite(d) for d in diff),'Non-finite difference')
        changed=sum(d!=0 for d in diff);maximum=max(abs(d) for d in diff)
        rows.append({'threads':a['threads'],'kind':kind,'reference_variant':a['variant'],'candidate_variant':b['variant'],
          'reference_repeat':a['repeat'],'candidate_repeat':b['repeat'],'field':name,'count':n,'finite':True,
          'hash_identical':a['fields'][name]['sha256']==b['fields'][name]['sha256'],'changed_count':changed,'changed_fraction':changed/n,
          'max_abs':maximum,'mae':math.fsum(abs(d) for d in diff)/n,'rmse':math.sqrt(math.fsum(d*d for d in diff)/n),
          'mean_signed_difference':math.fsum(diff)/n,'steps_identical':same_steps,'reference_realtime':float(a['integration']['realtime']),'candidate_realtime':float(b['integration']['realtime'])})
    return rows


def stats(values): return {'min':min(values),'median':statistics.median(values),'max':max(values)}


def envelopes(rows,threads):
    output=[]
    for thread in threads:
        for name in FIELDS:
            reference=[r for r in rows if r['threads']==thread and r['field']==name and r['kind']=='baseline_repeat']
            require(len(reference)==3,'Expected three baseline-repeat pairs')
            base={m:stats([r[m] for r in reference]) for m in METRICS}
            for variant in VARIANTS[1:]:
                candidate=[r for r in rows if r['threads']==thread and r['field']==name and r['candidate_variant']==variant and r['kind']=='matched_patch']
                require(len(candidate)==3,'Expected three matched patch pairs')
                observed={m:stats([r[m] for r in candidate]) for m in METRICS}
                ratios={m:(observed[m]['max']/base[m]['max'] if base[m]['max'] else None) for m in METRICS}
                above={m:observed[m]['max']>base[m]['max'] for m in METRICS}
                output.append({'threads':thread,'field':name,'variant':variant,'baseline_repeat_pairs':3,'matched_patch_pairs':3,
                  'baseline_steps_identical_pairs':sum(r['steps_identical'] for r in reference),'patch_steps_identical_pairs':sum(r['steps_identical'] for r in candidate),
                  'baseline_hash_identical_pairs':sum(r['hash_identical'] for r in reference),
                  'patch_hash_identical_pairs':sum(r['hash_identical'] for r in candidate),
                  'baseline_repeat_metrics':base,'matched_patch_metrics':observed,'patch_max_divided_by_baseline_max':ratios,
                  'patch_max_above_observed_baseline_max':above,
                  'interpretation':'Observed repeat variation only; no equivalence threshold or significance test is applied.'})
    return output


def write_csv(path,rows):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,default=Path(__file__).resolve().parents[2]);args=ap.parse_args()
    job=args.job.resolve();qa=job/'qa/recurrence_parallel';plan=load_json(qa/'plan.json');errors=[];runs={}
    expected_runs=len(VARIANTS)*3*3
    require(plan['threads']==[1,4,8] and plan['repeats']==3 and plan['expected_runs']==expected_runs,'Unexpected trial plan')
    require(plan['variants']==list(VARIANTS) and plan['serial'] is False and plan['snapshot'] is True and plan['binary'] is True,'Unexpected variants or output mode')
    expected_keys={(thread,repeat,variant) for thread in plan['threads'] for repeat in (1,2,3) for variant in VARIANTS}
    planned_keys=[(item['threads'],item['repeat'],item['variant']) for item in plan['run_order']]
    require(len(planned_keys)==expected_runs and set(planned_keys)==expected_keys,'Missing or duplicate planned runs')
    require(all(item['case']==f"recurrence_parallel_t{item['threads']}_r{item['repeat']}" for item in plan['run_order']),'Unexpected planned case path')
    for thread in plan['threads']:
        for repeat in (1,2,3):
            for variant in VARIANTS:
                key=(thread,repeat,variant)
                try:runs[key]=load_run(job,plan,*key)
                except Exception as error:errors.append({'threads':thread,'repeat':repeat,'variant':variant,'error':str(error)})
    if errors:
        result={'data_status':'fail','errors':errors,'valid_runs':len(runs),'expected_runs':expected_runs}
        (qa/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2));return 1
    rows=[]
    for thread in plan['threads']:
        for a,b in combinations((1,2,3),2):rows.extend(compare_runs(runs[(thread,a,'baseline')],runs[(thread,b,'baseline')],'baseline_repeat'))
        for variant in VARIANTS[1:]:
            for repeat in (1,2,3):rows.extend(compare_runs(runs[(thread,repeat,'baseline')],runs[(thread,repeat,variant)],'matched_patch'))
    expected_baseline_fields=len(plan['threads'])*3*len(FIELDS)
    expected_patch_fields=len(plan['threads'])*(len(VARIANTS)-1)*3*len(FIELDS)
    require(len(rows)==expected_baseline_fields+expected_patch_fields,'Incomplete field comparisons')
    require(sum(r['kind']=='baseline_repeat' for r in rows)==expected_baseline_fields,'Incomplete baseline repeat comparisons')
    require(sum(r['kind']=='matched_patch' for r in rows)==expected_patch_fields,'Incomplete matched patch comparisons')
    envelope=envelopes(rows,plan['threads'])
    require(len(envelope)==len(plan['threads'])*len(FIELDS)*(len(VARIANTS)-1),'Incomplete metric envelopes')
    result={'data_status':'complete_and_finite','equivalence_verdict':'not_assigned','runs':len(runs),'field_comparisons':len(rows),
      'variants':list(VARIANTS),'expected_runs':expected_runs,'metric_envelopes':len(envelope),'metric_rows':len(envelope)*len(METRICS),
      'baseline_repeat_field_comparisons':sum(r['kind']=='baseline_repeat' for r in rows),'matched_patch_field_comparisons':sum(r['kind']=='matched_patch' for r in rows),
      'hash_identical_field_pairs':sum(r['hash_identical'] for r in rows),'steps_identical_field_pairs':sum(r['steps_identical'] for r in rows),
      'scope':'Native Parallel dispatch; 48x36x24 coastal convective input, turbulence and radiation enabled, 300 model seconds; configured thread limits 1,4,8.',
      'metrics_include':'All allocated field values including halo cells; IEEE-754 double snapshots after integration.',
      'envelopes':envelope,'comparisons':rows,'errors':[]}
    (qa/'analysis.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    write_csv(qa/'field_comparisons.csv',rows)
    flat=[]
    for e in envelope:
        for metric in METRICS:
            flat.append({'threads':e['threads'],'field':e['field'],'variant':e['variant'],'metric':metric,
               **{'baseline_'+k:v for k,v in e['baseline_repeat_metrics'][metric].items()},
               **{'patch_'+k:v for k,v in e['matched_patch_metrics'][metric].items()},
               'patch_max_over_baseline_max':e['patch_max_divided_by_baseline_max'][metric],
               'above_observed_baseline_max':e['patch_max_above_observed_baseline_max'][metric],
               'baseline_hash_identical_pairs':e['baseline_hash_identical_pairs'],'patch_hash_identical_pairs':e['patch_hash_identical_pairs'],
               'baseline_steps_identical_pairs':e['baseline_steps_identical_pairs'],'patch_steps_identical_pairs':e['patch_steps_identical_pairs']})
    write_csv(qa/'baseline_variation_comparison.csv',flat)
    print(json.dumps({k:v for k,v in result.items() if k not in ('envelopes','comparisons')},indent=2));return 0

if __name__=='__main__': raise SystemExit(main())
