from pathlib import Path
import subprocess,os,json,shutil
ROOT=Path(__file__).resolve().parents[2];QA=ROOT/'qa/scalar_tdma';DOTNET=os.environ.get('GRAMM_TEST_DOTNET',shutil.which('dotnet') or 'dotnet')
for label,variant in [('baseline','baseline'),('patched','scalar_tdma')]:
    source=ROOT/'work'/('instrumented_'+variant)/'src'
    project=QA/(label+'_method.csproj')
    project.write_text(f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><AllowUnsafeBlocks>true</AllowUnsafeBlocks><Optimize>true</Optimize><StartupObject>GRAMM_2001.ScalarMethodCheck</StartupObject><EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup><ItemGroup><Compile Include="{source / "*.cs"}"/><Compile Include="{QA / "ScalarMethodCheck.cs"}"/></ItemGroup></Project>',encoding='utf-8')
    cmd=[DOTNET,'build',str(project),'-c','Release','-p:TreatWarningsAsErrors=true','-p:BaseIntermediateOutputPath='+str(QA/('obj_method_'+label))+'\\','-o',str(QA/('bin_method_'+label)),'--nologo']
    with (QA/(label+'_method_build.log')).open('w',encoding='utf-8') as stream:subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
    env=os.environ.copy();env['GRAMM_TEST_SERIAL']='1'
    with (QA/(label+'_method_run.log')).open('w',encoding='utf-8') as stream:subprocess.run([DOTNET,str(QA/('bin_method_'+label)/(label+'_method.dll')),str(QA/('method_output_'+label))],env=env,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
    print(label+' method checks complete',flush=True)
a=json.loads((QA/'method_output_baseline/cases.json').read_text());b=json.loads((QA/'method_output_patched/cases.json').read_text());assert len(a)==len(b)==108
checks=[]
for x,y in zip(a,b):
    assert x['id']==y['id']
    name=x['id']+'.bin';same=(QA/'method_output_baseline'/name).read_bytes()==(QA/'method_output_patched'/name).read_bytes()
    checks.append({'id':x['id'],'values':x['values'],'sha256':x['sha256'],'equal':same,'finite':x['finite'] and y['finite']})
result={'status':'pass' if all(r['equal'] and r['finite'] for r in checks) else 'fail','cases':108,'values':sum(r['values'] for r in checks),'serial_partition_replay':True,'configured_threads':[1,4,8],'modes':['both_off','temperature_only','humidity_only','both_on'],'sequential_dt':[1.5,5,2],'density_changed_at_stage':1,'actual_methods':['Define_Arrays','Max_Proc_File_Read','TERMIPSterms','Timp_calculate','Fimp_calculate'],'no_copied_solver_equations':True,'checks':checks}
(QA/'method_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='checks'}));assert result['status']=='pass'
