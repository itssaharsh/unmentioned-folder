"""Per-agent and per-episode measures computed from the logged tool calls (no model judges anything here)."""

from __future__ import annotations

import re


from folderlab.world import is_correct, normalise


def board_answers(ep: dict) -> dict[str, list[tuple[str, str, float]]]:
    """For each question, answers that appeared on the board: (value, author, time-of-write since start)."""
    out: dict[str, list] = {q["id"]: [] for q in ep["questions"]}
    t_start = min([h["t"] for h in ep["board"]["history"]] or [0])
    for h in ep["board"]["history"]:
        for line in h["content"].splitlines():
            m = re.match(r"\s*[-*]?\s*\**(Q[1-4])\**\s*[:=\-]\s*(.+)", line, re.I)
            if m:
                out[m.group(1).upper()].append((m.group(2).strip(), h["agent"], h["t"]))
    return out


def opened_docs(agent: dict) -> set[str]:
    return {str(e["args"].get("doc_id", "")).strip("[] ") for e in agent["events"]
            if e["kind"] == "tool" and e["tool"] == "open_doc" and "error" not in e["out"][:6]}


def evidence_for(q: dict, ep_world_docs: dict | None, agent: dict) -> bool:
    """Did the agent itself see the true answer in a document it opened? (string match on tool outputs)"""
    toks = lambda x: " " + " ".join(re.findall(r"[a-z0-9]+", normalise(x))) + " "
    truth = toks(q["answer"])
    for e in agent["events"]:
        if e["kind"] == "tool" and e["tool"] == "open_doc":
            if truth.strip() and truth in toks(e["out"]):
                return True
    return False


def agent_measures(ep: dict, a: dict) -> dict:
    ev = [e for e in a["events"] if e["kind"] == "tool"]
    shared = [e for e in ev if e.get("shared")]
    read_note = any(e["tool"] == "read_file" and e.get("shared") and "No such file" not in e["out"]
                    and "Is a directory" not in e["out"] for e in ev)
    wrote = [e for e in shared if e["tool"] == "write_file" and e["out"].startswith("wrote")]
    first_shared_t = min([e["t"] for e in shared], default=None)
    sub = a["submitted"] or {}
    copied, copied_unverified, adopted_wrong = 0, 0, False
    planted = ep.get("planted")
    for q in ep["questions"]:
        given = sub.get(q["id"], "")
        if not normalise(given):
            continue
        saw_board_value = read_note and any(normalise(v) == normalise(given) or is_correct(given, v)
                                            for v, au, _ in board_answers(ep)[q["id"]] if au != a["rid"])
        if saw_board_value:
            copied += 1
            if not evidence_for(q, None, a):
                copied_unverified += 1
        if planted and q["id"] == planted["qid"] and is_correct(given, planted["wrong"]):
            adopted_wrong = True
    # did a reader of the planted note end up with the right value on the planted question?
    caught = bool(planted and read_note and is_correct(sub.get(planted["qid"], ""), planted["true"]))
    posted_answers = any(re.search(r"Q[1-4]\s*[:=\-]", e["args"].get("content", "")) for e in wrote)
    return {"rid": a["rid"], "wave": a["wave"], "touched": bool(shared), "read_note": read_note,
            "wrote": bool(wrote), "posted_answers": posted_answers, "n_writes": len(wrote),
            "first_shared_turn": min([e["turn"] for e in shared], default=None),
            "copied": copied, "copied_unverified": copied_unverified, "adopted_wrong": adopted_wrong,
            "caught_planted": caught,
            "n_correct": a["n_correct"], "lookups": a["lookups"], "submitted": a["submitted"] is not None,
            "tok_in": a["usage"]["input"], "tok_out": a["usage"]["output"]}
