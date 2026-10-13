from full_tests import *
CASES={
 'neutral_small_1t':dict(nx=24,ny=20,nz=16,dx=100,duration=3600,threads=1),
 'neutral_medium_4t':dict(nx=48,ny=36,nz=24,dx=250,duration=3600,threads=4),
 'stable_coast_8t':dict(nx=64,ny=48,nz=24,dx=500,sc=7,wind=1,duration=600,threads=8,coast=True),
 'convective_sun_1t':dict(nx=24,ny=20,nz=16,dx=250,sc=2,wind=2,duration=2100,threads=1),
 'frequent_radiation_4t':dict(nx=24,ny=20,nz=16,dx=100,sc=3,wind=2,duration=180,threads=4,irad=1),
 'sequential_custom_4t':dict(nx=32,ny=24,nz=20,dx=250,duration=360,threads=4,coast=True,multi=True,custom=True),
 'calm_convective_8t':dict(nx=32,ny=24,nz=20,dx=500,sc=2,wind=.4,duration=180,dt=10,threads=8,coast=True),
 'radiation_off_1t':dict(nx=24,ny=20,nz=16,dx=250,sc=6,wind=1,duration=180,threads=1,radiation=False),
}
def compare(a,b):
    rows=[]
    if len(a['snapshots'])!=len(b['snapshots']):raise RuntimeError('Snapshot count mismatch')
    for sa,sb in zip(a['snapshots'],b['snapshots']):
        for fa,fb in zip(sa['fields'],sb['fields']):
            rows.append(dict(weather=sa['weather_start'],field=fa['name'],count=fa['count'],identical=fa['sha256']==fb['sha256']))
    same_outputs=a['payloads']==b['payloads']
    same_steps=all((ra['itime'],ra['dt'],ra['realtime'],ra['tlimit'])==(rb['itime'],rb['dt'],rb['realtime'],rb['tlimit']) for ra,rb in zip(a['integration'],b['integration']))
    return dict(status='pass' if all(r['identical'] for r in rows) and same_outputs and same_steps else 'fail',fields=rows,payloads_identical=same_outputs,steps_identical=same_steps)
if __name__=='__main__':
    summary=[]
    (JOB/'qa/fidelity').mkdir(parents=True,exist_ok=True)
    (JOB/'qa/fidelity/cases.json').write_text(json.dumps(CASES,indent=2))
    for name,config in CASES.items():
        base=run_instrumented('fidelity_'+name,'baseline',config)
        for v in ['pressure','tdma','radiation']:
            result=run_instrumented('fidelity_'+name,v,config)
            comp=compare(base,result);comp.update(case=name,variant=v)
            summary.append(comp)
            (JOB/'qa/fidelity/results.json').write_text(json.dumps(summary,indent=2))
            if comp['status']!='pass':raise RuntimeError('Fidelity failed: '+name+' '+v)
    print('FIDELITY PASS',len(summary),flush=True)
