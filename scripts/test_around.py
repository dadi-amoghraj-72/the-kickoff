"""Tests for Around The Sporting World and Interesting Stories: the structured sports, the headline rules, the spotlight, Claude's checks and the whole block. Run: .venv/bin/python scripts/test_around.py"""
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import around, daily, order  # noqa: E402
from kickoff.sources import feeds  # noqa: E402

FX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


load = lambda n: json.loads((FX / n).read_text())  # noqa: E731
NOW = utc(2026, 11, 5, 0, 0)
REAL_GAMES = around.GAMES
around.GAMES = []                      # the older tests below are not about a Games; NOW falls inside the 2026 Youth Olympics, which have their own tests at the end


class Src:
    """A fake Source with canned answers; a name in `boom` raises."""

    def __init__(self, rugby=None, golf=None, ufc=None, news=(), boom=()):
        self.r, self.g, self.u, self.n, self.boom = rugby or {}, golf or {}, ufc, list(news), set(boom)

    def rugby(self, league):
        if "rugby" in self.boom:
            raise RuntimeError
        return self.r.get(league, {"events": []})

    def golf(self, tour):
        if "golf" in self.boom:
            raise RuntimeError
        return self.g.get(tour, {"events": []})

    def ufc(self):
        if "ufc" in self.boom:
            raise RuntimeError
        return self.u or {"events": []}

    def ufc_page(self, slug):
        raise RuntimeError("no UFC.com in this fake")

    def news(self):
        if "news" in self.boom:
            raise RuntimeError
        return self.n

    def rugby_table(self, league):
        if "rugby" in self.boom:
            raise RuntimeError
        return self.tables.get(league, {}) if hasattr(self, "tables") else {}


item = lambda title, text="", source="BBC Sport", hours=3, link=None: {"source": source, "title": title, "text": text, "link": link or f"https://x/{abs(hash(title))}", "published": NOW - timedelta(hours=hours)}  # noqa: E731

# ---- rugby (real Six Nations scoreboard) ---------------------------------------------------------
six = load("other_rugby_six_nations.json")
final = next(e for e in six["events"] if e["status"]["type"]["name"] == "STATUS_FINAL")
when = datetime.fromisoformat(final["date"].replace("Z", "+00:00"))
got = around.rugby(Src(rugby={"180659": six}), when + timedelta(hours=5))
sides = {x["homeAway"]: x for x in final["competitions"][0]["competitors"]}
expected = f"{sides['home']['team']['displayName']} {int(sides['home']['score'])}\u2013{int(sides['away']['score'])} {sides['away']['team']['displayName']} (Six Nations)"
check("rugby: a finished Six Nations match in the window is a line with both teams and the score, as the raw data reads", [t for t, _ in got if t == expected] == [expected], (got, expected))
check("rugby: the same match a week later is out of the window", around.rugby(Src(rugby={"180659": six}), when + timedelta(days=7)) == [])
check("rugby: a league with odd data is skipped, the rest stay", [t for t, _ in around.rugby(Src(rugby={"180659": six, "164205": {"events": "junk"}}), when + timedelta(hours=5)) if t == expected] == [expected])

# ---- golf (the real 2025 Masters, finished, as the block gets it) -----------------------------------------
masters = json.loads((FX / "golf_masters_2025.json").read_text())
major = copy.deepcopy(masters)
major["events"][0]["endDate"] = "2026-11-04T20:00Z"

