from pathlib import Path
import argparse,hashlib,json,statistics
ap=argparse.ArgumentParser();ap.add_argument('--evidence-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
manifest={r['path']:r for r in json.loads((a.evidence_root/'file_manifest.json').read_text())['files']}
paths=['qa/native/fixed_dt_results.json','qa/native/scalar_results.json','qa/figures/rendered/scalar_figure_input.json']
base='https://github.com/Borealis-Thoon/GRAMM/blob/7e95104b8c3bb9c8eecf89c8f2d93b1d7f758c51/validation/coefficient-reuse-20261013/'
raw='https://raw.githubusercontent.com/Borealis-Thoon/GRAMM/7e95104b8c3bb9c8eecf89c8f2d93b1d7f758c51/validation/coefficient-reuse-20261013/'
sources=[]
for p in paths:
 data=(a.evidence_root/p).read_bytes();digest=hashlib.sha256(data).hexdigest();assert digest==manifest[p]['sha256']
 sources.append({'path':p,'sha256':digest,'url':base+p,'raw_url':raw+p})
original=json.loads((a.evidence_root/paths[-1]).read_text())['patches']['scalar_tdma']['cases']
records=json.loads((a.evidence_root/paths[0]).read_text())+json.loads((a.evidence_root/paths[1]).read_text())
rows=[]
for case in original:
 cs=case['case'];r=[x for x in records if x['case']==cs and x['measured'] and x['variant'] in ('baseline','scalar_tdma')]
 pairs=[]
 for rep in range(1,6):
  b=next(x for x in r if x['rep']==rep and x['variant']=='baseline');p=next(x for x in r if x['rep']==rep and x['variant']=='scalar_tdma')
  pct=100*(1-p['lifetime_seconds']/b['lifetime_seconds'])
  pairs.append({'rep':rep,'baseline_seconds':b['lifetime_seconds'],'patched_seconds':p['lifetime_seconds'],'saved_percent':pct})
 vals=[r['saved_percent'] for r in pairs];med=statistics.median(vals)
 assert all(abs(x-y)<1e-10 for x,y in zip(vals,case['paired_percent']))
 assert abs(med-case['time_saved_pct'])<1e-10
 rows.append({'case':cs,'pairs':pairs,'median_saved_percent':med,'faster_pairs':sum(v>0 for v in vals),'grid':b['config']['grid'],'worker_setting':b['config']['threads']})
out={'measurement_origin':'Existing public measurements from the coefficient-reuse review; this revision changes the figure only. No new scalar benchmark is claimed.','public_evidence_commit':'7e95104b8c3bb9c8eecf89c8f2d93b1d7f758c51','source_files':sources,'validation':'Original raw paired timings match the old public figure input to 1e-10 percentage points.','rows':rows,'memory_mib':[.332,.583],'memory_note':'Stored double values for the measured grids; jagged-array overhead is additional.','method_cases':108,'finite_bitwise_values':7803432,'full_field_pairs':99}
a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print('[PASS] 20 scalar timing pairs match the public source')
