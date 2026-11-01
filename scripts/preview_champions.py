"""Preview the Champions League block for an edition date with live data. Writes preview/champions.html.

  .venv/bin/python scripts/preview_champions.py 2026-10-22 --facts-only    (no Claude; plain scoreline notes)
  .venv/bin/python scripts/preview_champions.py 2026-10-22                 (Claude writes the notes; cents)
"""
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import champions, notes, render, settings  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
facts_only = "--facts-only" in sys.argv

matches = safe("Champions League results", champions.results, day)
rows = safe("Champions League table", espn.get_table, espn.CHAMPIONS_LEAGUE)
if not matches:
    sys.exit(f"No Champions League matches in the edition for {day}." if matches == [] else "Results unavailable.")

picked = champions.note_facts(matches, rows)
written, total = {}, {"input": 0, "output": 0}
if picked:
    if facts_only:
        written = {f["id"]: {"note": notes.plain_note(f), "source": "plain"} for _, f in picked}
    else:
        import anthropic
        load_env()
        written, total = notes.write_notes(anthropic.Anthropic(), [f for _, f in picked])

html = champions.section_html(matches, rows, written)
body = f'<main>{render._masthead(render.nice_date(day.isoformat()))}<section><h2>Football</h2>{html}</section></main>'
(ROOT / "preview").mkdir(exist_ok=True)
(ROOT / "preview" / "champions.html").write_text(render._page("Champions League preview", "", body))
print(f"Edition {day}: {len(matches)} matches, {len(picked)} notes" + ("" if facts_only else f" | model {settings.CLAUDE_MODEL}"))
for _, f in picked:
    w = written[f["id"]]
    print(f"  [{w.get('source', 'plain')}] {w['note']}")
    if w.get("problems"):
        print(f"      (rejected: {'; '.join(w['problems'])})")
if not facts_only:
    print(f"Tokens: {total['input']} in, {total['output']} out | estimated cost: ${notes.cost(total):.3f}")
print("Wrote preview/champions.html")
