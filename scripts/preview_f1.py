"""Preview the F1 section as a page.

  .venv/bin/python scripts/preview_f1.py            from saved real data: the United States Grand Prix (round 18) edition of 26 October 2026
  .venv/bin/python scripts/preview_f1.py --live     from the Jolpica API right now (free, no key): whatever F1 has happened since yesterday's edition
add --story to have Claude write the race story from the day's reports (needs your key; costs about half a cent), or --story-dry to show
what would be sent to Claude without calling it. Stories only work with --live (they use the last two days' reports).
add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/f1.html, --no-open to skip opening it.
Nothing is saved either way: a preview never uses up what the daily edition would report.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import f1, f1blurb, notes, render, settings  # noqa: E402
from kickoff.sources import espn, jolpica  # noqa: E402

if "--live" in sys.argv:
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
    api = jolpica.Api()
    note = "Built live from the Jolpica F1 API."
    story = None
    if "--story" in sys.argv:
        import anthropic
        from kickoff.envfile import load_env
        load_env()
        story = f1blurb.story(anthropic.Anthropic())
    elif "--story-dry" in sys.argv:
        def story(race, rows, start, extras=()):
            from kickoff.sources import feeds
            picked = f1blurb.pick_reports(feeds.fetch_all(f1blurb.FEEDS), race, rows, start)
            print("FACTS:", json.dumps(f1blurb.facts(race, rows, extras), ensure_ascii=False, indent=1))
            print(f"REPORTS ({len(picked)}):")
            for i in picked:
                print(f"  {i['published']:%d %b %H:%M} {i['source']}: {i['title']} | {i['text'][:90]}")
            return "", {"input": 0, "output": 0}
    out = f1.run(now, espn.window_start(day), {}, api, story=story)
    used = out["stats"].get("claude_tokens", {"input": 0, "output": 0})
    if used["input"]:
        print(f"Claude: {used['input']} tokens in, {used['output']} out, about ${notes.cost(used, settings.NEWS_MODEL):.4f}")
else:
    fx = ROOT / "tests" / "fixtures"
    load = lambda n: json.loads((fx / n).read_text())["MRData"]  # noqa: E731
    race, quali = load("jolpica_results_18.json")["RaceTable"]["Races"][0], load("jolpica_quali_18.json")["RaceTable"]["Races"][0]
    counts = json.loads((fx / "jolpica_counts.json").read_text())

    class Saved:
        calls = 0
        schedule = lambda self, season: load("jolpica_schedule_2026.json")["RaceTable"]["Races"]  # noqa: E731
        results = lambda self, season, rnd: race if int(rnd) == 18 else None  # noqa: E731
        qualifying = lambda self, season, rnd: quali if int(rnd) == 18 else None  # noqa: E731
        sprint = lambda self, season, rnd: None  # noqa: E731
        def driver_standings(self, season, rnd):
            ds = load("jolpica_dstand_18.json")["StandingsTable"]["StandingsLists"][0]
            if int(rnd) == 18:
                return ds
            earned = {x["Driver"]["driverId"]: float(x["points"]) for x in race["Results"]}  # the round before: this race's points taken off
            return {**ds, "round": str(rnd), "DriverStandings": [{**x, "points": str(int(float(x["points"]) - earned.get(x["Driver"]["driverId"], 0)))} for x in ds["DriverStandings"]]}
        constructor_standings = lambda self, season, rnd: load("jolpica_cstand_18.json")["StandingsTable"]["StandingsLists"][0]  # noqa: E731
        finishes = lambda self, did, pos: counts[did]["results"][str(pos)]  # noqa: E731
        poles = lambda self, did: counts[did]["poles"]  # noqa: E731

    now = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc)
    out = f1.run(now, datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc), {}, Saved())
    note = "Built from saved real data: the weekend of the United States Grand Prix (qualifying and race), as the edition of 26 October 2026 would show it."
if not out["html"]:
    sys.exit(f"No F1 to report in the window right now ({out['stats']}). Sessions appear about 75 minutes after qualifying and 2.5 hours after a race start, and again until published.")
edition = {"date": now.date().isoformat(), "dummy": False, "banner": f"F1 preview. {note}", "home": "../index.html", "headlines": [],
           "sections": [{"id": "f1", "title": "F1", "html": out["html"]}]}
page = ROOT / "docs" / "demo" / "f1.html"
page.parent.mkdir(parents=True, exist_ok=True)
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['stats']}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/f1.html")
    done = git("commit", "-m", "Update F1 demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/f1.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
