"""Compare completed CALCPR calls. Audit timings are not performance measurements."""
from pathlib import Path
import argparse,hashlib,json
import full_tests as ft
from fidelity_suite import compare
HERE=Path(__file__).resolve().parent
ft.JOB=HERE
_original_make_case=ft.make_case
_pressure=True
def make_case(folder,**config):
 c=_original_make_case(folder,**config)
 c['pressure']=_pressure
 if not _pressure:
  path=Path(folder)/'IIN.dat';text=path.read_text();assert text.count('UVW PN T: 1111100')==1
  path.write_text(text.replace('UVW PN T: 1111100','UVW PN T: 1110100'))
 (Path(folder)/'fixture.json').write_text(json.dumps(c,indent=2)+'\n')
 return c
ft.make_case=make_case
CASES=[
 ('neutral_pressure_on',True,dict(nx=24,ny=20,nz=16,dx=100,threads=1,sc=4,wind=2,duration=120)),
 ('neutral_pressure_off',False,dict(nx=24,ny=20,nz=16,dx=100,threads=1,sc=4,wind=2,duration=120)),
 ('coast_custom_sequence',True,dict(nx=32,ny=24,nz=20,dx=250,threads=4,duration=120,coast=True,multi=True,custom=True,turbulence=True))]
def load_rows(case,v):
 p=HERE/'runs'/case/v/'pressure_lifetime.jsonl'
 rows=[json.loads(line) for line in p.read_text().splitlines()]
 for row in rows:
  assert row['icpn']==_pressure
  assert all(f['count']==f['finite'] for f in row['fields'])
  assert {f['name'] for f in row['fields']}=={'SUZ','SUXYZ','DP','DPX','DPY','DPZ','U1N','U2N','V1N','V2N','W1N','W2N'}
  expected_slots=(row['nx']+1)*(row['ny']+1)*(row['nz']+1)
  assert all(f['count']==expected_slots for f in row['fields'])
  if row['kind']=='calcpr_return':assert row['restored_values']==2*(row['nx']-2)*(row['ny']-2)*(row['nz']-1)
 return rows
def verify_instrumentation():
 checks=[]
 removed_lines=[
  '            var harnessIntegrationTimer = System.Diagnostics.Stopwatch.StartNew();',
  '            int harnessWeatherStart = IWETTER;',
  '            harnessIntegrationTimer.Stop();',
  '            HarnessTiming.Write(harnessIntegrationTimer, harnessWeatherStart, IWETTER, ITIME, DT, REALTIME, TLIMIT, computation_retry, pOptions.MaxDegreeOfParallelism);',
  '            HarnessSnapshot.Write(harnessWeatherStart, IWETTER, ITIME, REALTIME);',
  '            PressureLifetimeAudit.Write(false);',
  '            PressureLifetimeAudit.Write(true);']
 for variant in ['baseline','pressure_products']:
  manifest=json.loads((HERE/(variant+'_manifest.json')).read_text())
  for row in manifest['files']:
   generated=(HERE/'work'/('instrumented_'+variant)/row['path']).read_bytes()
   assert hashlib.sha256(generated).hexdigest()==row['instrumented_sha256']
   restored=generated
   if row['path'].endswith('.cs'):
    text=generated.decode('utf-8-sig');newline='\r\n' if '\r\n' in text else '\n'
    for old,new in [('HarnessParallel.ForEach(','Parallel.ForEach('),('HarnessParallel.For(','Parallel.For('),('HarnessConsole.SetCursorPosition(','Console.SetCursorPosition('),('HarnessConsole.CursorTop','Console.CursorTop')]:text=text.replace(old,new)
    for line in removed_lines:text=text.replace(line+newline,'')
    restored=(b'\xef\xbb\xbf' if generated.startswith(b'\xef\xbb\xbf') else b'')+text.encode('utf-8')
   assert hashlib.sha256(restored).hexdigest()==row['source_sha256'],row['path']
  checks.append(dict(variant=variant,source_commit=manifest['source_commit'],tracked_files_verified=len(manifest['files']),reversing_only_declared_hooks_restores_all_source=True))
 return checks
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--analyze-only',action='store_true');args=parser.parse_args()
 HERE=args.output.resolve();ft.JOB=HERE
 results=[]
 for case,on,config in CASES:
  _pressure=on
  saved={}
  for variant in ['baseline','pressure_products']:
   path=HERE/'runs'/case/variant/'result.json'
   if args.analyze_only and not path.exists():raise FileNotFoundError(path)
   saved[variant]=json.loads(path.read_text()) if path.exists() else ft.run_instrumented(case,variant,config,serial=True,snapshot=True)
  base=saved['baseline'];patch=saved['pressure_products']
  a=load_rows(case,'baseline');b=load_rows(case,'pressure_products')
  assert a==b,'Returned state differs: '+case
  returns=[r for r in a if r['kind']=='calcpr_return'];ends=[r for r in a if r['kind']=='weather_end']
  assert len(ends)==base['config']['situations']
  if on:
   for end in ends:assert len([r for r in returns if r['weather']==end['weather']])>=3
  else:assert not returns and all(r['calls']==0 for r in ends)
  fidelity=compare(base,patch);assert fidelity['status']=='pass'
  row=dict(case=case,status='pass',pressure=on,weather_count=len(ends),completed_calls=len(returns),audit_records=len(a),raw_restoration_values_per_variant=sum(r['restored_values'] for r in returns),float_divergence_values_compared=sum(f['count'] for r in a for f in r['fields'] if f['name'] in ['SUZ','SUXYZ']),all_field_values_compared=sum(f['count'] for r in a for f in r['fields']),return_and_weather_rows_exact=True,full_model=fidelity)
  results.append(row)
  (HERE/'result.json').write_text(json.dumps(dict(status='in_progress',cases=results),indent=2)+'\n')
  print('[COMPARE]',case,'calls',len(returns),'exact',True,flush=True)
 final=dict(status='pass',scope='Audit-only fixed-order model execution; no performance claim',variants=['baseline','pressure_products'],cases=results,model_runs=2*len(CASES),completed_call_pairs=sum(r['completed_calls'] for r in results),audit_record_pairs=sum(r['audit_records'] for r in results),raw_restoration_values_per_variant=sum(r['raw_restoration_values_per_variant'] for r in results),float_divergence_values_compared=sum(r['float_divergence_values_compared'] for r in results),all_field_values_compared=sum(r['all_field_values_compared'] for r in results),source_mutations=False)
 final['instrumentation_integrity']=verify_instrumentation()
 recorded=json.loads((Path(__file__).resolve().parent/'recorded/result.json').read_text())
 for key in ['cases','model_runs','completed_call_pairs','audit_record_pairs','raw_restoration_values_per_variant','float_divergence_values_compared','all_field_values_compared']:assert final[key]==recorded[key], 'Recorded result differs: '+key
 final['matches_recorded_results']=True
 (HERE/'result.json').write_text(json.dumps(final,indent=2)+'\n')
 print('[PASS] pressure lifetime',final['completed_call_pairs'],'calls',flush=True)
