# Pressure-source product reuse: direct checks

The pressure solver uses the same `SUZ * AREAZ` and `SUXYZ * AREAXYZ` products in eight directional sweeps. This patch computes each float product once in `CALCPR` and reuses the existing divergence arrays during `PRIMP`. The final divergence pass writes fresh unweighted values before the mass-divergence summary. The top level remains unweighted because that summary also reads it.

The change is limited to `CALCPR.cs` and `PRIMP.cs`: 25 lines added and 48 removed, with no added arrays. `source_lock.json` records the baseline and candidate commits and the source hashes. The supplied patch applies to baseline `4da3b7c172860e3f9369c7d2fba56b2d82ffbefb`.

## Reproduce

Use Python 3.10 or newer, Git and the .NET 10 SDK. The local checkout must contain the baseline commit, available in the [GRAMM fork](https://github.com/Borealis-Thoon/GRAMM).

```text
python reproduce.py --source-root /path/to/GRAMM --output /path/to/new-results
```

`--dotnet /path/to/dotnet` selects a specific SDK executable. The output directory must be new or empty. The script exports the pinned baseline into that directory, applies the patch to a separate copy, verifies six source hashes, builds both engines with warnings treated as errors, and builds and runs the direct checks. It also checks that the generated harness and its results match the recorded version. The supplied checkout is left unchanged.

`direct_checks.py` extracts all 16 affected `DIM` expressions, the original cutoff and the new cache guard from the source files. It accepts `--source-root`, `--baseline-source-root` and `--output`; add `--run` to build and execute its generated harness.

## Recorded checks

All three Release builds completed with zero warnings and zero errors. The direct checks found zero bit differences across:

- 334,112 complete `DIM` expression comparisons, including 285,712 finite and 48,400 nonfinite results;
- 142,564 float comparisons, including stored products and unchanged boundary values;
- 6,300 guard cases covering pressure enabled or disabled, lateral boundaries, level zero and the top level.

Inputs include values around the existing cutoff, signed zero, random float bit patterns, NaN, infinities, and positive, negative or zero face areas. The guard cases contribute to the float comparison count above.

The `recorded/` files contain the results, source extraction record and build logs. Local working paths in those logs have been replaced with `<WORK>`. These are component checks; full-model fidelity and execution-time results are maintained with the separate model validation material.
