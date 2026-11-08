"""Export the data the companion site reads: site/data/{summary,replay,realdata}.json.

Every number on the site comes from these files, which come from runs/ and realdata/.
Usage: uv run python -m analysis.export_site [episode-file-for-replay]
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

from analysis.metrics import agent_measures, board_answers

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "data"


def short(v, n=220):
    s = v if isinstance(v, str) else json.dumps(v)
    return s if len(s) <= n else s[: n - 1] + "…"


def replay(path: Path) -> dict:
    ep = json.load(gzip.open(path, "rt"))
    agents = []
    for a in ep["agents"]:
        m = agent_measures(ep, a)
        agents.append({
            "rid": a["rid"], "wave": a["wave"], "n_correct": a["n_correct"], "lookups": a["lookups"],
            "submitted": a["submitted"], "score": a["score"], "measures": m,
            "events": [{"t": round(e["t"], 2), "turn": e["turn"], "kind": e["kind"],
                        **({"text": short(e["text"], 400)} if e["kind"] == "say" else
                           {"tool": e["tool"], "args": {k: short(v, 300) for k, v in e["args"].items()},
                            "out": short(e["out"], 300), "shared": e.get("shared", False)})}
                       for e in a["events"]],
        })
    return {"file": path.name, "model": ep["model"], "condition": ep["condition"], "seed": ep["seed"],
            "budget": ep["budget"], "questions": ep["questions"], "planted": ep["planted"],
            "board": {"history": [{"t": h["t"], "agent": h["agent"], "file": h["file"], "op": h["op"],
                                   "content": short(h["content"], 1200)} for h in ep["board"]["history"]]},
            "board_answers": board_answers(ep), "agents": agents}


def main():
    SITE.mkdir(parents=True, exist_ok=True)
    summ = json.loads((ROOT / "results" / "summary.json").read_text())
    (SITE / "summary.json").write_text(json.dumps(summ, indent=1))
    if len(sys.argv) > 1:
        (SITE / "replay.json").write_text(json.dumps(replay(Path(sys.argv[1])), indent=1))
    rd = ROOT / "results" / "realdata.json"
    if rd.exists():
        (SITE / "realdata.json").write_text(rd.read_text())
    print("exported to", SITE)


if __name__ == "__main__":
    main()
