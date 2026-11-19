"""Method overview: Grow Up / Root Down / Revise over a typed skill graph.

A Hallmark-guided restyle of the original Matplotlib figure. The content follows
``docs/research/GROW_UP_ROOT_DOWN_REVISE_20261113.md``; the soft palette follows
the reference supplied with the design request. Export remains PNG + PDF at 300 dpi.

Build (from the repo root; needs matplotlib 3.9.2, see
``grasp_optimization/reports/dependencies.json`` -> ``figures_20261114``)::

    python figures/plot_overview.py              # -> figures/overview.png, overview.pdf
    python figures/plot_overview.py <out_dir>    # -> <out_dir>/overview.png, overview.pdf

The PNG/PDF outputs are git-ignored; only this script is versioned.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
from matplotlib.path import Path


PALETTE = {
    "paper": "#FBFAF7",
    "surface": "#FEFDFB",
    "ink": "#27313A",
    "muted": "#5C6872",
    "rule": "#C9D0D1",
    "blue_panel": "#E8F0F5",
    "blue_fill": "#D7E4F1",
    "blue_rule": "#9AB3CB",
    "blue_ink": "#4E7089",
    "green_panel": "#EEF4E8",
    "green_fill": "#CCE9BC",
    "green_rule": "#ABCB9A",
    "green_ink": "#5E7B53",
    "violet_panel": "#F0EBF5",
    "violet_fill": "#EDE3F6",
    "violet_rule": "#B49ACB",
    "violet_ink": "#766184",
    "yellow": "#FDF3B8",
    "rose": "#FBDADC",
    "rose_ink": "#995761",
    "teal": "#B0DDDB",
    "neutral": "#F0ECE6",
}

plt.rcParams.update({
    "font.family": "Liberation Sans",
    "font.sans-serif": ["Liberation Sans", "DejaVu Sans"],
    "mathtext.fontset": "dejavusans",
    "font.size": 12,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})


def box(ax, x, y, w, h, fc="surface", ec="rule", lw=1.2, r=1.0, ls="-", z=3):
    """Draw a quiet container; all styling resolves through the palette."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        fc=PALETTE.get(fc, fc), ec=PALETTE.get(ec, ec),
        lw=lw, ls=ls, zorder=z,
    ))


def label(ax, x, y, text, fs=10, color="ink", ha="center", va="center",
          weight="normal", z=7, linespacing=1.18, family=None):
    font_kwargs = {} if family is None else {"fontfamily": family}
    ax.text(
        x, y, text, ha=ha, va=va, fontsize=fs,
        color=PALETTE.get(color, color), fontweight=weight,
        zorder=z, linespacing=linespacing, **font_kwargs,
    )


def arrow(ax, p0, p1, color="muted", lw=1.4, ls="-", rad=0.0,
          style="-|>", ms=11, z=4):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=ms,
        color=PALETTE.get(color, color), lw=lw, ls=ls,
        connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0, zorder=z,
    ))


def route(ax, points, color="muted", lw=1.3, ls="-", style="-|>", ms=10, z=4):
    """Orthogonal connector for off-axis nodes."""
    path = Path(points, [Path.MOVETO] + [Path.LINETO] * (len(points) - 1))
    ax.add_patch(FancyArrowPatch(
        path=path, arrowstyle=style, mutation_scale=ms,
        color=PALETTE.get(color, color), lw=lw, ls=ls,
        shrinkA=0, shrinkB=0, zorder=z,
    ))


def panel(ax, x, y, w, h, title, subtitle, fill, border):
    box(ax, x, y, w, h, fc=fill, ec=border, lw=1.6, r=1.8, z=1)
    label(ax, x + 2, y + h - 3.5, title, fs=18, ha="left", weight="bold")
    label(ax, x + 2, y + h - 7.2, subtitle, fs=11, color="muted", ha="left")


def process_step(ax, x, y, w, h, number, title, detail, highlight=False):
    box(
        ax, x, y, w, h,
        fc="yellow" if highlight else "surface",
        ec="blue_ink" if highlight else "blue_rule",
        lw=1.5 if highlight else 1.0, r=0.8,
    )
    ax.add_patch(Circle(
        (x + 3.0, y + h / 2), 1.35,
        fc=PALETTE["blue_ink"] if highlight else PALETTE["blue_fill"],
        ec="none", zorder=6,
    ))
    label(ax, x + 3.0, y + h / 2 + 0.05, str(number), fs=9.0,
          color="surface" if highlight else "blue_ink", weight="bold")
    label(ax, x + 6.0, y + h - 2.25, title, fs=10.2, ha="left", weight="bold")
    label(ax, x + 6.0, y + 1.95, detail, fs=9.4, color="muted", ha="left",
          linespacing=1.05)


