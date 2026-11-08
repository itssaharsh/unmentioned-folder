"""Aggregate every logged episode in runs/ into per-agent rows and per (model, condition) rates with
episode-level bootstrap 95% intervals. Writes results/agents.csv and results/summary.json.

Usage: uv run python -m analysis.aggregate
"""

from __future__ import annotations

import glob
import gzip
import json
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd

from analysis.metrics import agent_measures

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
OUT = ROOT / "results"

MODEL_ORDER = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "openai/gpt-5-nano", "openai/gpt-4.1-mini",
               "google/gemini-2.5-flash-lite", "deepseek-ai/DeepSeek-V4-Pro", "claude-haiku-4-5", "claude-haiku-5-5",
               "claude-sonnet-5-5"]
COND_ORDER = ["isolated", "hidden+answers", "linked+answers", "mentioned+answers", "mentioned+answers+rule",
              "mentioned+invite", "mentioned"]
RATES = ["touched", "read_note", "copied_any", "copied_unverified_any", "adopted_wrong", "wrote", "posted_answers"]


def load_rows() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(RUNS / "*.json.gz"))):
        ep = json.load(gzip.open(f, "rt"))
        for a in ep["agents"]:
            m = agent_measures(ep, a)
            # the same Gemini model reached through Google's endpoint or the Vercel gateway is one model
            model = ep["model"].replace("gemini-direct/", "google/").replace("featherless/", "")
            m.update({"model": model, "route": ep["model"], "condition": ep["condition"], "seed": ep["seed"],
                      "episode": Path(f).name, "copied_any": m["copied"] > 0,
                      "copied_unverified_any": m["copied_unverified"] > 0,
                      "accuracy": m["n_correct"] / len(ep["questions"]),
                      "planted": ep.get("planted") is not None})
            rows.append(m)
    return pd.DataFrame(rows)


def boot_ci(groups: list[list[float]], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Cluster bootstrap: resample episodes, pool their agents."""
    rng = random.Random(seed)
    if len(groups) < 2:
        return (float("nan"), float("nan"))
    stats = []
    for _ in range(n):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        flat = [x for g in pick for x in g]
        stats.append(sum(flat) / len(flat))
    stats.sort()
    return stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def summarise(df: pd.DataFrame) -> list[dict]:
    out = []
    for (model, cond), g in df.groupby(["model", "condition"]):
        rec = {"model": model, "condition": cond, "n_agents": int(len(g)), "n_episodes": int(g["episode"].nunique())}
        for k in RATES + ["accuracy"]:
            if k == "adopted_wrong" and not g["planted"].any():
                continue
            groups = [list(map(float, eg[k])) for _, eg in g.groupby("episode")]
            mean = float(g[k].astype(float).mean())
            lo, hi = boot_ci(groups)
            rec[k] = {"mean": round(mean, 4), "lo": round(lo, 4), "hi": round(hi, 4),
                      "count": int(g[k].astype(float).sum()) if k != "accuracy" else None}
        # adoption among agents who actually read the planted note
        if g["planted"].any():
            readers = g[g["read_note"]]
            rec["adopted_wrong_given_read"] = {"count": int(readers["adopted_wrong"].sum()), "of": int(len(readers))}
            rec["copied_given_read"] = {"count": int(readers["copied_any"].sum()), "of": int(len(readers))}
            rec["unverified_given_read"] = {"count": int(readers["copied_unverified_any"].sum()),
                                            "of": int(len(readers))}
            rec["caught_given_read"] = {"count": int(readers["caught_planted"].sum()), "of": int(len(readers))}
        out.append(rec)
    key = lambda r: (MODEL_ORDER.index(r["model"]) if r["model"] in MODEL_ORDER else 99,
                     COND_ORDER.index(r["condition"]) if r["condition"] in COND_ORDER else 99)
    return sorted(out, key=key)


def main():
    OUT.mkdir(exist_ok=True)
    df = load_rows()
    df.drop(columns=[]).to_csv(OUT / "agents.csv", index=False)
    summ = summarise(df)
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    tok = df.groupby("model")[["tok_in", "tok_out"]].sum()
    print(f"{len(df)} agents, {df['episode'].nunique()} episodes")
    print(tok)
    for r in summ:
        cells = " ".join(f"{k}={r[k]['mean']:.2f}" for k in RATES + ["accuracy"] if k in r)
        print(f"{r['model']:<20}{r['condition']:<24}n={r['n_agents']:<4}{cells}")


if __name__ == "__main__":
    main()
