"""Tests for D's comments on the 13 Nov 2026 edition: Arsenal's games in any competition are key scores, the score line above the Arsenal story, All-MLB by
position, plain manager news. (The Nations League and NBA standings are in test_natleague.py and test_nba.py.)
Run: .venv/bin/python scripts/test_morning6.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import awards, events, focus, football, news  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


# 1. Arsenal Women in the Women's Champions League
check("the competitions the football run reads", {"eng.1", "uefa.champions", "eng.fa", "eng.w.1"} <= football.COVERED and "uefa.wchampions" not in football.COVERED)
uwcl = {"id": "1", "league": "uefa.wchampions", "competition": "UEFA Women's Champions League", "completed": True, "home_score": 1, "away_score": 1,
        "home": {"id": "4573", "name": "Barcelona"}, "away": {"id": "19973", "name": "Arsenal"},
        "goals": [{"minute": "22'", "player": "Frida Maanum", "side": "away"}, {"minute": "59'", "player": "Caroline Graham Hansen", "side": "home"}], "reds": []}
got = events.football([(uwcl["competition"], [uwcl])], 4)
check("Barcelona 1-1 Arsenal Women is a key score, second after Arsenal's", got and got[0]["first"] == 2 and got[0]["text"] == "Women's Champions League: Barcelona 1\u20131 Arsenal", got)
line = focus.score_lines_html([{"competition": "UEFA Women's Champions League", "home": "Barcelona", "away": "Arsenal", "final_score": "1-1"}])
check("the score line: competition, then the score in gold", "Women&#x27;s Champions League</span> \u00b7 Barcelona <span class=\"n\">1\u20131</span> Arsenal" in line, line)
check("no games: no line", focus.score_lines_html([]) == "")

# 3. All-MLB by position
infos = [{"name": "Dylan Cease", "pos": "SP"}, {"name": "Gabriel Moreno", "pos": "C"}, {"name": "Chris Sale", "pos": "SP"}, {"name": "Mason Miller", "pos": "RP"},
         {"name": "Yordan Alvarez", "pos": "DH"}, {"name": "Pete Alonso", "pos": "1B"}]
rows = awards.mlb_positions(infos, ["TOR", "ARI", "ATL", "SD", "HOU", "BAL"])
check("catcher first, pitchers last, two starters numbered", rows == [("C", "Gabriel Moreno", "ARI"), ("1B", "Pete Alonso", "BAL"), ("DH", "Yordan Alvarez", "HOU"),
                                                                       ("SP 1", "Chris Sale", "ATL"), ("SP 2", "Dylan Cease", "TOR"), ("RP", "Mason Miller", "SD")], rows)

# 4. Plain manager news
check("the 13 Nov Palace line is sent back on both counts", len(news.plain_problems("Steve Parish has parted ways with Pierre Sage after five months.", "Crystal Palace", "manager_sacked")) == 2)
check("the plain line passes", news.plain_problems("Crystal Palace have sacked manager Pierre Sage after five months.", "Crystal Palace", "manager_sacked") == [])
check("a transfer can 'part company' with nobody, but must still start with the club", news.plain_problems("Arsenal have signed a midfielder.", "Arsenal", "transfer_confirmed") == [])

# 5. Records and the other sports' news (D, 2026-11-13: Harry Kane's caps record, Lawson and Lindblad at Racing Bulls, the Pandya-Arshdeep IPL swap)
from datetime import datetime, timezone  # noqa: E402
from kickoff import sportsnews  # noqa: E402
now = datetime(2026, 11, 13, 23, 15, tzinfo=timezone.utc)
kane = {"title": "Harry Kane becomes England's most-capped player", "text": "The captain won his 126th cap against Croatia.", "link": "k", "published": now, "source": "BBC Sport"}
got = news.candidates([kane], {"Arsenal", "Bayern Munich"}, now, nations={"England", "Spain"})
check("Kane's record is a candidate through England (a top-30 nation), as a milestone", got and got[0]["hint"] == "milestone" and got[0]["clubs"] == ["England"], got)
check("without the nations it is not (as before)", news.candidates([kane], {"Arsenal"}, now) == [])
shown = news.apply_rules(got, {"k": {"kind": "milestone", "club": "England", "summary": "England captain Harry Kane has become his country's most-capped player."}})
check("a milestone is shown, in Biggest News only (not under Transfers And Managers)", shown and shown[0]["section"] == "records" and news.html(shown, "football", "Transfers And Managers") == "")
check("and ranks after sackings, before transfers", [i["kind"] for i in sorted([{"kind": "transfer_confirmed"}, {"kind": "milestone"}, {"kind": "manager_sacked"}],
                                                                                  key=lambda i: events.NEWS_RANK[i["kind"]])] == ["manager_sacked", "milestone", "transfer_confirmed"])

def item(title, hours, link=None, text=""):
    from datetime import timedelta
    return {"source": "X", "title": title, "text": text, "link": link or title, "published": now - timedelta(hours=hours)}

fetched = {"Cricket": [item("IPL 2027: MI and PBKS complete Hardik Pandya-Arshdeep Singh swap", 61, text="Mumbai Indians and Punjab Kings have completed the trade for IPL 2027."), item("England v Australia – as it happened", 3),
                       item("Cummins goes above and beyond, but questions remain | Geoff Lemon", 5), item("Old news", 80)],
           "F1": [item("Lindblad and Lawson to continue at Racing Bulls", 31, text="Liam Lawson and Arvid Lindblad will stay with the team in 2027."), item("The Chequered Flag Podcast", 4), item("Could Hamilton retire?", 2)],
           "NFL": [], "NBA": []}
c = [i["title"] for _, i in sportsnews.candidates(fetched, now)]
check("candidates: the IPL swap (61 hours old) and the Racing Bulls seats; no live blog, column, podcast, question or 4-day-old item",
      c == ["IPL 2027: MI and PBKS complete Hardik Pandya-Arshdeep Singh swap", "Lindblad and Lawson to continue at Racing Bulls"], c)
check("a story judged before is not judged again", [i["title"] for _, i in sportsnews.candidates(fetched, now, {"Lindblad and Lawson to continue at Racing Bulls": now.isoformat()})]
      == ["IPL 2027: MI and PBKS complete Hardik Pandya-Arshdeep Singh swap"])


class Fake:
    pass


calls = []
real = sportsnews.notes.call_json
sportsnews.notes.call_json = lambda client, system, schema, content, model=None: (calls.append(content) or {"picks": [
    {"n": 1, "summary": "Hardik Pandya and Arshdeep Singh have swapped teams, Mumbai Indians and Punjab Kings, for IPL 2027."}, {"n": 2, "summary": "Racing Bulls have kept Liam Lawson and Arvid Lindblad for 2027."},
    {"n": 9, "summary": "nonsense"}]}, {"input": 100, "output": 20})
items, st, usage = sportsnews.find(Fake(), now, {}, fetched)
check("Claude's picks, labelled by sport, with the link", [i["text"] for i in items] == ["Cricket: Hardik Pandya and Arshdeep Singh have swapped teams, Mumbai Indians and Punjab Kings, for IPL 2027.",
                                                                                       "F1: Racing Bulls have kept Liam Lawson and Arvid Lindblad for 2027."] and all(i["us"] for i in items), items)
check("a summary that fails the checks (an invented name) falls back to the source's headline",
      sportsnews.check("Sachin Tendulkar has joined Racing Bulls.", fetched["F1"][0]) != [])
check("every candidate is now seen; usage recorded", set(st["seen"]) == {"IPL 2027: MI and PBKS complete Hardik Pandya-Arshdeep Singh swap", "Lindblad and Lawson to continue at Racing Bulls"} and usage["input"] == 100)
sportsnews.notes.call_json = lambda client, system, schema, content, model=None: (None, {"input": 0, "output": 0})
items, st, _ = sportsnews.find(Fake(), now, {}, fetched)
check("a failed call shows nothing and judges nothing (tomorrow tries again)", items == [] and st["seen"] == {})
n = len(calls)
items, st, _ = sportsnews.find(None, now, {}, fetched)
check("no Claude: nothing, no call", items == [] and len(calls) == n)
sportsnews.notes.call_json = real

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
