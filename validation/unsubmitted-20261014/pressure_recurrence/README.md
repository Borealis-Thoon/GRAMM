# Reusing pressure recurrence coefficients

`PRIMP` calculates the same reciprocal and `P` coefficients in each of its eight pressure sweeps. This patch calculates that descending recurrence once, at the end of each column in `TERMIP`. It stores the reciprocal in the existing `AP` array and `P` in `AB`. `AT` keeps its original value because the `Q` recurrence still needs it.

Each later `TERMIP` call writes fresh raw coefficients before rebuilding the recurrence. The change adds no grid arrays or cache-validity state. It preserves the `DIM`, `Q`, back-substitution and neighbor calculations. The density ratio, timestep-based coefficient skipping and pressure-source products are separate changes.

The patch changes two files: 46 lines added and 32 removed. `source_lock.json` records the exact commits and source hashes.

## Reproduce

Use Python 3.10 or newer, Git and the .NET 10 SDK. Provide a local [GRAMM fork](https://github.com/Borealis-Thoon/GRAMM) checkout containing baseline commit `4da3b7c172860e3f9369c7d2fba56b2d82ffbefb`:

```text
python reproduce.py --source-root /path/to/GRAMM --output /path/to/new-results
```

The output directory must be new or empty. Use `--dotnet /path/to/dotnet` to select the SDK executable. The script exports the pinned baseline, patches a separate copy, checks six source hashes, builds both engines with warnings treated as errors, and builds and runs the direct checks. It compares the generated harness and its results with the recorded version. It leaves the supplied checkout unchanged.

The direct checker extracts all 16 recurrence blocks and the guarded `TERMIP` transformation from the actual sources. It accepts `--source-root`, `--baseline-source-root` and `--output`. Running it independently also requires `--run --baseline-assembly /path/to/baseline/GRAMM.dll`.

## Recorded checks

A fresh run of the public reproducer verified all six source hashes and rebuilt the baseline, candidate and direct harness with zero warnings and zero errors. Its generated harness and results matched the recorded version exactly.

- 73,728 source-extracted recurrence cases and 3,207,168 double-value comparisons had zero bit differences, including 1,346,560 nonfinite comparisons.
- The checks include 4,608 pressure-disabled cases and 18,432 boundary cases. `AT` and untouched `AP`/`AB` boundary slots retain their original values.
- All eight compiled baseline pressure callbacks have `InitLocals=true`; the extracted stack-based recurrences also confirmed a positive-zero top `P`/`Q` boundary. This checks the zero boundary used by the cached recurrence.

The cases cover different vertical sizes, ordinary coefficients, small or zero denominators, signed zero, negative values, NaN and infinities. These counts include the coefficient and boundary checks, not just the recurrence outputs.

The `recorded/` folder contains the results and build logs. Local paths in the logs are replaced with `<WORK>`. Full-model comparisons and execution-time measurements are maintained separately.
