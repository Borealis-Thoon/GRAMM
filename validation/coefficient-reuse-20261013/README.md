# Reproduce the GRAMM coefficient-reuse checks

The scripts build a common baseline and four independent candidate patches from GRAMM V2701, commit `03224ce9d3490783c84a8aecd72642fe9df21242`. Each candidate contains one change: pressure-coefficient reuse, shared velocity TDMA coefficients, shared temperature/humidity TDMA reciprocals, or reuse of the temperature equation's radiation source. The proposed solver patch reuses the temperature/humidity reciprocals. The other three candidates remain in this package so reviewers can inspect the comparisons that led to that choice.

All five builds include `0001_warnings.patch`, which removes eight unused declarations so the projects build with `TreatWarningsAsErrors=true`. The other patch files contain only their respective calculation change. `staging_manifest.json` records their SHA256 hashes and the reviewed Git source trees.

## Recorded results

The native timing records contain 202 runs: 167 measured runs and 35 warm-up runs. Each summary retains every measured repeat and reports the median paired percentage of time saved. For the temperature/humidity patch, the medians were 2.03% in the neutral case with `Max_Proc.txt = 1`, 2.83% in the convective case with `Max_Proc.txt = 4`, 3.58% in the stable coastal case with `Max_Proc.txt = 8`, and 1.41% in the fixed-time-step case with `Max_Proc.txt = 4`. The coastal case had two slower repeats out of five; its interval crosses zero. See `qa/native/scalar_summary.json` and `qa/native/fixed_dt_summary.json` for the full ranges and memory measurements.

The completed serial-replay checks cover nine full-engine cases, 45 model runs, and 396 full-precision field comparisons. All comparisons were exact. `qa/test_review/completed_validation.json` records the checks against the actual completed outputs. Individual method checks passed 45 pressure cases, 80 velocity cases, 108 radiation cases, and 108 temperature/humidity cases.

`qa/hardware.json` records the machine and runtime used for these measurements. Source-review files retain the reviewer's notes from the implementation stage; the completed validation records show the subsequent test results.

## Requirements

Use Windows, Git, Python 3.10 or newer, and the .NET 10 SDK. Model validation uses the Python standard library. Rendering the figures also requires Matplotlib. Source preparation downloads the public GRAMM repository; later stages use the local checkouts.

The native runner creates a hidden Windows console. GRAMM's console cursor calls need a console output handle, so the runner leaves standard handles attached to that hidden console.

## Prepare and build

Set `$Python` to the full path of a working Python executable. Confirm the versions before starting:

```powershell
$Python = 'C:\Path\To\Python\python.exe'
& $Python --version
dotnet --version
git --version
```

Check the downloaded files, then choose an empty directory for the reproduction workspace:

```powershell
& $Python .\verify_bundle.py
& $Python .\prepare_sources.py --workspace C:\GRAMM_repro
Set-Location C:\GRAMM_repro
```

`prepare_sources.py` checks out the pinned upstream commit, creates five detached worktrees, applies the patches, and verifies that each `src` tree matches the reviewed source. It then builds the five native executables with warnings treated as errors. Local commits keep the worktrees clean for the snapshot builder; the script does not push them.

The native build locations are:

| Variant | Source | Built assembly |
|---|---|---|
| Common baseline | `work/warnings` | `work/build/baseline_clean/GRAMM.dll` |
| Pressure coefficients | `work/pressure` | `build/pressure/GRAMM.dll` |
| Velocity TDMA coefficients | `work/tdma` | `build/tdma/GRAMM.dll` |
| Radiation source | `work/radiation` | `qa/radiation/build/GRAMM.dll` |
| Temperature/humidity TDMA reciprocals | `work/scalar_tdma` | `build/scalar_tdma/GRAMM.dll` |

For a local Git mirror, add `--repository C:\path\to\GRAMM`. `--skip-build` prepares and checks the source trees without compiling. To select a specific .NET installation, set `GRAMM_TEST_DOTNET` to its executable path before running the scripts.

## Check individual methods

```powershell
& $Python .\run_components.py
```

The method checks call the engine's actual implementations. They compare pressure coefficients across time-step changes and reinitialization, velocity updates across the eight sweep directions, and radiation-source and temperature values across source updates. The TDMA fixtures include nonzero terrain projections. The temperature/humidity checks exercise both solvers together, each solver alone, and both disabled. They also vary time step and density. `run_components.py` prepares the required serial test adapters for these checks.

The summaries are written to:

- `qa/pressure/reproduced_component_checks.json`
- `qa/tdma/reproduced_component_results.json`
- `qa/radiation/reproduced_actual_method_checks.json`
- `qa/scalar_tdma/method_results.json`

For a short check after the method tests, run:

```powershell
& $Python .\qa\final_build\reproduce_smoke.py
& $Python .\qa\final_build\check_build_warnings.py
```

The smoke check runs the baseline and temperature/humidity candidate through one completed 60-second case, with both snapshot builds and native executables. The build check reproduces the eight upstream diagnostics under `TreatWarningsAsErrors=true` and confirms that the cleanup builds without warnings or errors.

## Compare complete model calculations

```powershell
& $Python .\qa\full_engine_harness\prepare_instrumented.py
& $Python .\qa\scalar_tdma\prepare_instrumented_scalar.py
& $Python .\work\fidelity_suite.py
& $Python .\work\fidelity_turbulence.py
& $Python .\work\fidelity_scalar.py
& $Python .\work\make_all_cases.py
& $Python .\qa\test_review\validate_completed.py --cases .\qa\fidelity\all_cases.json --variants baseline pressure tdma radiation scalar_tdma --expected-cases 9 --expected-runs 45 --expected-weather-runs 55
```

