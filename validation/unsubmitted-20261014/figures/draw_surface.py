"""Draw the terrestrial-radiation mechanism and every supplied timing condition.

Run only after timing work has finished. Input consists of the published native
measurement records; percentages are computed from matched repetitions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import statistics


CANDIDATE = "surface_radiation"
LABELS = {
    "medium_neutral_4": "Medium neutral",
    "stable_coast_8": "Stable coastal",
    "frequent_radiation_4": "Frequent radiation updates",
    "radiation_medium_4": "Medium grid, frequent radiation",
    "confirmation_neutral_4": "Neutral confirmation",
    "confirmation_stable_8": "Stable coastal confirmation",
    "small_neutral_1": "Small neutral",
    "convective_tke_4": "Convective, TKE enabled",
    "large_neutral_14": "Large neutral",
}
ORDER = [
    "medium_neutral_4", "confirmation_neutral_4", "stable_coast_8",
    "confirmation_stable_8", "frequent_radiation_4", "radiation_medium_4",
    "small_neutral_1", "convective_tke_4", "large_neutral_14",
]
SECONDARY = {"small_neutral_1", "convective_tke_4", "large_neutral_14"}
ALIASES = {"confirmation_neutral_4": "medium_neutral_4",
           "confirmation_stable_8": "stable_coast_8"}


def fail(message):
    raise ValueError(message)


def unpack_records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("records", "results", "measurements"):
            if isinstance(payload.get(key), list):
                return payload[key]
    fail("Expected a record list or a records/results/measurements list")


def elapsed(record):
    value = record.get("lifetime_seconds")
    if value is None:
        fail("A measured record is missing lifetime_seconds")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        fail("Invalid measured process lifetime")
    return value


def config_description(record):
    config = record.get("config", {})
    grid = config.get("grid", config)
    shape = [grid.get(key) for key in ("nx", "ny", "nz")]
    if any(value is None for value in shape):
        fail("Missing grid shape")
    threads = config.get("threads")
    if threads is None:
        fail("Missing worker setting")
    resolution = grid.get("dx_m", grid.get("dx"))
    bits = [" × ".join(str(value) for value in shape)]
    if resolution is not None:
        bits.append(f"{float(resolution):g} m")
    bits.append(f"worker setting {threads}")
    return " · ".join(bits)


def read_measurements(paths):
    indexed, source_files, records = {}, [], []
    for path in paths:
        raw = path.read_bytes()
        source_files.append({"file": path.name, "sha256": hashlib.sha256(raw).hexdigest()})
        records.extend(unpack_records(json.loads(raw.decode("utf-8-sig"))))
    candidate_cases = {record["case"] for record in records
                       if record.get("variant") == CANDIDATE and record.get("measured", False)}
    for record in records:
        if (record.get("case") not in candidate_cases or
                record.get("variant") not in ("baseline", CANDIDATE) or not record.get("measured", False)):
            continue
        if record.get("status") != "pass" or record.get("returncode", 0) != 0 or record.get("timed_out", False):
            fail("A measured record did not complete successfully")
        key = (record["case"], record["variant"], record["rep"])
        if key in indexed:
            fail(f"Duplicate measured case/variant/repetition: {key}")
        elapsed(record)
        indexed[key] = record
    cases = sorted({key[0] for key in indexed if key[1] == CANDIDATE}, key=lambda c: (ORDER.index(c) if c in ORDER else len(ORDER), c))
    rows = []
    for case in cases:
        baseline = {key[2]: value for key, value in indexed.items() if key[:2] == (case, "baseline")}
        candidate = {key[2]: value for key, value in indexed.items() if key[:2] == (case, CANDIDATE)}
        if not baseline or set(baseline) != set(candidate):
            fail(f"Missing matched baseline/candidate repetitions: {case}")
        pairs = []
        for rep in sorted(baseline):
            b, p = baseline[rep], candidate[rep]
            if b.get("config") != p.get("config"):
                fail(f"Mismatched fixture configuration: {case}/{rep}")
            pairs.append({"source_case": case, "rep": rep, "baseline_seconds": elapsed(b), "candidate_seconds": elapsed(p),
                          "saved_percent": 100.0 * (elapsed(b) - elapsed(p)) / elapsed(b)})
        rows.append({"case": case, "config": next(iter(baseline.values())).get("config"),
                     "condition": config_description(next(iter(baseline.values()))), "pairs": pairs})
    if not rows:
        fail("No measured baseline/candidate pairs were supplied")
    merged = {}
    for row in rows:
        canonical = ALIASES.get(row["case"], row["case"])
        if canonical not in merged:
            merged[canonical] = {"case": canonical, "config": row["config"],
                                 "condition": row["condition"], "pairs": [], "source_cases": {}}
        target = merged[canonical]
        if target["config"] != row["config"]:
            fail(f"Confirmation fixture differs from its original condition: {row['case']}")
        target["pairs"].extend(row["pairs"])
        target["source_cases"][row["case"]] = len(row["pairs"])
    rows = sorted(merged.values(), key=lambda row: (ORDER.index(row["case"]) if row["case"] in ORDER else len(ORDER), row["case"]))
    for row in rows:
        saved = [pair["saved_percent"] for pair in row["pairs"]]
        row.update(label=LABELS.get(row["case"], row["case"].replace("_", " ")),
                   median_saved_percent=statistics.median(saved),
                   faster_pairs=sum(value > 0 for value in saved), pair_count=len(saved),
                   secondary=row["case"] in SECONDARY)
        del row["config"]
    return rows, source_files


def draw(rows, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.transforms import blended_transform_factory
    from matplotlib.ticker import MaxNLocator, PercentFormatter

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "svg.fonttype": "none", "axes.unicode_minus": True,
                         "savefig.facecolor": "white"})
    navy, blue, pale, gray = "#16324F", "#167EAB", "#EAF5FA", "#6C7884"
    height = 4.35 + 0.62 * len(rows)
    fig = plt.figure(figsize=(14.8, height), facecolor="white")
    fig.text(.045, 1 - .34 / height, "Parallel columns shorten the terrestrial-radiation pass",
             size=20, weight="bold", color=navy, va="top")
    fig.text(.045, 1 - .77 / height, "Each column keeps the same surface-flux and heating-rate calculations.",
             size=12, color="#435466", va="top")
    diagram = fig.add_axes([.045, (height - 2.95) / height, .91, 1.92 / height])
    diagram.set(xlim=(0, 1), ylim=(0, 1)); diagram.axis("off")
    diagram.text(.015, .97, "Before: one i row at a time", color=navy, weight="bold", size=12, va="top")
    diagram.text(.54, .97, "After: independent i rows run in parallel", color=navy, weight="bold", size=12, va="top")
    ys = [.73, .47, .21]

    def row_box(x, y, index, shaded):
        diagram.add_patch(FancyBboxPatch((x, y - .085), .36, .17, boxstyle="round,pad=0.009,rounding_size=0.018",
                          linewidth=1, edgecolor="#B5C6D3", facecolor=pale if shaded else "#F3F5F7"))
        diagram.text(x + .015, y + .035, f"i = {index}", color=navy, weight="bold", size=10.5, va="center")
        diagram.text(x + .097, y + .035, "surface flux  →  heating rate", color=navy, size=11, va="center")
        diagram.text(x + .097, y - .044, "j columns in their original order", color="#586B7A", size=9.4, va="center")

    for index, y in enumerate(ys, 1):
        row_box(.055, y, index, False)
        row_box(.585, y, index, True)
    for a, b in zip(ys[:-1], ys[1:]):
        diagram.annotate("", (.078, b + .095), (.078, a - .095),
                         arrowprops={"arrowstyle": "-|>", "color": gray, "lw": 1.2})
    diagram.plot([.552, .552], [ys[-1], ys[0]], color=blue, lw=1.5)
    diagram.plot([.965, .965], [ys[-1], ys[0]], color=blue, lw=1.5)
    for y in ys:
        diagram.annotate("", (.575, y), (.552, y), arrowprops={"arrowstyle": "-|>", "color": blue, "lw": 1.2})
        diagram.plot([.952, .965], [y, y], color=blue, lw=1.3)
    diagram.text(.055, .015, "Serial outer loop", size=9.5, color=gray, va="bottom")
    diagram.text(.585, .015, "Parallel.For joins before the existing boundary copies", size=9.5, color=gray, va="bottom")

    chart_bottom, chart_height = .96 / height, .62 * len(rows) / height
    ax = fig.add_axes([.425, chart_bottom, .40, chart_height])
    all_values = [pair["saved_percent"] for row in rows for pair in row["pairs"]]
    low, high = min(-1, min(all_values)), max(1, max(all_values))
    pad = max(.65, .08 * (high - low))
    ax.set_xlim(low - pad, high + pad)
    ax.set_ylim(len(rows) - .5, -.5)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.grid(axis="x", color="#E0E6EB", linewidth=.7)
    ax.axvline(0, color="#6C7884", linewidth=1.15, zorder=2)
    ax.set_yticks([])
    for spine in ("left", "top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#BEC8D1")
    ax.tick_params(axis="x", labelsize=10, length=0, pad=8)
    ax.set_xlabel("Reduction in whole-model wall time", fontsize=11, labelpad=11, color=navy)
    transform = blended_transform_factory(fig.transFigure, ax.transData)
    for y, row in enumerate(rows):
        color = gray if row["secondary"] else blue
        ax.axhspan(y - .42, y + .42, color="#F5F7F9" if row["secondary"] else "#F0F8FC", zorder=0)
        values = [pair["saved_percent"] for pair in row["pairs"]]
        n = len(values)
        jitter = [0 if n == 1 else -.11 + .22 * k / (n - 1) for k in range(n)]
        ax.plot([min(values), max(values)], [y, y], color=color, alpha=.35, linewidth=1.2, zorder=2)
        ax.scatter(values, [y + j for j in jitter], s=33, color=color, alpha=.75,
                   edgecolors="white", linewidths=.5, zorder=3)
        ax.scatter([row["median_saved_percent"]], [y], s=80, marker="D", color=navy,
                   edgecolors="white", linewidths=.8, zorder=4)
        ax.text(.045, y - .105, row["label"], transform=transform, size=11.8,
                color=navy, weight="normal" if row["secondary"] else "bold", va="center", clip_on=False)
        ax.text(.045, y + .205, row["condition"], transform=transform, size=9.5,
                color="#596D7D", va="center", clip_on=False)
        ax.text(.892, y - .07, f'{row["median_saved_percent"]:.2f}%', transform=transform,
                color=navy, weight="bold", size=13, ha="center", va="center", clip_on=False)
        ax.text(.892, y + .225, f'{row["faster_pairs"]}/{row["pair_count"]} pairs faster', transform=transform,
                color=gray, size=9.3, ha="center", va="center", clip_on=False)
    heading = chart_bottom + chart_height + .27 / height
    fig.text(.045, heading, "Native whole-model comparisons", size=12, weight="bold", color=navy)
    fig.text(.892, heading, "Paired median", size=11, weight="bold", color=navy, ha="center")
    fig.text(.045, .15 / height,
             "Dots: matched repeats   ◆: median   Positive values mean less wall time.   Startup and output are included.",
             size=9.6, color="#526778", va="bottom")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".svg"):
        fig.savefig(destination.with_suffix(suffix), dpi=180, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, action="append", required=True,
                    help="Published native measurement JSON; repeat the argument to add confirmation records")
    ap.add_argument("--output", type=Path, required=True, help="Output stem for PNG, SVG and numerical JSON")
    args = ap.parse_args()
    rows, sources = read_measurements(args.results)
    draw(rows, args.output)
    audit = {"candidate": CANDIDATE, "aggregation": "Median of matched per-repetition lifetime reductions",
             "included_cases": len(rows), "included_pairs": sum(row["pair_count"] for row in rows),
             "all_supplied_measured_conditions_shown": True,
             "source_files": sources, "conditions": rows}
    args.output.with_suffix(".json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f'[SAVE] {args.output.name}: {len(rows)} conditions, {audit["included_pairs"]} measured pairs')


if __name__ == "__main__":
    main()