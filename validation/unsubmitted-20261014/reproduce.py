"""Restore and verify independent GRAMM comparisons in a new workspace."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
NAMES=['baseline','surface_radiation','store_height','terminal_diagnostics']
EXTRAS=['pressure_products','combined','pressure_recurrence','selected_combined']
HERE=Path(__file__).resolve().parent

def run(args):subprocess.run([str(x) for x in args],check=True,timeout=150)
def normalized_hash(path):return hashlib.sha256(path.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode()).hexdigest()
def restore_extra(work,variant):
 lock=json.loads((HERE/'full_model/additional_source_lock.json').read_text())[variant]
 dst=work/('gramm_'+variant)
 shutil.copytree(work/lock['parent'],dst,ignore=shutil.ignore_patterns('.git','bin','obj'))
 patch=HERE/lock['patch']
 if variant=='pressure_products':
  source_lock=json.loads((HERE/lock['source_lock']).read_text())
  files=source_lock['source_hashes']['candidate'];commit=source_lock['candidate']
  for name,expected in source_lock['source_hashes']['baseline'].items():
   if normalized_hash(dst/name)!=expected:raise ValueError('Baseline source hash mismatch: '+name)
 else:
  files=lock['files'];commit=lock['source_commit']
  if hashlib.sha256(patch.read_bytes()).hexdigest()!=lock['patch_sha256']:raise ValueError('Additional patch hash mismatch: '+variant)
 subprocess.run(['git','apply','--whitespace=error',str(patch)],cwd=dst,check=True,timeout=150)
 for name,expected in files.items():
  if normalized_hash(dst/name)!=expected:raise ValueError('Restored source hash mismatch: '+variant+'/'+name)
 print('RESTORED',variant,commit)
 return dict(variant=variant,source_commit=commit,verified_files=files)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--repo',required=True,type=Path,help='Local GRAMM repository containing upstream V2701 commit 03224ce9')
 p.add_argument('--workspace',required=True,type=Path)
 p.add_argument('--phase',choices=['prepare','build','fidelity','native'],required=True)
 p.add_argument('--extra-variants',nargs='+',choices=EXTRAS,default=[],help='Optional source copies to restore in prepare')
 p.add_argument('--variants',nargs='+',choices=NAMES+EXTRAS,default=NAMES,help='Variants to build or compare; defaults to the original four')
 p.add_argument('--cases',nargs='+');p.add_argument('--reps',default=5,type=int)
 a=p.parse_args();w=a.workspace.resolve();target=w/'gramm_validation'
 if len(set(a.extra_variants))!=len(a.extra_variants) or len(set(a.variants))!=len(a.variants):p.error('Variants must be unique')
 if a.phase in ['fidelity','native'] and (len(a.variants)<2 or a.variants[0]!='baseline'):p.error('Comparisons require baseline first and at least one candidate')
 if a.phase=='prepare':
  if w.exists() and any(w.iterdir()):raise SystemExit('Use a new, empty workspace.')
  w.mkdir(parents=True,exist_ok=True)
  shutil.copytree(HERE/'full_model',target)
  run([sys.executable,'-B',HERE/'components/prepare_sources.py','--repository',a.repo.resolve(),'--output',w/'work'])
  restored=[restore_extra(w/'work',v) for v in a.extra_variants]
  (w/'additional_sources.json').write_text(json.dumps(restored,indent=2)+'\n')
  for v in NAMES+a.extra_variants:
   dst=w/'work'/('gramm_'+v)
   run(['git','-C',dst,'init'])
   (dst/'.gitignore').write_text('src/bin/\nsrc/obj/\n')
   run(['git','-C',dst,'add','src','.gitignore'])
   run(['git','-C',dst,'-c','user.name=Validation','-c','user.email=validation@example.invalid','commit','-m','Restore verified '+v+' source'])
  print('PREPARED',w);return
 if not target.exists():raise SystemExit('Run prepare first.')
 for v in a.variants:
  if not (w/'work'/('gramm_'+v)/'src/GRAMM.csproj').is_file():raise SystemExit('Variant was not restored in prepare: '+v)
 if a.phase=='build':
  run([sys.executable,'-B',target/'work/candidate_suite.py','build','--variants',*a.variants])
  command=[sys.executable,'-B',target/'qa/full_engine_harness/prepare_instrumented.py']
  for v in a.variants:command+=['--variant',v]
  subprocess.run([str(x) for x in command],check=True)
 else:
  command=[sys.executable,'-B',target/'work/candidate_suite.py',a.phase,'--variants',*a.variants]
  if a.cases:command+=['--cases',*a.cases]
  if a.phase=='native':command+=['--reps',str(a.reps)]
  subprocess.run([str(x) for x in command],check=True)
  if a.phase=='fidelity':
   run([sys.executable,'-B',target/'qa/test_review/validate_completed.py','--job',target,
        '--cases',target/'qa/fidelity/plan.json','--variants',*a.variants])
if __name__=='__main__':main()
