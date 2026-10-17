"""Portable native integration matrix for an isolated GRAMM build pair.
Outputs are synthetic; each child has a 90 s cap, matrix has a 14 min cap.
"""
from pathlib import Path
import argparse, csv, hashlib, json, math, struct, sys, time, zipfile
from collections import Counter
from fixture import make_case
from native_console_runner import run_hidden_console

def sha(b): return hashlib.sha256(b).hexdigest()
def write_json(p,o): p.write_text(json.dumps(o,indent=2),encoding='utf-8')
def unpack_grid(raw, nx,ny,nz,dx, count):
    h=struct.unpack_from('<iiiif',raw)
    assert h==(-1,nx,ny,nz,float(dx)),h
    assert len(raw)==20+2*count,(len(raw),count)
    return list(struct.unpack_from('<'+'h'*count,raw,20))
def analyze(case,cfg):
    nx,ny,nz,dx=(cfg[k] for k in ('nx','ny','nz','dx'))
    with zipfile.ZipFile(case/'00001.scl') as z:
        assert sorted(z.namelist())==['00001.obl','00001.scl','00001.ust']
        payload={n:z.read(n) for n in z.namelist()}
    vals={Path(n).suffix:unpack_grid(b,nx,ny,nz,dx,nx*ny) for n,b in payload.items()}
    wnd=(case/'00001.wnd').read_bytes()
    winds=unpack_grid(wnd,nx,ny,nz,dx,nx*ny*nz*3)
    # landuse input is j-major/i-minor; AUSGABE output is i-major/j-minor.
    fw_in=list(map(float,(case/'landuse.asc').read_text().splitlines()[3].split()))
    water=[fw_in[j*nx+i]>.99 for i in range(nx) for j in range(ny)]
    assert water==[cfg['coast'] and i<nx//2 for i in range(nx) for j in range(ny)]
    interior=[i not in (0,nx-1) and j not in (0,ny-1) for i in range(nx) for j in range(ny)]
    eligible=[w and inside and ol>0 for w,inside,ol in zip(water,interior,vals['.obl'])]
    log=(case/'Logfile_GRAMMCore.txt').read_text(errors='replace')
    errors=(case/'Problemreport_GRAMM.txt').read_text(errors='replace') if (case/'Problemreport_GRAMM.txt').exists() else ''
    assert 'GRAMM domain area' in log and 'Computation started at:' in log,log
    assert not errors.strip(),errors
    assert not any(abs(x)==32767 or x==-32768 for x in winds),'saturated/nonfinite wind output'
    assert all(1<=v<=7 for v,ins in zip(vals['.scl'],interior) if ins),'invalid interior SC'
    progress=float((case/'PercentGramm.txt').read_text().strip())
    assert 0.8*360<=progress<=360,(case,progress)
    assert int((case/'DispNrGramm.txt').read_text().strip())==1
    steady=(case/'00001_steady_state.txt').read_text().splitlines()
    assert int(steady[0].split()[-1])==nx and int(steady[1].split()[-1])==ny
    steady_values=[float(v) for row in steady[6:] for v in row.split()]
    assert len(steady_values)==nx*ny and all(math.isfinite(v) and 0<=v<=7.01 for v in steady_values)
    files={p.name:p.read_bytes() for p in case.iterdir() if p.is_file() and (p.suffix.lower() in ('.wnd','.tsf','.grd') or p.name in ('RoughnessUsed.txt','albeq.dat','00001_steady_state.txt'))}
    result={'class_counts':dict(Counter(vals['.scl'])),'input_sha256':{n:sha((case/n).read_bytes()) for n in ('IIN.dat','CustomInit.txt','landuse.asc','meteopgt.all','ggeom.asc','GRAMM.geb','GRAMMin.dat','Max_Proc.txt')},'water_cells':sum(water),'interior_water_positive_ol_cells':sum(eligible),'interior_water_positive_ol_unstable_cells':sum(e and s<4 for e,s in zip(eligible,vals['.scl'])), 'ol_raw_min':min(vals['.obl']),'ol_raw_max':max(vals['.obl']),'ust_raw_min':min(vals['.ust']),'ust_raw_max':max(vals['.ust']),'wind_raw_min':min(winds),'wind_raw_max':max(winds),'normalized_last_progress_seconds':progress,'expected_input_duration_seconds':360,'steady_state_grid_valid':True,'tsf_available':(case/'00001.tsf').exists(),'log_valid':True,'problem_report_empty':True,'zip_members':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in payload.items()},'physical_files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in files.items()}}
    return result,vals,water,interior,eligible,files

def compare(a,b,*,apply_expected_patch=True):
    ar,av,water,interior,eligible,af=a; br,bv,_,_,_,bf=b
    changed=[x!=y for x,y in zip(av['.scl'],bv['.scl'])]
    changes=[{'from':x,'to':y,'count':n} for (x,y),n in Counter((x,y) for x,y in zip(av['.scl'],bv['.scl']) if x!=y).items()]
    physical={}
    for name in sorted(set(af)|set(bf)):
        x,y=af.get(name,b''),bf.get(name,b'')
        d={'byte_identical':x==y,'bytes_a':len(x),'bytes_b':len(y)}
        if len(x)==len(y) and name.endswith('.wnd'):
            xx=struct.unpack('<'+'h'*((len(x)-20)//2),x[20:]); yy=struct.unpack('<'+'h'*((len(y)-20)//2),y[20:])
            dd=[v-u for u,v in zip(xx,yy)]
            d.update(different_values=sum(v!=0 for v in dd),max_abs_raw_delta=max(map(abs,dd)),rms_raw_delta=math.sqrt(sum(v*v for v in dd)/len(dd)),scale='0.01 m/s')
        physical[name]=d
    expected=[4 if apply_expected_patch and water[q] and interior[q] and av['.obl'][q]>0 and x<4 else x for q,x in enumerate(av['.scl'])]
    return {'comparison_mode':'baseline_to_candidate_patch' if apply_expected_patch else 'same_build_identity',('baseline_formula_expected_mismatches' if apply_expected_patch else 'same_build_expected_class_mismatches'):sum(x!=y for x,y in zip(expected,bv['.scl'])),'changed_class_cells':sum(changed),'changed_class_fraction':sum(changed)/len(changed),'baseline_unstable_positive_ol_water_cells':ar['interior_water_positive_ol_unstable_cells'],'candidate_unstable_positive_ol_water_cells':br['interior_water_positive_ol_unstable_cells'],'changed_water_cells':sum(c and w for c,w in zip(changed,water)),'changed_land_cells':sum(c and not w for c,w in zip(changed,water)),'changed_water_positive_baseline_ol_cells':sum(c and e for c,e in zip(changed,eligible)),'class_transitions':changes,'decoded_zip_members':{k:{'byte_identical':av[k]==bv[k],'different_cells':sum(x!=y for x,y in zip(av[k],bv[k])),'max_abs_raw_delta':max(abs(x-y) for x,y in zip(av[k],bv[k]))} for k in av},'physical_files':physical}

def classify_status(*, scientific_guardrails, nonwind_physics_exact, bitwise_physics_exact, same_build_repeats_bitwise_exact):
    if not scientific_guardrails or not nonwind_physics_exact:
        return 'fail'
    if not bitwise_physics_exact or not same_build_repeats_bitwise_exact:
        return 'review_required'
    return 'pass'

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--baseline',type=Path);p.add_argument('--candidate',type=Path);p.add_argument('--limit',type=int,default=0);p.add_argument('--results-dir',type=Path);args=p.parse_args()
    root=args.root.resolve(); out=(args.results_dir or root/'qa/native');out.mkdir(parents=True,exist_ok=True);runroot=root/'runs/native';runroot.mkdir(parents=True,exist_ok=True)
    builds={k:(getattr(args,k) or root/f'build/{k}/GRAMM.dll').resolve(strict=True) for k in ('baseline','candidate')}
    specs=[]
    for grid in [dict(nx=24,ny=20,nz=16,dx=250),dict(nx=40,ny=32,nz=20,dx=500)]:
        for threads in [1,2,8]: specs.append(dict(grid,kind='cool_day',threads=threads,sc=2,wind=2,delta=-8,coast=True))
        specs.extend([dict(grid,kind='warm_day',threads=8,sc=2,wind=2,delta=8,coast=True),dict(grid,kind='cool_night',threads=1,sc=6,wind=2,delta=-8,coast=True),dict(grid,kind='land_day',threads=2,sc=2,wind=2,delta=-8,coast=False),dict(grid,kind='strong_neutral',threads=8,sc=4,wind=8,delta=-0.3,coast=True)])
    if args.limit: specs=specs[:args.limit]
    started=time.perf_counter(); records=[]; comparisons=[]; cache={}
    def one(cfg,build,rep=0):
        if time.perf_counter()-started>840: raise TimeoutError('matrix 14 minute cap')
        name=f"{cfg['kind']}_{cfg['nx']}x{cfg['ny']}x{cfg['nz']}_{cfg['dx']}m_t{cfg['threads']}";case=runroot/name/(build+('_repeat'+str(rep) if rep else ''))
        if not case.exists():
            make_case(case,**{k:cfg[k] for k in ('nx','ny','nz','dx','threads','sc','wind','coast')},duration=360,dt=5,irad=30,custom=False)
            # TSurface1m 293.15 K plus explicit water delta sets water 285.15/301.15 K.
            (case/'CustomInit.txt').write_text('Synthetic custom initial conditions\nheader\n'+f"27,{cfg['wind']},{cfg['sc']},1,1000000,293.15,303.15,293.15,{cfg['delta']},0.6,5000,-0.0065,0.01,-0.005\n")
            write_json(case/'native_config.json',cfg)
            rr=run_hidden_console(builds[build],case,timeout=90)
            assert rr['status']=='pass',rr
        else: rr=json.loads((case/'native_run_result.json').read_text())
        assert rr['status']=='pass' and rr['assembly_sha256']==sha(builds[build].read_bytes())
        assert json.loads((case/'native_config.json').read_text())==cfg
        data=analyze(case,cfg); rec={'name':name,'build':build,'repeat':rep,'configuration':cfg,'run':rr,**data[0]}; records.append(rec);cache[(name,build,rep)]=data
        print(f"[RUN] {name} {build} rep{rep} {rr['elapsed_seconds']:.2f}s positiveOLwater={data[0]['interior_water_positive_ol_cells']} unstable={data[0]['interior_water_positive_ol_unstable_cells']}",flush=True)
        write_json(out/'matrix_progress.json',{'runs':records,'elapsed_seconds':time.perf_counter()-started})
        return name,data
    for cfg in specs:
        name,a=one(cfg,'baseline');_,b=one(cfg,'candidate'); comp=compare(a,b);comparisons.append({'name':name,'configuration':cfg,**comp})
        if cfg['kind']=='cool_day' and cfg['threads']==1 and cfg['nx']==24:
            with (out/'representative_cool_day_cells.csv').open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['i_1based','j_1based','water','interior','baseline_class','candidate_class','baseline_ol_m','candidate_ol_m','baseline_ust_m_s','candidate_ust_m_s'])
                for i in range(cfg['nx']):
                    for j in range(cfg['ny']):
                        q=i*cfg['ny']+j;w.writerow([i+1,j+1,int(a[2][q]),int(a[3][q]),a[1]['.scl'][q],b[1]['.scl'][q],a[1]['.obl'][q]/10,b[1]['.obl'][q]/10,a[1]['.ust'][q]/1000,b[1]['.ust'][q]/1000])
    repeats=[]
    if not args.limit:
        for cfg in [x for x in specs if x['nx']==24 and ((x['kind']=='cool_day' and x['threads'] in (1,8)) or x['kind']=='land_day')]:
            for build in builds:
                name,b=one(cfg,build,1);a=cache[(name,build,0)];repeats.append({'name':name,'build':build,**compare(a,b,apply_expected_patch=False)})
    violation=sum(r['interior_water_positive_ol_unstable_cells'] for r in records if r['build']=='candidate')
    physics_exact=all(all(q['byte_identical'] for q in c['physical_files'].values()) and c['decoded_zip_members']['.ust']['byte_identical'] and c['decoded_zip_members']['.obl']['byte_identical'] for c in comparisons)
    formula_exact=all(c['baseline_formula_expected_mismatches']==0 for c in comparisons)
    land_exact=all(c['changed_land_cells']==0 for c in comparisons)
    repeat_exact=all(c['changed_class_cells']==0 and c['same_build_expected_class_mismatches']==0 and all(q['byte_identical'] for q in c['physical_files'].values()) and all(q['byte_identical'] for q in c['decoded_zip_members'].values()) for c in repeats)
    nonwind_exact=all(all(q['byte_identical'] for name,q in c['physical_files'].items() if name!='00001.wnd') and c['decoded_zip_members']['.ust']['byte_identical'] and c['decoded_zip_members']['.obl']['byte_identical'] for c in comparisons)
    repeat_nonwind_exact=all(c['changed_class_cells']==0 and c['same_build_expected_class_mismatches']==0 and all(q['byte_identical'] for name,q in c['physical_files'].items() if name!='00001.wnd') and all(q['byte_identical'] for q in c['decoded_zip_members'].values()) for c in repeats)
    guardrails=violation==0 and formula_exact and land_exact
    gate_status=classify_status(scientific_guardrails=guardrails,nonwind_physics_exact=nonwind_exact and repeat_nonwind_exact,bitwise_physics_exact=physics_exact,same_build_repeats_bitwise_exact=repeat_exact)
    result={'status':gate_status,'scientific_guardrails_pass':guardrails,'nonwind_physics_bitwise_identical':nonwind_exact and repeat_nonwind_exact,'review_reasons':[] if gate_status!='review_required' else ['Wind output is not bitwise identical; numeric equivalence has not been accepted. Same-build variability must be reviewed.'],'land_classes_unchanged':land_exact,'same_build_repeats_bitwise_identical':repeat_exact,'parallelism_semantics':'Max_Proc.txt requested limits 1/2/8; these are not measured actual thread counts. PRANDTL ForEach does not pass pOptions.','baseline_clamp_formula_exact_match':formula_exact,'native_process_elapsed_sum_seconds':sum(r['run']['elapsed_seconds'] for r in records),'scope':'synthetic short integration; native build regression, not production meteorology validation','native_matrix_cases':len(specs),'native_run_count':len(records),'analysis_and_new_execution_elapsed_seconds':time.perf_counter()-started,'candidate_positive_ol_water_unstable_violations':violation,'bitwise_physics_equivalence':all(all(q['byte_identical'] for q in c['physical_files'].values()) and c['decoded_zip_members']['.ust']['byte_identical'] and c['decoded_zip_members']['.obl']['byte_identical'] for c in comparisons),'comparison_tolerance':'none; all observed differences reported exactly','ol_encoding':'AUSGABE: Int16 round(clamp(OL * 10)); internal PRANDTL |OL| >= 5 and <=1000 m','tsf_note':'No .tsf writer exists in this engine source; no .tsf produced. Compare .wnd/.ust/.obl plus steady-state/roughness/radiation geometry cache outputs.', 'mask_orientation':'landuse input index j*nx+i -> AUSGABE index i*ny+j; 1-based internal indices','runs':records,'comparisons':comparisons,'same_build_repeats':repeats}
    write_json(out/'native_matrix_results.json',result)
    with (out/'native_matrix_summary.csv').open('w',newline='') as f:
        fields=['name','baseline_unstable_positive_ol_water_cells','candidate_unstable_positive_ol_water_cells','baseline_formula_expected_mismatches','changed_class_cells','changed_class_fraction','changed_water_cells','changed_land_cells','changed_water_positive_baseline_ol_cells'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(comparisons)
    print(json.dumps({k:v for k,v in result.items() if k not in ('runs','comparisons','same_build_repeats')},indent=2),flush=True)
    if result['status']!='pass': raise SystemExit(2 if result['status']=='review_required' else 1)

if __name__=='__main__':
    main()
