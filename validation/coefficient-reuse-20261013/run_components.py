"""Run the published actual-method checks after prepare_sources.py."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DOTNET = os.environ.get("GRAMM_TEST_DOTNET", shutil.which("dotnet") or "dotnet")
BASE = ROOT / "work/build/baseline_clean/GRAMM.dll"


def run(args, timeout=180):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True, timeout=timeout)


def build(project, name):
    output = ROOT / "build" / ("component_" + name)
    obj = ROOT / "build" / ("component_" + name + "_obj")
    run([DOTNET, "build", ROOT / project, "-c", "Release", "-p:TreatWarningsAsErrors=true",
         "-p:BaseIntermediateOutputPath=" + str(obj) + os.sep, "-o", output, "--nologo"])
    return output / (Path(project).stem + ".dll")


def main():
    if not BASE.exists():
        raise RuntimeError("Run prepare_sources.py before the component checks.")
    pressure = build("qa/pressure/PressureCheck.csproj", "pressure")
    run([DOTNET, pressure, BASE, ROOT / "build/pressure/GRAMM.dll", ROOT / "qa/pressure/reproduced_component_checks.json"])
    radiation = build("qa/radiation/harness/RadiationCheck.csproj", "radiation")
    run([DOTNET, radiation, BASE, ROOT / "qa/radiation/build/GRAMM.dll", ROOT / "qa/radiation/reproduced_actual_method_checks.json"])
    outputs = []
    for name in ("baseline", "patched"):
        dll = build("qa/tdma/" + name + ".csproj", "tdma_" + name)
        folder = ROOT / "runs" / ("component_tdma_" + name)
        if folder.exists():
            raise RuntimeError("Component output already exists: " + str(folder))
        run([DOTNET, dll, folder])
        outputs.append(folder)
    left, right = outputs
    expected = {p.name for p in left.glob("*.bin")}
    actual = {p.name for p in right.glob("*.bin")}
    if not expected or expected != actual:
        raise RuntimeError("TDMA output file set mismatch")
    rows = []
    for name in sorted(expected):
        a, b = (left / name).read_bytes(), (right / name).read_bytes()
        if a != b:
            raise RuntimeError("TDMA output mismatch: " + name)
        rows.append({"name": name, "identical": True, "bytes": len(a), "sha256": hashlib.sha256(a).hexdigest()})
    result = {"status": "pass", "cases": len(rows), "rows": rows}
    (ROOT / "qa/tdma/reproduced_component_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not (ROOT / "build/instrumented_baseline/GRAMM.dll").exists():
        run([sys.executable, ROOT / "qa/full_engine_harness/prepare_instrumented.py", "--variant", "baseline"])
    if not (ROOT / "build/instrumented_scalar_tdma/GRAMM.dll").exists():
        run([sys.executable, ROOT / "qa/scalar_tdma/prepare_instrumented_scalar.py"])
    run([sys.executable, ROOT / "qa/scalar_tdma/check_methods.py"], timeout=360)
    print("COMPONENTS PASS", flush=True)


if __name__ == "__main__":
    main()
