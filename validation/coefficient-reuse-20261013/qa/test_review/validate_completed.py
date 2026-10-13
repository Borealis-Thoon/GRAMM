"""Strict, read-only post-validation of completed full-engine fidelity runs.

Reads declared cases and selected variants. Missing runs, snapshots,
fields, or outputs fail. This script never runs GRAMM or edits its inputs.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, re, struct, sys, zipfile

FIELDS={"U","V","W","T","QU","PN","TE","DISS","RADIATION"}
VARIANTS=("baseline","pressure","tdma","radiation")
KNOWN_VARIANTS=VARIANTS+("scalar_tdma",)
SHA=re.compile(r"^[0-9a-f]{64}$")
REQUIRED_ROW={"weather_start","weather_end","elapsed_seconds","itime","dt","realtime","tlimit","retries","configured_threads","serial"}


def require(condition,message):
    if not condition: raise ValueError(message)


def read_json(path):
    require(path.is_file(),f"Missing JSON: {path}")
    def no_constant(value): raise ValueError(f"Non-finite JSON literal: {value}")
    return json.loads(path.read_text(encoding="utf-8-sig"),parse_constant=no_constant)


def digest(data): return hashlib.sha256(data).hexdigest()


def integration_target(sc,wind,duration):
    # Meteopgtall.Integrationtime for fixture's METEO=y, ISTAT=0, meteopgt_nr=0.
    if sc<4: return duration*(1 if wind<3 else .5 if wind<5 else .3 if wind<7 else .17)
    if sc==4: return min(duration*.17,600)
    if sc==6: return min(duration*1.5,3600) if wind<=2 else duration
    if sc==7: return min(duration*(2 if wind<.5 else 1.5 if wind<1 else 1),3600)
    return duration


def read_payload(data,nx,ny,nz,dx,values,label):
    require(len(data)>=20,f"Truncated header: {label}")
    header,x,y,z,spacing=struct.unpack_from('<iiiif',data)
    require(header==-1,f"Unexpected header: {label}: {header}")
    require((x,y,z)==(nx,ny,nz),f"Dimensions differ: {label}: {(x,y,z)} != {(nx,ny,nz)}")
    require(math.isfinite(spacing) and math.isclose(spacing,dx,rel_tol=1e-6),f"Resolution differs: {label}")
    require(len(data)==20+values*2,f"Payload count differs: {label}: bytes={len(data)} expected={20+values*2}")
    decoded=struct.unpack_from('<'+'h'*values,data,20)
    return {"sha256":digest(data),"bytes":len(data),"values":values,"min":min(decoded),"max":max(decoded)}


def validate_run(folder,plan):
    c=read_json(folder/'fixture.json'); result=read_json(folder/'result.json')
    grid=c['grid']; nx,ny,nz=(grid[k] for k in ('nx','ny','nz')); dx=grid['dx_m']; n=c['situations']
    for key,value in plan.items():
        actual=grid[key] if key in ('nx','ny','nz') else grid['dx_m'] if key=='dx' else c[key]
        require(actual==value,f"Fixture differs from plan: {key}: {actual} != {value}")
    require(result['config']==c,'result.json configuration differs from fixture.json')
    require(result['serial'] is True,'Fidelity result must use serial adapter')
    require(n==(3 if c['multi'] else 1),'Unexpected weather-situation count')
    raw_iin=(folder/'IIN.dat').read_text().splitlines(); iin=[line.split(':',1)[1].strip() for line in raw_iin]
    require(len(iin)>=29 and int(iin[25])==0,'Expected ISTAT=0 fixture')
    require(float(iin[3])==c['duration'],'IIN duration differs from configuration')
    require(int(iin[14])==c['irad'],'IIN radiation interval differs from configuration')
    require((int(iin[17])%10==1)==c.get('radiation',True),'IIN radiation switch differs from configuration')
    require(((int(iin[17])//100)%10==1)==c.get('turbulence',False),'IIN turbulence switch differs from configuration')
    gramm_in=(folder/'GRAMMin.dat').read_text().splitlines()
    require(gramm_in[1].lower()=='y' and int(gramm_in[-1])==0,'Expected meteopgt input without six-hour sunrise override')
    mets=[line.split(',') for line in (folder/'meteopgt.all').read_text().splitlines()[2:] if line.strip()]
    require(len(mets)==n,'Meteorology row count differs')
    weather_ids=list(range(1,n+1))
    for logfile in ('Problemreport_GRAMM.txt','Logfile_Problemreport.txt'):
        p=folder/logfile
        require(not p.exists() or not p.read_text(errors='replace').strip(),f"Problem report present: {logfile}")
    core=folder/'Logfile_GRAMMCore.txt'
    require(not core.exists() or 'GRAMM Error:' not in core.read_text(errors='replace'),'GRAMM Error present in core log')
    with (folder/'harness_integration.csv').open(newline='',encoding='utf-8-sig') as stream:
        reader=csv.DictReader(stream); require(REQUIRED_ROW <= set(reader.fieldnames or []),'Missing integration CSV columns'); rows=list(reader)
    require(len(rows)==n,'Incomplete integration CSV row count')
    require([int(row['weather_start']) for row in rows]==weather_ids,'Incorrect or duplicate integration weather identifiers')
    checked_rows=[]
    for weather,row in zip(weather_ids,rows):
        require(int(row['weather_end'])==weather,'Unexpected intermediate weather renumbering')
        require(int(row['retries'])==0,'Numerical retry occurred')
        require(int(row['configured_threads'])==c['threads'],'Configured thread count differs')
        require(int(row['serial'])==1,'Non-serial run in deterministic fidelity suite')
        steps=int(row['itime']); dt=float(row['dt']); rt=float(row['realtime']); limit=float(row['tlimit']); elapsed=float(row['elapsed_seconds'])
        require(all(math.isfinite(x) for x in (dt,rt,limit,elapsed)),'Non-finite integration metadata')
        require(steps>=3 and dt>0 and elapsed>0 and rt>=limit and rt<=limit+dt+1e-6,'Integration did not finish normally')
        expected=integration_target(int(mets[weather-1][2]),float(mets[weather-1][1]),c['duration'])
        require(math.isclose(limit,expected,rel_tol=1e-12,abs_tol=1e-9),f'Effective integration duration differs: {limit} != {expected}')
        checked_rows.append(dict(weather=weather,itime=steps,dt=dt,realtime=rt,tlimit=limit,elapsed_seconds=elapsed))
    require(result['integration']==rows,'Saved result integration differs from actual CSV')
    paths=sorted(folder.glob('harness_snapshot_*.json'))
    require([p.name for p in paths]==[f'harness_snapshot_{n:05d}.json' for n in weather_ids],'Missing or extra precision snapshots')
    snapshots={}; values=0
    for weather,p,row in zip(weather_ids,paths,checked_rows):
        snap=read_json(p)
        require((snap['nx'],snap['ny'],snap['nz'])==(nx,ny,nz),'Snapshot grid differs')
        require(snap['weather_start']==weather and snap['weather_end']==weather,'Snapshot weather identifier differs')
        require(snap['itime']==row['itime'] and snap['realtime']==row['realtime'],'Snapshot integration metadata differs')
        require(snap['encoding']=='float64-le' and snap['order']=='i,j,k including allocated halo cells','Unexpected snapshot encoding/order')
        fields=snap['fields']; require(len(fields)==len(FIELDS) and {f['name'] for f in fields}==FIELDS,'Missing, extra, or duplicate snapshot field')
        checked_fields={}
        for field in fields:
            name=field['name']; count=(nx+1)*(ny+1)*(nz if name=='RADIATION' else nz+1)
            require(field['count']==count and field['finite_count']==count and field['finite'] is True,f'Non-finite or wrong-sized field: {name}')
            require(math.isfinite(field['min']) and math.isfinite(field['max']) and field['min']<=field['max'],f'Invalid field extrema: {name}')
            require(isinstance(field['sha256'],str) and SHA.fullmatch(field['sha256']),f'Invalid SHA256: {name}')
            binary=field['binary_file']
            if binary is not None:
                require(Path(binary).name==binary,'Snapshot binary path must be local filename')
                data=(folder/binary).read_bytes();require(len(data)==count*8 and digest(data)==field['sha256'],f'Binary size/hash differs: {name}')
                require(all(math.isfinite(x[0]) for x in struct.iter_unpack('<d',data)),f'Non-finite binary value: {name}')
            checked_fields[name]={k:field[k] for k in ('count','finite_count','finite','min','max','sha256')};values+=count
        snapshots[weather]=checked_fields
    require(len(result['snapshots'])==n,'Saved result snapshot count differs')
    require(result['snapshots']==[read_json(p) for p in paths],'Saved result snapshots differ from actual JSON')
    payloads={}
    for weather in weather_ids:
        prefix=f'{weather:05d}'; data=(folder/(prefix+'.wnd')).read_bytes()
        record=read_payload(data,nx,ny,nz,dx,nx*ny*nz*3,prefix+'.wnd')
        require(record['min']>-30000 and record['max']<30000,'Wind output contains sentinel/extreme values')
        payloads[prefix+'.wnd']=record
        with zipfile.ZipFile(folder/(prefix+'.scl')) as archive:
            names=archive.namelist(); require(len(names)==3 and set(names)=={prefix+'.ust',prefix+'.obl',prefix+'.scl'},'Missing, extra, or duplicate SCL payload')
            require(archive.testzip() is None,'SCL CRC check failed')
            for name in sorted(names):
                payloads[prefix+'.scl/'+name]=read_payload(archive.read(name),nx,ny,nz,dx,nx*ny,name)
        steady=folder/(prefix+'_steady_state.txt')
        if steady.exists(): payloads[steady.name]={'sha256':digest(steady.read_bytes()),'bytes':steady.stat().st_size}
    console=(folder/'console.log').read_text(errors='replace')
    times=re.findall(r'(?m)^\s*(\d{1,2}\.\d{1,2} - \d{1,2}:\d{2})\s*$',console)
    dynamic=any(int(m[2])<4 and row['tlimit']>1800 for m,row in zip(mets,checked_rows)) and c.get('radiation',True)
    if dynamic: require(len(set(times))>=2,'No distinct solar timestamps despite passing 1800-second boundary')
    return dict(status='pass',folder=str(folder),situations=n,field_values=values,integration=checked_rows,snapshots=snapshots,
                payloads=payloads,solar_timestamps=times,dynamic_1800_boundary=dynamic,turbulence_equations_enabled=(int(iin[17])//100)%10==1)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--job',type=Path,default=Path(__file__).resolve().parents[2])
    ap.add_argument('--cases',type=Path,help='Case-plan JSON; defaults to qa/fidelity/cases.json')
    ap.add_argument('--select-case',action='append',help='Validate only this declared case; repeat for more cases')
    ap.add_argument('--variants',nargs='+',choices=KNOWN_VARIANTS,default=list(VARIANTS),help='Baseline first, followed by the patches to compare')
    ap.add_argument('--case-prefix',default='fidelity_',help='Folder prefix below job/runs')
    ap.add_argument('--expected-cases',type=int)
    ap.add_argument('--expected-runs',type=int)
    ap.add_argument('--expected-weather-runs',type=int,help='Total weather situations across all selected variants')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    job=args.job.resolve(); cases_path=(args.cases or job/'qa/fidelity/cases.json').resolve()
    cases=read_json(cases_path);variants=tuple(args.variants);errors=[];runs={};comparisons=[]
    require(isinstance(cases,dict) and cases,'Case plan must be a nonempty object')
    require(all(re.fullmatch(r'[A-Za-z0-9_-]+',case) and isinstance(plan,dict) for case,plan in cases.items()),'Invalid case name or configuration')
    require(re.fullmatch(r'[A-Za-z0-9_-]*',args.case_prefix) is not None,'Invalid case folder prefix')
    require(len(variants)>=2 and variants[0]=='baseline' and len(set(variants))==len(variants),'Select baseline first and at least one unique patch')
    if args.select_case:
        require(len(set(args.select_case))==len(args.select_case),'Duplicate selected case')
        require(set(args.select_case)<=set(cases),'Selected case is absent from the declared plan')
        cases={name:cases[name] for name in args.select_case}
    if args.expected_cases is not None:require(len(cases)==args.expected_cases,'Declared case count differs from expected count')
    expected_runs=len(cases)*len(variants)
    weather_per_variant=sum(3 if plan.get('multi',False) else 1 for plan in cases.values())
    expected_weather_runs=weather_per_variant*len(variants)
    if args.expected_runs is not None:require(expected_runs==args.expected_runs,'Planned process-run count differs from expected count')
    if args.expected_weather_runs is not None:require(expected_weather_runs==args.expected_weather_runs,'Planned weather-run count differs from expected count')
    for case,plan in cases.items():
        for variant in variants:
            key=case+'/'+variant
            try:runs[key]=validate_run(job/'runs'/(args.case_prefix+case)/variant,plan)
            except Exception as error:errors.append({'run':key,'error':str(error)});runs[key]={'status':'fail'}
    for case in cases:
        base=runs[case+'/baseline']
        for variant in variants[1:]:
            other=runs[case+'/'+variant]
            if base['status']!='pass' or other['status']!='pass':continue
            fields=[]
            for weather,base_fields in base['snapshots'].items():
                for name in sorted(FIELDS):
                    a=base_fields[name];b=other['snapshots'][weather][name]
                    fields.append(dict(weather=weather,field=name,count=a['count'],identical=a==b))
            steps=[{k:v for k,v in r.items() if k!='elapsed_seconds'} for r in base['integration']]==[{k:v for k,v in r.items() if k!='elapsed_seconds'} for r in other['integration']]
            payloads=base['payloads']==other['payloads'];good=all(f['identical'] for f in fields) and steps and payloads
            comparisons.append(dict(case=case,variant=variant,status='pass' if good else 'fail',fields=fields,steps_identical=steps,payloads_identical=payloads))
            if not good:errors.append({'run':case+'/'+variant,'error':'Baseline comparison mismatch'})
    expected_pairs=len(cases)*(len(variants)-1)
    expected_field_pairs=weather_per_variant*(len(variants)-1)*len(FIELDS)
    weather_runs=sum(r.get('situations',0) for r in runs.values())
    field_pairs=sum(len(c['fields']) for c in comparisons)
    if len(comparisons)!=expected_pairs:errors.append({'error':f'Expected {expected_pairs} comparisons, got {len(comparisons)}'})
    if weather_runs!=expected_weather_runs:errors.append({'error':f'Expected {expected_weather_runs} weather runs, got {weather_runs}'})
    if field_pairs!=expected_field_pairs:errors.append({'error':f'Expected {expected_field_pairs} precision field pairs, got {field_pairs}'})
    summary=dict(status='pass' if not errors else 'fail',cases_path=str(cases_path),case_prefix=args.case_prefix,variants=list(variants),case_count=len(cases),
        expected_runs=expected_runs,run_count=len(runs),expected_weather_runs=expected_weather_runs,weather_runs=weather_runs,
        passed_runs=sum(r['status']=='pass' for r in runs.values()),field_values_checked=sum(r.get('field_values',0) for r in runs.values()),
        expected_comparison_count=expected_pairs,comparison_count=len(comparisons),expected_full_precision_field_pairs=expected_field_pairs,
        full_precision_field_pairs=field_pairs,errors=errors,runs=runs,comparisons=comparisons)
    output=args.output or job/'qa/test_review/completed_validation.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('runs','comparisons')},indent=2))
    return 0 if summary['status']=='pass' else 1

if __name__=='__main__': raise SystemExit(main())
