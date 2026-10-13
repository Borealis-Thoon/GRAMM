from native_benchmark import *
NATIVE['scalar_tdma']=JOB/'build/scalar_tdma/GRAMM.dll'
PLAN_SCALAR={
 'scalar_neutral_1t':dict(nx=48,ny=36,nz=24,dx=250,duration=3600,threads=1),
 'scalar_convective_4t':dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True),
 'scalar_stable_coast_8t':dict(nx=64,ny=48,nz=24,dx=500,sc=7,wind=1,duration=600,threads=8,coast=True,turbulence=True),
}
if __name__=='__main__':
 records=[]
 (JOB/'qa/native/scalar_plan.json').write_text(json.dumps(PLAN_SCALAR,indent=2))
 for name,config in PLAN_SCALAR.items():
  for rep in range(6):
   order=['baseline','scalar_tdma'] if rep%2==0 else ['scalar_tdma','baseline']
   for variant in order:
    records.append(native_one(name,variant,config,rep))
    (JOB/'qa/native/scalar_results.json').write_text(json.dumps(records,indent=2))
 print('SCALAR_NATIVE PASS',len(records),flush=True)