# ---- which headlines count ---------------------------------------------------------------------------
sp = lambda t, x="": around.sport_of(item(t, x))  # noqa: E731
check("badminton: an event at the bar is sorted; a Super 750 semi-final by an Indian is the spotlight", sp("Satwik and Chirag reach All England final", "badminton")[0] == "badminton" and sp("Sindhu into Japan Open semi-final", "badminton Super 750") == ("badminton", True))
check("chess: the World Championship counts, a club open does not", sp("Gukesh wins Candidates in Toronto", "chess")[0] == "chess" and sp("Chess: local club open ends", "chess")[0] is None)
check("darts: the world championship counts; 'Chessum' does not make a chess story", sp("Luke Littler wins World Darts Championship")[0] == "darts" and sp("I couldn't see myself with another badge - Chessum")[0] is None)
check("athletics: the Diamond League counts", sp("Kerr wins Diamond League final in Brussels")[0] == "athletics")
check("spotlight: an Indian or Southeast Asian athlete's later-round finish below the bar still gets a line", sp("Lakshya Sen reaches final at Hylo Open", "badminton")[1] is True and around.sport_of(item("Neeraj Chopra wins gold in Zurich"))[1] is True)
check("spotlight does not steal sports we cover in full: India winning a cricket match is not an 'other sport'", sp("India win the final ODI by five wickets")[0] is None)
check("an ordinary headline is no story", sp("Lakers beat Celtics in overtime")[0] is None and sp("Weather delays training")[0] is None)

# ---- candidates ----------------------------------------------------------------------------------------
fresh = item("Littler wins World Darts Championship final", hours=5)
stale = item("Littler wins World Darts Championship final", hours=50, link="https://x/old")
preview = item("World Darts Championship preview: who can stop Littler?", hours=4)
seen_l = item("Humphries beats Littler in World Matchplay", hours=2, link="https://x/seen")
cands = around.candidates([fresh, stale, preview, seen_l], NOW, seen=["https://x/seen"])
check("candidates: fresh, not seen, and reading like a result or news; a preview, an old story and a seen link are out", [c["link"] for c in cands] == [fresh["link"]], [c["title"] for c in cands])
check("candidates: a withdrawal counts as news", len(around.candidates([item("Carlsen withdraws from Norway Chess after illness", "chess", hours=2)], NOW)) == 1)
check("a theft is not sport: 'Olympic gold stolen from a former hockey captain' is dropped everywhere", around.sport_of(item("Olympic gold, Asian Games silver stolen from former India hockey captain", "hockey")) == (None, False))

check("a line of several results is one item with the title in bold and each result on its own line (readable on a phone); a plain line is unchanged",
      around.line_html("All England Open: men's singles A; women's singles B", "https://w", "Wikipedia", split=True) == '<li><strong>All England Open</strong><br>men&#x27;s singles A<br>women&#x27;s singles B <a href="https://w" rel="noopener">Wikipedia</a></li>'
      and around.line_html("Ireland 43\u201321 Scotland (Six Nations)") == "<li>Ireland 43\u201321 Scotland (Six Nations)</li>")

# ---- Google News and the same story twice -----------------------------------------------------------
gn = (b'<?xml version="1.0"?><rss><channel><item><title>Satwik and Chirag reach All England final - Hindustan Times</title><link>https://news.google.com/rss/articles/abc</link>'
      b'<pubDate>Wed, 04 Nov 2026 22:00:00 GMT</pubDate><description>&lt;ol&gt;related&lt;/ol&gt;</description><source url="https://www.hindustantimes.com">Hindustan Times</source></item></channel></rss>')
pg = feeds.parse_gnews(gn, "Google News")
check("Google News: the publisher becomes the source and leaves the title; the related-headlines clutter is dropped", len(pg) == 1 and pg[0]["source"] == "Hindustan Times" and pg[0]["title"] == "Satwik and Chirag reach All England final" and pg[0]["text"] == "" and pg[0]["link"].startswith("https://news.google.com/"), pg)
check("the feed list now includes Yahoo Sports, The Hindu, The Straits Times, Times of India and Google News searches", {"Yahoo Sports", "The Hindu", "The Straits Times", "Times of India", "Google News"} <= {f[0] for f in around.other_sports.FEEDS} and any(f[1] == "gnews" for f in around.other_sports.FEEDS))
twice = [item("Littler wins World Darts Championship final", hours=5, link="https://x/a"), item("Littler wins World Darts Championship final!", hours=4, link="https://x/b", source="Google News")]
check("candidates: the same headline from two outlets is one candidate", len(around.candidates(twice, NOW)) == 1)

