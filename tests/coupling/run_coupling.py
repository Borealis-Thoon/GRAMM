from pathlib import Path
import argparse,array,csv,hashlib,json,math,os,re,shutil,struct,subprocess,time,zipfile,sys
parser=argparse.ArgumentParser()
parser.add_argument('--job-root',type=Path,default=Path(__file__).resolve().parents[2])
parser.add_argument('--native-root',type=Path,required=True)
parser.add_argument('--gral-dll',type=Path,required=True)
parser.add_argument('--pilot',action='store_true')
args=parser.parse_args()
ROOT=args.job_root;OLD=args.native_root;DLL=args.gral_dll
TEMPLATE=Path(__file__).with_name('template')
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def zipdata(p):
 with zipfile.ZipFile(p) as z:return {n.split('.')[-1]:z.read(n) for n in z.namelist()}
def configure(case,variant,tag=''):
 native=OLD/case['native'];a=zipdata(native/'baseline/00001.scl');b=zipdata(native/'candidate/00001.scl')
 selected={**a,'scl':b['scl'] if variant=='B' else a['scl']}
 d=ROOT/'runs/coupling'/f"{case['id']}_{variant}{tag}";d.mkdir(parents=True,exist_ok=False)
 for n in ('ggeom.asc','GRAMM.geb','landuse.asc'):shutil.copy2(native/'baseline'/n,d/n)
 (d/'micro_vert_layers.txt').write_bytes((TEMPLATE/'micro_vert_layers.txt').read_bytes())
 lines=(TEMPLATE/'in.dat').read_text().splitlines();lines[0]=str(case['rate']);lines[1]='300';lines[2]='1';lines[4]='1';lines[5]='0.1';lines[9]='2 10 30';lines[12]='0';lines[-1]='1';(d/'in.dat').write_text('\n'.join(lines)+'\n')
 dx=case['dx'];(d/'GRAL.geb').write_text('\n'.join(map(str,[100,100,'2,1.1',4000//dx,3000//dx,3,'1,2,3,4',1000,5000,1000,4000]))+'\n')
 (d/'Max_Proc.txt').write_text('1\n');met=(native/'baseline/meteopgt.all').read_text().splitlines();(d/'meteopgt.all').write_text('\n'.join(met[:2]+[met[2]]*case['situations'])+'\n')
 for s in range(1,case['situations']+1):
  shutil.copy2(native/'baseline/00001.wnd',d/f'{s:05}.wnd')
  with zipfile.ZipFile(d/f'{s:05}.scl','w',zipfile.ZIP_DEFLATED) as z:
   for suffix,raw in selected.items():z.writestr(f'{s:05}.{suffix}',raw)
 (d/'point.dat').write_text('header\nheader\n'+'\n'.join(','.join(map(str,[x,2500,h,1,0,0,0,1,1,293,sg])) for sg,(x,h) in enumerate([(2000,2),(2000,20),(4000,2),(4000,20)],1))+'\n')
 (d/'Receptor.dat').write_text('4\n1,2000,2500,2,water2\n2,2000,2500,20,water20\n3,4000,2500,2,land2\n4,4000,2500,20,land20\n')
 manifest={p.name:dict(size=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(d.iterdir()) if p.is_file()};save(d/'input_manifest.json',manifest)
 save(ROOT/'inputs/coupling'/f"{case['id']}_{variant}{tag}.json",dict(case=case,variant=variant,inputs=manifest,scl_payload_hashes={k:sha(v) for k,v in selected.items()}))
 return d

def output(d,case):
 result={}
 for p in sorted(d.glob('*.grz')):
  with zipfile.ZipFile(p) as z:
   for name in z.namelist():
    if not name.endswith('.con'):continue
    raw=z.read(name);header=struct.unpack_from('<iiiffii',raw);h,x,y,dx,dy,nx,ny=header
    assert h==-3 and nx==4000//case['dx'] and ny==3000//case['dx'] and dx==dy==case['dx'],header
    values=array.array('f');values.frombytes(raw[28:]);assert len(values)==nx*ny and all(math.isfinite(v) and v>=0 for v in values)
    total=sum(values);cx=sum(v*(1000+(i//ny+.5)*dx) for i,v in enumerate(values))/total if total else None;cy=sum(v*(1000+(i%ny+.5)*dy) for i,v in enumerate(values))/total if total else None
    fielddir=ROOT/'qa/coupling/fields'/d.name;fielddir.mkdir(parents=True,exist_ok=True)
    with (fielddir/(Path(name).stem+'.csv')).open('w',newline='') as f:
     w=csv.writer(f);w.writerow(['x_m','y_m','C_ug_m3']);w.writerows((1000+(i//ny+.5)*dx,1000+(i%ny+.5)*dy,v) for i,v in enumerate(values))
    result[p.name+':'+name]=dict(header=list(header),payload_sha256=sha(raw),maximum=max(values),spatial_integral=total*dx*dy,nonzero=sum(v>0 for v in values),centroid_x=cx,centroid_y=cy)
 assert len(result)==12*case['situations'],(len(result),12*case['situations'])
 assert sum(x['nonzero'] for x in result.values())>0
 return result

def run(d,case):
 start=time.monotonic()
 with (d/'console.log').open('wb') as out,(d/'stderr.log').open('wb') as err:
  p=subprocess.Popen(['dotnet',str(DLL),str(d)],cwd=d,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
  try:code=p.wait(timeout=120)
  except subprocess.TimeoutExpired:p.kill();p.wait();raise
 text=(d/'console.log').read_text(errors='replace');assert code==0,(code,text[-2000:]);assert 'Reading GRAMM stability classes:' in text,text
 outputs=output(d,case)
 assert text.count('Writing result files in a background thread')==case['situations'] and 'Process exit called' in text
 result=dict(directory=str(d),exit_code=code,wall_s=time.monotonic()-start,console_sha256=sha((d/'console.log').read_bytes()),outputs=outputs,particle_lines=[line for line in text.splitlines() if 'particle' in line.lower()],completion_tail=text[-1200:]);save(d/'result.json',result);print(d.name,round(result['wall_s'],2),len(outputs),flush=True);return result

def compare(a,b):
 rows=[]
 for n,av in a['outputs'].items():
  bv=b['outputs'][n];rows.append(dict(output=n,identical=av['payload_sha256']==bv['payload_sha256'],base_max=av['maximum'],candidate_max=bv['maximum'],max_pct=(bv['maximum']/av['maximum']-1)*100 if av['maximum'] else None,base_integral=av['spatial_integral'],candidate_integral=bv['spatial_integral'],integral_pct=(bv['spatial_integral']/av['spatial_integral']-1)*100 if av['spatial_integral'] else None))
 return rows

def main():
 cases=[dict(id='cool_main',native='cool_day_24x20x16_250m_t1',dx=100,rate=1000,situations=3),dict(id='cool_dx50',native='cool_day_24x20x16_250m_t1',dx=50,rate=1000,situations=1),dict(id='cool_rate100',native='cool_day_24x20x16_250m_t1',dx=100,rate=100,situations=1),dict(id='warm_control',native='warm_day_24x20x16_250m_t8',dx=100,rate=1000,situations=1),dict(id='neutral_control',native='strong_neutral_24x20x16_250m_t8',dx=100,rate=1000,situations=1),dict(id='land_control',native='land_day_24x20x16_250m_t2',dx=100,rate=1000,situations=1)]
 if args.pilot:cases=cases[:1]
 summary=dict(gral_dll_sha256=sha(DLL.read_bytes()),cases=[],comparisons={})
 for c in cases:
  results={v:run(configure(c,v),c) for v in ('A','B')}
  summary['cases'].append(dict(case=c,results=results));summary['comparisons'][c['id']]=compare(results['A'],results['B']);save(ROOT/'qa/coupling/summary.json',summary)
  if c['id']=='cool_main':
   repeat=run(configure(c,'A','_repeat'),c);repeat_compare=compare(results['A'],repeat);assert all(row['identical'] for row in repeat_compare);save(ROOT/'qa/coupling/repeat.json',dict(result=repeat,comparison=repeat_compare))
 save(ROOT/'qa/coupling/summary.json',summary)
if __name__=='__main__':main()

