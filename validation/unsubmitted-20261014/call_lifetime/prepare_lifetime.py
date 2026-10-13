"""Build independent audit copies; calculations remain the committed originals."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,shutil
ASSETS=Path(__file__).resolve().parent
HERE=None
DOTNET=shutil.which('dotnet') or r'C:\Program Files\dotnet\dotnet.exe'
def sha(b):return hashlib.sha256(b).hexdigest()
def prepare(source,variant):
 target=HERE/'work'/('instrumented_'+variant)
 if target.exists():raise RuntimeError('Refuse to overwrite an audit source copy')
 head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
 assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()
 names=subprocess.check_output(['git','-C',str(source),'ls-files','src'],text=True).splitlines()
 records=[]
 for name in names:
  raw=(source/name).read_bytes();data=raw
  if name.endswith('.cs'):
   text=raw.decode('utf-8-sig');newline='\r\n' if '\r\n' in text else '\n'
   for old,new in [('Parallel.ForEach(','HarnessParallel.ForEach('),('Parallel.For(','HarnessParallel.For('),('Console.SetCursorPosition(','HarnessConsole.SetCursorPosition('),('Console.CursorTop','HarnessConsole.CursorTop')]:text=text.replace(old,new)
   if name=='src/Program.cs':
    before='            while (REALTIME < TLIMIT)';after='            computation_retry = 0; // reset compuation retry counter'
    assert text.count(before)==text.count(after)==1
    text=text.replace(before,'            var harnessIntegrationTimer = System.Diagnostics.Stopwatch.StartNew();'+newline+'            int harnessWeatherStart = IWETTER;'+newline+before,1)
    text=text.replace(after,'            harnessIntegrationTimer.Stop();'+newline+'            HarnessTiming.Write(harnessIntegrationTimer, harnessWeatherStart, IWETTER, ITIME, DT, REALTIME, TLIMIT, computation_retry, pOptions.MaxDegreeOfParallelism);'+newline+'            HarnessSnapshot.Write(harnessWeatherStart, IWETTER, ITIME, REALTIME);'+newline+'            PressureLifetimeAudit.Write(false);'+newline+after,1)
   if name=='src/CALCPR.cs':
    anchor='            //5.4.2017 Ku '
    assert text.count(anchor)==1
    text=text.replace(anchor,'            PressureLifetimeAudit.Write(true);'+newline+anchor,1)
   data=(b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'')+text.encode('utf-8')
  dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
  records.append(dict(path=name,source_sha256=sha(raw),instrumented_sha256=sha(data)))
 support=(ASSETS/'HarnessSupport.cs').read_bytes();(target/'src/HarnessSupport.cs').write_bytes(support)
 original=(source/'src/CALCPR.cs').read_text(encoding='utf-8-sig')
 final=original.split('//Final computation of total mass-divergence after velocity correction')[1]
 expressions={n:re.search(r'\b'+n+r'_L\[k\]\s*=\s*(.*?);',final,re.S).group(1) for n in ['SUZ','SUXYZ']}
 audit=(ASSETS/'PressureLifetimeAudit.template.cs').read_text(encoding='utf-8-sig').replace('__EXPRESSION_Z__',expressions['SUZ']).replace('__EXPRESSION_XYZ__',expressions['SUXYZ'])
 (target/'src/PressureLifetimeAudit.cs').write_text(audit,encoding='utf-8')
 output=HERE/'build'/('instrumented_'+variant);obj=HERE/'build'/('obj_'+variant)
 cmd=[DOTNET,'build',str(target/'src/GRAMM.csproj'),'-c','Release','-p:TreatWarningsAsErrors=true','-p:BaseIntermediateOutputPath='+str(obj)+'\\','-o',str(output),'--nologo']
 p=subprocess.run(cmd,cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=120)
 (HERE/(variant+'_build.log')).write_text(p.stdout,encoding='utf-8')
 metadata=dict(variant=variant,source_commit=head,build_exit_code=p.returncode,files=records,support_sha256=sha(support),audit_sha256=sha(audit.encode()),raw_expression_source='Unmodified final CALCPR divergence expressions',calculation_edits=0)
 (HERE/(variant+'_manifest.json')).write_text(json.dumps(metadata,indent=2)+'\n')
 print('[BUILD]',variant,p.returncode,flush=True)
 if p.returncode:raise RuntimeError(p.stdout)
 return metadata
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 HERE=a.output.resolve()
 if HERE.exists() and any(HERE.iterdir()):p.error('--output must be new or empty')
 HERE.mkdir(parents=True,exist_ok=True)
 results=[prepare(a.source_root/('gramm_'+v),v) for v in ['baseline','pressure_products']]
 assert results[0]['audit_sha256']==results[1]['audit_sha256'],'Audit expressions differ'
 (HERE/'build_summary.json').write_text(json.dumps(results,indent=2)+'\n')
