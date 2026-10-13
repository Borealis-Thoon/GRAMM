"""Build and run the published GRAMM checks in a separate prepared work directory."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

VARIANTS=['baseline','scalar_tdma','radiation_column','uvw_sources','combined']

def run(command,root,env,log_name,timeout=3600):
    with (root/'logs'/log_name).open('wb') as stream:
        result=subprocess.run(command,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed; inspect logs/'+log_name)
    print('[PASS] '+log_name,flush=True)

def component_checks(root,dotnet,env):
    q=root/'qa/uvw_sources'
    for label,source in [('baseline','warnings'),('patched','uvw_sources')]:
        project=q/(label+'.csproj')
        text='<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><AllowUnsafeBlocks>true</AllowUnsafeBlocks><Optimize>true</Optimize><StartupObject>GRAMM_2001.HalfCellMethodCheck</StartupObject><EnableDefaultCompileItems>false</EnableDefaultCompileItems><TreatWarningsAsErrors>true</TreatWarningsAsErrors><TieredCompilation>true</TieredCompilation><TieredCompilationQuickJit>false</TieredCompilationQuickJit><TieredPGO>true</TieredPGO></PropertyGroup><ItemGroup><Compile Include="'+str(root/'work'/source/'src/*.cs')+'"/><Compile Include="'+str(q/'HalfCellMethodCheck.cs')+'"/></ItemGroup></Project>'
        project.write_text(text,encoding='utf-8')
        run([dotnet,'build',str(project),'-c','Release','-p:TreatWarningsAsErrors=true',
             '-p:BaseIntermediateOutputPath='+str(q/('obj_'+label))+os.sep,'-o',str(q/('bin_'+label)),'--nologo'],root,env,'component_uvw_'+label+'_build.log',180)
        run([dotnet,str(q/('bin_'+label)/(label+'.dll')),str(q/('output_'+label)),label],root,env,'component_uvw_'+label+'_run.log',300)
    a=json.loads((q/'output_baseline/cases.json').read_text());b=json.loads((q/'output_patched/cases.json').read_text())
    fields=['id','state_sha256','state_values','consumed_source_sha256','consumed_source_values']
    if len(a)!=720 or len(b)!=720:
        raise RuntimeError('Unexpected UVW method case count')
    failures=[x['id'] for x,y in zip(a,b) if any(x[k]!=y[k]for k in fields)]
    summary={'status':'fail' if failures else 'pass','cases':len(a),'failed_cases':failures,
             'bit_identical_state_values':sum(x['state_values']for x in a),
             'bit_identical_consumed_source_values':sum(x['consumed_source_values']for x in a),
             'unused_values_untouched':sum(x['untouched_source_values']for x in b)}
    (q/'component_results.json').write_text(json.dumps(summary,indent=2)+'\n')
    if failures: raise RuntimeError('UVW method comparisons differ')
    r=root/'qa/radiation_column';h=r/'harness'
    run([sys.executable,str(r/'prepare_harness.py'),'--baseline',str(root/'work/warnings'),
         '--candidate',str(root/'work/radiation_column'),'--output',str(h)],root,env,'component_radiation_prepare.log',60)
    run([dotnet,'build',str(h/'RadiationColumnCheck.csproj'),'-c','Release','-p:TreatWarningsAsErrors=true',
         '-p:BaseIntermediateOutputPath='+str(r/'obj')+os.sep,'-o',str(r/'bin'),'--nologo'],root,env,'component_radiation_build.log',180)
    run([dotnet,str(r/'bin/RadiationColumnCheck.dll'),str(r/'component_result.json')],root,env,'component_radiation_run.log',300)
    rad=json.loads((r/'component_result.json').read_text())
    if rad['status']!='pass' or rad['cases']!=135:raise RuntimeError('Radiation method check failed')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--dotnet',default=shutil.which('dotnet') or 'dotnet')
    parser.add_argument('--mode',choices=['build-native','build-instrumented','components','fidelity','native','verify-fidelity','parallel-state','smoke'],required=True)
    parser.add_argument('--variants',nargs='+',choices=VARIANTS)
    args=parser.parse_args();root=args.work_dir.resolve(strict=True)
    if not (root/'preparation.json').exists():raise RuntimeError('Run prepare_sources.py first')
    env=os.environ.copy();env['DOTNET_EXE']=args.dotnet
    env['DOTNET_CLI_HOME']=str(root/'cache/dotnet_home');env['NUGET_PACKAGES']=str(root/'cache/nuget')
    mode=args.mode
    if mode=='build-native':
        run([sys.executable,str(root/'work/build_native.py'),*(args.variants or VARIANTS)],root,env,'build_native_all.log',600)
    elif mode=='build-instrumented':
        options=[]
        for v in args.variants or VARIANTS:options+=['--variant',v]
        run([sys.executable,str(root/'qa/full_engine_harness/prepare_instrumented.py'),*options],root,env,'build_instrumented_all.log',600)
    elif mode=='components':component_checks(root,args.dotnet,env)
    elif mode=='fidelity':
        variants=args.variants or ['radiation_column','uvw_sources','scalar_tdma']
        variants=[v for v in variants if v!='baseline']
        if not variants:raise RuntimeError('Select at least one candidate')
        run([sys.executable,str(root/'work/review_suite.py'),'fidelity',*variants],root,env,'fidelity_run.log',7200)
    elif mode=='native':
        if os.name!='nt':raise RuntimeError('Native console timing uses Windows process counters')
        variants=args.variants or ['baseline','radiation_column','uvw_sources']
        if variants[0]!='baseline':raise RuntimeError('Native variants must begin with baseline')
        env['GRAMM_TEST_VARIANTS']=','.join(variants)
        run([sys.executable,str(root/'work/review_suite.py'),'native'],root,env,'native_run.log',7200)
    elif mode=='verify-fidelity':
        variants=args.variants or ['baseline','radiation_column','uvw_sources','scalar_tdma']
        run([sys.executable,str(root/'qa/test_review/validate_completed.py'),'--job',str(root),
             '--cases',str(root/'qa/fidelity/plan.json'),'--case-prefix','fidelity_','--variants',*variants],root,env,'verify_fidelity.log',300)
    elif mode=='parallel-state':
        run([sys.executable,str(root/'qa/parallel_state/run_parallel_state.py')],root,env,'parallel_state_run.log',7200)
        run([sys.executable,str(root/'qa/parallel_state/analyze_parallel_state.py'),'--job',str(root)],root,env,'parallel_state_analysis.log',600)
        run([sys.executable,str(root/'qa/parallel_state/review_outputs.py'),'--job',str(root)],root,env,'parallel_state_output_review.log',600)
    elif mode=='smoke':
        sys.path.insert(0,str(root/'work'));import full_tests
        full_tests.DOTNET=args.dotnet
        from fidelity_suite import compare
        variants=args.variants or ['baseline','radiation_column','uvw_sources','scalar_tdma','combined']
        config=dict(nx=16,ny=16,nz=12,dx=100,duration=60,sc=5,threads=1)
        baseline=full_tests.run_instrumented('reproduction_smoke_16x16','baseline',config)
        results=[]
        for v in variants:
            if v=='baseline':continue
            result=full_tests.run_instrumented('reproduction_smoke_16x16',v,config)
            record=compare(baseline,result);record['variant']=v;results.append(record)
            if record['status']!='pass':raise RuntimeError('Smoke mismatch: '+v)
        p=root/'qa/reproduction_smoke.json';p.write_text(json.dumps(results,indent=2)+'\n')
        plan=root/'qa/reproduction_smoke_plan.json'
        plan.write_text(json.dumps({'reproduction_smoke_16x16':config},indent=2)+'\n')
        run([sys.executable,str(root/'qa/test_review/validate_completed.py'),'--job',str(root),
             '--cases',str(plan),'--case-prefix','','--variants',*variants,'--expected-cases','1',
             '--expected-runs',str(len(variants)),'--expected-weather-runs',str(len(variants)),
             '--output',str(root/'qa/reproduction_smoke_strict.json')],root,env,'smoke_strict.log',180)
    print('[PASS] '+mode)

if __name__=='__main__':main()