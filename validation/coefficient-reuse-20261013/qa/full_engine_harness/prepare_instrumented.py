"""Create identical test-only adapters around four committed GRAMM source snapshots.

No model run is performed. The upstream input duration and output path are preserved.
Serial mode is solely for strict numerical comparison and is not a performance claim.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, sys, os, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DOTNET=Path(os.environ.get('GRAMM_TEST_DOTNET',shutil.which('dotnet') or 'dotnet'))
VARIANTS={'baseline':'warnings','pressure':'pressure','tdma':'tdma','radiation':'radiation'}

def digest(data): return hashlib.sha256(data).hexdigest()

def prepare_and_build(variant):
    source=ROOT/'work'/VARIANTS[variant]
    target=ROOT/'work'/('instrumented_'+variant)
    target.mkdir(parents=True,exist_ok=True)
    status=subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
    if status: raise RuntimeError(f'Source must be committed before snapshot: {source}: {status}')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    tracked=subprocess.check_output(['git','ls-files','src'],cwd=source,text=True).splitlines()
    records=[]; counts={'parallel_for':0,'parallel_foreach':0,'console_top':0,'console_set':0,'timing_loop':0}
    for name in tracked:
        original=(source/name).read_bytes(); transformed=original
        if name.endswith('.cs'):
            text=original.decode('utf-8-sig'); bom=original.startswith(b'\xef\xbb\xbf')
            # Same replacement on all four snapshots, including commented calls.
            for old,new,key in [('Parallel.ForEach(', 'HarnessParallel.ForEach(', 'parallel_foreach'),
                                ('Parallel.For(', 'HarnessParallel.For(', 'parallel_for'),
                                ('Console.SetCursorPosition(', 'HarnessConsole.SetCursorPosition(', 'console_set'),
                                ('Console.CursorTop', 'HarnessConsole.CursorTop', 'console_top')]:
                counts[key]+=text.count(old); text=text.replace(old,new)
            if name=='src/Program.cs':
                newline='\r\n' if '\r\n' in text else '\n'
                before='            while (REALTIME < TLIMIT)'
                after='            computation_retry = 0; // reset compuation retry counter'
                if text.count(before)!=1 or text.count(after)!=1: raise RuntimeError('Integration-loop anchors changed')
                text=text.replace(before,
                    '            var harnessIntegrationTimer = System.Diagnostics.Stopwatch.StartNew();'+newline+
                    '            int harnessWeatherStart = IWETTER;'+newline+before,1)
                text=text.replace(after,
                    '            harnessIntegrationTimer.Stop();'+newline+
                    '            HarnessTiming.Write(harnessIntegrationTimer, harnessWeatherStart, IWETTER, ITIME, DT, REALTIME, TLIMIT, computation_retry, pOptions.MaxDegreeOfParallelism);'+newline+
                    '            HarnessSnapshot.Write(harnessWeatherStart, IWETTER, ITIME, REALTIME);'+newline+newline+after,1)
                counts['timing_loop']=1
            transformed=(b'\xef\xbb\xbf' if bom else b'')+text.encode('utf-8')
        destination=target/name; destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(transformed)
        records.append({'path':name,'source_sha256':digest(original),'instrumented_sha256':digest(transformed),'modified':original!=transformed})
    support=(HERE/'HarnessSupport.cs').read_bytes()
    (target/'src/HarnessSupport.cs').write_bytes(support)
    output=ROOT/'build'/('instrumented_'+variant)
    obj=ROOT/'build'/('instrumented_'+variant+'_obj')
    cmd=[str(DOTNET),'build',str(target/'src/GRAMM.csproj'),'-c','Release','-p:TreatWarningsAsErrors=true',
         '-p:BaseIntermediateOutputPath='+str(obj)+'\\','-o',str(output),'--nologo']
    process=subprocess.run(cmd,cwd=target,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120,encoding='utf-8',errors='replace')
    (HERE/(variant+'_build.log')).write_text(process.stdout,encoding='utf-8')
    result={'variant':variant,'source_commit':commit,'source_path':str(source),'instrumented_path':str(target),'build_command':cmd,
            'build_exit_code':process.returncode,'support_sha256':digest(support),'replacement_counts':counts,'files':records,
            'integration_csv':'harness_integration.csv','snapshot_json':'harness_snapshot_{weather_start:05d}.json','snapshot_enable':'GRAMM_TEST_SNAPSHOT=1','binary_enable':'GRAMM_TEST_BINARY=1','models_run':False}
    (HERE/(variant+'_manifest.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f'{variant}: build_exit={process.returncode} commit={commit}',flush=True)
    if process.returncode: print(process.stdout);raise SystemExit(process.returncode)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=list(VARIANTS),action='append');args=ap.parse_args()
    all_results=[prepare_and_build(v) for v in args.variant or VARIANTS]
    (HERE/'build_summary.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='files'} for r in all_results],indent=2)+'\n',encoding='utf-8')
