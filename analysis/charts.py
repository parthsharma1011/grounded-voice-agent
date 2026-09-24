from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, PathPatch
from matplotlib.path import Path as MPath

from analysis import settings
from analysis.settings import BOX_FILL, GRID, INK, MUTED, PALE_BLUE, RULE
from analysis.settings import BLUE as ACCENT
from analysis.settings import CONDITION_COLORS as COND
from analysis.settings import CONDITION_NAMES as NAME
from analysis.settings import INK_SECONDARY as INK2

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "thesis" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
S = json.load(open(HERE / "output" / "stats.json"))
A = json.load(open(HERE / "output" / "audit_stats.json"))

DPI = settings.DPI

N_QUESTIONS = {name: S[name]["n_scenarios"] for name in settings.SET_NAMES}
N_ANSWERS = sum(S[name]["n_rows"] for name in settings.SET_NAMES)
N_FLAGS = sum(S[name]["rates"][c]["failures"] for name in settings.SET_NAMES for c in settings.LABELS)
N_TRAP_ANSWERS = sum(A["trap_audit"][c]["n"] for c in settings.LABELS)

plt.rcParams.update({
    "font.family": settings.FONT_FAMILY,
    "font.size": settings.FONT_SIZE,
    "axes.edgecolor": RULE,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.titlesize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def _lum(hexc):
    h = hexc.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def on(fill):
    lf = _lum(fill)
    white = (1.05) / (lf + 0.05)
    ink = (lf + 0.05) / (_lum(INK) + 0.05)
    return "white" if white >= ink else INK


def clean(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(RULE)
    ax.spines["bottom"].set_color(RULE)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(length=0)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)


def rounded_bar(ax, x0, width, y0, height, color, r_pt=2.2):
    fig = ax.figure
    fig.canvas.draw()
    bb = ax.get_window_extent()
    xl, yl = ax.get_xlim(), ax.get_ylim()
    ppx = bb.width / (xl[1] - xl[0])
    ppy = bb.height / (yl[1] - yl[0])
    r_px = r_pt * fig.dpi / 72
    rx, ry = r_px / ppx, r_px / ppy
    k = 0.5523
    x1, y1 = x0 + width, y0 + height
    ry = min(ry, abs(height) / 2)
    rx = min(rx, width / 2)
    verts = [(x0, y0), (x0, y1 - ry), (x0, y1 - ry + k * ry), (x0 + rx - k * rx, y1), (x0 + rx, y1),
             (x1 - rx, y1), (x1 - rx + k * rx, y1), (x1, y1 - ry + k * ry), (x1, y1 - ry), (x1, y0), (x0, y0)]
    codes = [MPath.MOVETO, MPath.LINETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4,
             MPath.LINETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4, MPath.LINETO, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none", zorder=3))


def legend_row(fig, items, y=0.955, x0=0.08):
    x = x0
    for label, color in items:
        fig.patches.append(FancyBboxPatch((x, y - 0.012), 0.016, 0.024, boxstyle="round,pad=0,rounding_size=0.004",
                                          transform=fig.transFigure, facecolor=color, edgecolor="none"))
        fig.text(x + 0.024, y, label, va="center", ha="left", fontsize=9, color=INK2)
        x += 0.024 + 0.0105 * len(label) + 0.04


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI)
    plt.close(fig)
    print("wrote", name)


def chart_rates():
    fig, ax = plt.subplots(figsize=(settings.CHART_WIDTH, 3.3))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.86, bottom=0.14)
    groups = [(name, f"{label} ({N_QUESTIONS[name]} questions)") for name, label in settings.SET_NAMES.items()]
    bw = 0.2
    ax.set_xlim(-0.5, 1.5)
    ax.set_ylim(0, 100)
    clean(ax)
    y_ticks = list(range(0, 101, 20))
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([f"{v}%" for v in y_ticks])
    ax.set_ylabel("Answers scored grounded")
    for gi, (key, label) in enumerate(groups):
        for ci, c in enumerate(settings.LABELS):
            r = S[key]["rates"][c]
            x = gi + (ci - 1) * (bw + 0.035) - bw / 2
            rounded_bar(ax, x, bw, 0, r["rate"], COND[c])
            lo, hi = r["wilson"]
            ax.plot([x + bw / 2] * 2, [lo, hi], color=INK, linewidth=0.9, zorder=4)
            for yy in (lo, hi):
                ax.plot([x + bw / 2 - 0.025, x + bw / 2 + 0.025], [yy, yy], color=INK, linewidth=0.9, zorder=4)
            ax.text(x + bw / 2, 3.5, f"{r['rate']:.1f}", ha="center", va="bottom", fontsize=8.5,
                    color=on(COND[c]), fontweight="bold", zorder=5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g[1] for g in groups], color=INK2)
    legend_row(fig, [(NAME[c], COND[c]) for c in COND])
    fig.text(0.98, 0.955, "Whiskers: 95% Wilson interval", ha="right", va="center", fontsize=8, color=MUTED)
    save(fig, "chart1_rates.png")


