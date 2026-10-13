# Pressure-source return-state audit

This audit checks the `pressure_products` candidate at every completed `CALCPR` call. The patch uses `SUZ` and `SUXYZ` as temporary product storage during the pressure sweeps, then restores raw divergence before returning. The audit verifies that restoration and compares the state seen by the caller across consecutive calls.

The recorded run contains six model executions: baseline and candidate for a neutral case with pressure enabled, the same case with pressure disabled, and a coastal three-weather sequence with the TKE model and stretched vertical spacing. The pressure-disabled case follows the normal caller path and makes no `CALCPR` calls.

All 104 completed call pairs and five weather-end pairs matched exactly. The check compares 21,149,100 field values, including 3,524,850 values in the two float divergence arrays. At each return it also recomputes the original final divergence expressions, checking 2,436,720 restored values per variant. Pressure fields, corrected velocities, convergence histories and integration state are included. See [the recorded result](recorded/result.json) for the case-by-case counts. A fresh run of these public tools [reproduced the results exactly](recorded/portable_reproduction.json).

## Reproduce

First restore sources with the top-level `reproduce.py` and include `--extra-variants pressure_products`. Then run these commands from this directory, using a new output folder:

```text
python prepare_lifetime.py --source-root NEW_WORKSPACE/work --output NEW_AUDIT_OUTPUT
python run_lifetime.py --output NEW_AUDIT_OUTPUT
```

The preparation script copies the two verified sources, adds the test hooks and builds with warnings treated as errors. The runner checks the recorded counts and exact results, then writes `NEW_AUDIT_OUTPUT/result.json`. To recheck completed local output without running models:

```text
python run_lifetime.py --output NEW_AUDIT_OUTPUT --analyze-only
```

The hooks read the model state; they do not write model fields. The original calculation expressions and types are preserved. Both variants use the same fixed-order test adapter, and reversing only the declared hooks restores every tracked source file byte for byte. These audit runs establish return-state preservation; their timings are not used in the performance comparison.

The bundle includes the audit source, synthetic fixture generators, final result and build logs. It excludes raw state binaries and model output files, which the commands create locally.
