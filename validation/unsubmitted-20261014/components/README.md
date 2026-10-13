# GRAMM component checks

These checks compare three independent changes against GRAMM V2701 with the warning cleanup from PR #27. Each candidate starts from commit `4da3b7c172860e3f9369c7d2fba56b2d82ffbefb`. The candidate commits and source hashes are listed in `source_lock.json`.

| Candidate | Changed work | Change size |
|---|---|---|
| `surface_radiation` | Run independent terrestrial radiation columns through the existing worker setting | +2 / -2 lines |
| `store_height` | Compute the mixing-length column term once and retain the final first-level expression | +6 / -7 lines |
| `terminal_diagnostics` | Compute surface diagnostic sums only on console-output steps | +2 / -2 lines |

The recorded run passed 2,082 conditions and compared 19,796,568 values bit for bit. Of those values, 19,762,815 were finite; 33,753 came from deliberate NaN and infinity cases in the viscosity checks.

## Reproduce

Python 3.12 or later, Git and the .NET 10 SDK are required. Start with a local clone containing upstream commit `03224ce9d3490783c84a8aecd72642fe9df21242`. The commands below use `python`; on Windows, replace it with the path to your installed Python executable if needed. Both output directories must be new.

```text
python prepare_sources.py --repository path/to/GRAMM --output restored_sources
python prepare_component_harness.py --source-root restored_sources --output component_check
dotnet build component_check/ComponentChecks.csproj -c Release --nologo -warnaserror
dotnet component_check/bin/Release/net10.0/ComponentChecks.dll component_result_reproduced.json
```

`prepare_sources.py` restores the upstream source and applies the warning cleanup, then one candidate patch per directory. It checks the locked source hashes after restoring each variant. `prepare_component_harness.py` verifies the hashes again and extracts the actual methods or loop blocks into a small C# project. It uses the original element types, constants and arithmetic expressions.

## Coverage

The viscosity checks cover 336 combinations, including both turbulence branches, zero friction velocity, stability thresholds, 0 to 65 vertical levels and worker settings 1, 4 and 8. The extracted viscosity block is tested before the unchanged STORE boundary passes.

The soil checks cover 1,296 combinations across two horizontal grids, four soil-layer counts, wet and dry surfaces, and worker settings 1, 4 and 8. They compare temperature, humidity and boundary values, plus the three serial diagnostic sums, on both sides of the console-output threshold and over repeated calls. The existing parallel diagnostic reductions `EINTRAG4` and `EINTRAG5` are outside the console equality check.

The terrestrial radiation checks cover 450 combinations across three grids, five cloud profiles, spatially varying terrain indices, repeated calls and worker settings 1, 2, 4, 8 and 14. They compare surface radiation and every heating-rate array slot, including untouched values.

The full-model comparisons and runtime measurements are provided separately. These component checks establish numerical preservation for the extracted calculations.

## Files

`patches/` contains the warning cleanup and the three independent candidates. `logs/` contains the recorded candidate Release build logs, with the local work directory replaced by `<WORK>`. `implementations.json` records the commit IDs and exact change counts. `component_result.json` records the final component-check result.