def chart_sensitivity():
    fig, ax = plt.subplots(figsize=(settings.CHART_WIDTH, 2.7))
    fig.subplots_adjust(left=0.24, right=0.70, top=0.80, bottom=0.2)
    conds = settings.LABELS[::-1]
    points = {c: (S["hard"]["rates"][c]["rate"], A["hard_sensitivity"]["conservative"][c]["rate"],
                  A["hard_two_sided"][c]["rate"]) for c in conds}
    x_min = 5 * math.floor((min(min(p) for p in points.values()) - 1) / 5)
    x_ticks = list(range(x_min, 101, 5))
    clean(ax, grid_axis="x")
    ax.set_xlim(x_min, 100)
    ax.set_ylim(-0.6, 2.6)
    for i, c in enumerate(conds):
        a, b, d = points[c]
        lo, hi = min(a, b, d), max(a, b, d)
        ax.plot([lo, hi], [i, i], color=RULE, linewidth=2, zorder=2, solid_capstyle="round")
        ax.scatter([a], [i], s=46, facecolor="white", edgecolor=COND[c], linewidth=2, zorder=3)
        ax.scatter([b], [i], s=46, color=COND[c], edgecolor="white", linewidth=1.5, zorder=4)
        ax.scatter([d], [i], s=58, marker="D", color=INK2, edgecolor="white", linewidth=1.2, zorder=5)
        fig.text(0.72, ax.transData.transform((0, i))[1] / fig.bbox.height,
                 f"{a:.1f}  /  {b:.1f}  /  {d:.1f}", va="center", ha="left", fontsize=8.5, color=INK)
    ax.set_yticks(range(3))
    ax.set_yticklabels([NAME[c] for c in conds], color=INK2)
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([f"{v}%" for v in x_ticks])
    ax.set_xlabel("Grounded-answer rate, hard set")
    fig.text(0.72, 0.84, "as scored / errors cleared /\ninventions also failed (%)", fontsize=7.8, color=MUTED, va="center")
    fig.text(0.24, 0.95, "Hollow: as scored.   Filled: scorer errors cleared.   Diamond: inventions also failed.",
             fontsize=7.6, color=MUTED, va="center")
    save(fig, "chart2_sensitivity.png")


def box(ax, x, y, w, h, text, fill=BOX_FILL, edge=RULE, weight="normal", size=8.6, color=INK, lw=0.9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                facecolor=fill, edgecolor=edge, linewidth=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color,
            fontweight=weight, zorder=3, linespacing=1.25)


def arrow(ax, x0, y0, x1, y1, color=MUTED, lw=1.1, style="-|>", ls="-"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, linestyle=ls,
                                shrinkA=0, shrinkB=0, mutation_scale=9), zorder=1)


