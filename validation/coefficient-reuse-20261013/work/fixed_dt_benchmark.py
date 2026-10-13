from native_benchmark import *
NATIVE['scalar_tdma']=JOB/'build/scalar_tdma/GRAMM.dll'
name='fixed_dt_4t'
config=dict(nx=48,ny=36,nz=24,dx=250,sc=5,wind=2,duration=450,dt=1.5,irad=60,threads=4,turbulence=True)
variants=['baseline','pressure','tdma','radiation','scalar_tdma']
if __name__=='__main__':
 records=[]
 for rep in range(6):
  order=variants[rep%5:]+variants[:rep%5]
  if rep%2: order=list(reversed(order))
  for variant in order:
   records.append(native_one(name,variant,config,rep))
   (JOB/'qa/native/fixed_dt_results.json').write_text(json.dumps(records,indent=2))
 print('FIXED_DT PASS',len(records),flush=True)