def draw_revise(ax):
    box(ax, 2, 87, 196, 13.5, fc="violet_panel", ec="violet_rule", lw=1.5, r=1.8, z=1)
    label(ax, 4, 96.5, "Revise", fs=18, ha="left", weight="bold")
    label(ax, 4, 92.3, "Every N rounds, after round 3\nMethod-layer update",
          fs=10.0, color="muted", ha="left")
    steps = [
        "Split practice history E\ndevelopment | scoring",
        "Generate candidates\nversions of A and R",
        "Replay evaluation\nconsistency + snapshot forks",
        "Select best version\ncurrent + noise floor",
        "Apply next round\nrollback if direction reverses",
    ]
    x0, w, gap = 30, 31.4, 2.8
    for i, text in enumerate(steps):
        x = x0 + i * (w + gap)
        box(ax, x, 90, w, 7.5, fc="surface", ec="violet_rule", lw=0.9, r=0.8)
        label(ax, x + w / 2, 93.75, text, fs=10.5)
        if i:
            arrow(ax, (x - gap + 0.3, 93.75), (x - 0.3, 93.75),
                  color="violet_ink", lw=1.1, ms=9)


def draw_grow_up(ax):
    panel(ax, 2, 17, 54, 65, "Grow Up", "Online each round | accumulation algorithm A",
          "blue_panel", "blue_rule")
    label(ax, 54, 74.8, "Frozen this round", fs=9.5, color="muted", ha="right")

    x, w, h = 4, 30, 7.2
    ys = [66, 57.6, 49.2, 40.8, 32.4]
    steps = [
        ("Retrieve and execute", "Bounded skill pack\nsnapshots at boundaries"),
        ("Extract or propose", "Success → composite\nrepeated gap → leaf"),
        ("Check contracts", "Every post holds\non recorded snapshots"),
        ("Evidence gate", "Paired forks\nfrom the same snapshots"),
        ("Merge and promote", "Deduplicate and merge\nlater reuse → validated"),
    ]
    for i, ((title, detail), y) in enumerate(zip(steps, ys), start=1):
        process_step(ax, x, y, w, h, i, title, detail, highlight=(i == 4))
        if i > 1:
            arrow(ax, (x + w / 2, y + h + 1.2), (x + w / 2, y + h),
                  color="blue_ink", lw=1.2, ms=9)

    # Failure is a side branch, not a downstream step after promotion.
    route(ax, [(4, 69.6), (2.9, 69.6), (2.9, 24.6), (4, 24.6)],
          color="rose_ink", lw=1.1, ls=(0, (3, 2)), ms=9, z=2)
    box(ax, 4, 20.5, 50, 8.2, fc="rose", ec="rose_ink", lw=0.9, r=0.8)
    label(ax, 6, 26.0, "Failure branch", fs=10.2, ha="left", weight="bold")
    label(ax, 6, 22.8, "Gap record → triage → Grow Up candidate, or a kernel gap",
          fs=9.4, color="muted", ha="left")

    # Paired-fork evidence gate: the same boundary snapshot feeds both arms.
    ix, iy, iw, ih = 36.2, 34.0, 18.0, 24.0
    box(ax, ix, iy, iw, ih, fc="surface", ec="blue_ink", lw=1.0, r=0.8, ls=(0, (4, 2)))
    arrow(ax, (34, 44.4), (ix, 44.4), color="blue_ink", lw=1.1, style="-", ms=8)
    label(ax, ix + iw / 2, iy + ih - 2.6, "Paired fork", fs=10.5,
          color="blue_ink", weight="bold")
    label(ax, ix + iw / 2, iy + ih - 5.1, "one snapshot in bucket b", fs=8.5,
          color="muted")
    sx, sy = ix + 2.8, iy + 12.3
    ax.add_patch(Circle((sx, sy), 1.35, fc=PALETTE["blue_fill"],
                        ec=PALETTE["blue_ink"], lw=0.9, zorder=6))
    box(ax, ix + 7.0, sy + 1.8, 9.0, 3.6, fc="neutral", ec="rule", lw=0.8, r=0.5, z=5)
    box(ax, ix + 7.0, sy - 5.4, 9.0, 3.6, fc="green_fill", ec="green_ink", lw=0.8, r=0.5, z=5)
    label(ax, ix + 11.5, sy + 3.6, "A  original", fs=8.8)
    label(ax, ix + 11.5, sy - 3.6, "D  candidate", fs=8.8)
    arrow(ax, (sx + 1.2, sy + 0.5), (ix + 7.0, sy + 3.6),
          color="muted", lw=1.0, ms=8)
    arrow(ax, (sx + 1.2, sy - 0.5), (ix + 7.0, sy - 3.6),
          color="green_ink", lw=1.0, ms=8)
    label(ax, ix + iw / 2, iy + 4.6, "n pairs\nwins − losses ≥ δ", fs=9.0,
          weight="bold", linespacing=1.05)
    label(ax, ix + iw / 2, iy + 1.6, "specialize / alternative\n/ reject", fs=8.0,
          color="muted", linespacing=1.05)


