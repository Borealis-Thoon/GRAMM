import argparse,array,csv,hashlib,json,struct,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--job-root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--native-root',type=Path,required=True);args=p.parse_args();R=args.job_root;N=args.native_root
sha=lambda b:hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def payloads(p):
 with zipfile.ZipFile(p) as z:return {n.split('.')[-1]:z.read(n) for n in z.namelist()}
def vals(raw):a=array.array('h');a.frombytes(raw[20:]);return a
n=N/'cool_day_24x20x16_250m_t1';A=payloads(n/'baseline/00001.scl');B=payloads(n/'candidate/00001.scl');av,bv=vals(A['scl']),vals(B['scl']);changed=[dict(i=i//20,j=i%20,x_m=(i//20+.5)*250,y_m=(i%20+.5)*250,base=a,candidate=b) for i,(a,b) in enumerate(zip(av,bv)) if a!=b];assert len(changed)==198 and all(0<r['i']<23 and 0<r['j']<19 and r['x_m']<3000 and r['base']==2 and r['candidate']==4 for r in changed)
s=read(R/'qa/coupling/summary.json');checks=[]
for item in s['cases']:
 c=item['case'];res=item['results'];da,db=[Path(res[v]['directory']) for v in ('A','B')];ma,mb=[read(d/'input_manifest.json') for d in (da,db)];diff=[k for k in ma if ma[k]['sha256']!=mb[k]['sha256']];assert set(diff).issubset({f'{i:05}.scl' for i in range(1,c['situations']+1)}),diff
 for situation in range(1,c['situations']+1):
  pa,pb=[payloads(d/f'{situation:05}.scl') for d in (da,db)]
  assert pa['ust']==pb['ust'] and pa['obl']==pb['obl'];assert (pa['scl']==pb['scl']) if c['id'].endswith('control') else (pa['scl']!=pb['scl'])
 for v in ('A','B'):
  text=(Path(res[v]['directory'])/'console.log').read_text(errors='replace');assert f"Using a total of {c['rate']*300} particles ({c['rate']} part./s)" in text
  assert text.count('Reading GRAMM stability classes:')==c['situations'] and text.count('Writing result files in a background thread')==c['situations'] and 'Process exit called' in text
 control=c['id'].endswith('control');same=all(row['identical'] for row in s['comparisons'][c['id']]);assert same if control else not same
 checks.append(dict(case=c['id'],particle_count_per_situation=c['rate']*300,output_fields_per_variant=len(res['A']['outputs']),only_changed_inputs=diff,exact_identical= same,control=control))
rows={v:list(csv.DictReader((R/f'qa/coupling/imported_meteo_{v}.csv').open())) for v in ('A','B')};met=[]
for a,b in zip(rows['A'],rows['B']):
 assert all(a[k]==b[k] for k in ['x_m','y_m','z0_m','u_first_m_s','v_first_m_s'])
 if a['SC']!=b['SC']:met.append(dict(x_m=float(a['x_m']),y_m=float(a['y_m']),baseline_SC=int(a['SC']),candidate_SC=int(b['SC']),baseline_OL_m=float(a['OL_m']),candidate_OL_m=float(b['OL_m']),baseline_ustar_m_s=float(a['ustar_m_s']),candidate_ustar_m_s=float(b['ustar_m_s'])))
assert len(met)==198 and all(r['x_m']<3000 and r['baseline_OL_m']==-4 and r['candidate_OL_m']==1000 for r in met)
repeat=read(R/'qa/coupling/repeat.json');assert all(x['identical'] for x in repeat['comparison'])
# Three weather IDs deliberately enter the official IWET-dependent deterministic seed.
main=s['cases'][0]['results']['A']['outputs'];seeds={w:[v['payload_sha256'] for k,v in main.items() if k.startswith(f'{w:05}.grz')] for w in (1,2,3)};assert len(set(tuple(v) for v in seeds.values()))==3
report=dict(status='pass',native_changed_cells=len(changed),native_changes=changed,imported_meteo_changed_cells=len(met),imported_meteo_changes=met,cases=checks,repeat_identical_fields=len(repeat['comparison']),seed_payload_sets_distinct=True,official_gral_dll_sha256=s['gral_dll_sha256'],total_official_gral_processes=2*len(checks)+1,diagnostic_processes=2)
save(R/'qa/coupling/validation.json',report);print('PASS',len(checks),'cases',len(met),'changed cells')

