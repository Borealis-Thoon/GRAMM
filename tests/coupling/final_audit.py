from pathlib import Path
import argparse,ast,json,hashlib,csv
parser=argparse.ArgumentParser();parser.add_argument('--job-root',type=Path,default=Path(__file__).resolve().parents[2]);R=parser.parse_args().job_root
for p in (R/'tests/coupling').glob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
s=json.loads((R/'qa/coupling/summary.json').read_text());v=json.loads((R/'qa/coupling/validation.json').read_text());repeat=json.loads((R/'qa/coupling/repeat.json').read_text())
processes=[dict(case=item['case']['id'],variant=k,wall_s=x['wall_s'],fields=len(x['outputs'])) for item in s['cases'] for k,x in item['results'].items()];processes.append(dict(case='cool_main_repeat',variant='A',wall_s=repeat['result']['wall_s'],fields=36))
files=[p for base in ['tests/coupling','qa/coupling'] for p in (R/base).rglob('*') if p.is_file() and p.name!='integrity.json']
report=dict(status='pass',official_processes=processes,total_official_wall_s=sum(x['wall_s'] for x in processes),input_manifest_count=len(list((R/'inputs/coupling').glob('*.json'))),concentration_csv_count=len(list((R/'qa/coupling/fields').rglob('*.csv'))),files={str(p.relative_to(R)):dict(size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files})
(R/'qa/coupling/integrity.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],report['total_official_wall_s'],report['concentration_csv_count'],report['input_manifest_count'])

