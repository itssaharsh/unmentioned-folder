"""Structural statistics of the real collusion.wiki board, computed from the public export with no model in the loop.

Usage: uv run python -m realdata.structure   (needs realdata/raw/revisions.jsonl.gz from collusion.wiki/explorer/download)
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERIFY = re.compile(r"\b(confirmed|verified|checked|exact)\b", re.I)
ANSWERISH = re.compile(r"\b(R\d+\s*[=:]|answer|answers|answered|Q\d+\s*[:=])", re.I)
INVITE = re.compile(r"\b(please post|post (?:R\d|it|your|here|the)|add your|append|let'?s pool|share (?:your|the)|"
                    r"if you (?:get|find|have|see)|everyone|all runs|other (?:agents|runs))\b", re.I)


def main():
    revs = [json.loads(l) for l in gzip.open(ROOT / "raw" / "revisions.jsonl.gz", "rt")]
    revs.sort(key=lambda r: (r["time"] or "", r["page_key"], r["seq"]))
    creator, labels_by_page = {}, defaultdict(set)
    for r in revs:
        creator.setdefault(r["page_key"], r["label"])
        labels_by_page[r["page_key"]].add(r["label"])
    later = [r for r in revs if r["seq"] > 1]
    cross = [r for r in later if r["label"] and creator[r["page_key"]] != r["label"]]
    bodies = [(r["body"] or "") for r in revs]
    answerish = [b for b in bodies if ANSWERISH.search(b)]
    stats = {
        "source": "collusion.wiki export (revisions.jsonl.gz), downloaded 2026-11-08",
        "revisions": len(revs),
        "pages": len(labels_by_page),
        "labels": len({r["label"] for r in revs}),
        "first": revs[0]["time"], "last": revs[-1]["time"],
        "edits_to_existing_pages": len(later),
        "edits_by_other_label": len(cross),
        "share_cross_label_edits": round(len(cross) / max(len(later), 1), 4),
        "multi_author_pages": sum(1 for s in labels_by_page.values() if len(s) > 1),
        "revisions_with_answer_markers": len(answerish),
        "answer_revisions_claiming_verification": sum(1 for b in answerish if VERIFY.search(b)),
        "share_answer_revisions_claiming_verification": round(
            sum(1 for b in answerish if VERIFY.search(b)) / max(len(answerish), 1), 4),
        "revisions_inviting_others": sum(1 for b in bodies if INVITE.search(b)),
        "per_day": sorted(Counter((r["time"] or "")[:10] for r in revs).items()),
        "regexes": {"verify": VERIFY.pattern, "answerish": ANSWERISH.pattern, "invite": INVITE.pattern},
    }
    out = ROOT.parent / "results"
    out.mkdir(exist_ok=True)
    (out / "realdata_structure.json").write_text(json.dumps(stats, indent=1))
    print({k: v for k, v in stats.items() if k not in ("per_day", "regexes")})


if __name__ == "__main__":
    main()
