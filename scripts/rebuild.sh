#!/usr/bin/env bash
# Rebuild every number, figure, the report PDF and the site data from runs/ and the real-board files.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -m analysis.aggregate > /dev/null
uv run python -m analysis.figures
[ -f realdata/coded_real.json ] && uv run python -m realdata.compare > /dev/null
uv run python -m analysis.mechanism > /dev/null
uv run python -m analysis.numbers
uv run python -m analysis.readme_results
uv run python -m analysis.export_site runs/sonnet-5-5__encouraged+invite__s100.json.gz
cp results/adoption_by_cost.json site/data/
cd report
pdflatex -interaction=nonstopmode main.tex > /dev/null
bibtex main > /dev/null
pdflatex -interaction=nonstopmode main.tex > /dev/null
pdflatex -interaction=nonstopmode main.tex > /dev/null
if grep -qE "^!|Undefined control" main.log; then grep -E "^!|Undefined control" main.log; exit 1; fi
cp main.pdf unmentioned-folder.pdf
echo "rebuilt: $(pdfinfo unmentioned-folder.pdf | grep Pages)"
