"""Preview the Arsenal and Arsenal Women blocks for an edition date, with live data.

  .venv/bin/python scripts/preview_arsenal.py 2026-11-02 --facts-only     (no Claude, no cost)
  .venv/bin/python scripts/preview_arsenal.py 2026-11-02                  (Claude writes the notes; a few cents)
"""
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff import focus, notes, settings, state  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
facts_only = "--facts-only" in sys.argv

tables = {lg: safe(f"{lg} table", espn.get_table, lg) for lg in ("eng.1", espn.CHAMPIONS_LEAGUE, espn.WSL)}
tables = {k: v for k, v in tables.items() if v}
saved = state.load("tables")
previous = {lg: {r[0]: r[1] for r in saved.get(lg, {}).get("rows", [])} for lg in saved}

client = None
if not facts_only:
    import anthropic
    load_env()
    client = anthropic.Anthropic()
total = {"input": 0, "output": 0}
print(f"Edition {day}" + ("" if facts_only else f" | model {settings.CLAUDE_MODEL}") + "\n")

for club, tier in ((focus.ARSENAL, "arsenal"), (focus.ARSENAL_WOMEN, "women")):
    block = safe(club["name"], focus.build, club, day, tables, previous, None, tier)
    print(f"== {club['name']}")
    if block is None:
        print("   data unavailable\n")
        continue
    if not block["facts"]:
        print("   no match in this edition's window")
    for f in block["facts"]:
        if facts_only:
            print("   FACTS:", f)
        else:
            written, usage = notes.write_notes(client, [f])
            total = {k: total[k] + usage[k] for k in total}
            w = written[f["id"]]
            print(f"   [{w['source']}] {w['note']}")
            if w["problems"]:
                print(f"       (Claude's note was rejected: {'; '.join(w['problems'])})")
    for x in block["next"]:
        print(f"   NEXT: {x['opponent']} ({x['venue']}), {x['competition']}, {x['when']}")
    print()
if not facts_only:
    print(f"Tokens: {total['input']} in, {total['output']} out | estimated cost: ${notes.cost(total):.3f}")
