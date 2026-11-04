"""Preview the FPL corner with live data for D's classic team and Draft league. No keys, no Claude, free.

  python3 scripts/preview_fpl.py --friday    what the morning edition inside the 24 hours before the next deadline shows (the time is set to 19 hours before it)
  python3 scripts/preview_fpl.py --recap     what the morning after a gameweek's bonus points are final shows (the finished gameweek is treated as data-checked)
  python3 scripts/preview_fpl.py             what the corner shows right now (usually nothing: it is left out on most mornings)
  --publish puts the page at https://dadi-amoghraj-72.github.io/the-kickoff/demo/fpl.html
Writes docs/demo/fpl.html and keeps its memory in preview/state/ (not the real state files).
"""
import shutil
import sys
from datetime import datetime, timedelta, timezone
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


def fpl_trend(gw):
    """{gameweek: {player id: {"points", "minutes"}}} for the last three gameweeks (the transfer hints), as the football run builds it."""
    out = {}
    for g in range(max(1, gw - 2), gw + 1):
        live = safe(f"live {g}", fpl.get_live_stats, g)
        if live:
            out[g] = live
    return out

now = datetime.now(timezone.utc)
nxt = next((e for e in boot["events"] if e["is_next"]), None)
if "--friday" in sys.argv and nxt:
    now = fplcorner.parse_time(nxt["deadline_time"]) - timedelta(hours=19, minutes=15)
    saved = {}
if "--recap" in sys.argv:
    boot = {**boot, "events": [dict(e, data_checked=True) if e["id"] == gw else e for e in boot["events"]]}
    event = fplcorner.current_event(boot)
    saved = {}
html, new_state = fplcorner.build(boot, players, entry, picks, history, live, draft, settings.FPL_DRAFT_ENTRY_ID, saved, now, trend_fn=(lambda: fpl_trend(gw)) if "--friday" in sys.argv else None)
state.save("fpl", new_state, mem)
print(f"Gameweek {gw} ({'finished' if event['finished'] else 'in progress'}) | memory: {'first run' if not saved else 'remembered'} | {len(html)} characters of HTML\n")
print(html.replace("</p>", "</p>\n").replace("</li>", "</li>\n").replace("</tr>", "</tr>\n")[:3000])
import subprocess  # noqa: E402

page = ROOT / "docs" / "demo" / "fpl.html"
page.parent.mkdir(parents=True, exist_ok=True)
what = "the Friday-morning edition inside 24 hours of the deadline" if "--friday" in sys.argv else "the morning after the bonus points are final" if "--recap" in sys.argv else "this morning"
page.write_text(render.render_edition({"date": now.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Singapore")).date().isoformat(), "dummy": False, "banner": f"FPL corner preview: {what}, from FPL's live data. Normally the corner is shown on those two mornings only.",
                                       "home": "../index.html", "headlines": [], "sections": [{"id": "football", "title": "Football", "html": html or "<p>The FPL corner is left out this morning: it is not within 24 hours of a deadline and no gameweek has just finished.</p>"}]}))
print("Built", page.relative_to(ROOT))
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/fpl.html")
    done = git("commit", "-m", "Update FPL demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit")
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/fpl.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
