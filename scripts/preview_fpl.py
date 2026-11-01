"""Preview the FPL corner with live data for D's classic team and Draft league. No keys, no Claude, free.

  python3 scripts/preview_fpl.py --reset     first run
  python3 scripts/preview_fpl.py             second run: pieces that haven't changed are left out
Writes preview/fpl.html and keeps its memory in preview/state/ (not the real state files).
"""
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import fplcorner, render, settings, state  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import fpl  # noqa: E402

mem = ROOT / "preview" / "state"
if "--reset" in sys.argv:
    shutil.rmtree(mem, ignore_errors=True)
boot = fpl.get_bootstrap()
players = fpl.players(boot, safe("fixtures", fpl.get_fixtures))
event = fplcorner.current_event(boot)
gw = event["id"]
entry = safe("classic entry", fpl.get_entry, settings.FPL_CLASSIC_TEAM_ID)
picks = safe("classic picks", fpl.get_picks, settings.FPL_CLASSIC_TEAM_ID, gw)
history = safe("classic history", fpl.get_history, settings.FPL_CLASSIC_TEAM_ID)
live = safe("live points", fpl.get_live, gw)
draft = safe("draft league", fpl.get_draft_league, settings.FPL_DRAFT_LEAGUE_ID)
saved = state.load("fpl", directory=mem)
now = datetime.now(timezone.utc)
html, new_state = fplcorner.build(boot, players, entry, picks, history, live, draft, settings.FPL_DRAFT_ENTRY_ID, saved, now)
state.save("fpl", new_state, mem)
print(f"Gameweek {gw} ({'finished' if event['finished'] else 'in progress'}) | memory: {'first run' if not saved else 'remembered'} | {len(html)} characters of HTML\n")
print(html.replace("</p>", "</p>\n").replace("</li>", "</li>\n").replace("</tr>", "</tr>\n")[:3000])
(ROOT / "preview").mkdir(exist_ok=True)
(ROOT / "preview" / "fpl.html").write_text(render._page("FPL corner preview", "", f"<main><section>{html}</section></main>"))
