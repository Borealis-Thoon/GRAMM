from full_tests import *
sys.path.insert(0,str(JOB/'qa/pressure'))
from native_console_runner import run_hidden_console
PLAN={
 'small_neutral_1t':dict(config=dict(nx=24,ny=20,nz=16,dx=100,duration=3600,threads=1),repeats=5),
 'medium_neutral_1t':dict(config=dict(nx=48,ny=36,nz=24,dx=250,duration=3600,threads=1),repeats=5),
 'large_neutral_4t':dict(config=dict(nx=96,ny=64,nz=28,dx=500,duration=3600,threads=4,turbulence=True),repeats=5),
 'stable_coast_8t':dict(config=dict(nx=64,ny=48,nz=24,dx=500,sc=7,wind=1,duration=600,threads=8,coast=True,turbulence=True),repeats=5),
 'convective_4t':dict(config=dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True),repeats=5),
 'every_step_radiation_4t':dict(config=dict(nx=24,ny=20,nz=16,dx=100,sc=3,wind=2,duration=300,threads=4,irad=1),repeats=3),
}
# Rotation balances process ordering over baseline and three isolated patches.
ORDERS=[['baseline','pressure','tdma','radiation'],['pressure','radiation','baseline','tdma'],['tdma','baseline','radiation','pressure'],['radiation','tdma','pressure','baseline']]

def native_one(name,variant,config,rep):
    folder=JOB/'runs/native'/name/(f'r{rep:02d}_'+variant)
    c=make_case(folder,**config)
    r=run_hidden_console(NATIVE[variant],folder,timeout=300,last=c['situations'])
    if r['status']!='pass':raise RuntimeError('Native execution failed '+str(folder))
    if (folder/'Problemreport_GRAMM.txt').exists() and (folder/'Problemreport_GRAMM.txt').stat().st_size:raise RuntimeError('Native numerical problem '+str(folder))
    payload=outputs(folder,c['situations'])
    rec=dict(case=name,variant=variant,rep=rep,measured=rep>0,config=c,lifetime_seconds=r['lifetime_seconds'],cpu_seconds=r['process_cpu_seconds'],peak_working_set_bytes=r['peak_working_set_bytes'],assembly_sha256=r['assembly_sha256'],payloads=payload,folder=str(folder))
    (folder/'benchmark_result.json').write_text(json.dumps(rec,indent=2))
    print(f"NATIVE {name} r{rep} {variant} {r['lifetime_seconds']:.4f}s",flush=True)
    return rec
if __name__=='__main__':
    (JOB/'qa/native').mkdir(parents=True,exist_ok=True)
    (JOB/'qa/native/plan.json').write_text(json.dumps(PLAN,indent=2))
    records=[]
    for name,plan in PLAN.items():
        for rep in range(plan['repeats']+1):
            for v in ORDERS[rep%4]:
                rec=native_one(name,v,plan['config'],rep);records.append(rec)
                (JOB/'qa/native/results.json').write_text(json.dumps(records,indent=2))
    print('NATIVE PASS',len(records),flush=True)
