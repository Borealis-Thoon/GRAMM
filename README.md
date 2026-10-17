# Water stability consistency in GRAMM

This evidence accompanies a six-line change to GRAMM's water-cell stability classification. A radiation/wind lookup can produce convective classes while the current Obukhov length is positive. The patch gives those cells neutral class 4 and leaves subsequent calls free to respond to changing conditions.

The production base is GRAMM `a6fc7a3fd4d48ee057706daef09539caccfaf9bd`; the GRAL linkage tests use unmodified GRAL `cd540abf4eda380e5669a891911323351d789e86`. The patch is in `patches/water-stability-diagnostic.patch`. [The PR description](docs/PR_body.md) explains the problem, change and measured dispersion response.

## Reproduce

Requirements: Git, .NET 10 SDK and Python 3.12 or later. The numerical tests use Python's standard library. Plotting additionally requires the packages listed in `requirements-figures.txt`.

From PowerShell, provide a new work directory and explicit executable paths:

```powershell
.\reproduce.ps1 -WorkRoot 'D:\GRAMM_stability_reproduction' -Python 'C:\path\to\python.exe' -Dotnet 'C:\Program Files\dotnet\dotnet.exe' -Git 'C:\Program Files\Git\cmd\git.exe'
```

The script fetches the pinned sources, applies the patch to a separate checkout, builds both GRAMM variants and GRAL with warnings treated as errors, then runs the component, repeated-call, native and GRAL linkage checks. Each model process has a timeout. Choose an otherwise quiet machine for timing comparisons. The coupling matrix took about four minutes on the test machine; the full native and component checks add to that time.

Exit code 0 means all checks passed. Exit code 2 means the functional checks passed but the native wind comparison requires review. The script still completes the downstream linkage checks in that case. Other failures stop the run.

To regenerate the public figures after installing the plot requirements:

```powershell
python tests/figures/build_stability_figures.py --job-root 'D:\GRAMM_stability_reproduction'
python tests/figures/build_coupling_figures.py --job-root 'D:\GRAMM_stability_reproduction'
```

## Evidence map

| Location | Contents |
| --- | --- |
| `qa/component/` | 99,792 production-method cell executions and physical-array comparisons |
| `qa/temporal/` | 504 calls using the same arrays while radiation, wind and temperature gradient change |
| `qa/native/` | Initial 34 native GRAMM runs |
| `qa/reproduction/` | Fresh 34-run native matrix, including the wind-identity review result |
| `qa/native_followup/` | 36 targeted repeats and strict-gate checks |
| `qa/public_reproduction/` | Clean execution of this public package; all 192 matrix concentration payloads reproduced exactly |
| `qa/coupling/` | Six GRAL cases, imported SC/OL/u*, decoded concentration fields and input/output integrity checks |
| `qa/figures/` | Plot data, numerical checks and source hashes |
| `figures/` | Temporal response, three-realization concentration response and a plume map |

The GRAL pairs hold baseline wind, friction-velocity and Obukhov-length payloads fixed and replace only the stability-class payload. This isolates the classification effect from the small wind differences seen in repeated native runs. The official GRAL executable produces the concentration results; a separate diagnostic build records the imported meteorological arrays.

The repeated-call test exercises the production `Prandtl_calculate` method with prescribed forcing. The native matrix exercises the GRAMM executable. The original fresh-matrix record retains its strict `fail` result. The follow-up separates the passing class and surface-exchange checks from wind identity and records `review_required`: same-build repeats as well as cross-build pairs differed by up to 0.01 m/s. All supplied class, friction-velocity and OL expectations passed.

The `.csv` concentration fields are decoded synthetic-test results. Raw solver archives, executables and private research inputs are excluded. Author-specific local paths in the public records are replaced with RUN_ROOT, INITIAL_RUN or PUBLIC_REPRODUCTION. Engine, source, input and numerical-output hashes retain the original run provenance.

