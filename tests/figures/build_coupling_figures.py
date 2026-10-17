from pathlib import Path
import csv,json,hashlib,os,argparse
parser=argparse.ArgumentParser()
parser.add_argument("--job-root",type=Path,default=Path(__file__).resolve().parents[2])
args=parser.parse_args()
ROOT=args.job_root.resolve()
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'cache/matplotlib_figures'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize,TwoSlopeNorm
import numpy as np
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.labelsize':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.facecolor':'white'})
OUT=ROOT/'figures'; QA=ROOT/'qa/figures'
OUT.mkdir(parents=True,exist_ok=True); QA.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(fig,name):
 for ext in ('png','svg'):fig.savefig(OUT/f'{name}.{ext}',dpi=210,bbox_inches='tight')
 plt.close(fig)
def writecsv(name,rows):
 with (QA/name).open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary=ROOT/'qa/coupling/summary.json'; summary_hash=sha(summary)
s=json.loads(summary.read_text(encoding='utf-8-sig'))
validation=ROOT/'qa/coupling/validation.json'
v=json.loads(validation.read_text(encoding='utf-8-sig'))
assert v['status']=='pass'
comp=s['comparisons']['cool_main']
selected=[]
for r in comp:
 stem=r['output'].split(':')[1].split('.')[0];weather,suffix=stem.split('-');level=int(suffix[0]);sg=int(suffix[1:])
 if level!=1:continue
 assert 1<=sg<=4 and 1<=int(weather)<=3
 assert np.isclose(r['max_pct'],100*(r['candidate_max']/r['base_max']-1))
 assert np.isclose(r['integral_pct'],100*(r['candidate_integral']/r['base_integral']-1))
 selected.append({'seed':int(weather),'source_group':sg,'source_surface':'water' if sg<=2 else 'land','source_height_m':2 if sg in (1,3) else 20,'receptor_height_m':2,**r})
assert len(selected)==12
writecsv('03_gral_ground_response.csv',selected)
fig,axes=plt.subplots(1,2,figsize=(13.5,5.4))
labels=['Water\nh = 2 m','Water\nh = 20 m','Land\nh = 2 m','Land\nh = 20 m']
for ax,metric,title in zip(axes,['max_pct','integral_pct'],['a  Maximum concentration at 2 m','b  Spatial integral of concentration at 2 m']):
 for seed,color,marker,offset in [(1,'#176A81','o',-.13),(2,'#D8782C','s',0),(3,'#705A8F','^',.13)]:
  rr=sorted([r for r in selected if r['seed']==seed],key=lambda r:r['source_group'])
  ax.scatter(np.arange(4)+offset,[r[metric] for r in rr],s=70,color=color,marker=marker,label=f'Seed {seed}',zorder=3)
 for j in range(4):
  vals=[r[metric] for r in selected if r['source_group']==j+1]; lo,hi=min(vals),max(vals)
  ax.plot([j,j],[lo,hi],color='#74828A',lw=1,zorder=1)
  text=f'{lo:+.1f} to {hi:+.1f}%' if abs(hi-lo)>.01 else f'{lo:.1f}%'
  ax.annotate(text,(j,hi),xytext=(0,13),textcoords='offset points',ha='center',fontsize=10,fontweight='bold',color='#36434C')
 ax.axhline(0,color='#5B6770',lw=1.1);ax.set_xlim(-.5,3.5);ax.set_xticks(range(4),labels);ax.set_ylabel('Candidate / baseline change (%)');ax.set_title(title,loc='left',fontweight='bold',pad=17);ax.grid(axis='y',color='#E3E7EA');ax.set_axisbelow(True)
axes[0].set_ylim(-85,32);axes[1].set_ylim(-15,187)
axes[0].legend(ncol=3,loc='lower center',bbox_to_anchor=(.5,1.10),frameon=False,handletextpad=.35,columnspacing=1.2)
fig.suptitle('GRAMM stability changes propagate into GRAL dispersion',x=.08,y=.995,ha='left',fontsize=17,fontweight='bold')
fig.text(.08,.925,'Cool-water test; identical emissions and paired random seeds; 3 deterministic seed realizations',color='#4B5962')
fig.text(.08,.01,'All sources: 1 kg h$^{-1}$; receptor layer centred at 2 m (4 m thickness); 100 m horizontal grid.\nSpatial integral = sum(C x cell area) at the 2 m sampling level.',fontsize=10,color='#4B5962')
fig.subplots_adjust(left=.08,right=.985,top=.72,bottom=.23,wspace=.27)
save(fig,'03_gral_ground_response')
# Single seed, marine elevated source, with the same positive colour scale.
inputs=[];arrays=[]
for tag in ('A','B'):
 p=ROOT/f'qa/coupling/fields/cool_main_{tag}/00001-102.csv';inputs.append(p)
 a=np.genfromtxt(p,delimiter=',',names=True);xs=np.unique(a['x_m']);ys=np.unique(a['y_m']);z=np.full((len(ys),len(xs)),np.nan)
 for row in a:z[np.searchsorted(ys,row['y_m']),np.searchsorted(xs,row['x_m'])]=row['C_ug_m3']
 assert np.isfinite(z).all()
 arrays.append(z)
