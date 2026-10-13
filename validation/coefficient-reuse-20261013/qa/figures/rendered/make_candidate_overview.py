"""Plot all GRAMM reuse candidates from paired timing summaries and raw runs.

Each --dataset supplies one summary.json and its matching results.json.
Rendering must wait until the benchmark owner releases the timing window.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

from make_reuse_figures import COLORS

CANDIDATES = {
    "pressure": "Pressure coefficients",
    "tdma": "Momentum forward coefficients",
    "radiation": "Temperature radiation source",
    "scalar_tdma": "Temperature / humidity pivots",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def reject(value):
        raise ValueError("Non-finite JSON constant: " + value)
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject)


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dataset(summary_path, records_path):
    summary, records = read_json(summary_path), read_json(records_path)
    require(isinstance(summary, dict) and isinstance(summary.get("rows"), list) and summary["rows"], "Missing summary rows")
    require(isinstance(summary.get("method"), str) and summary["method"].strip(), "Missing summary method")
    require(isinstance(records, list) and records, "Missing raw timing records")
    indexed = {}
    for record in records:
        if record.get("measured") is not True:
            continue
        key = (record["case"], record["variant"], record["rep"])
        require(key not in indexed, f"Duplicate raw timing record: {key}")
        seconds = record["lifetime_seconds"]
        require(isinstance(seconds, (float, int)) and math.isfinite(seconds) and seconds > 0, f"Invalid elapsed seconds: {key}")
        indexed[key] = record
    checked = []
    for source in summary["rows"]:
        row = dict(source)
        case, variant = row["case"], row["variant"]
        require(variant in CANDIDATES, f"Unknown candidate: {variant}")
        for field in ("paired_time_saved_pct", "low_pct", "high_pct", "min_pct", "max_pct", "baseline_median_s", "patched_median_s"):
            require(isinstance(row.get(field), (float, int)) and math.isfinite(row[field]), f"Invalid {field}: {case}/{variant}")
        require(isinstance(row.get("pairs"), int) and row["pairs"] > 0, f"Invalid paired count: {case}/{variant}")
        require(row["low_pct"] <= row["high_pct"] and row["min_pct"] <= row["max_pct"], f"Reversed interval: {case}/{variant}")
        candidate = sorted((r for (c, v, _), r in indexed.items() if c == case and v == variant), key=lambda r: r["rep"])
        baseline = sorted((r for (c, v, _), r in indexed.items() if c == case and v == "baseline"), key=lambda r: r["rep"])
        require(len(candidate) == len(baseline) == row["pairs"], f"Incomplete paired raw runs: {case}/{variant}")
        require([r["rep"] for r in baseline] == [r["rep"] for r in candidate], f"Repeat IDs differ: {case}/{variant}")
        config = baseline[0]["config"]
        require(all(r["config"] == config for r in baseline + candidate), f"Conditions differ within dataset: {case}/{variant}")
        grid = config["grid"]
        require(all(k in grid for k in ("nx", "ny", "nz", "dx_m", "dy_m", "first_dz_m", "vertical_stretch", "terrain_height_m")), f"Incomplete grid metadata: {case}")
        require(all(k in config for k in ("sc", "wind", "duration", "dt", "threads", "irad", "turbulence", "radiation", "coast", "multi", "custom", "situations")), f"Incomplete condition metadata: {case}")
        values = [100 * (1 - p["lifetime_seconds"] / b["lifetime_seconds"]) for b, p in zip(baseline, candidate)]
        require(len(row.get("paired_percent", [])) == len(values) and all(close(a, b) for a, b in zip(row["paired_percent"], values)), f"Paired percentages differ from raw times: {case}/{variant}")
        for field, expected in (("paired_time_saved_pct", statistics.median(values)), ("min_pct", min(values)), ("max_pct", max(values)), ("baseline_median_s", statistics.median(r["lifetime_seconds"] for r in baseline)), ("patched_median_s", statistics.median(r["lifetime_seconds"] for r in candidate))):
            require(close(row[field], expected), f"Summary {field} differs from raw times: {case}/{variant}")
        row.update(config=config, summary_source=str(summary_path.resolve()), records_source=str(records_path.resolve()), interval_method=summary["method"])
        checked.append(row)
    expected = {(case, variant) for case, variant, _ in indexed if variant in CANDIDATES}
    require({(r["case"], r["variant"]) for r in checked} == expected, "Summary omits measured candidate conditions")
    return checked


def condition_label(case, c):
    g = c["grid"]
    labels = {"convective_4t": "Convective", "every_step_radiation_4t": "Radiation at every step",
              "large_neutral_4t": "Large neutral", "medium_neutral_1t": "Medium neutral",
              "small_neutral_1t": "Small neutral", "stable_coast_8t": "Stable coast", "fixed_dt_4t": "Fixed time step"}
    label = labels.get(case, case.replace("_", " "))
    grid = f'{g["nx"]} × {g["ny"]} × {g["nz"]}; dx/dy {g["dx_m"]:g}/{g["dy_m"]:g} m'
    weather = f'SC {c["sc"]}; wind {c["wind"]:g} m/s; Max_Proc = {c["threads"]}'
    if c["multi"]:
        weather = f'{c["situations"]} weather situations; Max_Proc = {c["threads"]}'
    duration = f'Configured {c["duration"]:g} s; max dt {c["dt"]:g} s; IRAD {c["irad"]}'
    switches = f'Radiation {"on" if c["radiation"] else "off"}; turbulence {"on" if c["turbulence"] else "off"}; coast {"yes" if c["coast"] else "no"}'
    if c["multi"] or c["custom"]:
        switches += f'; {c["situations"]} situations; custom init {"yes" if c["custom"] else "no"}'
    return "\n".join((label, grid, weather, duration, switches))


def render(rows, cases, configs, output):
    height = max(9.0, 3.4 + 1.12 * len(cases))
    fig = plt.figure(figsize=(21, height), facecolor=COLORS["white"])
    fig.text(.03, .955, "Measured run-time changes across reuse candidates", fontsize=23, weight="bold", color=COLORS["ink"], va="top")
    fig.text(.03, .915, "Native process elapsed time; paired comparison with the baseline for each case", fontsize=12, color=COLORS["muted"], va="top")
    indexed = {(r["case"], r["variant"]): r for r in rows}
    bounds = [0.0] + [r[k] for r in rows for k in ("low_pct", "high_pct", "min_pct", "max_pct", "paired_time_saved_pct")]
    span = max(max(bounds) - min(bounds), 4.0)
    limits = (min(bounds) - .10 * span, max(bounds) + .10 * span)
    bottom, top, left, right, gap = .21, .83, .292, .982, .022
    width = (right - left - 3 * gap) / 4
    axes = []
    for col, (variant, title) in enumerate(CANDIDATES.items()):
        ax = fig.add_axes([left + col * (width + gap), bottom, width, top - bottom])
        axes.append(ax)
        ax.set(xlim=limits, ylim=(len(cases) - .48, -.62))
        ax.axvline(0, color=COLORS["muted"], linewidth=1.1)
        ax.grid(axis="x", color=COLORS["grid"], linewidth=.65)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.set_yticks([])
        ax.tick_params(axis="x", labelsize=9.5, length=0, pad=7)
        ax.set_xlabel("Run time saved (%)", fontsize=10, color=COLORS["muted"], labelpad=8)
        ax.set_title(title, fontsize=12.5, weight="bold", color=COLORS["ink"], pad=20)
        for spine in ax.spines.values():
            spine.set_visible(False)
        for i, case in enumerate(cases):
            if i % 2 == 0:
                ax.axhspan(i - .48, i + .48, color=COLORS["panel"], zorder=-1)
            row = indexed.get((case, variant))
            if row is None:
                ax.text(.5, i, "Not measured", transform=ax.get_yaxis_transform(), ha="center", va="center", fontsize=10, color=COLORS["muted"])
                continue
            value, low, high = (row[k] for k in ("paired_time_saved_pct", "min_pct", "max_pct"))
            color = COLORS["new"] if value >= 0 else COLORS["old"]
            y = i + .09
            ax.hlines(y, row["min_pct"], row["max_pct"], color=COLORS["muted"], linewidth=1.0, zorder=2)
            ax.vlines((row["min_pct"], row["max_pct"]), y-.065, y+.065, color=COLORS["muted"], linewidth=.9, zorder=2)
            ax.hlines(y, low, high, color=color, linewidth=3.5, zorder=3)
            ax.scatter([value], [y], color=color, s=33, zorder=4, edgecolors="white", linewidth=.6)
            ax.text(.5, i-.26, f'{value:+.2f}% [{low:+.2f}, {high:+.2f}]', transform=ax.get_yaxis_transform(), fontsize=9.5, color=color, ha="center", va="center", weight="bold")
            ax.text(.5, i+.33, f'{row["baseline_median_s"]:.2f} → {row["patched_median_s"]:.2f} s; n={row["pairs"]}', transform=ax.get_yaxis_transform(), fontsize=9, color=COLORS["muted"], ha="center", va="center")
    for i, case in enumerate(cases):
        y = fig.transFigure.inverted().transform(axes[0].transData.transform((0, i)))[1]
        fig.text(.03, y, condition_label(case, configs[case]), fontsize=9.6, color=COLORS["ink"], va="center", linespacing=1.28)
    fig.text(.03, .115, "Point: paired median. Line and brackets: observed range of paired measurements. All measured repeats are retained.", fontsize=10.5, color=COLORS["muted"])
    fig.text(.03, .085, "n = 3 or 5: descriptive repeats. Each candidate uses its own paired baseline. Max_Proc is the Max_Proc.txt setting.", fontsize=10.5, color=COLORS["muted"])
    fig.text(.03, .055, "Positive: less elapsed time", fontsize=10.5, color=COLORS["new"], weight="bold")
    fig.text(.225, .055, "Negative: more elapsed time", fontsize=10.5, color=COLORS["old"], weight="bold")
    files = []
    for extension in ("png", "svg"):
        path = output / f"candidate_overview.{extension}"
        fig.savefig(path, dpi=180, facecolor=COLORS["white"], metadata={"Creator": "GRAMM candidate evidence renderer"})
        files.append({"file": path.name, "sha256": sha(path)})
    plt.close(fig)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", nargs=2, action="append", type=Path, required=True, metavar=("SUMMARY", "RECORDS"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows, sources = [], []
    for summary, records in args.dataset:
        rows.extend(load_dataset(summary, records))
        sources.append({"summary": str(summary.resolve()), "summary_sha256": sha(summary), "records": str(records.resolve()), "records_sha256": sha(records)})
    configs, indexed = {}, {}
    for row in rows:
        source_case = row["case"]
        case = next((name for name, config in configs.items() if config == row["config"]), source_case)
        row["source_case"] = source_case
        row["case"] = case
        key = (case, row["variant"])
        require(key not in indexed, f"Duplicate summary case/candidate: {key}")
        indexed[key] = row
        case = row["case"]
        require(case not in configs or configs[case] == row["config"], f"Different conditions use the same case name: {case}")
        configs[case] = row["config"]
    cases = list(configs)
    require(1 <= len(cases) <= 20, "Supply 1 to 20 complete case descriptions")
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none", "axes.unicode_minus": True})
    args.output.mkdir(parents=True, exist_ok=True)
    files = render(rows, cases, configs, args.output)
    data_path = args.output / "candidate_overview_data.json"
    data = {"candidates": CANDIDATES, "cases": cases, "sources": sources, "rows": rows,
            "missing_measurements": [{"case": case, "variant": variant} for case in cases for variant in CANDIDATES if (case, variant) not in indexed]}
    data_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    csv_path = args.output / "candidate_overview_data.csv"
    fields = ("case", "variant", "pairs", "paired_time_saved_pct", "low_pct", "high_pct", "min_pct", "max_pct", "baseline_median_s", "patched_median_s", "condition", "interval_method")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: condition_label(row["case"], row["config"]) if k == "condition" else row[k] for k in fields})
    files.extend({"file": p.name, "sha256": sha(p)} for p in (data_path, csv_path))
    (args.output / "candidate_overview_manifest.json").write_text(json.dumps({"sources": sources, "script_sha256": sha(Path(__file__)), "outputs": files}, indent=2) + "\n", encoding="utf-8")
    print(f"[SAVE] cases={len(cases)} measured_cells={len(rows)} missing_cells={len(data['missing_measurements'])}")


if __name__ == "__main__":
    main()
