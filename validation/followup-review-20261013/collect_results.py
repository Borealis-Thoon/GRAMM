"""Copy the declared public summaries from a completed local validation run."""
from pathlib import Path
import argparse
import json
import re

FILES=[
 'qa/native/plan.json','qa/native/results.json','qa/native/summary.json',
 'qa/fidelity/plan.json','qa/fidelity/results.json','qa/test_review/completed_validation.json','qa/test_review/completed_validation_with_combined.json',
 'qa/submission_decisions.json',
 'qa/uvw_sources/component_results.json','qa/uvw_sources/implementation_review.json',
 'qa/uvw_sources/output_baseline/cases.json','qa/uvw_sources/output_patched/cases.json',
 'qa/radiation_column/component_result.json',
 'qa/build_baseline.json','qa/build_scalar_tdma.json','qa/build_radiation_column.json',
 'qa/build_uvw_sources.json','qa/build_combined.json',
 'qa/full_engine_harness/build_summary.json',
 'qa/full_engine_harness/baseline_manifest.json','qa/full_engine_harness/scalar_tdma_manifest.json',
 'qa/full_engine_harness/radiation_column_manifest.json','qa/full_engine_harness/uvw_sources_manifest.json',
 'qa/full_engine_harness/combined_manifest.json',
 'qa/parallel_state/plan.json','qa/parallel_state/run_progress.json','qa/parallel_state/analysis.json',
 'qa/parallel_state/output_review.json','qa/parallel_state/field_comparisons.csv',
 'qa/parallel_state/baseline_variation_comparison.csv','qa/parallel_state/output_comparisons.csv',
 'qa/parallel_state/output_changed_locations.csv',
 'qa/reproduction_smoke.json',
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parent/'results')
    args=parser.parse_args();root=args.work_dir.resolve(strict=True);out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    roots=[str(root),str(root).replace('\\','/'),str(root).replace('\\','\\\\')]
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items()if k not in {'pid'}}
        if isinstance(value,list):return [clean(x)for x in value]
        if isinstance(value,str):
            for base in roots:value=value.replace(base,'${WORKDIR}')
            value=value.replace('C:\\Program Files\\dotnet\\dotnet.exe','dotnet')
            if '${WORKDIR}'in value:value=value.replace('\\','/')
            if re.search(r'[A-Za-z]:[\\/]',value):raise ValueError('Unmapped absolute path in a public result')
        return value
    copied=[];missing=[]
    for name in FILES:
        source=root/name
        if not source.exists():missing.append(name);continue
        destination=out/name.removeprefix('qa/');destination.parent.mkdir(parents=True,exist_ok=True)
        if source.suffix=='.json':
            data=json.loads(source.read_text(encoding='utf-8-sig'))
            destination.write_text(json.dumps(clean(data),indent=2)+'\n',encoding='utf-8')
        else:destination.write_text(clean(source.read_text(encoding='utf-8-sig')),encoding='utf-8')
        copied.append(name)
    print(json.dumps({'copied':copied,'not_present':missing},indent=2))

if __name__=='__main__':main()