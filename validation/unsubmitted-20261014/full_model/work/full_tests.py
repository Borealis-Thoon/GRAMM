from pathlib import Path
import sys,json,os,subprocess,time,csv,hashlib,zipfile,struct,math
JOB=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(JOB/'work'))
from fixture import make_case
DOTNET=__import__('shutil').which('dotnet') or r'C:\Program Files\dotnet\dotnet.exe'
def outputs(folder,situations):
    values={}
    for n in range(1,situations+1):
        wnd=folder/f'{n:05d}.wnd'
        if not wnd.exists():raise RuntimeError('Missing output: '+str(wnd))
        raw=wnd.read_bytes(); header,nx,ny,nz,dx=struct.unpack_from('<iiiif',raw)
        if len(raw)!=20+nx*ny*nz*6:raise RuntimeError('Wrong wind length')
        wind=struct.unpack_from('<'+'h'*((len(raw)-20)//2),raw,20)
        if any(abs(v)>30000 for v in wind):raise RuntimeError('Nonphysical/sentinel wind')
        values[wnd.name]={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
        with zipfile.ZipFile(folder/f'{n:05d}.scl') as z:
            for name in sorted(z.namelist()):
                b=z.read(name);values[f'{n:05d}.scl/{name}']={'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
        p=folder/f'{n:05d}_steady_state.txt'
        if p.exists():values[p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}
    problem=folder/'Problemreport_GRAMM.txt'
    if problem.exists() and problem.stat().st_size:raise RuntimeError('Problem report: '+problem.read_text(errors='replace')[:600])
    return values

def run_instrumented(case,variant,config,*,serial=True,snapshot=True,binary=False):
    folder=JOB/'runs'/case/variant
    c=make_case(folder,**config)
    env=os.environ.copy();env['GRAMM_TEST_SERIAL']='1' if serial else '0'
    env['GRAMM_TEST_SNAPSHOT']='1' if snapshot else '0';env['GRAMM_TEST_BINARY']='1' if binary else '0'
    dll=JOB/'build'/('instrumented_'+variant)/'GRAMM.dll'
    t=time.perf_counter()
    with (folder/'console.log').open('wb') as log:
        try:r=subprocess.run([DOTNET,str(dll),'1',str(c['situations'])],cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        except subprocess.TimeoutExpired:raise RuntimeError('Model watchdog timeout: '+str(folder))
    elapsed=time.perf_counter()-t
    if r.returncode:raise RuntimeError(f'Model failed {r.returncode}: {folder}')
    csvpath=folder/'harness_integration.csv'
    rows=list(csv.DictReader(csvpath.open()))
    if len(rows)!=c['situations']:raise RuntimeError('Incomplete integration: '+str(rows))
    for row in rows:
        if int(row['itime'])<3 or float(row['realtime'])<float(row['tlimit']):raise RuntimeError('Incomplete steps')
        if int(row['retries']):raise RuntimeError('Retry in matched test')
    payload=outputs(folder,c['situations'])
    snaps=[]
    for p in sorted(folder.glob('harness_snapshot_*.json')):
        snap=json.loads(p.read_text());snaps.append(snap)
        if not all(f['finite'] for f in snap['fields']):raise RuntimeError('Nonfinite full-precision model state')
    if snapshot and len(snaps)!=c['situations']:raise RuntimeError('Missing full precision snapshot')
    for snap in snaps:
        if {f['name'] for f in snap['fields']}!={'U','V','W','T','QU','PN','TE','DISS','RADIATION'}:raise RuntimeError('Missing expected field')
    result=dict(case=case,variant=variant,config=c,serial=serial,wall_seconds=elapsed,integration=rows,payloads=payload,snapshots=snaps)
    (folder/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'case':case,'variant':variant,'wall':round(elapsed,3),'integration':rows}),flush=True)
    return result
