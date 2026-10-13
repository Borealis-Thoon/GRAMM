from pathlib import Path
import json,statistics,random,math,csv,argparse
JOB=Path(__file__).resolve().parents[1]
def quantile(v,p):
 s=sorted(v);f=(len(s)-1)*p;i=int(f);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(f-i)
def summarize(records, draws=20000):
 rng=random.Random(20261013);rows=[]
 cases=sorted({r['case'] for r in records})
 for case in cases:
  b={r['rep']:r for r in records if r['case']==case and r['variant']=='baseline' and r['measured']}
  for variant in ['pressure','tdma','radiation','scalar_tdma']:
   p={r['rep']:r for r in records if r['case']==case and r['variant']==variant and r['measured']}
   reps=sorted(set(b)&set(p))
   if not reps:continue
   before=[b[i]['lifetime_seconds'] for i in reps];after=[p[i]['lifetime_seconds'] for i in reps]
   deltas=[100*(1-y/x) for x,y in zip(before,after)]
   boot=[statistics.median(rng.choices(deltas,k=len(deltas))) for _ in range(draws)]
   row=dict(case=case,variant=variant,pairs=len(reps),baseline_median_s=statistics.median(before),patched_median_s=statistics.median(after),paired_time_saved_pct=statistics.median(deltas),low_pct=quantile(boot,.025),high_pct=quantile(boot,.975),min_pct=min(deltas),max_pct=max(deltas),faster_pairs=sum(d>0 for d in deltas),baseline_min_s=min(before),baseline_max_s=max(before),patched_min_s=min(after),patched_max_s=max(after),baseline_peak_mib=statistics.median(b[i]['peak_working_set_bytes']/2**20 for i in reps),patched_peak_mib=statistics.median(p[i]['peak_working_set_bytes']/2**20 for i in reps),paired_percent=deltas)
   rows.append(row)
 return rows
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--records',type=Path,default=JOB/'qa/native/results.json');ap.add_argument('--out',type=Path,default=JOB/'qa/native/summary.json');args=ap.parse_args()
 rows=summarize(json.loads(args.records.read_text()))
 args.out.write_text(json.dumps({'method':'Median of paired 100*(1 - patched/baseline), 95% percentile bootstrap interval, 20000 resamples, seed 20261013; warm-up excluded; all observed repeats retained.','rows':rows},indent=2))
 for r in rows:print(r['case'],r['variant'],round(r['paired_time_saved_pct'],2),[round(r['low_pct'],2),round(r['high_pct'],2)],str(r['faster_pairs'])+'/'+str(r['pairs']))

