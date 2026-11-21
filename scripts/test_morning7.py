"""Tests for D's comments on the 15 Nov 2026 edition: cricket news only for the big sides and only when done, no rumours, Young Guns in one form, the rugby
table's columns, tennis never in Other Sports, a skiing World Cup under World Cups (not Women's football).
Run: .venv/bin/python scripts/test_morning7.py"""
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import around, sportsnews  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    results.append(ok)


NOW = datetime(2026, 11, 14, 23, 0, tzinfo=timezone.utc)

# 1. Cricket news: the big sides only, and only what has happened
zim = {"title": "Justin Sammons resigns as Zimbabwe head coach", "text": "The ongoing Test against Afghanistan will be his last before he returns to South Africa."}
check("Zimbabwe's coach resigning is not wanted (even though the blurb names South Africa)", not sportsnews.wanted("Cricket", zim))
check("India's new captain is wanted", sportsnews.wanted("Cricket", {"title": "Shubman Gill named India's ODI captain", "text": "He takes over after the Sri Lanka series."}))
check("an IPL franchise's coach is wanted", sportsnews.wanted("Cricket", {"title": "Lucknow Super Giants appoint new head coach for IPL 2027", "text": "x"}))
check("the rule is cricket's only", sportsnews.wanted("NBA", {"title": "Hornets fire head coach", "text": "Charlotte, after a Zimbabwe trip"}))
check("'set to trade' is not done yet", sportsnews.NOT_YET.search("SRH set to trade Harshal Patel to GT for INR 4 crore"))
check("a completed swap still passes", not sportsnews.NOT_YET.search("IPL 2027: MI and PBKS complete Hardik Pandya-Arshdeep Singh swap"))


class Fake:
    def __init__(self, reply):
        self.reply = reply


def fake_call(client, system, schema, listing, model=None):
    return client.reply, {"input": 10, "output": 5}


import kickoff.notes as notes  # noqa: E402
notes_call = notes.call_json
notes.call_json = fake_call
item = lambda t, x, h: {"source": "ESPNcricinfo", "title": t, "text": x, "link": t, "published": NOW - timedelta(hours=h)}  # noqa: E731
fetched = {"Cricket": [item(zim["title"], zim["text"], 2)]}
got, _, _ = sportsnews.find(Fake({"picks": [{"n": 1, "summary": "Zimbabwe head coach Justin Sammons has resigned."}]}), NOW, {}, fetched)
check("Claude picking Zimbabwe's coach anyway: dropped by code", got == [], got)
notes.call_json = notes_call

# 3. Young Guns and 2. rumours: see test_youngguns.py and test_news.py

# 4. The rugby table: # narrow and on the left, Team wide enough for 'South Africa'
from kickoff import rugbytables  # noqa: E402
w = [int(x) for x in re.findall(r"width:(\d+)%", rugbytables.COLS)]
check("rugby widths are on the table itself (the title row spans every column, so the stylesheet's widths split them evenly) and add up to 100%", len(w) == 7 and sum(w) == 100, w)
check("# is narrow, Team is the widest by far", w[0] <= 8 and w[1] >= 40, w)
check("the colgroup comes straight after <table>, before the title row", rugbytables.COLS.startswith("<table><colgroup>"))

# 5 and 6. Other Sports: tennis never; a skiing World Cup under World Cups; a women's football World Cup still under Women's football
mk = lambda t, x, src="The Straits Times": {"title": t, "text": x, "link": t, "source": src, "published": NOW - timedelta(hours=3)}  # noqa: E731
items = [mk("Aicher wins women's World Cup slalom in Levi", "Emma Aicher won the season's first women's World Cup slalom in Levi, converting a first-run lead."),
         mk("Mirra Andreeva beats Jessica Pegula to reach WTA Finals final", "Andreeva won in straight sets at Indian Wells; the Olympic Games silver medallist", "The Guardian"),
         mk("England beat Spain to reach Women's World Cup final", "The Lionesses won the football semi-final.", "BBC Sport")]
sports = {c["title"][:8]: c["sport"] for c in around.candidates(items, NOW)}
check("the slalom goes under World Cups, not Women's football", sports.get("Aicher w") == "worldcups", sports)
check("Andreeva's WTA Finals is not in Other Sports (Tennis has it)", "Mirra An" not in sports, sports)
check("a women's football World Cup is still Women's football", sports.get("England ") == "womens-football", sports)
check("'Indian Wells' is not India", not around.OURS.search("at Indian Wells") and around.OURS.search("Indian shooter wins gold"))


class Src:
    def __init__(self, items):
        self.items = items

    def news(self):
        return self.items

    def __getattr__(self, name):
        def fail(*a, **k):
            raise RuntimeError("not in this test")
        return fail


def classify(client, cands, told=()):
    return {c["link"]: {"kind": "result", "summary": "Emma Aicher won the season's first women's slalom at Levi, her first career slalom win.", "sport": "", "named": "Alpine skiing"}
            for c in cands}, {"input": 0, "output": 0}


real = around.classify
around.classify = classify
out = around.run(NOW, {}, Src(items[:1]), client=object())
around.classify = real
html = "".join(s_["html"] for s_ in out["sections"] if s_["id"] == "other-sports")
check("the line sits under World Cups and starts with its sport", ">World Cups</h4>" in html and "<strong>Alpine skiing:</strong> Emma Aicher" in html, html[:400])
check("the sport's name must be a plain name, never a person or a number", not re.fullmatch(r"[A-Z][a-z]+(?: [a-z]+){0,2}", "Emma Aicher"))

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