def canvas(w, h, xmax, ymax):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def fig_pipeline():
    fig, ax = canvas(settings.DIAGRAM_WIDTH, 3.3, 16, 8.2)
    fs = 7.7
    box(ax, 0.1, 3.3, 1.7, 1.5, "Caller\non a phone", size=fs)
    box(ax, 2.2, 3.3, 2.2, 1.5, "Twilio SIP trunk\n+ LiveKit room", size=fs)
    box(ax, 4.9, 5.4, 3.1, 1.6, "Speech to text\nDeepgram nova-3\n+ VAD, turn detector", size=fs)
    box(ax, 4.9, 1.1, 3.1, 1.6, "Text to speech\nCartesia Sonic", size=fs)
    box(ax, 8.9, 3.1, 3.3, 1.9, f"Language model\n{settings.MODEL_NAME}\nsystem prompt +\ngrounding strategy",
        fill=PALE_BLUE, edge=ACCENT, weight="bold", size=fs)
    box(ax, 12.9, 3.1, 3.0, 1.9, "Function tools\nsearch, availability,\ncoverage, booking", size=fs)
    box(ax, 12.9, 0.35, 3.0, 1.6, "Knowledge base\nlistings, restaurant,\nclinic data", size=fs)
    arrow(ax, 1.8, 4.05, 2.2, 4.05)
    arrow(ax, 4.4, 4.4, 4.9, 5.9)
    arrow(ax, 8.0, 6.2, 10.55, 5.0)
    arrow(ax, 10.55, 3.1, 8.0, 1.9)
    arrow(ax, 4.9, 1.9, 4.4, 3.3)
    arrow(ax, 12.2, 4.3, 12.9, 4.3)
    arrow(ax, 12.9, 3.75, 12.2, 3.75)
    arrow(ax, 14.4, 3.1, 14.4, 1.95)
    ax.text(12.55, 4.5, "call", ha="center", fontsize=7.2, color=INK2)
    ax.text(12.55, 3.35, "result", ha="center", fontsize=7.2, color=INK2)
    ax.add_patch(FancyBboxPatch((8.65, 0.15), 7.3, 5.6, boxstyle="round,pad=0,rounding_size=0.2",
                                facecolor="none", edgecolor=ACCENT, linewidth=1.1, linestyle=(0, (4, 3)), zorder=0))
    ax.text(8.85, 6.55, "Where grounding is decided:\nthe experiment isolates this loop", fontsize=7.8, color=ACCENT, va="center")
    save(fig, "figure1_pipeline.png")


def fig_conditions():
    fig, ax = canvas(settings.DIAGRAM_WIDTH, 4.1, 16, 10.4)
    lanes = [
        ("P1  Prompt only", 7.6, [("Caller\nturn", 1.4), ("LLM\ntool choice: auto", 2.5), ("Tools\n(if the model\nchooses)", 2.2),
                                    ("Free prose\nreply", 2.0)]),
        ("P2  Cited schema", 4.3, [("Caller\nturn", 1.4), ("LLM\ntool choice: auto", 2.5), ("Tools\n(if the model\nchooses)", 2.2),
                                     ("JSON reply:\nspoken_reply +\nclaims[fact, source]", 2.6)]),
        ("P3  Forced + verified", 1.0, [("Caller\nturn", 1.4), ("LLM\ntool choice:\nrequired", 2.2), ("Tools\n(always,\nfirst round)", 1.9),
                                          ("Draft\n(same JSON)", 1.8), ("Verify pass:\ndraft vs tool\nresults", 2.1), ("Final\nreply", 1.4)]),
    ]
    for title, y, steps in lanes:
        ax.text(0.2, y + 2.0, title, fontsize=9.2, color=INK, fontweight="bold", va="center")
        x = 0.2
        prev = None
        for text, w in steps:
            hl = "Verify" in text or "required" in text
            box(ax, x, y, w, 1.6, text, fill=PALE_BLUE if hl else BOX_FILL, edge=ACCENT if hl else RULE, size=7.9)
            if prev is not None:
                arrow(ax, prev, y + 0.8, x, y + 0.8)
            prev = x + w
            x += w + 0.55
    ax.text(15.8, 9.6, "Same model, tools and persona prompt in all three; P2 and P3 add the format addendum", fontsize=8, color=MUTED, ha="right")
    save(fig, "figure2_conditions.png")


