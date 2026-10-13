"""Verify every file against the finalized bundle manifest."""
from pathlib import Path
import hashlib
import json

def main():
    root=Path(__file__).resolve().parent
    manifest=root/'file_manifest.json'
    data=json.loads(manifest.read_text())
    expected={row['path']:row for row in data['files']}
    actual={p.relative_to(root).as_posix()for p in root.rglob('*')if p.is_file()and p!=manifest}
    if actual!=set(expected):raise RuntimeError('Manifest file set differs')
    for name,row in expected.items():
        raw=(root/name).read_bytes()
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise RuntimeError('Content differs: '+name)
    print(json.dumps({'status':'pass','files':len(expected),'bytes':sum(x['bytes']for x in expected.values())}))

if __name__=='__main__':main()