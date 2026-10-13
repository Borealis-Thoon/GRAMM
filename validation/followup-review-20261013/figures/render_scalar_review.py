from pathlib import Path
import argparse,hashlib,json,statistics,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
data=json.loads(a.input.read_text());rows=data['rows'];assert len(rows)==4
for r in rows:
 assert len(r['pairs'])==5
 assert abs(statistics.median(p['saved_percent'] for p in r['pairs'])-r['median_saved_percent'])<1e-10
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','axes.unicode_minus':False})
navy='#183349';teal='#147D87';orange='#B87727';grey='#5C6B74'
fig=plt.figure(figsize=(16,8.5),facecolor='white')
fig.text(.04,.94,'Reuse the TDMA reciprocal chain for temperature and humidity',fontsize=21,fontweight='bold',color=navy)
fig.text(.04,.895,'Compute each reciprocal chain once for sixteen solver sweeps.',fontsize=14,color=grey)
fig.lines.append(Line2D([.455,.455],[.17,.83],transform=fig.transFigure,color='#D9E0E4',lw=1))
ax=fig.add_axes([.04,.24,.385,.58]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
ax.text(0,1,'One coefficient update',fontsize=15,fontweight='bold',color=navy,va='top')
ax.text(0,.875,'Before: rebuild the same chain for every sweep',fontsize=11,color=grey)
def box(x,y,w,h,text,color,fill):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.012,rounding_size=.012',ec=color,fc=fill,lw=1.3))
 ax.text(x+w/2,y+h/2,text,ha='center',va='center',color=color,fontsize=11)
box(.04,.63,.4,.16,'Temperature\n8 calculations',orange,'#FFF4E7');box(.56,.63,.4,.16,'Humidity\n8 calculations',orange,'#FFF4E7')
ax.text(0,.49,'After: build the chain once and reuse it',fontsize=11,color=grey)
box(.30,.285,.40,.13,'1 shared calculation',teal,'#E9F5F4')
for x in [.04,.56]:
 ax.add_patch(FancyArrowPatch((.50,.285),(x+.20,.195),arrowstyle='-|>',mutation_scale=12,color=teal,lw=1.2))
box(.04,.015,.4,.16,'Temperature\n8 reads',teal,'#E9F5F4');box(.56,.015,.4,.16,'Humidity\n8 reads',teal,'#E9F5F4')
ax.text(.5,-.075,'Each equation keeps its own sweep order.',ha='center',color=grey,fontsize=11)
fig.text(.49,.82,'Whole-process time saved',fontsize=15,fontweight='bold',color=navy)
fig.text(.49,.775,'Dots: paired runs   Diamond: median   Line: observed range',fontsize=10.5,color=grey)
chart=fig.add_axes([.72,.27,.205,.435])
vals=[p['saved_percent'] for r in rows for p in r['pairs']];lo=min(-.4,min(vals));hi=max(.4,max(vals));pad=max(.4,(hi-lo)*.14)
chart.set_xlim(min(-2,lo-pad),hi+pad);chart.set_ylim(-.55,3.55)
labels=['Fixed time step\n48 × 36 × 24 | setting 4','Neutral\n48 × 36 × 24 | setting 1','Convective\n48 × 36 × 24 | setting 4','Stable coastal surface\n64 × 48 × 24 | setting 8']
for i,r in enumerate(rows):
 y=3-i;v=[p['saved_percent'] for p in r['pairs']];m=r['median_saved_percent']
 chart.plot([min(v),max(v)],[y,y],color='#9DB6BC',lw=2,zorder=1)
 chart.scatter(v,[y+d for d in [-.10,-.05,0,.05,.10]],s=23,color=teal,alpha=.72,zorder=3)
 chart.scatter([m],[y],marker='D',s=60,color=navy,edgecolors='white',linewidths=.8,zorder=4)
 chart.text(1.055,y,f'{m:+.2f}%',transform=chart.get_yaxis_transform(),ha='left',va='center',fontsize=12,fontweight='bold',color=navy)
chart.axvline(0,color='#7E8D95',ls=(0,(3,3)),lw=1)
chart.set_yticks([3,2,1,0],labels,fontsize=10);chart.tick_params(axis='y',length=0,pad=13);chart.tick_params(axis='x',colors=grey,labelsize=10)
chart.set_xlabel('Time saved (%)',color=grey,labelpad=8);chart.grid(axis='x',color='#EEF1F3',lw=.6)
for spine in chart.spines.values():spine.set_visible(False)
chart.set_axisbelow(True)
fig.text(.49,.177,'Positive values mean a shorter complete run.',fontsize=10.5,color=grey)
fig.text(.49,.14,'Setting = Max_Proc.txt. Preparation runs excluded.',fontsize=10.5,color=grey)
fig.text(.04,.083,'Additional stored values: 0.332 to 0.583 MiB for these grids, plus array overhead.',fontsize=11,color=navy)
fig.text(.04,.043,'Earlier measurements reused. 108 method cases passed; 99 field pairs matched with a fixed partition order.',fontsize=10.5,color=grey)
a.output.mkdir(parents=True,exist_ok=True)
for ext in ('png','svg'):fig.savefig(a.output/('scalar_review.'+ext),dpi=180,facecolor='white')
plt.close(fig)
meta={'status':'rendered','input_sha256':hashlib.sha256(a.input.read_bytes()).hexdigest(),'measurement_origin':data['measurement_origin'],'public_evidence_commit':data['public_evidence_commit'],'points':20,'percent_method':'Median of paired 100*(1-candidate_seconds/baseline_seconds) values.','files':{('scalar_review.'+ext):hashlib.sha256((a.output/('scalar_review.'+ext)).read_bytes()).hexdigest() for ext in ('png','svg')}}
(a.output/'scalar_review.json').write_text(json.dumps(meta,indent=2)+'\n')
print('[SAVE] scalar_review.png/svg')
