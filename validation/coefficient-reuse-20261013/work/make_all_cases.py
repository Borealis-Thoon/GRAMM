from fidelity_suite import CASES,JOB
import json
cases=dict(CASES)
cases['k_epsilon_4t']=dict(nx=48,ny=36,nz=24,dx=250,sc=2,wind=2,duration=600,threads=4,turbulence=True)
(JOB/'qa/fidelity/all_cases.json').write_text(json.dumps(cases,indent=2))
print('CASE_PLAN',len(cases))
