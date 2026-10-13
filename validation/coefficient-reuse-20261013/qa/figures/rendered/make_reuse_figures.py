"""Render reviewed GRAMM patch figures from supplied measured results.

No timings are generated or estimated here. Required input schema is documented
in figure_input_schema.json. Run only after the root timing owner releases the
benchmark window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

COLORS = {
    "ink": "#17324A", "muted": "#52697C", "grid": "#DDE5EB",
    "old": "#B96536", "old_fill": "#FFF3E9", "new": "#087E75",
    "new_fill": "#E8F6F3", "panel": "#F5F8FA", "white": "#FFFFFF",
}
TITLES = {
    "pressure": (
        "Reuse pressure coefficients while the time step is unchanged",
        "Density and grid geometry stay fixed within a weather situation.",
    ),
    "tdma": (
        "Compute the momentum forward coefficients once",
        "U, V and W use the same AIM, BIM and CIM coefficients.",
    ),
    "radiation": (
        "Reuse the temperature radiation source between updates",
        "Solar and terrestrial heating rates change only when radiation is refreshed or reinitialized.",
    ),
    "scalar_tdma": (
        "Reuse the inverse pivots in temperature and humidity sweeps",
        "Temperature and humidity each make eight sweeps with the same A_PS, B_PS and C_PS coefficients.",
    ),
}


def wrapped(value: str, width: int = 32) -> str:
    return "\n".join(textwrap.fill(part, width=width) for part in value.split("\n"))


def box(ax, x, y, w, h, label, *, tone="neutral", size=12):
    fill = COLORS["panel"] if tone == "neutral" else COLORS[tone + "_fill"]
    edge = COLORS["grid"] if tone == "neutral" else COLORS[tone]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.010,rounding_size=0.017",
                               facecolor=fill, edgecolor=edge, linewidth=1.25))
    ax.text(x+w/2, y+h/2, label, ha="center", va="center", fontsize=size,
            color=COLORS["ink"], linespacing=1.35)


def arrow(ax, start, end, *, color=None):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13,
                                linewidth=1.55, color=color or COLORS["muted"],
                                shrinkA=0, shrinkB=2))


def panel(fig, rect, label, tone):
    ax = fig.add_axes(rect)
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((.004, .012), .99, .97,
                               boxstyle="round,pad=0,rounding_size=0.025",
                               facecolor=COLORS["white"], edgecolor=COLORS["grid"], linewidth=1.0))
    ax.text(.035, .9, label, fontsize=11, weight="bold", color=COLORS[tone], va="center")
    return ax


def pressure_diagram(before, after):
    box(before, .035, .39, .36, .30, "Same time step\nSame density and grid")
    box(before, .495, .39, .465, .30, "Rebuild pressure\ncoefficient arrays", tone="old")
    arrow(before, (.41, .54), (.477, .54))
    before.text(.035, .16, "Full grid pass on every coefficient call", fontsize=12, color=COLORS["muted"])
    box(after, .035, .38, .37, .32, "Time step changed\nor new weather\nsituation?", size=11.5)
    box(after, .545, .59, .405, .17, "Changed: rebuild", tone="new", size=12)
    box(after, .545, .29, .405, .17, "Unchanged: reuse", tone="new", size=12)
    arrow(after, (.42, .60), (.528, .675), color=COLORS["new"])
    arrow(after, (.42, .48), (.528, .375), color=COLORS["new"])
    after.text(.035, .12, "1 to 0 grid passes on an unchanged-input call", fontsize=12, color=COLORS["new"])


def tdma_diagram(before, after):
    box(before, .035, .30, .24, .43, "AIM\nBIM\nCIM", size=12)
    for y, component in zip((.64, .43, .22), "UVW"):
        box(before, .425, y, .52, .16, f"{component}: compute forward P", tone="old", size=11.5)
        arrow(before, (.29, .51), (.406, y+.08))
    before.text(.035, .095, "Three identical forward P chains", fontsize=12, color=COLORS["muted"])
    box(after, .035, .35, .23, .36, "AIM\nBIM\nCIM", size=12)
    box(after, .385, .36, .25, .34, "One shared\nP chain", tone="new", size=12)
    arrow(after, (.285, .53), (.367, .53), color=COLORS["new"])
    for y, component in zip((.64, .43, .22), "UVW"):
        box(after, .765, y, .18, .16, component, tone="new", size=12)
        arrow(after, (.648, .53), (.746, y+.08), color=COLORS["new"])
    after.text(.035, .095, "3 to 1 P chains; separate Q values for U, V and W", fontsize=11.5, color=COLORS["new"])


def radiation_diagram(before, after):
    box(before, .035, .56, .36, .18, "Solar heating", size=12)
    box(before, .035, .28, .36, .18, "Terrestrial heating", size=12)
    box(before, .52, .31, .43, .39, "Interpolate and scale\non every\ntemperature solve", tone="old", size=12)
    arrow(before, (.41, .65), (.502, .56))
    arrow(before, (.41, .37), (.502, .46))
    before.text(.035, .12, "Heating rates can stay unchanged across many steps", fontsize=11.5, color=COLORS["muted"])
    box(after, .035, .44, .38, .31, "Radiation update\nor reinitialization", size=12)
    box(after, .545, .50, .405, .25, "Refresh the existing\nRADIATION buffer", tone="new", size=11.5)
    arrow(after, (.43, .595), (.525, .625), color=COLORS["new"])
    box(after, .545, .145, .405, .20, "Reuse between updates", tone="new", size=11.5)
    arrow(after, (.747, .479), (.747, .366), color=COLORS["new"])
    after.text(.035, .19, "No new\ngrid-sized buffer", fontsize=12, color=COLORS["new"], linespacing=1.3)


def scalar_tdma_diagram(before, after):
    box(before, .035, .35, .24, .37, "A_PS\nB_PS\nC_PS", size=12)
    box(before, .43, .58, .52, .18, "Temperature: 8 pivot chains", tone="old", size=11)
    box(before, .43, .29, .52, .18, "Humidity: 8 pivot chains", tone="old", size=11)
    arrow(before, (.29, .57), (.411, .67))
    arrow(before, (.29, .48), (.411, .38))
    before.text(.035, .105, "16 inverse-pivot chains per column", fontsize=11.5, color=COLORS["muted"])
    box(after, .035, .39, .27, .33, "TERMI_PS\nCompute once", tone="new", size=11.5)
    box(after, .39, .42, .22, .28, "One H_PS\nbuffer", tone="new", size=11.5)
    arrow(after, (.32, .555), (.374, .56), color=COLORS["new"])
    box(after, .715, .59, .245, .17, "Temperature", tone="new", size=10.5)
    box(after, .715, .29, .245, .17, "Humidity", tone="new", size=10.5)
    arrow(after, (.626, .57), (.699, .675), color=COLORS["new"])
    arrow(after, (.626, .51), (.699, .375), color=COLORS["new"])
    after.text(.035, .105, "16 to 1; each solver keeps its P, Q and back substitution", fontsize=10.5, color=COLORS["new"])

def check_input(data: dict):
    if set(data.get("patches", {})) - set(TITLES):
        raise ValueError("Unknown patch key; allowed keys: pressure, tdma, radiation, scalar_tdma")
    if not data.get("patches"):
        raise ValueError("At least one measured patch is required")
    for key, p in data["patches"].items():
        cases = p.get("cases", [])
        if not 1 <= len(cases) <= 10:
            raise ValueError(f"{key}: supply 1 to 10 displayed cases")
        for field in ("interval_label", "timing_context"):
            if not isinstance(p.get(field), str) or not p[field].strip():
                raise ValueError(f"{key}: missing {field}")
        if not p.get("verification") or len(p["verification"]) > 5:
            raise ValueError(f"{key}: supply 1 to 5 short verification facts")
        for c in cases:
            for field in ("time_saved_pct", "low_pct", "high_pct", "baseline_s", "patched_s"):
                if not isinstance(c.get(field), (int, float)) or not math.isfinite(c[field]):
                    raise ValueError(f"{key}: invalid {field}")
            if c["low_pct"] > c["high_pct"]:
                raise ValueError(f"{key}: reversed interval")
            if c["time_saved_pct"] > 100 or min(c["baseline_s"], c["patched_s"]) <= 0:
                raise ValueError(f"{key}: invalid measured time")
            if not isinstance(c.get("pairs"), int) or c["pairs"] < 1:
                raise ValueError(f"{key}: missing positive pair count")
            if not isinstance(c.get("label"), str) or not c["label"].strip():
                raise ValueError(f"{key}: missing case label")


def performance_panel(fig, p):
    fig.text(.047, .48, "Measured change in run time", fontsize=18, weight="bold", color=COLORS["ink"])
    ax = fig.add_axes([.265, .185, .355, .26])
    cases = p["cases"]
    extrema = [0.0] + [c[n] for c in cases for n in ("low_pct", "high_pct", "time_saved_pct")]
    lo, hi = min(extrema), max(extrema)
    span = max(hi-lo, 5.0)
    xmin, xmax = lo-.055*span, hi+.38*span
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(len(cases)-.45, -.55)
    ax.axvline(0, color=COLORS["muted"], linewidth=1.0, zorder=1)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=.7, zorder=0)
    for i, c in enumerate(cases):
        value = c["time_saved_pct"]
        color = COLORS["new"] if value >= 0 else COLORS["old"]
        ax.barh(i, value, height=.46, color=color, alpha=.23, zorder=2)
        ax.hlines(i, c["low_pct"], c["high_pct"], color=color, linewidth=2.0, zorder=3)
        ax.vlines([c["low_pct"], c["high_pct"]], i-.11, i+.11, color=color, linewidth=1.5, zorder=3)
        ax.scatter([value], [i], color=color, s=38, marker="D", zorder=4)
        for j, pair in enumerate(c.get("paired_percent", [])):
            pair_color = COLORS["new"] if pair >= 0 else COLORS["old"]
            ax.scatter([pair], [i+.20+(j%2)*.015], color=pair_color, s=16, alpha=.75, zorder=3)
        label_x = max(c["high_pct"], value)+.025*span
        ax.text(label_x, i, f"{value:+.2f}%", fontsize=11, color=color, va="center", weight="bold")
        ax.text(1.04, i, f'{c["baseline_s"]:.2f} → {c["patched_s"]:.2f} s', transform=ax.get_yaxis_transform(),
                fontsize=10, ha="left", va="center", color=COLORS["muted"])
    ax.set_yticks(range(len(cases)), [wrapped(c["label"], 32) for c in cases])
    ax.tick_params(axis="both", labelsize=10.5, length=0, pad=8)
    ax.set_xlabel("Run time saved (%)", fontsize=11, color=COLORS["muted"], labelpad=7)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_facecolor(COLORS["white"])
    fig.text(.636, .453, "Median times: before → after", fontsize=10, color=COLORS["muted"])
    return ax


def verification_panel(fig, p):
    ax=fig.add_axes([.817, .18, .153, .30])
    ax.set(xlim=(0,1), ylim=(0,1)); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0,.01), .98,.98, boxstyle="round,pad=0.0,rounding_size=.025",
                               facecolor=COLORS["new_fill"], edgecolor=COLORS["grid"], linewidth=1))
    ax.text(.065,.88,"Result checks",fontsize=13,weight="bold",color=COLORS["ink"],va="center")
    y=.72
    total_lines=sum(len(wrapped(str(v), 24).splitlines()) for v in p["verification"])
    step=min(.115,.57/max(total_lines+len(p["verification"])*.4,1))
    for fact in p["verification"]:
        label=wrapped(str(fact),24)
        ax.text(.07,y,"•",fontsize=13,color=COLORS["new"],va="top")
        ax.text(.15,y,label,fontsize=10.5,color=COLORS["ink"],va="top",linespacing=1.3)
        y-=step*(len(label.splitlines())+.7)


def render(key, p, out):
    fig=plt.figure(figsize=(16,9),facecolor=COLORS["white"])
    title, subtitle=TITLES[key]
    fig.text(.045,.943,title,fontsize=24,weight="bold",color=COLORS["ink"],va="top")
    fig.text(.045,.887,subtitle,fontsize=13.5,color=COLORS["muted"],va="top")
    before=panel(fig,[.045,.535,.44,.31],"CURRENT CODE","old")
    after=panel(fig,[.515,.535,.44,.31],"WITH THIS PATCH","new")
    {"pressure":pressure_diagram,"tdma":tdma_diagram,"radiation":radiation_diagram,"scalar_tdma":scalar_tdma_diagram}[key](before,after)
    performance_panel(fig,p)
    verification_panel(fig,p)
    pairs=sorted(set(c["pairs"] for c in p["cases"]))
    pair_text=str(pairs[0]) if len(pairs)==1 else ", ".join(map(str,pairs))
    fig.text(.045,.083,wrapped(p["timing_context"],150),fontsize=10.5,color=COLORS["muted"],va="top")
    fig.text(.045,.048,wrapped(f'{p["interval_label"]}  |  Paired runs per case: {pair_text}',155),
             fontsize=9.5,color=COLORS["muted"],va="top")
    files=[]
    for ext in ("png","svg"):
        path=out/f"{key}_reuse.{ext}"
        fig.savefig(path,dpi=180,facecolor=COLORS["white"],metadata={"Creator":"GRAMM patch evidence renderer"})
        files.append({"file":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    plt.close(fig)
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    data=json.loads(args.input.read_text(encoding="utf-8-sig"))
    check_input(data)
    plt.rcParams.update({"font.family":"DejaVu Sans","svg.fonttype":"none","axes.unicode_minus":True})
    args.output.mkdir(parents=True,exist_ok=True)
    files=[]
    for key,p in data["patches"].items(): files.extend(render(key,p,args.output))
    manifest={"input_sha256":hashlib.sha256(args.input.read_bytes()).hexdigest(),
              "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"outputs":files}
    (args.output/"figure_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(f"[SAVE] {len(files)} figure files")

if __name__=="__main__": main()