check("headlines in other languages (Korean, Vietnamese ...) are not candidates", around.english("Asian Games gold, foreign players boost KBL season") and not around.english("아시안게임 금메달 외국인 선수") and not around.english("Vi\u1ec7t Nam gi\u00e0nh huy ch\u01b0\u01a1ng v\u00e0ng"))
check("multi-sport games: a past medallist in the news (a ban, a theft, a golf title) is not the Games; the Games themselves are",
      sp("Olympic medallist Barbosu banned for doping violation")[0] is None and sp("Commonwealth Games medallist Hawkes claims Irish Open title")[0] is None and sp("India top the medal table at the Asian Games, win gold in squash")[0] == "games")

# ---- Claude's check -------------------------------------------------------------------------------------
real_call = around.notes.call_json


def fake_claude(answers):
    state = {"n": 0}

    def call(client, system, schema, content, model=None):
        a = answers[min(state["n"], len(answers) - 1)]
        state["n"] += 1
        return a, {"input": 100, "output": 20}
    return call


c0 = cands[0]
good = {"items": [{"link": c0["link"], "kind": "result", "summary": "Littler won the World Darts Championship final."}]}
around.notes.call_json = fake_claude([good])
v, usage = around.classify(object(), cands)
check("Claude: a summary built from the headline's own facts is accepted", v[c0["link"]]["summary"] == "Littler won the World Darts Championship final." and usage["input"] == 100, v)
bad = {"items": [{"link": c0["link"], "kind": "result", "summary": "Luke Littler won his fourth world title, beating Michael van Gerwen 7-2."}]}
around.notes.call_json = fake_claude([bad, bad])
v, _ = around.classify(object(), cands)
check("Claude: a summary with invented names or numbers fails both tries, so the page shows the source's own headline (summary None)", v[c0["link"]]["summary"] is None and v[c0["link"]]["kind"] == "result", v)
around.notes.call_json = fake_claude([bad, good])
v, _ = around.classify(object(), cands)
check("Claude: a rewrite that passes on the second try is used", v[c0["link"]]["summary"] == "Littler won the World Darts Championship final.")
around.notes.call_json = fake_claude([{"items": [{"link": c0["link"], "kind": "none", "summary": ""}]}])
v, _ = around.classify(object(), cands)
check("Claude: 'none' keeps a headline off the page", v[c0["link"]]["kind"] == "none")
around.notes.call_json = fake_claude([None])
v, _ = around.classify(object(), cands)
check("Claude failing gives an empty verdict, never an error", v == {})

# ---- stories --------------------------------------------------------------------------------------------
pool = [item(f"Feature {i}: a surprising tale from the pool number {i}", f"Details about tale {i}.", hours=4, link=f"https://x/f{i}") for i in range(6)]
picks = {"picks": [{"n": i, "text": f"Tale {i - 1} turns out to be a surprise."} for i in (1, 2, 3)]}
around.notes.call_json = fake_claude([picks])
got, _ = around.stories(object(), pool, NOW, set())
check("stories: three picks that pass the check are shown, each with its link", len(got) == 3 and all(g["link"].startswith("https://x/f") for g in got), got)
around.notes.call_json = fake_claude([{"picks": picks["picks"][:2]}])
check("stories: fewer than three survivors means none (a thin list is worse than none)", around.stories(object(), pool, NOW, set())[0] == [])
check("stories: a link shown in the last week is not offered again", around.story_pool(pool, NOW, {"https://x/f0", "https://x/f1"}) == pool[2:])
check("stories: without Claude there are none", around.stories(None, pool, NOW, set())[0] == [])
around.notes.call_json = fake_claude([{"picks": [{"n": 1, "text": "Mbappe scored 40 goals in 12 matches."}] * 3}])
check("stories: a text with invented figures is rejected", around.stories(object(), pool, NOW, set())[0] == [])

