"""Two counts from the tool logs behind the mechanism claims (results/mechanism.json):
1. Which note answers did readers check? For every reader of the answers note and every question, did the agent open
   the record that holds the true value? Split by how many lookups the question needs (3 or 4), over all seeds, so every
   world contributes both kinds of question.
2. Did later waves use pointers from the board? In invite episodes, the share of wave 2-4 agents that opened a record
   id which a peer had posted earlier and which had not appeared in any of the agent's own earlier tool outputs.
"""
import glob
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

from analysis.metrics import agent_measures, evidence_for

ROOT = Path(__file__).resolve().parent.parent
ID = re.compile(r"\b[pct]\d\d\b")


def main():
    model_of = lambda ep: ep["model"].replace("gemini-direct/", "google/").replace("featherless/", "")
    checked = defaultdict(lambda: {3: [0, 0], 4: [0, 0]})
    pointer = defaultdict(lambda: [0, 0])
    for f in sorted(glob.glob(str(ROOT / "runs" / "*.json.gz"))):
        ep = json.load(gzip.open(f, "rt"))
        m = model_of(ep)
        if "answers" in ep["condition"]:
            for a in ep["agents"]:
                if not agent_measures(ep, a)["read_note"]:
                    continue
                for q in ep["questions"]:
                    checked[m][q["cost"]][1] += 1
                    checked[m][q["cost"]][0] += int(evidence_for(q, None, a))
        if ep["condition"] == "encouraged+invite":
            posts = sorted(ep["board"]["history"], key=lambda h: h["t"])
            for a in ep["agents"]:
                if a["wave"] == 0:
                    continue
                seen, used = set(), False
                for e in a["events"]:
                    if e["kind"] != "tool":
                        continue
                    if e["tool"] == "open_doc":
                        d = str(e["args"].get("doc_id", "")).strip("[] ")
                        on_board = any(h["agent"] != a["rid"] and h["t"] - posts[0]["t"] <= e["t"] + 1e9 and d in ID.findall(h["content"])
                                       for h in posts[1:])
                        if on_board and d not in seen:
                            used = True
                    seen |= set(ID.findall(e.get("out", "")))
                pointer[m][1] += 1
                pointer[m][0] += int(used)
    # 3. where later-wave correct answers came from in the relay and in the control
    from folderlab.world import is_correct
    source = defaultdict(lambda: [0, 0])  # (model, condition) -> [correct and self-checked, correct but never checked]
    for f in sorted(glob.glob(str(ROOT / "runs" / "*.json.gz"))):
        ep = json.load(gzip.open(f, "rt"))
        if ep["condition"] not in ("encouraged+invite", "isolated"):
            continue
        for a in ep["agents"]:
            if a["wave"] == 0:
                continue
            for q in ep["questions"]:
                if is_correct((a["submitted"] or {}).get(q["id"], ""), q["answer"]):
                    source[(model_of(ep), ep["condition"])][0 if evidence_for(q, None, a) else 1] += 1
    # 4. within-exam swap: the same exam run with the planted answer on the 4-lookup and on a 3-lookup question
    swap = defaultdict(lambda: defaultdict(lambda: {3: [0, 0], 4: [0, 0]}))  # model -> seed -> cost -> [adopted, readers]
    for f in sorted(glob.glob(str(ROOT / "runs" / "*encouraged+answers*.json.gz"))):
        ep = json.load(gzip.open(f, "rt"))
        if "rule" in ep["condition"] or not ep.get("planted"):
            continue
        cost = next(q["cost"] for q in ep["questions"] if q["id"] == ep["planted"]["qid"])
        for a in ep["agents"]:
            ms = agent_measures(ep, a)
            if ms["read_note"]:
                swap[model_of(ep)][ep["seed"]][cost][1] += 1
                swap[model_of(ep)][ep["seed"]][cost][0] += int(ms["adopted_wrong"])
    out_swap = {}
    for m, seeds in swap.items():
        both = {sd: v for sd, v in seeds.items() if v[3][1] and v[4][1]}  # exams run with both placements
        out_swap[m] = {"exams_with_both": sorted(both),
                       "costly": [sum(v[4][0] for v in both.values()), sum(v[4][1] for v in both.values())],
                       "cheap": [sum(v[3][0] for v in both.values()), sum(v[3][1] for v in both.values())],
                       "by_exam": {str(sd): {"costly": v[4], "cheap": v[3]} for sd, v in sorted(seeds.items())}}
    out_src = {f"{m}|{c}": {"self_checked": v[0], "unchecked": v[1]} for (m, c), v in source.items()}
    out = {"within_exam_swap": out_swap, "relay_answer_source_waves_2_4": out_src,
           "checked_by_cost": {m: {str(k): {"checked": v[0], "of": v[1]} for k, v in d.items()} for m, d in checked.items()},
           "pointer_use_waves_2_4": {m: {"used": v[0], "of": v[1]} for m, v in pointer.items()}}
    (ROOT / "results" / "mechanism.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
