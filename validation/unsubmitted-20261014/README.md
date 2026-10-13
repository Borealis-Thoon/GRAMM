# GRAMM validation sources and reproduction

This directory contains the source patches, synthetic inputs and tools used to compare the proposed GRAMM changes. Each change is tested on the same warning-free baseline. The baseline is upstream V2701 commit `03224ce9d3490783c84a8aecd72642fe9df21242` with the warning cleanup from #27 (`4da3b7c172860e3f9369c7d2fba56b2d82ffbefb`).

The changes selected for submission are surface-column radiation parallelism and pressure-recurrence coefficient reuse. Mixing-length reuse, unused terminal-diagnostic removal and pressure-source-product reuse remain on hold because the measured gains were small or inconsistent. [The submission decisions](measurements/decisions.json) retain the evidence for every candidate.

The default comparison restores four independent variants: baseline, surface-column radiation parallelism, mixing-length reuse, and removal of unused terminal diagnostics. Four optional variants are available:

- `pressure_products` reuses the two pressure-source products in the existing temporary arrays.
- `pressure_recurrence` reuses the pressure recurrence coefficients in `AP` and `AB`, leaving the `AT` coefficient and Q update unchanged.
- `selected_combined` combines the two selected changes with the longwave-emissivity reuse from #29 for compatibility checks.
- `combined` applies the surface-column change together with the longwave-emissivity reuse already proposed in #29. It measures how those two radiation changes work together.

The component and pressure directories pin source commits and file hashes. `full_model/additional_source_lock.json` pins both combined builds and the pressure-recurrence sources. Restored copies are checked against these hashes before they become local validation repositories. The new local commit IDs will differ from the original development commits because they record source snapshots for reproduction.

## Prepare and build

Use Python, Git and .NET 10. Native timing uses Windows process APIs. Supply a local GRAMM clone that contains the pinned upstream commit. Run each command to completion before starting the next; keep other model runs and builds idle during timing.

For the default four variants:

```text
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase prepare
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase build
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase fidelity
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase native --reps 5
```

To restore all eight supported sources and build the selected changes together, use a fresh workspace:

```text
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase prepare --extra-variants pressure_products combined pressure_recurrence selected_combined
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase build --variants baseline surface_radiation pressure_recurrence selected_combined
```

Builds treat warnings as errors. The fidelity phase runs the strict completed-run validator after the model comparisons; it checks declared cases, integration completion, finite fields, output payloads and exact field hashes. You can select candidates and cases without changing the default suite:

```text
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase fidelity --variants baseline pressure_products --cases small_neutral_1 medium_neutral_4 stable_coast_8 convective_tke_4 large_neutral_14
python reproduce.py --repo GRAMM_CLONE --workspace NEW_WORKSPACE --phase native --variants baseline pressure_products --cases small_neutral_1 medium_neutral_4 stable_coast_8 convective_tke_4 large_neutral_14 --reps 5
```

## Follow-up checks

The paths below are inside `NEW_WORKSPACE/gramm_validation`. Build the optional variants before running their checks. The pressure fidelity follow-up reads the completed baseline runs, so first run the default fidelity phase across all declared cases.

```text
python work/pressure_followup.py fidelity
python work/pressure_followup.py native
python work/surface_followup.py fidelity
python work/surface_followup.py native
python work/recurrence_followup.py fidelity
python work/recurrence_followup.py native
```

The surface follow-up includes the second measurement windows for the neutral and stable conditions, plus a larger case with frequent radiation updates. Pair each candidate run with its baseline by case and repetition. For the two confirmation windows, pool the five original and five confirmation ratios before taking the median.

The native parallel-state check uses four variants, three worker settings and three repeats, for 36 runs. It records full-precision fields as well as the normal model outputs:

```text
python qa/parallel_state/run_parallel_state.py
python qa/parallel_state/analyze_parallel_state.py
python qa/parallel_state/review_outputs.py
```

The run script requires a fresh set of parallel-state folders. The analysis scripts can be rerun on completed output without running GRAMM. State binaries and raw model outputs are created locally; they are not part of this public bundle.

## What the checks establish

Fixed-order comparisons use the existing test-only `HarnessParallel` adapter so that scheduling differences do not hide arithmetic changes. Native timing uses builds without the test-only adapters. The parallel-state check separately measures the final fields under the normal parallel dispatcher. Its output review checks every saved wind component against rounding of the final double-precision field.

In the 36-run parallel-state check, all surface outputs, steady-state records and integration steps matched. For the surface-column and pressure-source-product patches, seven of nine matched wind files were identical; the remaining files differed by one 0.01 m/s storage step in at most three components for the surface patch and two for the pressure patch. The largest full-precision wind differences were 0.00001935 m/s and 0.00001923 m/s, respectively. Baseline repeats differed by up to 0.00000969 m/s. These are observed differences from the tested coastal convective case; fixed-order field comparisons provide the separate check of arithmetic preservation.

For the pressure-source-product change, the additional call-lifetime audit checks every completed `CALCPR` return. It confirms that `SUZ` and `SUXYZ` hold raw divergence again before the caller resumes, and checks the pressure fields, corrected velocities and divergence histories across consecutive calls. See [call_lifetime/README.md](call_lifetime/README.md) for the reproduction tools and recorded results.

The pressure-recurrence parallel check is separate: baseline and recurrence variants, three worker settings and three repeats (18 runs).

```text
python qa/recurrence_parallel/run_parallel_state.py
python qa/recurrence_parallel/analyze_parallel_state.py
python qa/recurrence_parallel/review_outputs.py
```

The recurrence native follow-up also adds the large-grid confirmation window shared by the pressure-product comparison. Its `products_confirmation_large_14` pairs are pooled with the five original pressure-product large-grid pairs in the figure.

## Recorded evidence

- [Native measurements](measurements/native_records.json) and [per-window summaries](measurements/native_summary.json): 306 completed runs, including 255 measured runs and 51 warmups. The figures pair runs by case and repetition, then pool the declared confirmation windows.
- [Completed fixed-order validation](measurements/fidelity/final_all_candidates.json): all six independent variants, ten cases and 72 weather runs; all 540 field pairs matched. [The frequent-radiation comparison](measurements/fidelity/frequent_radiation_combined.json) adds the larger radiation case.
- [Native parallel output review](measurements/parallel/output_review.json) for the 36-run surface/product comparison and [the separate recurrence review](measurements/recurrence_parallel/output_review.json) for 18 runs.
- [Selected-combination validation](measurements/fidelity/selected_combined.json): the two selected changes plus #29 passed three cases and five weather situations, with all 45 field pairs unchanged.
- [Fresh public-tool reproduction](full_model/recorded/public_reproduction.json): all eight sources restored, 16 strict builds completed without warnings, and the frequent-radiation case passed for every variant. [Build logs](full_model/recorded/builds/) are included.
- [Component checks](components/component_result.json), [pressure-return audit](call_lifetime/README.md), and the source-extracted tests in the two pressure directories provide checks of the changed calculations.

Some component records contain `pending` or `not_measured`. They preserve the result at that earlier stage. The completed model checks and submission decisions linked above give the final assessment. The earlier six-variant reproduction record is retained as a separate completed check.

The [surface figure](figures/surface_radiation.png) shows all 45 matched pairs across seven conditions. The [pressure-product figure](figures/pressure_products.png) preserves all 30 pairs for that held candidate, including its large-grid confirmation window. Regenerate either figure from this directory:

```text
python figures/draw_surface.py --results measurements/native_records.json --output figures/surface_radiation
python figures/draw_pressure_products.py --results measurements/native_records.json --output figures/pressure_products
```