# ---- the whole block -------------------------------------------------------------------------------------
around.notes.call_json = real_call


def claude_all(client, system, schema, content, model=None):
    """A fake Claude that calls every headline a result with a plain, checkable sentence; no stories."""
    if system != around.SYSTEM:
        return {"picks": []}, {"input": 1, "output": 1}
    items = json.loads(content.split("Items:\n", 1)[1])
    return {"items": [{"link": i["link"], "kind": "result", "summary": "A result was reported."} for i in items]}, {"input": 10, "output": 5}


news = [item("Littler wins World Darts Championship final", hours=5), item("Gukesh wins Candidates in Toronto", "chess", hours=4, source="ChessBase")]
six_now = copy.deepcopy(six)
next(e for e in six_now["events"] if e["status"]["type"]["name"] == "STATUS_FINAL")["date"] = (NOW - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%MZ")
around.notes.call_json = claude_all
out = around.run(NOW, {}, Src(rugby={"180659": six_now}, golf={"pga": major}, news=news), object())
html = out["sections"][0]["html"]
check("the block: rugby, then golf, then chess, then darts, each under its own heading", [html.index(f'">{n}</h4>') for n in ("Rugby", "Golf", "Chess", "Darts")] == sorted(html.index(f'">{n}</h4>') for n in ("Rugby", "Golf", "Chess", "Darts")) and html.count('<h4 class="sport') == 4 and html.count("sport first") == 1, html[:500])
check("the feed lines are Claude's sentence with the source's link and name", "A result was reported." in html and 'href="https://x/' in html and ">ChessBase</a>" in html and ">BBC Sport</a>" in html)
out2 = around.run(NOW, {}, Src(golf={"pga": major}, news=news), object())
again = around.run(NOW, out2["state"]["around"], Src(golf={"pga": major}, news=news), object())
check("the block: nothing shown twice — a second run with the saved state has no sections", again["sections"] == [], [s["id"] for s in again["sections"]])
many = [item(f"Wins World Darts Championship round {i}", hours=2, link=f"https://x/d{i}") for i in range(6)]
out3 = around.run(NOW, {}, Src(news=many), object())
check("the block: at most 2 feed lines for one sport (D, 2026-11-05)", out3["sections"][0]["html"].count("<li>") == 2, out3["sections"][0]["html"].count("<li>"))
around.notes.call_json = real_call
nocl = around.run(NOW, {}, Src(rugby={"180659": six_now}, golf={"pga": major}, news=news), None)
check("without Claude there are no feed lines at all (no plain headlines), only the structured sports", '">Rugby</h4>' in nocl["sections"][0]["html"] and "Darts" not in nocl["sections"][0]["html"] and "Chess" not in nocl["sections"][0]["html"] and "<a href=\"https://x/" not in nocl["sections"][0]["html"])
around.notes.call_json = claude_all
tab = [item("Tanvi Patri scripts history, first Indian woman in the Youth Olympics final", hours=2, source="Facebook"), item("PV Sindhu qualifies for World Tour Finals after Hylo Open win", "badminton", hours=2, source="The News Mill"),
       item("Satwik and Chirag win the All England Open title", "badminton", hours=2, source="The Hindu"), item("Scheffler wins the Masters", "golf", hours=2, source="BBC Sport"),
       item("Diamond League final: Kerr wins the mile", "athletics", hours=2, source="BBC Sport"), item("Kerr wins the Diamond League mile in Brussels", "athletics", hours=2, source="Yahoo Sports", link="https://x/y")]
got = around.candidates(tab, NOW)
check("the feed candidates are only from the outlets D would trust (BBC, Guardian, ESPN, Straits Times, The Hindu, ChessBase): no Facebook, no small sites, no Yahoo", {c["source"] for c in got} <= {"BBC Sport"} and any("Diamond League" in c["title"] for c in got), [(c["source"], c["title"][:40]) for c in got])
check("sports with a structured source of their own (badminton, golf, UFC) never come from the feeds", not any(c["sport"] in around.NO_FEED for c in around.candidates([item("Satwik and Chirag win the All England Open title", "badminton", hours=2), item("Scheffler wins the Masters", "golf", hours=2)], NOW)))
check("there is no Spotlight section any more", "spotlight" not in around.ORDER or not any(c["sport"] == "spotlight" for c in around.candidates([item("Neeraj Chopra wins gold in Zurich", hours=2)], NOW)))
quiet = around.run(NOW, {}, Src(news=[item("Weather delays training")]), object())
check("a quiet day gives no sections", quiet["sections"] == [] and quiet["state"]["around"]["seen"] == [])
broken = around.run(NOW, {}, Src(boom=("rugby", "golf", "ufc", "news")), object())
check("every page failing gives an empty block and counts the failures, never an error", broken["sections"] == [] and broken["stats"]["failed"] >= 3, broken["stats"])
around.notes.call_json = real_call

# ---- 8 November 2026 (D): the Games named while they are on, every Games line with its sport, India and Singapore finals, rugby tables ----
around.GAMES = REAL_GAMES
from datetime import date as _date  # noqa: E402
on = around.games_on(_date(2026, 11, 8))
check("the Youth Olympic Games are on 8 November: Dakar, day 9 of 14, until Friday 13 November", on and on[:4] == ("Youth Olympic Games", "Dakar", 9, 14) and "Dakar \u00b7 Day 9 of 14 \u00b7 until Fri 13 Nov" in around.games_html(on), on)
check("no Games on 20 November", around.games_on(_date(2026, 11, 20)) is None)


def claude_sport(client, system, schema, content, model=None):
    if system != around.SYSTEM:
        return {"picks": []}, {"input": 1, "output": 1}
    items = json.loads(content.split("Items:\n", 1)[1])
    return {"items": [{"link": i["link"], "kind": "result", "summary": "A result was reported.", "sport": "Badminton" if "badminton" in (i["headline"] + i["blurb"]).lower() else "Judo"} for i in items]}, {"input": 10, "output": 5}


around.notes.call_json = claude_sport
G_NOW = utc(2026, 11, 7, 23, 15)
gitem = lambda title, text="", hours=3, link=None: {"source": "The Hindu", "title": title, "text": text, "link": link or f"https://x/{abs(hash(title))}", "published": G_NOW - timedelta(hours=hours)}  # noqa: E731
yog = around.run(G_NOW, {}, Src(news=[gitem("Tanvi Patri wins Youth Olympic Games silver", "The badminton prodigy saved six match points in the final"),
                                       gitem("Indian teenager claims Youth Olympic Games bronze", "a result in Dakar")]), object())
gh = yog["sections"][0]["html"]
check("while the Games are on, Other Sports opens with them, named, with the host and the day", gh.startswith('<h4 class="sport first">Youth Olympic Games</h4><p class="games-sub">Dakar'), gh[:200])
check("a Games line starts with its sport in bold when the source names it", "<li><strong>Badminton:</strong> A result was reported." in gh, gh)
check("a Games line whose source does not name the sport is left out, never guessed (Claude said Judo, the text never did)", "Judo" not in gh and gh.count("<li>") == 1, gh)
quiet_games = around.run(G_NOW, {}, Src(), object())
check("the Games are named even on a day with no Games result yet", quiet_games["sections"] and "Youth Olympic Games" in quiet_games["sections"][0]["html"])
check("the sport has to be backed by the text: 'Badminton' with 'badminton' in the blurb is kept, 'Judo' is not",
      around.sport_named("Badminton", {"title": "x", "text": "the badminton prodigy"}) == "Badminton" and around.sport_named("Judo", {"title": "silver", "text": "final"}) == "")
around.GAMES = []
hk = [gitem("India beat Japan 4-1 to lift the Asian Champions Trophy hockey title"), gitem("Singapore reach hockey semi-final at the regional cup", link="https://x/sg"),
      gitem("India hockey team names new coach", link="https://x/coach")]
hko = around.run(G_NOW, {}, Src(news=hk), object())
hh = hko["sections"][0]["html"] if hko["sections"] else ""
check("hockey: India's Asian Champions Trophy title and Singapore's semi-final both get a line (D, 2026-11-08), a coach story does not", '">Field hockey</h4>' in hh and hh.count("<li>") == 2, hh)
check("the India and Singapore rule: a final or semi-final in a covered sport counts even when the event is not on the list",
      around.sport_of({"title": "Singapore win handball title at SEA championship", "text": ""})[0] == "handball" and around.sport_of({"title": "India handball team arrives", "text": ""})[0] is None)
from kickoff import rugbytables  # noqa: E402
nc = {"children": [{"standings": {"entries": [{"team": {"displayName": t}, "stats": [{"name": "gamesPlayed", "displayValue": "4"}, {"name": "gamesWon", "displayValue": str(w)}, {"name": "gamesLost", "displayValue": str(4 - w)},
      {"name": "pointsDifference", "displayValue": f"{pd:+d}"}, {"name": "points", "displayValue": str(p)}]} for t, w, pd, p in
      [("Ireland", 3, 29, 15), ("South Africa", 4, 140, 20), ("France", 2, 41, 12), ("New Zealand", 4, 73, 20), ("Italy", 0, -153, 0), ("Japan", 1, -33, 5)]]}}]}
th = rugbytables.table_html("17567", nc)
check("Nations Championship: two pools, the Six Nations sides North, the others South, each ranked by points then difference",
      th.index("Northern pool") < th.index("Ireland") < th.index("France") < th.index("Italy") < th.index("Southern pool") < th.index("South Africa") < th.index("New Zealand") < th.index("Japan"), th)
check("the rugby table columns fit a phone: # Team P W L PD Pts, the difference signed", "<th class=\"n\">PD</th>" in th and ">+140<" in th and ">-153<" in th and 'class="rugbyt"' in th, th[:300])
check("a season not started (every side on 0 played) or an unreadable feed gives no table", rugbytables.table_html("244293", {"children": [{"standings": {"entries": []}}]}) == "" and rugbytables.table_html("180659", {"children": [{"standings": {"entries": [{"team": {"displayName": "France"}, "stats": []}]}}]}) == "")
rs = Src(rugby={"180659": six_now})
rs.tables = {"180659": {"children": [{"standings": {"entries": [{"team": {"displayName": "France"}, "stats": [{"name": "gamesPlayed", "displayValue": "1"}, {"name": "gamesWon", "displayValue": "1"},
             {"name": "gamesLost", "displayValue": "0"}, {"name": "pointsDifference", "displayValue": "+12"}, {"name": "points", "displayValue": "5"}]}]}}]}}
rt = around.run(NOW, {}, rs, None)["sections"][0]["html"]
check("a morning with a Six Nations result shows the Six Nations table under the rugby results", rt.index('">Rugby</h4>') < rt.index("Ireland 43") < rt.index(">Six Nations</th>"), rt[:400])
around.notes.call_json = real_call

# ---- the edition -------------------------------------------------------------------------------------------
adapter = lambda n, d, s: around.run(NOW, {}, Src(golf={"pga": major}, news=news), None)  # noqa: E731
ed = daily.build_edition(NOW, NOW.date(), {}, [("around", "Other Sports", adapter)])
secs = {s["id"]: s for s in ed["edition"]["sections"]}
check("the edition puts the other sports under Around The Sporting World and saves their state", "around" in secs and "Other Sports" in secs["around"]["html"] and "around" in ed["state"], list(secs))
check("around is one of the saved states", "around" in daily.STATE_NAMES)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
