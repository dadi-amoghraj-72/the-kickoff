"""Write real match notes for an edition date, using live results and the real Claude. Spends a few cents.

  .venv/bin/python scripts/preview_notes.py 2026-11-01
  .venv/bin/python scripts/preview_notes.py 2026-11-01 --model claude-sonnet-5-5

Each run is also saved to preview/notes-<model>.txt so two models can be compared side by side.

Prints every note, whether Claude wrote it or the plain fallback was used, and what the calls cost.
Nothing is published and no state files are changed.
"""
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import anthropic  # noqa: E402

from kickoff import notes, settings, state  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402

load_env()
args = sys.argv[1:]
if "--model" in args:
    settings.CLAUDE_MODEL = args[args.index("--model") + 1]  # for this run only
    args = [a for a in args if a not in ("--model", settings.CLAUDE_MODEL)]
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
lines = []


def out(text=""):
    print(text)
    lines.append(text)


client = anthropic.Anthropic()
saved = state.load("tables")
total = {"input": 0, "output": 0}
counts = {"claude": 0, "plain": 0}
out(f"Edition {day} | model {settings.CLAUDE_MODEL} | effort {settings.CLAUDE_EFFORT}\n")

for league, name in espn.LEAGUES.items():
    results = safe(f"{name} results", espn.recent_results, league, day)
    rows = safe(f"{name} table", espn.get_table, league)
    if results is None:
        out(f"== {name}: results unavailable\n")
        continue
    chosen = notes.select(league, results)
    if not chosen:
        out(f"== {name}: nothing to write\n")
        continue
    previous = {r[0]: r[1] for r in saved.get(league, {}).get("rows", [])}
    facts = [notes.match_facts(m, tier, rows, previous, name) for m, tier in chosen]
    written, usage = notes.write_notes(client, facts)
    total = {k: total[k] + usage[k] for k in total}
    out(f"== {name} ({len(facts)} notes)")
    for f in facts:
        w = written[f["id"]]
        counts[w["source"]] += 1
        out(f"  [{w['source']}] {w['note']}")
        if w["problems"]:
            out(f"      (Claude's note was rejected: {'; '.join(w['problems'])})")
    out()

out(f"Notes from Claude: {counts['claude']} | plain fallbacks: {counts['plain']}")
out(f"Tokens: {total['input']} in, {total['output']} out | estimated cost: ${notes.cost(total):.3f}")

Path(__file__).resolve().parent.parent.joinpath("preview").mkdir(exist_ok=True)
(Path(__file__).resolve().parent.parent / "preview" / f"notes-{settings.CLAUDE_MODEL}.txt").write_text("\n".join(lines) + "\n")
