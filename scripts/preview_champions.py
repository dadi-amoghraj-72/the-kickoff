"""Preview the Champions League block for an edition date with live data. Writes preview/champions.html.

  .venv/bin/python scripts/preview_champions.py 2026-10-22 --facts-only    (no Claude; the plain overview)
  .venv/bin/python scripts/preview_champions.py 2026-10-22                 (Claude writes the overview; cents)
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import champions, notes, overview, render, settings  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn  # noqa: E402

args = sys.argv[1:]
if "--model" in args:
    settings.CLAUDE_MODEL = args[args.index("--model") + 1]  # for this run only
    args = [a for a in args if a not in ("--model", settings.CLAUDE_MODEL)]
args = [a for a in args if not a.startswith("--")]
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
facts_only = "--facts-only" in sys.argv

matches = safe("Champions League results", champions.results, day)
rows = safe("Champions League table", espn.get_table, espn.CHAMPIONS_LEAGUE)
if not matches:
    sys.exit(f"No Champions League matches in the edition for {day}." if matches == [] else "Results unavailable.")

odds = overview.collect_odds(espn.CHAMPIONS_LEAGUE, matches)
facts = overview.matchday_facts(champions.COMPETITION, matches, odds)
total = {"input": 0, "output": 0}
if facts_only:
    result = {"note": overview.plain_overview(facts), "source": "plain", "problems": []}
else:
    import anthropic
    load_env()
    result, total = overview.write_overview(anthropic.Anthropic(), facts)

html = champions.section_html(matches, rows, result["note"])
body = f'<main>{render._masthead(render.nice_date(day.isoformat()))}<section><h2>Football</h2>{html}</section></main>'
(ROOT / "preview").mkdir(exist_ok=True)
(ROOT / "preview" / "champions.html").write_text(render._page("Champions League preview", "", body))
print(f"Edition {day}: {len(matches)} matches | expectations: {facts['expectations']}" + ("" if facts_only else f" | model {settings.CLAUDE_MODEL}"))
if "tally" in facts:
    print("Tally:", facts["tally"])
print("Game of the night:", facts.get("game_of_the_night"))
print(f"\n[{result['source']}] {result['note']}")
if result["problems"]:
    print(f"   (Claude's overview was rejected: {'; '.join(result['problems'])})")
if not facts_only:
    print(f"\nTokens: {total['input']} in, {total['output']} out | estimated cost: ${notes.cost(total):.3f}")
(ROOT / "preview" / f"overview-{'plain' if facts_only else settings.CLAUDE_MODEL}.txt").write_text(result["note"] + "\n")
print("Wrote preview/champions.html")
