"""Verify the published file inventory without building or running GRAMM."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'file_manifest.json').read_text(encoding='utf-8'))
errors=[]
for row in manifest['files']:
    path=ROOT/row['path']
    if not path.is_file():errors.append('Missing '+row['path']);continue
    data=path.read_bytes()
    if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:errors.append('Changed '+row['path'])
listed={row['path'] for row in manifest['files']}|{'file_manifest.json'}
extra=[p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in listed]
result={'status':'pass' if not errors and not extra else 'fail','checked_files':len(manifest['files']),'errors':errors,'extra_files':extra}
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='pass' else 1)
