"""Restore locked GRAMM sources and install the validation scripts into a new folder."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tarfile

BUNDLE = Path(__file__).resolve().parent
NAMES = {'baseline':'warnings', 'scalar_tdma':'scalar_tdma',
         'radiation_column':'radiation_column', 'uvw_sources':'uvw_sources', 'combined':'combined'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def command(args, cwd=None):
    # Preserve repository blob bytes regardless of the caller's checkout settings.
    if args and args[0]=='git': args=['git','-c','core.autocrlf=false','-c','core.eol=lf',*args[1:]]
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT)

def verify_sources(root, lock):
    checked = 0
    for variant, record in lock['variants'].items():
        folder = root/'work'/NAMES[variant]
        actual = {p.relative_to(folder).as_posix() for p in (folder/'src').rglob('*') if p.is_file()}
        if actual != set(record['files']):
            raise RuntimeError('Source file list differs: '+variant)
        for name, expected in record['files'].items():
            if digest((folder/name).read_bytes()) != expected:
                raise RuntimeError('Source hash differs: '+variant+'/'+name)
            checked += 1
    return checked

def restore_archive(data, folder):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        for member in archive:
            target = folder/member.name
            if not target.resolve().is_relative_to(folder.resolve()) or member.issym() or member.islnk():
                raise RuntimeError('Unexpected archive path or link: '+member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
            else:
                raise RuntimeError('Unexpected archive entry: '+member.name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--upstream-checkout', type=Path,
                        help='A local clone of the upstream GRAMM repository containing the locked commit')
    parser.add_argument('--work-dir', type=Path, required=True,
                        help='A new empty directory for restored sources, builds and model outputs')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    root = args.work_dir.resolve()
    lock = json.loads((BUNDLE/'source_lock.json').read_text())
    for name, expected in lock['patch_sha256'].items():
        if digest((BUNDLE/'patches'/name).read_bytes()) != expected:
            raise RuntimeError('Patch hash differs: '+name)
    if args.verify_only:
        count = verify_sources(root, lock)
        print(json.dumps({'status':'pass','source_files_checked':count}))
        return
    if args.upstream_checkout is None:
        parser.error('--upstream-checkout is required when preparing sources')
    if root.exists() and any(root.iterdir()):
        raise RuntimeError('Use a new empty work directory: '+str(root))
    upstream = args.upstream_checkout.resolve(strict=True)
    resolved = command(['git','rev-parse',lock['upstream_commit']+'^{commit}'],upstream).decode().strip()
    if resolved != lock['upstream_commit']:
        raise RuntimeError('Upstream revision differs')
    archive = command(['git','archive','--format=tar',lock['upstream_commit'],'src'],upstream)
    root.mkdir(parents=True,exist_ok=True)
    for variant, record in lock['variants'].items():
        folder = root/'work'/NAMES[variant]
        folder.mkdir(parents=True)
        restore_archive(archive, folder)
        command(['git','init','--quiet'],folder)
        for patch in record['patches']:
            patch_path = str(BUNDLE/'patches'/patch)
            command(['git','apply','--check',patch_path],folder)
            command(['git','apply',patch_path],folder)
        (folder/'source_receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    count = verify_sources(root, lock)
    shutil.copytree(BUNDLE/'support', root, dirs_exist_ok=True)
    for name in ['build','logs','tests','runs','cache','tmp']:
        (root/name).mkdir(exist_ok=True)
    (root/'source_lock.json').write_bytes((BUNDLE/'source_lock.json').read_bytes())
    (root/'preparation.json').write_text(json.dumps({'status':'pass','upstream_commit':resolved,
        'source_files_checked':count,'variants':list(lock['variants']),'models_run':False},indent=2)+'\n')
    print(json.dumps({'status':'pass','source_files_checked':count,'variants':list(lock['variants'])}))

if __name__ == '__main__':
    main()