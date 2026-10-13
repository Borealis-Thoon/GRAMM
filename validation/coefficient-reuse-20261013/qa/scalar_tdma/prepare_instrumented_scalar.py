from pathlib import Path
import importlib.util,json
ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'qa/full_engine_harness/prepare_instrumented.py'
spec=importlib.util.spec_from_file_location('shared_instrumentation',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.VARIANTS['scalar_tdma']='scalar_tdma'
result=module.prepare_and_build('scalar_tdma')
(ROOT/'qa/scalar_tdma/instrumented_build_summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
