"""Render the longwave PR figure from measured summary JSON only."""
from pathlib import Path
import argparse, json, math, statistics, hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

LABELS={
 'neutral_1':'Neutral\n48 × 36 × 24 | setting 1',
 'convective_4':'Convective\n48 × 36 × 24 | setting 4',
 'stable_coast_8':'Stable, coastal surface\n64 × 48 × 24 | setting 8',
 'large_neutral_14':'Larger neutral domain\n96 × 64 × 28 | setting 14',
 'frequent_radiation_4':'Frequent radiation updates\n24 × 20 × 16 | setting 4',
}
ORDER=list(LABELS)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--summary',type=Path)
 ap.add_argument('--output',type=Path,required=True)
 ap.add_argument('--component',type=Path)
 ap.add_argument('--preview',action='store_true')
 a=ap.parse_args()
 if not a.preview and not a.summary:ap.error('--summary is required outside preview mode')
 rows=[] if a.preview else [r for r in json.loads(a.summary.read_text()) if r['variant']=='radiation_column']
 if not a.preview:
  assert len(rows)==len(ORDER), 'Five planned conditions required'
  rows=sorted(rows,key=lambda r:ORDER.index(r['case']))
  for r in rows:
   vals=r['saved_percent'];assert len(vals)==r['pairs']==5
   assert all(math.isfinite(v) for v in vals)
   assert abs(statistics.median(vals)-r['median_saved_percent'])<1e-10
 a.output.mkdir(parents=True,exist_ok=True)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','axes.unicode_minus':False})
 navy='#183349';teal='#147D87';orange='#B87727';grey='#5C6B74'
 fig=plt.figure(figsize=(16,8.5),facecolor='white')
 fig.text(.04,.94,'Reuse the common longwave radiation profile',fontsize=23,fontweight='bold',color=navy)
 fig.text(.04,.895,'Compute each height once, then copy the results to the existing fields.',fontsize=14,color=grey)
 fig.lines.append(Line2D([.455,.455],[.17,.83],transform=fig.transFigure,color='#D9E0E4',lw=1))
 ax=fig.add_axes([.04,.22,.385,.60]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
 ax.text(0,1,'Repeated work at one height',fontsize=15,fontweight='bold',color=navy,va='top')
 ax.text(0,.89,'Before: run the same calculation in every column',color=grey,fontsize=11)
 def box(x,y,w,h,text,color,fill):
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.012,rounding_size=.012',ec=color,fc=fill,lw=1.3))
  ax.text(x+w/2,y+h/2,text,ha='center',va='center',color=color,fontsize=11)
 for x in [.02,.27,.52,.77]:box(x,.65,.20,.14,'Compute',orange,'#FFF4E7')
 ax.text(.50,.59,'Same profile and same result',ha='center',color=grey,fontsize=11)
 ax.text(0,.46,'After: compute once and copy to every column',color=grey,fontsize=11)
 box(.35,.28,.30,.12,'Compute once',teal,'#E9F5F4')
 for x in [.02,.27,.52,.77]:
  ax.add_patch(FancyArrowPatch((.50,.28),(x+.1,.17),arrowstyle='-|>',mutation_scale=11,lw=1,color=teal,connectionstyle='arc3,rad=0'))
  box(x,.035,.20,.12,'Copy',teal,'#E9F5F4')
 ax.text(.5,-.055,'Existing output fields; no new grid arrays',ha='center',color=grey,fontsize=11)
 fig.text(.49,.82,'Whole-process time saved',fontsize=15,fontweight='bold',color=navy)
 fig.text(.49,.775,'Dots: paired runs   Diamond: median   Line: observed range',fontsize=10.5,color=grey)
 chart=fig.add_axes([.72,.265,.205,.45])
 if a.preview:
  chart.set_xlim(-1,5);chart.set_ylim(-.7,4.7)
  chart.text(.5,.5,'Measured results\nwill appear here',transform=chart.transAxes,ha='center',va='center',color=grey)
 else:
  allvals=[v for r in rows for v in r['saved_percent']]
  lo=min(-.4,min(allvals));hi=max(.4,max(allvals));pad=max(.35,(hi-lo)*.15)
  chart.set_xlim(lo-pad,hi+pad);chart.set_ylim(-.7,4.7)
  for i,r in enumerate(rows):
   y=4-i;vals=r['saved_percent'];med=r['median_saved_percent']
   chart.plot([min(vals),max(vals)],[y,y],color='#9DB6BC',lw=2,zorder=1)
   chart.scatter(vals,[y+d for d in [-.10,-.05,0,.05,.10]],s=21,color=teal,alpha=.72,zorder=3)
   chart.scatter([med],[y],marker='D',s=60,color=navy,edgecolors='white',linewidths=.8,zorder=4)
   chart.text(1.055,y,f'{med:+.2f}%',transform=chart.get_yaxis_transform(),ha='left',va='center',fontsize=12,fontweight='bold',color=navy)
 chart.axvline(0,color='#7E8D95',ls=(0,(3,3)),lw=1)
 chart.set_yticks([4,3,2,1,0],[LABELS[c] for c in ORDER],fontsize=10)
 chart.tick_params(axis='y',length=0,pad=13)
 chart.tick_params(axis='x',colors=grey,labelsize=10)
 chart.set_xlabel('Time saved (%)',color=grey,labelpad=8)
 chart.grid(axis='x',color='#EEF1F3',lw=.6)
 for spine in chart.spines.values():spine.set_visible(False)
 chart.set_axisbelow(True)
 fig.text(.49,.177,'Positive values mean a shorter complete run.',fontsize=10.5,color=grey)
 fig.text(.49,.14,'Setting = Max_Proc.txt. Preparation runs excluded.',fontsize=10.5,color=grey)
 fig.text(.04,.08,'Calls per updated height: horizontal column count → 1.',fontsize=11,color=navy)
 if a.component:
  c=json.loads(a.component.read_text())
  assert c['status']=='pass'
  fig.text(.04,.044,f"Source-derived checks: {c['cases']:,} conditions; {c['finite_bitwise_equal_values']:,} finite values exactly equal.",fontsize=10.5,color=grey)
 stem='radiation_column_preview' if a.preview else 'radiation_column_reuse'
 for ext in ('png','svg'):fig.savefig(a.output/f'{stem}.{ext}',dpi=180,facecolor='white')
 plt.close(fig)
 result={'status':'preview' if a.preview else 'rendered','summary_sha256':None if a.preview else hashlib.sha256(a.summary.read_bytes()).hexdigest(),'rows':rows,'percent_method':'Median of five paired values 100*(1-candidate_seconds/baseline_seconds).','files':{(stem+'.'+ext):hashlib.sha256((a.output/(stem+'.'+ext)).read_bytes()).hexdigest() for ext in ('png','svg')}}
 (a.output/f'{stem}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print('[SAVE]',stem)
if __name__=='__main__':main()
