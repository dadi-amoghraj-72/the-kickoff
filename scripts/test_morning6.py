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

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
