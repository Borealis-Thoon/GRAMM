"""Reproduce pressure-source product checks from a pinned local GRAMM checkout."""
from pathlib import Path
import argparse, hashlib, io, json, shutil, subprocess, sys, zipfile


def invoke(command, *, cwd=None):
    result=subprocess.run(command,cwd=cwd,text=True,encoding='utf-8',capture_output=True)
    text=result.stdout+result.stderr
    if result.returncode:
        sys.stderr.write(text)
        raise RuntimeError(f'Command failed with exit code {result.returncode}: {command[0]}')
    return text


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True,help='Local Git checkout containing the pinned baseline commit.')
    parser.add_argument('--output',type=Path,required=True,help='New or empty directory for source copies, builds and results.')
    parser.add_argument('--dotnet',default='dotnet')
    args=parser.parse_args()
    source=args.source_root.resolve()
    out=args.output.resolve()
    evidence=Path(__file__).resolve().parent
    if out.exists() and any(out.iterdir()):
        parser.error('--output must be a new or empty directory')
    out.mkdir(parents=True,exist_ok=True)
    lock=json.loads((evidence/'source_lock.json').read_text(encoding='utf-8'))
    invoke(['git','-C',str(source),'cat-file','-e',lock['baseline']+'^{commit}'])
    archive=subprocess.check_output(['git','-C',str(source),'archive','--format=zip',lock['baseline'],'src'])
    baseline=out/'baseline'
    baseline.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for entry in z.infolist():
            path=Path(entry.filename)
            if path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Unexpected archive path')
        z.extractall(baseline)
    candidate=out/'candidate'
    shutil.copytree(baseline,candidate)
    invoke(['git','apply','--check',str(evidence/lock['patch'])],cwd=candidate)
    invoke(['git','apply',str(evidence/lock['patch'])],cwd=candidate)
    verified=[]
    for label,root in [('baseline',baseline),('candidate',candidate)]:
        for relative,expected in lock['source_hashes'][label].items():
            value=hashlib.sha256((root/relative).read_text(encoding='utf-8-sig').encode()).hexdigest()
            if value!=expected:
                raise RuntimeError('Source hash mismatch: '+label+'/'+relative)
            verified.append({'variant':label,'file':relative,'sha256':value})
    logs=out/'logs';logs.mkdir()
    def clean(text):
        for path,replacement in [(out,'<OUTPUT>'),(source,'<SOURCE_ROOT>'),(evidence,'<EVIDENCE>')]:
            text=text.replace(str(path),replacement).replace(path.as_posix(),replacement)
        return text
    builds=[]
    for label,root in [('baseline',baseline),('candidate',candidate)]:
        log=invoke([args.dotnet,'build',str(root/'src/GRAMM.csproj'),'-c','Release','--artifacts-path',str(out/'build'/label),'--nologo','-warnaserror'])
        (logs/(label+'_build.log')).write_text(clean(log),encoding='utf-8')
        builds.append({'variant':label,'status':'pass','warnings_as_errors':True,'log':'logs/'+label+'_build.log'})
    invoke([sys.executable,'-X','utf8','-B',str(evidence/'direct_checks.py'),'--baseline-source-root',str(baseline),'--source-root',str(candidate),'--output',str(out/'direct'),'--run','--dotnet',args.dotnet])
    for filename in ('build.log','run.log'):
        path=out/'direct'/filename
        path.write_text(clean(path.read_text(encoding='utf-8')),encoding='utf-8')
    result=json.loads((out/'direct/result.json').read_text(encoding='utf-8'))
    recorded=json.loads((evidence/'recorded/direct_result.json').read_text(encoding='utf-8'))
    if result!=recorded:
        raise RuntimeError('Direct result differs from the recorded result; inspect direct/result.json')
    extracted=json.loads((out/'direct/source_extraction.json').read_text(encoding='utf-8'))
    previous=json.loads((evidence/'recorded/source_extraction.json').read_text(encoding='utf-8'))
    if extracted['harness_sha256']!=previous['harness_sha256']:
        raise RuntimeError('Generated harness differs from the recorded source extraction')
    summary={'status':'pass','baseline':lock['baseline'],'candidate':lock['candidate'],'source_hashes_checked':verified,'engine_builds':builds,'direct_harness_build':'pass; warnings treated as errors','generated_harness_matches_recorded':True,'direct_result_matches_recorded':True,'direct_result':result,'performance_measured':False}
    (out/'reproduction.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
