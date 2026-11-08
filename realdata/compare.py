"""Compare the real collusion.wiki sample with our sandbox board posts under the same coding scheme, and measure how
well the two model coders agree (Cohen's kappa). Writes results/realdata_coding.json and merges a summary into
results/realdata.json for the site.

Usage: uv run python -m realdata.compare
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RES = ROOT.parent / "results"
CATS = ["ANSWERS", "COORDINATION", "ENVIRONMENT", "PROBE", "OTHER"]


def kappa(a: list, b: list) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def load(which: str):
    p = ROOT / f"coded_{which}.json"
    return json.loads(p.read_text()) if p.exists() else []


def summarise(rows: list, coders: list[str]) -> dict:
    both = [r for r in rows if all(r["codes"].get(c) for c in coders)]
    out = {"n": len(rows), "n_both_coded": len(both)}
    if not both:
        return out
    a = [r["codes"][coders[0]] for r in both]
    b = [r["codes"][coders[1]] for r in both]
    out["kappa_category"] = round(kappa([x["category"] for x in a], [x["category"] for x in b]), 3)
    out["agree_category"] = round(sum(x["category"] == y["category"] for x, y in zip(a, b)) / len(both), 3)
    for k in ("claims_verified", "addresses_others"):
        out[f"kappa_{k}"] = round(kappa([x[k] for x in a], [x[k] for x in b]), 3)
    # the mix: counted where the two coders agree
    agreed = [x for x, y in zip(a, b) if x["category"] == y["category"]]
    mix = Counter(x["category"] for x in agreed)
    out["mix_agreed"] = {c: round(mix[c] / max(len(agreed), 1), 3) for c in CATS}
    out["n_agreed"] = len(agreed)
    for k in ("claims_verified", "addresses_others"):
        both_true = sum(1 for x, y in zip(a, b) if x[k] and y[k])
        out[f"share_{k}_both"] = round(both_true / len(both), 3)
    return out


SHARED = "openai/gpt-4o-mini"  # the coder used on both corpora, so their mixes are comparable


def single(rows: list, coder: str) -> dict:
    got = [r["codes"][coder] for r in rows if r["codes"].get(coder)]
    if not got:
        return {}
    mix = Counter(x["category"] for x in got)
    return {"coder": coder, "n": len(got), "mix": {c: round(mix[c] / len(got), 3) for c in CATS},
            "claims_verified": round(sum(x["claims_verified"] for x in got) / len(got), 3),
            "addresses_others": round(sum(x["addresses_others"] for x in got) / len(got), 3)}


def main():
    real, sandbox = load("real"), load("sandbox")
    rc = list(real[0]["codes"].keys()) if real else []
    sc = list(sandbox[0]["codes"].keys()) if sandbox else []
    res = {"coders": {"real": rc, "sandbox": sc}, "real": summarise(real, rc), "sandbox": summarise(sandbox, sc),
           "same_coder": {"real": single(real, SHARED), "sandbox": single(sandbox, SHARED)}}
    pct = lambda x: f"{100 * x:.0f}\\%"
    macros = {}
    for side, tag in (("real", "Real"), ("sandbox", "Sand")):
        s = res[side]
        if s.get("n_both_coded"):
            macros[f"code{tag}N"] = str(s["n_both_coded"])
            macros[f"code{tag}Kappa"] = f"{s['kappa_category']:.2f}"
            macros[f"code{tag}Answers"] = pct(s["mix_agreed"]["ANSWERS"])
            macros[f"code{tag}Coord"] = pct(s["mix_agreed"]["COORDINATION"])
            macros[f"code{tag}Env"] = pct(s["mix_agreed"]["ENVIRONMENT"])
            macros[f"code{tag}Probe"] = pct(s["mix_agreed"]["PROBE"])
            macros[f"code{tag}Verified"] = pct(s["share_claims_verified_both"])
            macros[f"code{tag}Addresses"] = pct(s["share_addresses_others_both"])
            macros[f"code{tag}KappaVerified"] = f"{s['kappa_claims_verified']:.2f}"
            macros[f"code{tag}Agree"] = pct(s["agree_category"])
    for side, tag in (("real", "Real"), ("sandbox", "Sand")):
        sc_ = res["same_coder"][side]
        if sc_:
            macros[f"one{tag}N"] = str(sc_["n"])
            for cat, short in (("ANSWERS", "Answers"), ("COORDINATION", "Coord"), ("ENVIRONMENT", "Env"),
                               ("PROBE", "Probe")):
                macros[f"one{tag}{short}"] = pct(sc_["mix"][cat])
            macros[f"one{tag}Verified"] = pct(sc_["claims_verified"])
            macros[f"one{tag}Addresses"] = pct(sc_["addresses_others"])
    res["macros"] = macros
    (RES / "realdata_coding.json").write_text(json.dumps(res, indent=1))
    rd = RES / "realdata.json"
    if rd.exists():
        d = json.loads(rd.read_text())
        d["coding"] = {k: res[k] for k in ("coders", "real", "sandbox", "same_coder")}
        rd.write_text(json.dumps(d, indent=1))
    print(json.dumps({k: res[k] for k in ("coders", "real", "sandbox", "same_coder")}, indent=1))


if __name__ == "__main__":
    main()