The snapshot builder applies the same test adapters to all five source trees. It records the source and transformed file hashes. Fidelity runs execute the partitions in a fixed serial order for exact comparison. Each completed weather situation records the full-precision `U`, `V`, `W`, `T`, `QU`, `PN`, `TE`, `DISS`, and `RADIATION` fields, along with the integration state. The checks also compare wind files, decompressed surface-field payloads, and the steady-state output.

The cases vary grid size, resolution, configured partition count, stability, wind, surface properties, radiation frequency, and sequential weather initialization. `fidelity_turbulence.py` adds a case with the k-epsilon equations enabled. The full-engine geometries are flat; the method checks cover nonzero terrain projections separately.

Read `qa/fidelity/results.json`, `qa/fidelity/k_epsilon.json`, and `qa/fidelity/scalar_tdma.json` for the reproduced comparisons. Each model process has a 300-second watchdog.

## Compare native parallel state

After the snapshot builds are ready, run:

```powershell
& $Python .\qa\parallel_state\run_parallel_state.py
& $Python .\qa\parallel_state\analyze_parallel_state.py
```

This check uses the engine's native parallel dispatch with full-precision snapshots. It repeats the baseline and all four candidates three times with `Max_Proc.txt` set to 1, 4, and 8: 45 runs of a coastal convective case with turbulence and radiation enabled. The analyzer reports each field's absolute differences, mean absolute error, root mean square error, and changed fraction. Baseline-to-baseline repeats provide the observed variation for comparison. The outputs are `qa/parallel_state/analysis.json`, `field_comparisons.csv`, and `baseline_variation_comparison.csv`. These completed results are included. To inspect how full-precision wind differences appear in the saved wind files, run:

```powershell
& $Python .\qa\benefit_review\review_native_wnd.py
```

The script checks each saved integer against the corresponding final wind value and records changed cells in `qa/benefit_review/native_wnd_changed_locations.csv`.

## Measure native execution

Close other compute-heavy jobs before running:

```powershell
& $Python .\work\native_benchmark.py
& $Python .\work\fixed_dt_benchmark.py
& $Python .\work\scalar_benchmark.py
& $Python .\work\summarize_benchmarks.py
& $Python .\work\summarize_benchmarks.py --records .\qa\native\fixed_dt_results.json --out .\qa\native\fixed_dt_summary.json
& $Python .\work\summarize_benchmarks.py --records .\qa\native\scalar_results.json --out .\qa\native\scalar_summary.json
```

These suites run the native executables with the engine's normal parallel execution. They rotate the execution order, exclude each case's warm-up round, and record repeated runs. The first suite compares the baseline with the pressure, velocity TDMA, and radiation candidates. The fixed-time-step case compares all five builds, including the temperature/humidity candidate. The scalar suite adds neutral, convective, and stable coastal cases with `Max_Proc.txt` set to 1, 4, and 8. Case definitions and repetition counts are in the three scripts.

Windows `GetProcessTimes` supplies process lifetime and CPU time. `GetProcessMemoryInfo` supplies peak working-set bytes. The three record files are `qa/native/results.json`, `qa/native/fixed_dt_results.json`, and `qa/native/scalar_results.json`. They include the assembly hash and output checks. The summarizer calculates paired changes, a 95% percentile bootstrap interval with 20,000 resamples, and peak working-set comparisons. Its random seed is fixed at `20261013`.

The model creates its inputs and outputs under `runs/`. Each suite expects fresh case directories and stops if they already exist, which preserves previous results. Use another empty workspace for a complete rerun.

## Recreate the figures

The figure inputs contain the recorded results. From the reproduction workspace:

```powershell
& $Python .\qa\figures\rendered\make_reuse_figures.py --input .\qa\figures\rendered\scalar_figure_input.json --output .\qa\figures\reproduced
& $Python .\qa\figures\rendered\make_candidate_overview.py --dataset .\qa\native\summary.json .\qa\native\results.json --dataset .\qa\native\fixed_dt_summary.json .\qa\native\fixed_dt_results.json --dataset .\qa\native\scalar_summary.json .\qa\native\scalar_results.json --output .\qa\figures\reproduced
```

The scalar figure explains the repeated calculation, the shared reciprocal, and the observed time savings. The overview retains results for all four candidates. Both use the observed range of paired measurements, so slower repeats remain visible.

## Files and provenance

`work/fixture.py` and `work/geometry_fixture.py` generate synthetic inputs and check the binary geometry layout. `qa/full_engine_harness/HarnessSupport.cs` contains the test adapters and snapshot code. These validation helpers are kept outside the proposed engine patches.

`qa/final_patch_sizes.json` is the final change-count record. It counts Unicode code points in added and removed line bodies, including one LF per line. `qa/benefit_review/final_decisions.json` records the decision for each candidate.

The benchmark runs preceded a final cleanup of three orphan XML comment lines. `qa/final_source_provenance.json` retains both sets of source commits. Fresh strict builds and method checks passed after that edit. The old and final native builds have identical method IL, signatures, local-variable signatures, exception regions, and member/type references; the detailed comparison is in `qa/final_build/method_il_comparison.json`. The short final model check is recorded separately in `qa/final_build/smoke_results.json` and does not enter the timing summaries.

Published result paths are relative to the reproduction workspace. Numerical values, measured assembly hashes, source commits, and output hashes are preserved. `staging_manifest.json` records the original and published hashes of each copied file. Where path cleanup changes a JSON file, the figure manifests retain its original hash alongside the hash of the published file.

The source changes follow the [GRAMM license](https://github.com/GralDispersionModel/GRAMM/blob/03224ce9d3490783c84a8aecd72642fe9df21242/License.md). The package contains no research inputs, compiled executables, raw model fields, or checkpoint files. Running the scripts creates fresh local model outputs for the comparisons.
