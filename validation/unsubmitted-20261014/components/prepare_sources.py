from pathlib import Path
import argparse,hashlib,io,json,subprocess,tarfile
ap=argparse.ArgumentParser(description='Restore four independent GRAMM source variants from a local upstream clone.')
ap.add_argument('--repository',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();bundle=Path(__file__).resolve().parent
lock=json.loads((bundle/'source_lock.json').read_text())
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
archive=subprocess.check_output(['git','-C',str(a.repository.resolve()),'archive',lock['upstream_base'],'src'])
for folder,entry in lock['sources'].items():
 dst=out/folder;dst.mkdir()
 with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(dst,filter='data')
 patches=['warning_cleanup.patch']+([entry['patch']] if entry['patch'] else [])
 for patch in patches:
  subprocess.run(['git','apply','--whitespace=error',str(bundle/'patches'/patch)],cwd=dst,check=True)
 for name,expected in entry['files'].items():
  raw=(dst/name).read_text(encoding='utf-8-sig').replace('\r\n','\n').encode('utf-8')
  if hashlib.sha256(raw).hexdigest()!=expected['utf8_lf_sha256']:raise ValueError(f'Source hash mismatch: {folder}/{name}')
 print('[OK]',folder)
