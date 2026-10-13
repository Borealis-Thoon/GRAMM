from fidelity_suite import *
CASES['k_epsilon_4t']=dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True)
summary=[]
for name,config in CASES.items():
 base=json.loads((JOB/'runs'/('fidelity_'+name)/'baseline/result.json').read_text())
 result=run_instrumented('fidelity_'+name,'scalar_tdma',config)
 comp=compare(base,result);comp.update(case=name,variant='scalar_tdma');summary.append(comp)
 (JOB/'qa/fidelity/scalar_tdma.json').write_text(json.dumps(summary,indent=2))
 if comp['status']!='pass':raise RuntimeError('Scalar fidelity failed: '+name)
print('SCALAR FIDELITY PASS',len(summary),flush=True)
