"""Tests for D's comments of 21 Nov 2026: a story already told in the last 7 days is not told again (Pochettino ran four mornings, Thomas Frank three,
Bottas two), and football's team news, transfers and managers stay in their own sections, not Biggest News.
Run: .venv/bin/python scripts/test_morning8.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import bigstuff, daily, events, news, sportsnews  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


D14 = datetime(2026, 11, 13, 23, 15, tzinfo=timezone.utc)
day = lambda n: D14 + timedelta(days=n)  # noqa: E731


def item(club, kind, summary, link):
    return {"kind": kind, "club": club, "summary": summary, "headline": "h", "source": "BBC Sport", "link": link, "published": D14, "section": "football"}


poch1 = item("Manchester United", "manager_appointed", "Manchester United have appointed Mauricio Pochettino as their new head coach.", "a")
poch2 = item("Manchester United", "manager_appointed", "Manchester United have a new boss in Mauricio Pochettino, who says he will make the club the most successful in Manchester.", "b")
poch3 = item("Manchester United", "manager_appointed", "Manchester United confirmed Mauricio Pochettino as their new head coach, and compensation owed to US Soccer is part of a near £100m cost.", "c")

# 1. Football: once told, not again for 7 days
shown, told = news.fresh([poch1], [], day(0))
check("14 Nov: Pochettino's appointment is shown and remembered", shown == [poch1] and told[0]["club"] == "Manchester United", told)
shown, told = news.fresh([poch2], told, day(5))
check("19 Nov: a new article about the same appointment is not shown", shown == [], shown)
shown, told = news.fresh([poch3], told, day(6))
check("20 Nov: nor the next one (a manager: the same club and kind is the same story, whatever the wording)", shown == [])
sack = item("Manchester United", "manager_sacked", "Manchester United have sacked Mauricio Pochettino.", "d")
check("a different kind (a sacking after an appointment) is new", news.fresh([sack], told, day(6))[0] == [sack])
check("after 7 days the memory is gone", news.fresh([poch3], told, day(8))[0] == [poch3] and all(t["at"] != day(0).isoformat() for t in news.fresh([], told, day(8))[1]))
saka1 = item("Arsenal", "injury", "Arsenal forward Bukayo Saka may not return before Christmas with a thigh injury, Mikel Arteta has said.", "e")
saka2 = item("Arsenal", "injury", "Arsenal's Bukayo Saka will miss the north London derby with his thigh injury.", "f")
ode = item("Arsenal", "injury", "Arsenal captain Martin Odegaard is out until Christmas with an ankle injury.", "g")
_, t2 = news.fresh([saka1], [], day(7))
check("Saka's injury told once is not told again", news.fresh([saka2], t2, day(8))[0] == [])
check("Odegaard's injury at the same club is a different story ('Christmas' is not a name)", news.fresh([ode], t2, day(8))[0] == [ode])
plain = {**poch2, "kind": "manager_news", "summary": None, "headline": "Pochettino arrives at Manchester United"}
check("a run without Claude ('Manager' tag) does not repeat a told appointment", news.fresh([plain], told, day(5))[0] == [])
check("the memory is saved every day (news_told)", "news_told" in daily.FOOTBALL_STATE and "news_told" in daily.STATE_NAMES)

# 1. Other sports: two names in common is the same story
bot1 = {"source": "BBC Sport", "title": "Bottas' stay at Cadillac confirmed for 2027", "text": "", "link": "x1", "published": day(5) - timedelta(hours=2)}
bot2 = {"source": "ESPN", "title": "Valtteri Bottas to race for Cadillac in 2027 after Colton Herta 'noise'", "text": "", "link": "x2", "published": day(6) - timedelta(hours=2)}
mi1 = {"source": "ESPNcricinfo", "title": "Mumbai Indians trade Rohit Sharma to Lucknow Super Giants", "text": "", "link": "x3", "published": day(5) - timedelta(hours=2)}
mi2 = {"source": "ESPNcricinfo", "title": "Mumbai Indians sign Shardul Thakur from Delhi Capitals", "text": "", "link": "x4", "published": day(6) - timedelta(hours=2)}


class Fake:
    def __init__(self, reply):
        self.reply = reply


import kickoff.notes as notes  # noqa: E402
_real = notes.call_json
notes.call_json = lambda client, *a, **k: (client.reply, {"input": 1, "output": 1})
got, st, _ = sportsnews.find(Fake({"picks": [{"n": 1, "summary": ""}, {"n": 2, "summary": ""}]}), day(5), {}, {"F1": [bot1], "Cricket": [mi1]})
check("19 Nov: Bottas and the Mumbai trade are shown and remembered", len(got) == 2 and len(st["told"]) == 2, (got, st))
got2, st2, _ = sportsnews.find(Fake({"picks": [{"n": 1, "summary": ""}, {"n": 2, "summary": ""}]}), day(6), st, {"F1": [bot2], "Cricket": [mi2]})
check("20 Nov: Bottas again is dropped before Claude sees it; a different Mumbai Indians trade is new", [g["link"] for g in got2] == ["x4"], got2)
check("the told memory keeps 7 days", sportsnews.find(None, day(14), st2, {})[1]["told"] == [])
notes.call_json = _real

# 2b. Biggest News: football's records only; the rest stays in its section
rec = item("England", "milestone", "England captain Harry Kane has become the country's most-capped men's player.", "r")
rec["section"] = "records"
fn = events.football_news([poch1, saka1, rec])
check("Biggest News takes the record, not the appointment or the injury", [x["link"] for x in fn] == ["r"], fn)
us = [{"text": "F1: Bottas stays at Cadillac", "us": True, "link": "u1"}, {"text": "Cricket: Dhoni ends IPL career", "us": True, "link": "u2"}]
check("with no record, Biggest News is the other sports' news", [i["link"] for i in bigstuff.top_news(events.football_news([poch1]) + us)] == ["u1", "u2"])
check("the appointment still shows in Transfers And Managers", "Pochettino" in news.html([poch1], "football", "Transfers And Managers"))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
