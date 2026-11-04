"""Preview the F1 and tennis sections as D reviews them (2026-11-04): the most recent Grand Prix, the most recent Grand Slam, and the ATP Finals and WTA Finals.

  .venv/bin/python scripts/preview_f1_tennis.py            writes docs/demo/f1-tennis.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/f1-tennis.html, --no-open to skip opening it.

F1: the Mexico City Grand Prix (round 19, 1 November 2026), as the edition of 2 November shows it, live from the Jolpica API (free, no key), with the title note.
Tennis: the US Open 2026 final weekend (live from ESPN, free), and the real 2025 ATP Finals and WTA Finals from saved ESPN data, morning by morning."""
import copy
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import f1, render, tennis  # noqa: E402
from kickoff.sources import espn_tennis, jolpica  # noqa: E402

FX = ROOT / "tests" / "fixtures"
utc = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731

# ---- F1 ----
f1_html = f1.run(utc(2026, 11, 2, 23, 0), utc(2026, 10, 31, 20, 0), {}, jolpica.Api())["html"]     # the window includes Saturday's qualifying too

# ---- Tennis: the US Open ----
slam_html = tennis.run(utc(2026, 9, 14, 2, 0), {}, espn_tennis.Source())["html"]

# ---- Tennis: the tour finals, as they would have come, morning by morning ----
TF = json.loads((FX / "espn_tour_finals_2025.json").read_text())


class Finals:
    def __init__(self, event):
        self.event, self.calls = event, 0

    def slam_events(self, now):
        return []

    def finals_events(self, now):
        e = copy.deepcopy(self.event)
        for g in e["groupings"]:
            g["competitions"] = [c for c in g["competitions"] if tennis.utc(c["date"]) <= now]
        return [e]


tour_html, state = "", {}
for label, now, ev in (("ATP Finals · the first morning (two group matches played)", utc(2025, 11, 10, 0, 0), TF["atpf20251116"]),
                       ("ATP Finals · the morning after the group stage (a group is complete: the top two go through)", utc(2025, 11, 15, 0, 0), TF["atpf20251116"]),
                       ("ATP Finals · the morning after the final", utc(2025, 11, 17, 2, 0), TF["atpf20251116"]),
                       ("WTA Finals · the morning after the final", utc(2025, 11, 9, 2, 0), TF["wtaf20251108"])):
    state = {} if "first" in label or "WTA" in label else state
    out = tennis.run(now, state, Finals(ev))
    state = out["state"]
    tour_html += f"<h4>{label}</h4>" + (out["html"] or "<p class=muted>Nothing new.</p>")

banner = ("REVIEW of F1 and tennis on real data: the Mexico City Grand Prix (latest), the US Open 2026 (latest Slam), and the ATP Finals and WTA Finals (the real 2025 events, since the 2026 ones "
          "have not been played yet).")
edition = {"date": date(2026, 11, 4).isoformat(), "dummy": False, "banner": banner, "home": "../index.html", "headlines": [],
           "sections": [{"id": "f1", "title": "F1", "html": f1_html}, {"id": "tennis", "title": "Tennis · US Open", "html": slam_html}, {"id": "tour", "title": "Tennis · ATP Finals and WTA Finals", "html": tour_html}]}
out = ROOT / "docs" / "demo" / "f1-tennis.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(render.render_edition(edition))
print("Built", out.relative_to(ROOT))
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(out)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/f1-tennis.html")
    done = git("commit", "-m", "Update F1 and tennis review page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/f1-tennis.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
