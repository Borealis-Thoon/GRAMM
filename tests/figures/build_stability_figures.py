from pathlib import Path
import csv, json, hashlib, os, argparse
parser=argparse.ArgumentParser()
parser.add_argument("--job-root",type=Path,default=Path(__file__).resolve().parents[2])
args=parser.parse_args()
ROOT=args.job_root.resolve()
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'cache/matplotlib_figures'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.labelsize':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.facecolor':'white'})
OUT=ROOT/'figures'; QA=ROOT/'qa/figures'
OUT.mkdir(parents=True,exist_ok=True); QA.mkdir(parents=True,exist_ok=True)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(fig,name):
    for ext in ('png','svg'): fig.savefig(OUT/f'{name}.{ext}',dpi=210,bbox_inches='tight')
    plt.close(fig)
def write_csv(name,rows):
    with (QA/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
temporal=ROOT/'qa/temporal/temporal_checks.json'
raw=ROOT/'qa/temporal/temporal_cell_results.csv'
t=json.loads(temporal.read_text(encoding='utf-8-sig'))
rows=list(csv.DictReader(raw.open(encoding='utf-8-sig')))
assert t['status']=='pass' and sha(raw)==t['csv_sha256']
selected=[]
fig,axes=plt.subplots(1,2,figsize=(13.4,5.6),sharey=True)
for ax,case_id,title in zip(axes,[12,0],['a  Water cell: FW = 1, OL > 0','b  Land cell: FW = 0, OL > 0']):
    for engine,color,marker,ls in [('baseline','#D8782C','o','--'),('candidate','#176A81','s','-')]:
        subset=[r for r in rows if r['engine']==engine and r['geometry']=='0' and r['threads']=='1' and r['initial_AKLA']=='1' and r['phase']=='solar_roundtrip' and int(r['id'])==case_id]
        subset.sort(key=lambda r:int(r['step']))
        assert len(subset)==6
        y=[int(r['class']) for r in subset]
        if case_id==12: assert y==t['stable_water_solar_classes'][engine]
        for initial in ('1','6'):
            test=[r for r in rows if r['engine']==engine and r['geometry']=='0' and r['threads']=='1' and r['initial_AKLA']==initial and r['phase']=='solar_roundtrip' and int(r['id'])==case_id]
            test.sort(key=lambda r:int(r['step']))
            assert [int(r['class']) for r in test]==y
        ax.plot(range(6),y,color=color,marker=marker,linestyle=ls,lw=2.6,ms=8,markerfacecolor='white' if engine=='baseline' else color,label=engine.capitalize(),zorder=3 if engine=='baseline' else 2)
        for r in subset:
            selected.append({k:r[k] for k in ['engine','geometry','threads','initial_AKLA','phase','step','id','thermal','FW','radiation','wind10','gradient','class','OL','TST','AKLA','boundary_cells']})
    ax.set_title(title,loc='left',pad=15,fontweight='bold')
    ax.set_xticks(range(6),[f'{i+1}\n{v}' for i,v in enumerate(t['radiation_sequence'])])
    ax.set_xlabel('Repeated call / imposed solar radiation (W m$^{-2}$)',labelpad=9)
    ax.set_xlim(-.25,5.25); ax.set_ylim(7.4,.6)
    ax.set_yticks(range(1,8),['1  Strongly unstable','2  Unstable','3  Slightly unstable','4  Neutral','5  Slightly stable','6  Stable','7  Very stable'])
    ax.grid(axis='y',color='#DDE3E5',lw=.8,zorder=0)
    ax.axhspan(3.5,7.5,color='#EAF3F5',alpha=.45,zorder=0)
axes[0].set_ylabel('GRAMM stability class')
axes[0].legend(loc='upper right',frameon=True,facecolor='white',framealpha=.95)
axes[1].text(.5,.50,'Baseline and candidate overlap',transform=axes[1].transAxes,ha='center',color='#42515A',bbox={'facecolor':'white','edgecolor':'none','alpha':.9})
fig.suptitle('Interior stability updates when radiation changes',x=.12,ha='left',fontsize=17,fontweight='bold',y=.99)
fig.text(.12,.915,'Repeated production-method calls; same physical surface state in each baseline / candidate pair',fontsize=11,color='#4B5962')
fig.text(.12,.01,'Initial AKLA = 1 and 6 give the same interior sequence. Boundary cells retain their prescribed initial class.\nControlled test: wind = 1 m s$^{-1}$; stable thermal gradient.',fontsize=10,color='#4B5962')
fig.subplots_adjust(left=.19,right=.985,top=.80,bottom=.24,wspace=.13)
save(fig,'01_stability_temporal_response')
write_csv('01_stability_temporal_response.csv',selected)
manifest={'status':'pass','source_inputs':[{'path':str(v.relative_to(ROOT)),'sha256':sha(v)} for v in [temporal,raw]],'assertions':{'temporal_csv_matches_audit_hash':True,'representative_water_sequence_matches_audit':True,'initial_AKLA_1_6_same_selected_interior_sequence':True},'figures':[{'path':str(v.relative_to(ROOT)),'sha256':sha(v)} for v in sorted(OUT.glob('01*')) if v.suffix in ('.png','.svg')],'private_data_required':False,'visual_review':'pending'}
(QA/'figure_checks.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('[SAVE] temporal PNG+SVG and CSV')
