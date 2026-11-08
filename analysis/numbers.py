"""Write report/numbers.tex: every number quoted in the report text, computed from results/agents.csv and the
real-board statistics, as LaTeX macros. The report never types a result by hand.

Usage: uv run python -m analysis.numbers
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analysis.figures import SHORT, ci

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

KEYS = {"claude-haiku-4-5": "HaikuFour", "claude-haiku-5-5": "HaikuFive", "claude-sonnet-5-5": "Sonnet",
        "openai/gpt-oss-120b": "OssBig", "openai/gpt-oss-20b": "OssSmall", "openai/gpt-5-nano": "Nano",
        "openai/gpt-4.1-mini": "FourOneMini", "google/gemini-2.5-flash-lite": "Gemini",
        "deepseek-ai/DeepSeek-V4-Pro": "DeepSeek"}
CONDS = {"isolated": "Iso", "hidden+answers": "Hid", "linked+answers": "Lnk", "mentioned+answers": "Men",
         "encouraged+answers": "Enc", "encouraged+answers+rule": "EncRule", "encouraged": "Empty",
         "encouraged+invite": "Inv", "encouraged+invite+rule": "InvRule", "mentioned+invite": "MenInv"}


def pct(x: float) -> str:
    return f"{100 * x:.0f}\\%"


def main():
    df = pd.read_csv(RES / "agents.csv")
    out = []

    def define(name: str, value):
        out.append(f"\\newcommand{{\\{name}}}{{{value}}}")

    models = [m for m in KEYS if m in set(df.model)]
    define("nmodels", len(models))
    define("nagents", f"{len(df):,}")
    define("nepisodes", df.episode.nunique())
    define("modellist", ", ".join(SHORT.get(m, m) for m in models))

    # per model x condition: rates (percent), k/n and intervals
    for m in models:
        for c, ck in CONDS.items():
            sub = df[(df.model == m) & (df.condition == c)]
            if not len(sub):
                continue
            base = f"{KEYS[m]}{ck}"
            define(f"n{base}", len(sub))
            for col, ab in [("touched", "Open"), ("read_note", "Read"), ("copied_unverified_any", "Unver"),
                            ("adopted_wrong", "Wrong"), ("wrote", "Wrote"), ("accuracy", "Acc")]:
                mean, lo, hi = ci(sub, col)
                define(f"{ab}{base}", pct(mean))
                define(f"{ab}{base}CI", f"[{pct(lo)}, {pct(hi)}]")
            readers = sub[sub.read_note]
            if len(readers) and c.endswith(("answers", "answers+rule")):
                define(f"UnverRead{base}", f"{int(readers.copied_unverified_any.sum())}/{len(readers)}")
                define(f"WrongRead{base}", f"{int(readers.adopted_wrong.sum())}/{len(readers)}")
            # accuracy by wave
            for w in range(4):
                sw = sub[sub.wave == w]
                if len(sw):
                    define(f"Acc{base}W{'ABCD'[w]}", pct(sw.accuracy.mean()))

    # pooled facts
    hid = df[df.condition == "hidden+answers"]
    define("hiddenOpened", f"{int(hid.touched.sum())}")
    define("hiddenN", f"{len(hid)}")
    define("hiddenModels", hid.model.nunique())
    emp = df[df.condition == "encouraged"]
    define("emptyWrote", f"{int(emp.wrote.sum())}")
    define("emptyN", f"{len(emp)}")

    # planted-answer adoption among readers, by how costly the planted question is to check
    import gzip
    kinds = {}
    for ep in df.episode.unique():
        e = json.load(gzip.open(ROOT / "runs" / ep, "rt"))
        if e.get("planted"):
            q = next(q for q in e["questions"] if q["id"] == e["planted"]["qid"])
            kinds[ep] = q["cost"]
    df["planted_cost"] = df.episode.map(kinds)
    readers = df[df.read_note & df.planted_cost.notna()]
    rows = []
    for m in models + ["all"]:
        r = readers if m == "all" else readers[readers.model == m]
        for cost, tag in [(4, "Costly"), (3, "Cheap")]:
            rc = r[r.planted_cost == cost]
            key = "All" if m == "all" else KEYS[m]
            if len(rc):
                define(f"Adopt{tag}{key}", f"{int(rc.adopted_wrong.sum())}/{len(rc)}")
                define(f"AdoptPct{tag}{key}", pct(rc.adopted_wrong.mean()))
                define(f"Caught{tag}{key}", f"{int(rc.caught_planted.sum())}/{len(rc)}")
                rows.append({"model": m, "cost": cost, "readers": len(rc), "adopted": int(rc.adopted_wrong.sum()),
                             "caught": int(rc.caught_planted.sum())})
    (RES / "adoption_by_cost.json").write_text(json.dumps(rows, indent=1))

    mech = RES / "mechanism.json"
    if mech.exists():
        mj = json.loads(mech.read_text())
        claude = ["claude-haiku-4-5", "claude-haiku-5-5", "claude-sonnet-5-5"]
        for m, d in mj["checked_by_cost"].items():
            if m in KEYS:
                for cost, tag in (("3", "Cheap"), ("4", "Costly")):
                    if cost in d and d[cost]["of"]:
                        define(f"Checked{tag}{KEYS[m]}", f"{d[cost]['checked']}/{d[cost]['of']}")
                        define(f"CheckedPct{tag}{KEYS[m]}", pct(d[cost]["checked"] / d[cost]["of"]))
        for cost, tag in (("3", "Cheap"), ("4", "Costly")):
            c = sum(mj["checked_by_cost"][m][cost]["checked"] for m in claude if m in mj["checked_by_cost"])
            n_ = sum(mj["checked_by_cost"][m][cost]["of"] for m in claude if m in mj["checked_by_cost"])
            define(f"CheckedPct{tag}Claude", pct(c / n_))
            define(f"Checked{tag}Claude", f"{c}/{n_}")
        for key, v in mj["relay_answer_source_waves_2_4"].items():
            m, c = key.split("|")
            if m in KEYS and c in ("encouraged+invite", "isolated"):
                tot = v["self_checked"] + v["unchecked"]
                tag = "Inv" if c == "encouraged+invite" else "Iso"
                define(f"Unchecked{tag}{KEYS[m]}", f"{v['unchecked']}/{tot}")
                define(f"UncheckedPct{tag}{KEYS[m]}", pct(v["unchecked"] / tot) if tot else "0\\%")

    st = json.loads((RES / "realdata_structure.json").read_text())
    define("realRevisions", f"{st['revisions']:,}")
    define("realLabels", f"{st['labels']:,}")
    define("realPages", f"{st['pages']:,}")
    define("realcross", pct(st["share_cross_label_edits"]))
    define("realAnswerRevs", f"{st['revisions_with_answer_markers']:,}")
    define("realverify", pct(st["share_answer_revisions_claiming_verification"]))
    define("realInvite", f"{st['revisions_inviting_others']:,}")

    coded = RES / "realdata_coding.json"
    if coded.exists():
        cd = json.loads(coded.read_text())
        for k, v in cd.get("macros", {}).items():
            define(k, v)

    (ROOT / "report" / "numbers.tex").write_text("\n".join(out) + "\n")
    print(f"{len(out)} macros written")


if __name__ == "__main__":
    main()
