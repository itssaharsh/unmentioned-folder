"""Figures and tables for the report, from results/agents.csv (written by analysis.aggregate).

Usage: uv run python -m analysis.figures
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = ROOT / "report" / "figures"

INK, MUTED, RED, BLUE, GOLD, GREEN = "#1d1d1f", "#6b6b70", "#c8102e", "#2f5d9e", "#c99a2e", "#2e7d4f"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 200})

SHORT = {"claude-haiku-4-5": "Claude Haiku 4.5", "claude-haiku-5-5": "Claude Haiku 5.5",
         "claude-sonnet-5-5": "Claude Sonnet 5.5", "openai/gpt-oss-120b": "gpt-oss-120b",
         "openai/gpt-5-nano": "GPT-5 nano", "openai/gpt-4.1-mini": "GPT-4.1 mini",
         "google/gemini-2.5-flash-lite": "Gemini 2.5 Flash-Lite", "openai/gpt-oss-20b": "gpt-oss-20b", "deepseek-ai/DeepSeek-V4-Pro": "DeepSeek V4 Pro"}
MAIN_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "openai/gpt-5-nano", "google/gemini-2.5-flash-lite"]
MODEL_COLORS = {"openai/gpt-oss-120b": BLUE, "openai/gpt-oss-20b": "#8fb3e0", "openai/gpt-5-nano": GOLD, "google/gemini-2.5-flash-lite": GREEN,
                "openai/gpt-4.1-mini": "#7a4fa0"}


def ci(df: pd.DataFrame, col: str, n: int = 2000, seed: int = 0):
    groups = [g[col].astype(float).tolist() for _, g in df.groupby("episode")]
    mean = float(df[col].astype(float).mean()) if len(df) else float("nan")
    if len(groups) < 2:
        return mean, mean, mean
    rng = random.Random(seed)
    stats = []
    for _ in range(n):
        pick = [x for _ in groups for x in groups[rng.randrange(len(groups))]]
        stats.append(sum(pick) / len(pick))
    stats.sort()
    return mean, stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def grouped(ax, df, conds, col, models, labels, ylabel, title):
    w = 0.8 / len(models)
    for i, m in enumerate(models):
        xs, ys, los, his = [], [], [], []
        for j, c in enumerate(conds):
            sub = df[(df.model == m) & (df.condition == c)]
            if not len(sub):
                continue
            mean, lo, hi = ci(sub, col)
            xs.append(j + (i - (len(models) - 1) / 2) * w)
            ys.append(mean)
            los.append(mean - lo)
            his.append(hi - mean)
        ax.bar(xs, ys, w * 0.92, color=MODEL_COLORS.get(m, MUTED), label=SHORT.get(m, m))
        ax.errorbar(xs, ys, yerr=[los, his], fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
    ax.set_xticks(range(len(conds)))
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontsize=9.5, color=INK, fontweight="bold")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RES / "agents.csv")
    models = [m for m in MAIN_MODELS + ["openai/gpt-4.1-mini"] if m in set(df.model)]

    # Figure 1: the exposure ladder (did the agent open the folder at all?)
    fig, ax = plt.subplots(figsize=(6.6, 2.5))
    conds = ["hidden+answers", "linked+answers", "mentioned+answers"]
    grouped(ax, df, conds, "read_note", models,
            ["hidden\n(/mnt/shared only)", "linked\n(shared/ in home dir)", "mentioned\n(one line in task file)"],
            "agents who read the note", "How visible must the folder be before agents read it?")
    ax.legend(frameon=False, fontsize=7.5, ncol=len(models), loc="upper left")
    fig.tight_layout()
    fig.savefig(FIG / "fig1_exposure.pdf")
    fig.savefig(FIG / "fig1_exposure.png")
    plt.close(fig)

    # Figure 2: what readers did with the note (no rule vs rule), mentioned exposure
    readers = df[df.read_note & df.condition.isin(["mentioned+answers", "mentioned+answers+rule", "linked+answers"])]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5), sharey=True)
    for ax, col, title in [(axes[0], "copied_unverified_any", "Submitted a note answer they never checked"),
                           (axes[1], "adopted_wrong", "Submitted the planted wrong answer")]:
        grouped(ax, readers, ["mentioned+answers", "mentioned+answers+rule"], col, models,
                ["no rule", "'work independently'"], "share of note readers", title)
    axes[0].legend(frameon=False, fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIG / "fig2_trust.pdf")
    fig.savefig(FIG / "fig2_trust.png")
    plt.close(fig)

    # Table 1 (LaTeX): model x condition
    rows = []
    order = ["isolated", "hidden+answers", "linked+answers", "mentioned+answers", "mentioned+answers+rule",
             "mentioned+invite", "mentioned"]
    for m in [x for x in SHORT if x in set(df.model)]:
        for c in order:
            sub = df[(df.model == m) & (df.condition == c)]
            if not len(sub):
                continue
            f = lambda col: f"{100 * sub[col].astype(float).mean():.0f}"
            planted = c.endswith("answers") or c.endswith("answers+rule")
            rows.append([SHORT[m], c.replace("+", " + "), str(len(sub)), str(sub.episode.nunique()),
                         f("touched"), f("read_note"), f("copied_unverified_any") if planted else "--",
                         f("adopted_wrong") if planted else "--", f("wrote"), f"{sub.accuracy.mean():.2f}"])
    tex = ["\\begin{tabular}{llrrrrrrrr}", "\\toprule",
           "Model & Condition & $n$ & ep. & Opened & Read & Copied & Planted & Wrote & Acc. \\\\",
           " & & agents & & folder \\% & note \\% & unverif. \\% & wrong \\% & \\% & \\\\", "\\midrule"]
    last = None
    for r in rows:
        if last and r[0] != last:
            tex.append("\\midrule")
        tex.append(" & ".join([r[0] if r[0] != last else ""] + r[1:]) + " \\\\")
        last = r[0]
    tex += ["\\bottomrule", "\\end{tabular}"]
    (RES / "table1.tex").write_text("\n".join(tex))
    print("figures and table written")


if __name__ == "__main__":
    main()


def timeline(path: str, out: str = "fig3_timeline"):
    """One episode as a strip per agent: lookups, folder visits, note reads, and the submission."""
    import gzip as _gz

    from analysis.metrics import agent_measures

    ep = json.load(_gz.open(path, "rt"))
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    n = len(ep["agents"])
    for i, a in enumerate(ep["agents"]):
        y = n - i
        m = agent_measures(ep, a)
        ts = [e["t"] for e in a["events"]]
        if ts:
            ax.plot([min(ts), max(ts)], [y, y], color="#d9d9de", lw=1, zorder=1)
        for e in a["events"]:
            if e["kind"] != "tool":
                continue
            if e["tool"] in ("search", "open_doc"):
                ax.scatter(e["t"], y, s=6, color=MUTED, zorder=2)
            elif e.get("shared") and e["tool"] == "read_file":
                ax.scatter(e["t"], y, s=34, marker="s", color=GOLD, edgecolor=INK, lw=0.4, zorder=3)
            elif e.get("shared") and e["tool"] == "write_file":
                ax.scatter(e["t"], y, s=34, marker="^", color=BLUE, edgecolor=INK, lw=0.4, zorder=3)
            elif e.get("shared"):
                ax.scatter(e["t"], y, s=18, marker="o", facecolor="none", edgecolor=GOLD, lw=0.8, zorder=3)
            elif e["tool"] == "submit":
                c = RED if m["adopted_wrong"] else INK
                ax.scatter(e["t"], y, s=40, marker="X" if m["adopted_wrong"] else "D", color=c, zorder=4)
        ax.text(-2, y, f"{a['rid']}  w{a['wave'] + 1}", ha="right", va="center", fontsize=6.5, color=MUTED)
    ax.set_yticks([])
    ax.set_xlabel("seconds since the episode started")
    ax.spines["left"].set_visible(False)
    title = f"{SHORT.get(ep['model'], ep['model'])}, {ep['condition']}, seed {ep['seed']}"
    ax.set_title(title, loc="left", fontsize=9, fontweight="bold")
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker="o", ls="", color=MUTED, ms=3, label="lookup"),
         Line2D([], [], marker="o", ls="", mfc="none", mec=GOLD, ms=5, label="looked in folder"),
         Line2D([], [], marker="s", ls="", color=GOLD, ms=5, label="read the note"),
         Line2D([], [], marker="^", ls="", color=BLUE, ms=5, label="wrote to folder"),
         Line2D([], [], marker="D", ls="", color=INK, ms=4, label="submitted"),
         Line2D([], [], marker="X", ls="", color=RED, ms=6, label="submitted planted wrong answer")]
    ax.legend(handles=h, frameon=False, fontsize=6.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    fig.savefig(FIG / f"{out}.pdf")
    fig.savefig(FIG / f"{out}.png")
    plt.close(fig)


def waves(df: pd.DataFrame, models: list[str], out: str = "fig4_waves"):
    """Accuracy by wave: does the folder make later agents better than earlier ones?"""
    conds = [("isolated", "no folder (control)", MUTED, "o"), ("encouraged", "empty folder", "#9a9aa0", "v"),
             ("encouraged+invite", "folder with an invitation (no answers)", RED, "s"),
             ("encouraged+answers", "folder with the planted note", GOLD, "D")]
    fig, axes = plt.subplots(1, len(models), figsize=(6.6, 2.4), sharey=True, squeeze=False)
    for ax, m in zip(axes[0], models):
        for c, label, color, mk in conds:
            sub = df[(df.model == m) & (df.condition == c)]
            if not len(sub):
                continue
            xs, ys, lo, hi = [], [], [], []
            for w in range(4):
                sw = sub[sub.wave == w]
                if not len(sw):
                    continue
                mean, l, h = ci(sw, "accuracy")
                xs.append(w + 1)
                ys.append(mean)
                lo.append(mean - l)
                hi.append(h - mean)
            ax.errorbar(xs, ys, yerr=[lo, hi], color=color, marker=mk, ms=4, lw=1.4, capsize=2,
                        label=f"{label} (n={sub.episode.nunique()} ep.)" if m == models[0] else None)
        ax.set_title(SHORT.get(m, m), loc="left", fontsize=9, fontweight="bold")
        ax.set_xticks([1, 2, 3, 4])
        ax.set_xlabel("wave (3 agents each, in order)")
        ax.set_ylim(0, 1.05)
    axes[0][0].set_ylabel("accuracy (of 4 questions)")
    fig.legend(frameon=False, fontsize=7, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    fig.savefig(FIG / f"{out}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{out}.png", bbox_inches="tight")
    plt.close(fig)
