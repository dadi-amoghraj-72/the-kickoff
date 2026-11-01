"""Preview injuries and returns with live Premier League data. Uses a throwaway memory in preview/state/.

  python3 scripts/preview_injuries.py 2026-11-02 --reset     first run: only news from the last week
  python3 scripts/preview_injuries.py 2026-11-03             next day: repeats nothing
"""
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import injuries, state  # noqa: E402
from kickoff.sources import fpl  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0])
mem = ROOT / "preview" / "state"
if "--reset" in sys.argv:
    shutil.rmtree(mem, ignore_errors=True)

players = fpl.players(fpl.get_bootstrap(), fpl.get_fixtures())
key = [p for p in players if injuries.is_key(p)]
saved = state.load("injuries", directory=mem)
items, new_saved = injuries.detect(players, saved, day)
state.save("injuries", new_saved, mem)
print(f"{len(players)} players, {len(key)} key players | memory: {'first run' if not saved else str(len(saved)) + ' remembered'}")
print(f"Items to show on {day}: {len(items)}")
for i in items:
    back = f" | back {i['back']}" if i["back"] else ""
    print(f"  {i['kind']:9} {i['name']} ({i['team']}): {i['detail'] or '-'}{back}")
(ROOT / "preview").mkdir(exist_ok=True)
(ROOT / "preview" / "injuries.html").write_text(injuries.html(items))