A,B=arrays;assert A.shape==B.shape
r=[r for r in selected if r['seed']==1 and r['source_group']==2][0]
assert np.isclose(A.max(),r['base_max']) and np.isclose(B.max(),r['candidate_max'])
extent=[xs.min()-50,xs.max()+50,ys.min()-50,ys.max()+50]
fig=plt.figure(figsize=(14.1,6.3));gs=fig.add_gridspec(2,3,height_ratios=[16,1],hspace=.50,wspace=.28)
axes=[fig.add_subplot(gs[0,j]) for j in range(3)]
norm=Normalize(0,max(A.max(),B.max())); lim=np.max(np.abs(B-A));dnorm=TwoSlopeNorm(vmin=-lim,vcenter=0,vmax=lim)
ims=[]
for ax,z,title in zip(axes,[A,B,B-A],['a  Baseline','b  Candidate','c  Candidate - baseline']):
 im=ax.imshow(z,origin='lower',extent=np.array(extent)/1000,cmap='YlOrBr' if len(ims)<2 else 'RdBu_r',norm=norm if len(ims)<2 else dnorm,interpolation='nearest');ims.append(im)
 ax.axvline(3,color='#737F86',ls='--',lw=1);ax.scatter([2],[2.5],marker='*',s=100,c='#202A31',edgecolors='white',linewidth=.5,zorder=5)
 ax.set_title(title,loc='left',fontweight='bold',pad=12);ax.set_xlabel('Local x (km)');ax.set_ylabel('Local y (km)');ax.set_xticks([1,2,3,4,5]);ax.set_yticks([1,2,3,4])
 ax.text(.04,.04,'Water  |  Land',transform=ax.transAxes,color='#3D4951',fontsize=10,bbox={'facecolor':'white','alpha':.9,'edgecolor':'none','pad':3})
cax=fig.add_subplot(gs[1,:2]);cb=fig.colorbar(ims[0],cax=cax,orientation='horizontal');cb.set_label('Concentration at 2 m ($\\mu$g m$^{-3}$)')
cax2=fig.add_subplot(gs[1,2]);cb2=fig.colorbar(ims[2],cax=cax2,orientation='horizontal');cb2.set_label('Difference ($\\mu$g m$^{-3}$)')
fig.suptitle('Elevated water source: the ground-level plume changes',x=.065,y=.99,ha='left',fontsize=17,fontweight='bold')
fig.text(.065,.875,'Changed water cells: SC 2 -> 4; source and receptor geometry unchanged',color='#4B5962')
fig.text(.065,.925,'Source height = 20 m; emission = 1 kg h$^{-1}$; paired seed 1; dashed line = water / land boundary',color='#4B5962')
fig.text(.065,.01,f'Seed 1: maximum {r["base_max"]:.2f} -> {r["candidate_max"]:.2f} $\\mu$g m$^{{-3}}$; spatial integral change {r["integral_pct"]:+.1f}%.\nConcentration decrease at the peak coexists with a positive spatial-integral change. Idealized native-model coupling test.',fontsize=10,color='#4B5962')
fig.subplots_adjust(left=.065,right=.98,top=.79,bottom=.24)
save(fig,'04_gral_water20_ground_plume')
manifest={'status':'pass','source_inputs':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in [summary,validation,*inputs]],'summary_sha256_at_read':summary_hash,'summary_unchanged_during_plot':sha(summary)==summary_hash,'assertions':{'12_ground_seed_source_comparisons':True,'percentage_recalculation':True,'csv_field_max_matches_summary':True,'map_fields_finite_and_equal_shape':True},'figures':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sorted(OUT.glob('0[34]*'))],'visual_review':'pending'}
(QA/'coupling_figure_checks.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('[SAVE] coupling: 2 figures PNG+SVG; 12-row metric CSV')


