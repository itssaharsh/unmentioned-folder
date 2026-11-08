"""Print the abstract as plain text with every macro resolved, for the submission form's summary field."""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
mac = {}
for line in (root / "report" / "numbers.tex").read_text().splitlines():
    m = re.match(r"\\newcommand\{\\(\w+)\}\{(.*)\}$", line)
    if m:
        mac[m.group(1)] = m.group(2).replace("\\%", "%")
t = (root / "report" / "sections" / "abstract.tex").read_text()
t = re.sub(r"\\(\w+)\{\}", lambda m: mac.get(m.group(1), m.group(0)), t)
t = t.replace("\\begin{abstract}", "").replace("\\end{abstract}", "").replace("\\noindent", "")
t = t.replace("``", "\u201c").replace("''", "\u201d").replace("'", "\u2019")
print(" ".join(t.split()))
