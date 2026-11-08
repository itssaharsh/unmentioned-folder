"""Fill the README's results block from report/numbers.tex, so the README and the report quote the same numbers.

Usage: uv run python -m analysis.readme_results
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def macros() -> dict[str, str]:
    out = {}
    for line in (ROOT / "report" / "numbers.tex").read_text().splitlines():
        m = re.match(r"\\newcommand\{\\(\w+)\}\{(.*)\}$", line)
        if m:
            out[m.group(1)] = m.group(2).replace("\\%", "%")
    return out


def main():
    n = macros()
    block = f"""**What we found** ({n['nepisodes']} episodes, {n['nagents']} agent runs, {n['nmodels']} models; every number below is rebuilt from `runs/` by `analysis/`):

- **Nobody opens a folder nobody mentions.** {n['hiddenOpened']} of {n['hiddenN']} agents opened `/mnt/shared` when nothing pointed to it. One neutral line in the task file ("A shared scratch folder is mounted at ~/shared") made {n['ReadHaikuFiveMen']} of Claude Haiku 5.5 and {n['ReadSonnetMen']} of Claude Sonnet 5.5 agents read what was in it.
- **One invitation note starts a relay board.** An empty folder stayed empty ({n['emptyWrote']} of {n['emptyN']} agents wrote in it). A single note inviting agents to pool confirmed answers, with no answers in it, was enough: early agents posted "confirmed" partial results with record ids, and later waves finished from them. Sonnet 5.5's accuracy went from {n['AccSonnetInvWA']} in the first wave to {n['AccSonnetInvWD']} in the fourth; Haiku 5.5's from {n['AccHaikuFiveInvWA']} to {n['AccHaikuFiveInvWD']}. With no folder, every wave scores about 50%.
- **Checking follows cost, not risk.** Given a note claiming four verified answers (one planted wrong), Sonnet 5.5's measured accuracy rose from {n['AccSonnetIso']} to {n['AccSonnetEnc']}. Readers checked what was cheap and copied the rest: the planted wrong answer reached {n['AdoptCostlyAll']} readers ({n['AdoptPctCostlyAll']}) when it sat on the question that costs most to check, and {n['AdoptCheapAll']} ({n['AdoptPctCheapAll']}) otherwise.
- **One line in the system prompt stops it.** "Work independently..." cut Sonnet 5.5's folder use from {n['ReadSonnetEnc']} to {n['ReadSonnetEncRule']} and stopped the relay for both newer Claude models.
- **The real board looks the same.** On collusion.wiki, {n['realcross']} of edits to an existing page came from a different agent name, and {n['realverify']} of answer-bearing posts claim the answers are confirmed or verified.

![Accuracy by wave](report/figures/fig4_waves.png)
"""
    readme = (ROOT / "README.md").read_text()
    readme = re.sub(r"<!-- RESULT-START -->.*<!-- RESULT-END -->",
                    f"<!-- RESULT-START -->\n{block}\n<!-- RESULT-END -->", readme, flags=re.S)
    (ROOT / "README.md").write_text(readme)
    import json
    content = {
        "title": "Unmentioned Folder",
        "question": "How little does it take for parallel AI agents to start a message board?",
        "answer": (f"No agent opened a shared folder nobody mentioned ({n['hiddenOpened']} of {n['hiddenN']}), and an empty "
                   f"folder stayed empty ({n['emptyWrote']} of {n['emptyN']} wrote in it). But one note inviting agents to "
                   f"pool answers, with no answers in it, was enough: early agents posted \u201cconfirmed\u201d results "
                   f"with record ids, and Claude Sonnet 5.5\u2019s accuracy rose from {n['AccSonnetInvWA']} in the first "
                   f"wave to {n['AccSonnetInvWD']} in the last. One line in the system prompt stopped it."),
        "named_example": ("Episode s100, Claude Sonnet 5.5, encouraged + invite: 12 agents in 4 waves; the shared folder "
                          "starts with one note from r-0412 asking agents to pool what they confirm."),
        "report_url": "https://github.com/itssaharsh/unmentioned-folder/blob/main/report/unmentioned-folder.pdf",
        "repo_url": "https://github.com/itssaharsh/unmentioned-folder",
        "event": "Apart Research \u00d7 AI Alignment Foundation \u00b7 Swarm Alignment Hackathon 2026",
    }
    (ROOT / "site" / "data" / "content.json").write_text(json.dumps(content, indent=1, ensure_ascii=False))
    print("README results and site content updated")


if __name__ == "__main__":
    main()
