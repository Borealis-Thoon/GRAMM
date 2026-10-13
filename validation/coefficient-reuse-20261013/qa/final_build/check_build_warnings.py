"""Compare pristine upstream and warning-cleanup builds with warnings as errors."""
from pathlib import Path
import collections,json,os,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2]
DOTNET=os.environ.get('GRAMM_TEST_DOTNET',shutil.which('dotnet') or 'dotnet')

def build(name,folder):
    command=[DOTNET,'build',str(ROOT/'work'/folder/'src/GRAMM.csproj'),'-c','Release','-t:Rebuild',
        '-p:TreatWarningsAsErrors=true','-p:BaseIntermediateOutputPath='+str(ROOT/'build'/('warning_check_'+name+'_obj'))+os.sep,
        '-o',str(ROOT/'build'/('warning_check_'+name)),'--nologo']
    env={**os.environ,'DOTNET_CLI_UI_LANGUAGE':'en-US'}
    process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300,env=env)
    text=process.stdout+process.stderr
    rows={}
    for match in re.finditer(r'([^\r\n]+?\.cs)\((\d+),(\d+)\): error (CS\d+): (.*?) \[.*?\]',text):
        file,line,column,code,message=match.groups()
        path=Path(file.strip()).relative_to(ROOT).as_posix()
        row=dict(file=path,line=int(line),column=int(column),code=code,message=message)
        rows[(path,int(line),int(column),code)]=row
    counts=collections.Counter(row['code'] for row in rows.values())
    warnings=re.findall(r'(\d+) Warning\(s\)',text);errors=re.findall(r'(\d+) Error\(s\)',text)
    if not warnings or not errors:raise RuntimeError('Missing compiler totals: '+name+' '+text)
    return dict(variant=name,exit_code=process.returncode,compiler_warnings=int(warnings[-1]),compiler_errors=int(errors[-1]),
        warnings_promoted_to_errors=list(rows.values()),diagnostic_codes=dict(counts),
        command=[x.replace(str(ROOT),'.').replace('\\','/') if str(ROOT) in x else 'dotnet' if x==DOTNET else x for x in command])

def main():
    before=build('upstream','upstream');after=build('cleanup','warnings')
    status='pass' if before['exit_code']!=0 and before['compiler_errors']==8 and len(before['warnings_promoted_to_errors'])==8 and after['exit_code']==0 and after['compiler_errors']==0 and after['compiler_warnings']==0 else 'fail'
    output=dict(status=status,upstream_commit='03224ce9d3490783c84a8aecd72642fe9df21242',
        cleanup_commit='4da3b7c172860e3f9369c7d2fba56b2d82ffbefb',strict=True,before=before,after=after)
    (ROOT/'qa/build_warning_comparison.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output,indent=2));return 0 if status=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
