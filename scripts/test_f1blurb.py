"""Offline tests for the F1 race story: choosing reports, checking Claude's words, retries, failures. No network, no Claude.
Run: python3 scripts/test_f1blurb.py"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import f1, f1blurb, notes  # noqa: E402

FX = ROOT / "tests" / "fixtures"
L = lambda n: json.loads((FX / n).read_text())["MRData"]  # noqa: E731
SCHED = L("jolpica_schedule_2026.json")["RaceTable"]["Races"]
RACE18 = L("jolpica_results_18.json")["RaceTable"]["Races"][0]
ROWS = RACE18["Results"]
DS18 = L("jolpica_dstand_18.json")["StandingsTable"]["StandingsLists"][0]
COUNTS = json.loads((FX / "jolpica_counts.json").read_text())
SCHEDULE_ENTRY = next(x for x in SCHED if x["round"] == "18")
START = f1.start_of(SCHEDULE_ENTRY, "race")
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


def item(title, text, hours, source="BBC Sport"):
    return {"source": source, "title": title, "text": text, "link": f"https://x/{title[:12]}-{hours}", "published": START + timedelta(hours=hours)}


# ---- Choosing the reports ----
ITEMS = [
    item("Antonelli takes the win in Austin", "Mercedes driver Kimi Antonelli won the United States Grand Prix from pole position, ahead of Leclerc.", 3),
    item("Leclerc says Ferrari lacked pace in Austin", "Charles Leclerc finished second at the circuit.", 4, "The Guardian"),
    item("Before lights-out: Austin preview", "Antonelli and Leclerc on the front row in Austin.", -5),        # before the start
    item("Next week: Mexico City preview", "Verstappen heads to Mexico City.", 80),                            # after the 48-hour window
    item("Tennis: Paris Masters round-up", "Nothing about motor racing here.", 5),                           # unrelated
    item("Norris wins sprint in Qatar", "Norris, Piastri and Russell on the podium in Qatar.", 6),                # not this race's podium or place
]
picked = f1blurb.pick_reports(ITEMS, SCHEDULE_ENTRY, ROWS, START)
titles = [i["title"] for i in picked]
check("keywords: the place, the country and the podium's surnames (not generic words like Grand Prix)", {"Austin", "Antonelli", "Leclerc"} <= f1blurb.keywords(SCHEDULE_ENTRY, ROWS)
      and not ({"Grand", "Prix", "United", "States"} & f1blurb.keywords(SCHEDULE_ENTRY, ROWS)), f1blurb.keywords(SCHEDULE_ENTRY, ROWS))
check("reports are those from lights-out to 48 hours later that name the place or a podium driver", set(titles) == {"Antonelli takes the win in Austin", "Leclerc says Ferrari lacked pace in Austin"}, titles)
check("the most relevant report (most keywords) comes first", titles[0] == "Antonelli takes the win in Austin", titles)
check("no more than 8 reports are sent", len(f1blurb.pick_reports([item(f"Austin story {i}", "Austin race", 2 + i % 40) for i in range(20)], SCHEDULE_ENTRY, ROWS, START)) == 8)

# ---- Facts ----
F = f1blurb.facts(SCHEDULE_ENTRY, ROWS, ["Biggest Mover: X."])
check("facts: winner, podium with grid slots, fastest lap, retirements, laps, notable standouts", F["winner"] == "Kimi Antonelli" or F["winner"].endswith("Antonelli")
      and len(F["podium"]) == 3 and F["did_not_finish"] == 3 and F["winning_margin_seconds"] == "13.078" and F["fastest_lap"]["time"] == "1:37.976" and F["notable"] == ["Biggest Mover: X."], F)
check("facts hold only what the results say: no standings, no history", set(F) <= {"race", "winner", "podium", "did_not_finish", "laps", "fastest_lap", "notable", "winning_margin_seconds"}, set(F))

# ---- Checking Claude's words ----
good = "Antonelli took victory in Austin from pole, and Leclerc came home second after a quiet afternoon."
check("a blurb made only of the facts and reports passes", f1blurb.check(good, F, picked) == [], f1blurb.check(good, F, picked))
check("an invented name at the start of a sentence is caught too", any("Norris" in p for p in f1blurb.check("Norris won it.", F, picked)))
check("an invented driver name is caught", any("Norris" in p for p in f1blurb.check("Antonelli won, with Norris third.", F, picked)))
check("an invented number is caught", any("17" in p for p in f1blurb.check("Antonelli won after 17 laps in front.", F, picked)))
check("a history claim the material never makes is caught", f1blurb.check("It was Antonelli's record fourth win.", F, picked) != [])
check("hype is caught", f1blurb.check("A stunning win for Antonelli.", F, picked) != [])
check("more than 65 words is caught", any("words" in p for p in f1blurb.check(" ".join(["Antonelli"] * 70), F, picked)))
check("copying six words in a row from a report is caught", any("copies" in p for p in f1blurb.check("Mercedes driver Kimi Antonelli won the United States Grand Prix from pole position.", F, picked)))
claim = [item("Antonelli seals the world title in Austin", "Kimi Antonelli became champion with four races left.", 3)]
check("a big claim passes when a report states it (the title) and fails when no report does",
      f1blurb.check("Antonelli became champion in Austin.", F, claim) == [] and any("champion" in p for p in f1blurb.check("Antonelli became champion in Austin.", F, picked)),
      (f1blurb.check("Antonelli became champion in Austin.", F, claim), f1blurb.check("Antonelli became champion in Austin.", F, picked)))
check("an invented cause is caught: a collision, a penalty, rain", all(f1blurb.check(f"Leclerc finished second after {w}.", F, picked) for w in ("a collision", "a penalty", "heavy rain")))

# ---- Asking Claude (call_json faked) ----
class Fake:
    def __init__(self, *replies):
        self.replies, self.sent = list(replies), []

    def __call__(self, client, system, schema, content, model=None):
        self.sent.append(content)
        reply = self.replies.pop(0)
        return (None, {"input": 100, "output": 20}) if reply is None else ({"blurb": reply}, {"input": 100, "output": 20})


real = notes.call_json
try:
    fake = Fake(good)
    notes.call_json = fake
    blurb, usage = f1blurb.write(None, F, picked)
    check("a good first answer is used, one call, tokens counted", blurb == good and len(fake.sent) == 1 and usage == {"input": 100, "output": 20}, (blurb, usage))
    fake = Fake("Antonelli won, with Norris third.", good)
    notes.call_json = fake
    blurb, usage = f1blurb.write(None, F, picked)
    check("a bad first answer is retried once with the problems named; the second is used", blurb == good and len(fake.sent) == 2 and "Norris" in fake.sent[1] and usage["input"] == 200, (blurb, fake.sent[-1][:120]))
    fake = Fake("Antonelli won, with Norris third.", "Norris won it.")
    notes.call_json = fake
    check("two bad answers give no blurb, never an unchecked one", f1blurb.write(None, F, picked)[0] is None and len(fake.sent) == 2)
    fake = Fake(None)
    notes.call_json = fake
    check("Claude unreachable or refusing gives no blurb and no retry", f1blurb.write(None, F, picked)[0] is None and len(fake.sent) == 1)
    sent = json.loads(Fake(good) and fake.sent[0])
    check("only headlines and short blurbs go to Claude, with the facts", set(sent) == {"facts", "reports"} and all(set(x) == {"source", "headline", "blurb"} for x in sent["reports"]) and sent["facts"]["winner"], sent.keys())

    # ---- story(): the function the F1 block calls ----
    fake = Fake(good)
    notes.call_json = fake
    html, usage = f1blurb.story(None, fetch=lambda feeds: ITEMS)(SCHEDULE_ENTRY, ROWS, START, ["Biggest Mover: X."])
    check("story: a paragraph of the blurb, then who the reports were by", html.startswith('<p class="f1story">Antonelli took') and "From reports by BBC Sport, The Guardian." in html, html)
    fake = Fake(good)
    notes.call_json = fake
    html, usage = f1blurb.story(None, fetch=lambda feeds: [item("Tennis", "no racing", 3)])(SCHEDULE_ENTRY, ROWS, START)
    check("no relevant report: no blurb and Claude is not called at all (no cost)", html == "" and fake.sent == [] and usage == {"input": 0, "output": 0})

    def down(feeds):
        raise RuntimeError("feeds down")
    fake = Fake(good)
    notes.call_json = fake
    check("every news feed down: no blurb, no call, no exception", f1blurb.story(None, fetch=down)(SCHEDULE_ENTRY, ROWS, START) == ("", {"input": 0, "output": 0}) and fake.sent == [])
    fake = Fake('Antonelli won <b>& Leclerc was second</b> in Austin.')
    notes.call_json = fake
    check("the blurb is escaped before it goes into the page", "<b>" not in f1blurb.story(None, fetch=lambda feeds: ITEMS)(SCHEDULE_ENTRY, ROWS, START)[0])

    # ---- Inside the F1 block ----
    class Api:
        calls = 0
        schedule = lambda self, season: SCHED  # noqa: E731
        finishes = lambda self, did, pos: COUNTS[did]["results"][str(pos)]  # noqa: E731
        results = lambda self, s, rnd: RACE18  # noqa: E731
        qualifying = lambda self, s, rnd: L("jolpica_quali_18.json")["RaceTable"]["Races"][0]  # noqa: E731
        sprint = lambda self, s, rnd: None  # noqa: E731
        poles = lambda self, did: COUNTS[did]["poles"]  # noqa: E731

        def driver_standings(self, s, rnd):
            got = {x["Driver"]["driverId"]: float(x["points"]) for x in ROWS}
            return DS18 if int(rnd) == 18 else {**DS18, "round": str(rnd), "DriverStandings": [{**x, "points": str(int(float(x["points"]) - got.get(x["Driver"]["driverId"], 0)))} for x in DS18["DriverStandings"]]}
        constructor_standings = lambda self, s, rnd: L("jolpica_cstand_18.json")["StandingsTable"]["StandingsLists"][0]  # noqa: E731

    seen = []

    def story(race, rows, start, extras):
        seen.append((race["raceName"], start, list(extras)))
        return '<p class="f1story">STORY</p>', {"input": 300, "output": 40}
    NOW, W = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc), datetime(2026, 10, 24, 20, 0, tzinfo=timezone.utc)
    withs = f1.run(NOW, W, {}, Api(), story=story)
    h = withs["html"]
    check("the story sits right after the race line and before the table", h.index("f1sum") < h.index("STORY") < h.index(">Race</th>"), h[:300])
    check("it is called once, for the race only (not qualifying), with the race's start and its standouts", len(seen) == 1 and seen[0][1] == START and seen[0][0] == "United States Grand Prix", seen)
    check("its tokens are reported in the stats", withs["stats"]["claude_tokens"] == {"input": 300, "output": 40}, withs["stats"])
    plain = f1.run(NOW, W, {}, Api())
    check("without a story function the page is exactly as before and no tokens are used", "STORY" not in plain["html"] and plain["stats"]["claude_tokens"] == {"input": 0, "output": 0}
          and plain["html"].replace('<p class="f1story">STORY</p>', "") == h.replace('<p class="f1story">STORY</p>', ""))

    def broken(race, rows, start, extras):
        raise RuntimeError("boom")
    safe = f1.run(NOW, W, {}, Api(), story=broken)
    check("a story function that raises costs nothing: the tables are all still there", safe["html"] == plain["html"] and safe["stats"]["shown"] == plain["stats"]["shown"], safe["stats"])
finally:
    notes.call_json = real

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