def graph_leaf(ax, cx, cy, text, fill="surface", border="blue_ink", ls="-"):
    box(ax, cx - 6, cy - 3, 12, 6, fc=fill, ec=border, lw=1.1, r=0.7, ls=ls, z=5)
    label(ax, cx, cy, text, fs=10.5, weight="bold")


def draw_graph(ax):
    box(ax, 64, 17, 72, 65, fc="surface", ec="ink", lw=1.5, r=1.8, z=1)
    label(ax, 66, 78.5, "Typed skill graph  $G_r$", fs=18, ha="left", weight="bold")
    label(ax, 66, 74.8, "Artifacts accumulate; code and skills are their projections",
          fs=11, color="muted", ha="left")

    # Original three-over-two edge legend, retained with the new palette.
    legend = [
        (66, 70.5, "call", "ink", "-"),
        (80, 70.5, "chain  (post ⊨ pre)", "blue_ink", (0, (4, 2))),
        (101, 70.5, "specialize | b", "green_ink", "-"),
        (66, 67.1, "alternative | b", "muted", "-"),
        (82, 67.1, "conflict | b", "rose_ink", "-"),
    ]
    for x, y, text, color, ls in legend:
        if text.startswith("alternative"):
            for dy in (-0.35, 0.35):
                ax.plot([x, x + 3.5], [y + dy, y + dy], color=PALETTE[color], lw=1.4, zorder=5)
        else:
            arrow(ax, (x, y), (x + 3.5, y), color=color, lw=1.8, ls=ls,
                  style="-" if text.startswith("conflict") else "-|>", ms=10)
            if text.startswith("conflict"):
                label(ax, x + 1.75, y, "×", fs=13, color=color, weight="bold")
        label(ax, x + 4.3, y, text, fs=9.2, ha="left",
              family="DejaVu Sans" if text.startswith("chain") else None)

    # A composite and its call edges to a five-leaf execution chain.
    box(ax, 89, 60, 22, 6.2, fc="blue_fill", ec="blue_ink", lw=1.6, r=0.8, z=5)
    label(ax, 100, 63.1, "pick_place", fs=12, weight="bold")
    label(ax, 134, 63.8, "P3 / P2 / P1 / P0", fs=9.2, ha="right", weight="bold")
    label(ax, 134, 61.0, "projections per artifact", fs=8.5, color="muted", ha="right")

    xs, y_leaf = [72, 86, 100, 114, 128], 49
    call_routes = [
        [(92, 60), (92, 56), (72, 56), (72, 52)],
        [(96, 60), (96, 54.5), (86, 54.5), (86, 52)],
        [(100, 60), (100, 52)],
        [(104, 60), (104, 54.5), (114, 54.5), (114, 52)],
        [(108, 60), (108, 56), (128, 56), (128, 52)],
    ]
    for points in call_routes:
        route(ax, points, color="ink", lw=1.0, ms=8, z=3)
    for name, x in zip(["Locate", "Approach", "Grasp", "Place", "Release"], xs):
        graph_leaf(ax, x, y_leaf, name)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, (a + 6, y_leaf), (b - 6, y_leaf), color="blue_ink",
              lw=1.1, ls=(0, (4, 2)), ms=8, z=6)

    # Grown variants and evidence-backed typed relations.
    graph_leaf(ax, 86, 38, "Approach′", fill="green_fill", border="green_ink")
    graph_leaf(ax, 100, 38, "Grasp′", fill="surface", border="muted", ls=(0, (4, 2)))
    arrow(ax, (86, 41), (86, 46), color="green_ink", lw=1.6, ms=10)
    label(ax, 78.5, 43.5, "$\\sqsubseteq$ | near-neighbor", fs=8.5, color="green_ink", weight="bold")
    for dx in (-0.4, 0.4):
        ax.plot([100 + dx, 100 + dx], [41, 46], color=PALETTE["muted"], lw=1.0, zorder=4)
    label(ax, 103, 43.5, "≈ | b", fs=9.0, color="muted", ha="left")
    route(ax, [(106, 38), (110, 38), (110, 43), (114, 43), (114, 46)],
          color="rose_ink", lw=1.2, style="-")
    label(ax, 110, 43, "×", fs=12, color="rose_ink", weight="bold")
    label(ax, 117, 38.8, "conflict in bucket b\nprunes retrieval", fs=8.3,
          color="rose_ink", ha="left")
    label(ax, 66, 32.8, "Variants enter the graph only through the evidence gate",
          fs=8.8, color="muted", ha="left")

    # Kernel is one restrained strip, not a second set of floating cards.
    kx, ky, kw, kh = 66, 19, 68, 10.5
    box(ax, kx, ky, kw, kh, fc="neutral", ec="rule", lw=1.0, r=0.8, z=2)
    label(ax, kx + 1.2, ky + kh - 2.0, "Kernel K", fs=9.5, ha="left", weight="bold")
    label(ax, kx + kw - 1.2, ky + kh - 2.0,
          "frozen within a series | new versions by humans",
          fs=8.5, color="muted", ha="right")
    ax.plot([kx + 1, kx + kw - 1], [ky + 5.4, ky + 5.4],
            color=PALETTE["rule"], lw=0.8, zorder=3)
    cells = ["Body API", "Perception\n+ planning", "Isolated\nworker",
             "Safety\nmonitor", "Evaluator", "Brain LLM"]
    cw = kw / len(cells)
    for i, text in enumerate(cells):
        if i:
            ax.plot([kx + i * cw, kx + i * cw], [ky + 0.9, ky + 4.9],
                    color=PALETTE["rule"], lw=0.7, zorder=3)
        label(ax, kx + (i + 0.5) * cw, ky + 2.7, text, fs=8.5)
    label(ax, 66, 30.8, "Leaves call only kernel primitives", fs=8.5,
          color="muted", ha="left")


