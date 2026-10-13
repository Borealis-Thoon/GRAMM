from full_tests import *
from fidelity_suite import compare
config=dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True)
a=run_instrumented('fidelity_k_epsilon_4t','baseline',config)
summary=[]
for v in ['pressure','tdma','radiation']:
 b=run_instrumented('fidelity_k_epsilon_4t',v,config);c=compare(a,b);c.update(case='k_epsilon_4t',variant=v);summary.append(c)
 if c['status']!='pass':raise RuntimeError(c)
(JOB/'qa/fidelity/k_epsilon.json').write_text(json.dumps(summary,indent=2))
print('K_EPSILON PASS')