def fig_conceptual():
    fig, ax = canvas(settings.DIAGRAM_WIDTH, 3.4, 16, 8.4)
    box(ax, 0.2, 3.0, 3.4, 2.4, "Grounding strategy\n(independent variable)\n\nP1 prompt only\nP2 cited schema\nP3 forced + verified",
        fill=PALE_BLUE, edge=ACCENT, size=8.2)
    box(ax, 5.0, 5.4, 4.6, 1.6, "Lookup made when needed\n(tool call present)", size=8.2)
    box(ax, 5.0, 3.3, 4.6, 1.6, "Claims declared\n(tagged with a source tool)", size=8.2)
    box(ax, 5.0, 1.2, 4.6, 1.6, "Declared claims checked\nagainst tool output", size=8.2)
    box(ax, 11.2, 3.9, 4.6, 2.2, "Outcomes\n\nGrounded-answer rate (primary)\nFailure type\nLatency (cost)", size=8.2)
    box(ax, 11.2, 0.6, 4.6, 2.2, "Moderators\n\nQuestion difficulty (golden / hard)\nDomain (real estate, restaurant,\nhealthcare)", size=8.0)
    for yy in (6.2, 4.1, 2.0):
        arrow(ax, 3.6, 4.2, 5.0, yy)
        arrow(ax, 9.6, yy, 11.2, 5.0)
    arrow(ax, 13.5, 2.8, 13.5, 3.9, ls=(0, (3, 2)))
    ax.text(0.2, 7.8, f"Controls held fixed: model ({settings.MODEL_NAME}), tools, system prompts, scenarios, scorer",
            fontsize=8, color=MUTED)
    save(fig, "figure3_conceptual.png")


def fig_process():
    fig, ax = canvas(settings.DIAGRAM_WIDTH, 2.5, 16, 6.2)
    w, gap = 2.8, 0.45
    labels = [
        f"Scenario design\n\n{N_QUESTIONS['golden']} golden +\n{N_QUESTIONS['hard']} hard questions\nwith ground truth",
        f"Experiment runner\n\n{len(settings.LABELS)} conditions x {sum(N_QUESTIONS.values())}\n= {N_ANSWERS} answers\n"
        "text layer, live model",
        "Deterministic scorer\n\nlookup rule +\nnumber tracing +\nsafety rules",
        "Statistics\n\nWilson, Cochran's Q,\nexact McNemar,\nHolm, Newcombe",
        f"Audit\n\n{N_FLAGS} flags +\n{N_TRAP_ANSWERS} trap answers\nread by hand",
    ]
    xs = [0.1 + i * (w + gap) for i in range(len(labels))]
    for text, x in zip(labels, xs):
        box(ax, x, 1.5, w, 3.5, text, size=7.6)
    for i in range(len(xs) - 1):
        arrow(ax, xs[i] + w, 3.25, xs[i + 1], 3.25)
    cx_audit, cx_scorer = xs[4] + w / 2, xs[2] + w / 2
    arrow(ax, cx_audit, 1.5, cx_audit, 0.75, ls=(0, (3, 2)))
    arrow(ax, cx_audit, 0.75, cx_scorer, 0.75, ls=(0, (3, 2)))
    arrow(ax, cx_scorer, 0.75, cx_scorer, 1.5, ls=(0, (3, 2)))
    ax.text((cx_audit + cx_scorer) / 2, 0.22, "audit findings feed back as a sensitivity analysis on the scorer",
            ha="center", fontsize=7.4, color=MUTED)
    save(fig, "figure4_process.png")


if __name__ == "__main__":
    chart_rates()
    chart_sensitivity()
    fig_pipeline()
    fig_conditions()
    fig_conceptual()
    fig_process()
