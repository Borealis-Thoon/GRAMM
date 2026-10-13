"""Run one short completed case with the baseline and scalar candidate."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'work'))
from fidelity_suite import run_instrumented,compare
from native_benchmark import native_one,NATIVE
NATIVE['scalar_tdma']=ROOT/'build/scalar_tdma/GRAMM.dll'
CONFIG=dict(nx=24,ny=20,nz=16,dx=250,sc=2,wind=2,duration=60,dt=5,threads=1,turbulence=True,coast=True)

def main():
    first=run_instrumented('reproduction_smoke','baseline',CONFIG)
    second=run_instrumented('reproduction_smoke','scalar_tdma',CONFIG)
    exact=compare(first,second)
    native=[native_one('reproduction_smoke',v,CONFIG,0) for v in ('baseline','scalar_tdma')]
    same=native[0]['payloads']==native[1]['payloads']
    result={'status':'pass' if exact['status']=='pass' and same else 'fail',
        'config':CONFIG,'instrumented':exact,'native_payloads_identical':same,
        'native_assembly_hashes':{x['variant']:x['assembly_sha256'] for x in native},
        'model_processes':4,'watchdog_seconds':300,
        'purpose':'Reproduction smoke check; excluded from reported performance measurements.'}
    (ROOT/'qa/final_build/smoke_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
