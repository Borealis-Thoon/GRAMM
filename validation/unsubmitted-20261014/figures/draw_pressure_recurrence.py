"""Plot pressure-recurrence reuse and all matched native timing conditions.

The companion draw_surface.py supplies strict record pairing and condition labels.
Confirmation cases can be pooled with --alias INPUT_CASE=CANONICAL_CONDITION.
"""
from pathlib import Path
import argparse,json
import draw_surface as common

CANDIDATE = "pressure_recurrence"
CONDITIONS = ("medium_neutral_4", "stable_coast_8", "small_neutral_1", "convective_tke_4", "large_neutral_14")

def read_measurements(paths, aliases=()):
    common.CANDIDATE = CANDIDATE
    common.ORDER = list(CONDITIONS)
    common.SECONDARY = set()
    common.ALIASES = {"recurrence_" + name: name for name in CONDITIONS}
    common.ALIASES["products_confirmation_large_14"] = "large_neutral_14"
    for item in aliases:
        key, separator, value = item.partition("=")
        if not separator or not key or value not in CONDITIONS:
            raise ValueError("Use --alias INPUT_CASE=CANONICAL_CONDITION")
        if key in common.ALIASES and common.ALIASES[key] != value:
            raise ValueError("Conflicting condition alias: " + key)
        common.ALIASES[key] = value
    return common.read_measurements(paths)

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
    fig.text(.045, 1 - .34 / height, "Build pressure recurrence coefficients once for eight sweeps",
             size=20, weight="bold", color=navy, va="top")
    fig.text(.045, 1 - .77 / height, "TERMIP prepares the reciprocal and P in the existing AP/AB arrays; every pressure sweep reuses them.",
             size=12, color="#435466", va="top")
    diagram = fig.add_axes([.045, (height - 2.95) / height, .91, 1.92 / height])
    diagram.set(xlim=(0, 1), ylim=(0, 1)); diagram.axis("off")
    diagram.text(.02, .96, "Before: rebuild the coefficients in every sweep", color=navy, weight="bold", size=12, va="top")
    diagram.text(.55, .96, "After: one descending recurrence per column", color=navy, weight="bold", size=12, va="top")
    diagram.text(.02, .79, "8 descending coefficient recurrences", color=navy, size=11.2, va="top")
    diagram.text(.55, .79, "Build reciprocal + P once in TERMIP", color=blue, weight="bold", size=12, va="top")
    for index in range(8):
        col, row = index % 4, index // 4
        x, y = .022 + col * .107, .43 - row * .235
        diagram.add_patch(FancyBboxPatch((x, y), .092, .165, boxstyle="round,pad=0.009,rounding_size=0.012", linewidth=1, edgecolor="#B5C6D3", facecolor="#F3F5F7"))
        diagram.text(x + .046, y + .115, f"Sweep {index + 1}", ha="center", va="center", color=navy, size=9.3)
        diagram.text(x + .046, y + .045, "build again", ha="center", va="center", color=gray, size=9.2)
        x = .552 + col * .107
        diagram.add_patch(FancyBboxPatch((x, y), .092, .165, boxstyle="round,pad=0.009,rounding_size=0.012", linewidth=1, edgecolor="#B5C6D3", facecolor=pale))
        diagram.text(x + .046, y + .115, f"Sweep {index + 1}", ha="center", va="center", color=navy, size=9.3)
        diagram.text(x + .046, y + .045, "read AP/AB", ha="center", va="center", color=blue, size=9.5)
    diagram.annotate("", (.757, .618), (.757, .69), arrowprops={"arrowstyle": "-|>", "color": blue, "lw": 1.4})
    diagram.text(.02, .045, "Reciprocal and P repeat unchanged across sweeps", size=10, color=gray, va="bottom")
    diagram.text(.55, .045, "Q still updates each sweep · no added grid arrays", size=10, color=blue, va="bottom")

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
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results",type=Path,action="append",required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--alias",action="append",default=[],help="Pool a confirmation case: INPUT_CASE=CANONICAL_CONDITION")
    args=ap.parse_args()
    rows,sources=read_measurements(args.results,args.alias)
    draw(rows,args.output)
    audit={"candidate":CANDIDATE,"aggregation":"Median of matched per-repetition lifetime reductions", "aliases":args.alias,
           "included_cases":len(rows),"included_pairs":sum(row["pair_count"] for row in rows),
           "all_candidate_measured_conditions_shown":True,"source_files":sources,"conditions":rows,
           "mechanism_counts":{"coefficient_recurrences_per_column_before":8,"coefficient_recurrences_per_column_after":1,"pressure_sweeps":8,"new_grid_arrays":0}}
    args.output.with_suffix(".json").write_text(json.dumps(audit,indent=2)+"\n",encoding="utf-8")
    print(f'[SAVE] {args.output.name}: {len(rows)} conditions, {audit["included_pairs"]} measured pairs')

if __name__=="__main__":main()