def projection_node(ax, x, y, w, h, title, detail, fill):
    box(ax, x, y, w, h, fc=fill, ec="green_ink", lw=1.0, r=0.8)
    label(ax, x + w / 2, y + h - 2.2, title, fs=9.5, weight="bold")
    label(ax, x + w / 2, y + 1.85, detail, fs=9.2, color="muted")


def draw_root_down(ax):
    panel(ax, 144, 17, 54, 65, "Root Down", "Offline after each round | projection algorithm R",
          "green_panel", "green_rule")
    label(ax, 146, 71.0, "P3 and P2 are generated when the artifact is created",
          fs=9.0, color="muted", ha="left")

    projection_node(ax, 147, 62, 21.5, 7.2, "P3  Template", "brain decides steps", "yellow")
    projection_node(ax, 174.5, 62, 21.5, 7.2, "P2  Skill", "brain picks card", "blue_fill")
    projection_node(ax, 154, 50.5, 32, 7.2, "P1  Route", "bucket → node | spec. edge or k, p", "teal")
    projection_node(ax, 154, 38.5, 32, 7.2, "P0  Code", "mechanical compile | post monitors", "green_fill")
    route(ax, [(157.75, 62), (157.75, 60.2), (164, 60.2), (164, 57.7)],
          color="green_ink", lw=1.3, ms=9)
    route(ax, [(183.25, 62), (183.25, 60.2), (176, 60.2), (176, 57.7)],
          color="green_ink", lw=1.3, ms=9)
    arrow(ax, (170, 50.5), (170, 45.7), color="green_ink", lw=1.3, ms=9)
    label(ax, 172, 48.3, "fixed sequence\n+ evaluable post", fs=8.3, color="muted", ha="left")

    # Runtime fallback and offline demotion are different operations.
    route(ax, [(154, 42.1), (150, 42.1), (150, 65.6), (147, 65.6)],
          color="rose_ink", lw=1.1, ls=(0, (3, 2)), ms=9, z=3)
    label(ax, 146, 47.7, "monitor fails → P3", fs=8.8, color="rose_ink", ha="left")
    label(ax, 170, 36.3, "High failure rate: demote one level", fs=8.8,
          color="rose_ink")

    label(ax, 146, 33.8, "Validate before changing the frozen graph", fs=9.0,
          color="muted", ha="left")
    box(ax, 146, 26.2, 22.5, 6.0, fc="surface", ec="green_rule", lw=0.9, r=0.7)
    box(ax, 172.5, 26.2, 23.5, 6.0, fc="surface", ec="green_rule", lw=0.9, r=0.7)
    label(ax, 157.25, 30.4, "Equivalence replay", fs=9.5, weight="bold")
    label(ax, 157.25, 27.9, "drop failed item", fs=9.0, color="muted")
    label(ax, 184.25, 30.4, "Subgraph regression", fs=9.5, weight="bold")
    label(ax, 184.25, 27.9, "≤ 30 history tasks", fs=9.0, color="muted")
    arrow(ax, (168.5, 29.2), (172.5, 29.2), color="green_ink", lw=1.0, ms=8)

    box(ax, 146, 18.8, 22.5, 5.2, fc="green_fill", ec="green_ink", lw=0.9, r=0.7)
    box(ax, 172.5, 18.8, 23.5, 5.2, fc="rose", ec="rose_ink", lw=0.9, r=0.7)
    label(ax, 157.25, 21.4, "Freeze  $G_{r+1}$", fs=9.5, color="green_ink", weight="bold")
    label(ax, 184.25, 21.4, "Roll back to  $G_r$", fs=9.5, color="rose_ink", weight="bold")
    route(ax, [(181, 26.2), (181, 25.0), (157.25, 25.0), (157.25, 24.0)],
          color="green_ink", lw=1.0, ms=8)
    label(ax, 165, 25.0, "pass", fs=8.0, color="green_ink")
    arrow(ax, (185.5, 26.2), (185.5, 24.0), color="rose_ink", lw=1.0, ms=8)
    label(ax, 189, 25.0, "worse", fs=8.0, color="rose_ink")


def draw_links(ax):
    arrow(ax, (64, 69.5), (56, 69.5), color="blue_ink", lw=1.8, ms=12)
    label(ax, 60, 71.5, "pack", fs=9.5, color="blue_ink", weight="bold")
    arrow(ax, (56, 35.5), (64, 35.5), color="blue_ink", lw=1.8, ms=12)
    label(ax, 60, 37.5, "commit", fs=9.5, color="blue_ink", weight="bold")
    arrow(ax, (136, 69.5), (144, 69.5), color="green_ink", lw=1.8, ms=12)
    label(ax, 140, 71.5, "logs", fs=9.5, color="green_ink", weight="bold")
    arrow(ax, (144, 54), (136, 54), color="green_ink", lw=1.8, ms=12)
    label(ax, 140, 56, "routes", fs=9.5, color="green_ink", weight="bold")
    arrow(ax, (29, 87), (29, 82), color="violet_ink", lw=1.6, ms=11)
    label(ax, 31, 84.5, "update A", fs=9.5, color="violet_ink", ha="left", weight="bold")
    arrow(ax, (171, 87), (171, 82), color="violet_ink", lw=1.6, ms=11)
    label(ax, 173, 84.5, "update R", fs=9.5, color="violet_ink", ha="left", weight="bold")
    arrow(ax, (171, 17), (29, 17), color="muted", lw=1.7, ms=13, rad=-0.06)
    label(ax, 100, 11.0, "round  r  →  r + 1", fs=11, weight="bold")


def draw_footer(ax):
    ax.plot([2, 198], [7.4, 7.4], color=PALETTE["rule"], lw=0.8)
    label(ax, 2, 3.8, "Curriculum: TP03 / TP04 → TP05 gather → TP06 sort",
          fs=10.5, ha="left")
    label(ax, 100, 3.8, "Same-budget baselines: A_static | A_single | A_voyager | A_ours",
          fs=10.5)
    label(ax, 198, 3.8, "MuJoCo | G1 + 2× Dex3-1 | simulation only",
          fs=10.5, color="muted", ha="right")


def main(out_dir):
    fig = plt.figure(figsize=(20, 11.25), facecolor=PALETTE["paper"])
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 112.5)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.add_patch(plt.Rectangle((0, 0), 200, 112.5, fc=PALETTE["paper"], ec="none", zorder=-10))

    label(ax, 2, 107.0, "Grow Up / Root Down / Revise", fs=24, ha="left", weight="bold")
    label(ax, 2, 102.9, "Artifacts accumulate as typed skills and shift toward lower-cost execution.",
          fs=11.3, color="muted", ha="left")
    draw_revise(ax)
    draw_grow_up(ax)
    draw_graph(ax)
    draw_root_down(ax)
    draw_links(ax)
    draw_footer(ax)

    os.makedirs(out_dir, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(out_dir, f"overview.{ext}"), dpi=300,
                    facecolor=PALETTE["paper"])
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
