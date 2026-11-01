"""Offline tests for the news pipeline. Run: .venv/bin/python scripts/test_news.py"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import news, settings  # noqa: E402
from kickoff.http import SourceError  # noqa: E402
from kickoff.sources import feeds  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))
    results.append(ok)


# ---- Parsing the real saved feeds ----
bbc = feeds.parse_rss((FIX / "news_bbc.xml").read_bytes(), "BBC Sport")
gdn = feeds.parse_rss((FIX / "news_guardian.xml").read_bytes(), "The Guardian")
esp = feeds.parse_espn((FIX / "news_espn.json").read_bytes(), "ESPN")
check("BBC, Guardian and ESPN samples all parse into items", len(bbc) >= 10 and len(gdn) >= 10 and len(esp) >= 4, (len(bbc), len(gdn), len(esp)))
check("every item has a title, a link and a UTC time", all(i["title"] and i["link"].startswith("http") and i["published"].tzinfo for i in bbc + gdn + esp))
check("Guardian blurbs have their HTML removed", all("<" not in i["text"] and "&amp;" not in i["text"] for i in gdn), [i["text"][:60] for i in gdn if "<" in i["text"]][:1])
check("clean() strips tags, decodes entities and squeezes spaces", feeds.clean("<p>Arsenal &amp;  <b>Spurs</b>\n win</p>") == "Arsenal & Spurs win")

# ---- Fetching: a failing feed is skipped, duplicates removed ----
RAW = {"bbc": (FIX / "news_bbc.xml").read_bytes(), "gdn": (FIX / "news_guardian.xml").read_bytes()}


def fake_bytes(url, *a, **k):
    if "bbci" in url:
        return RAW["bbc"]
    if "theguardian" in url and "arsenal" not in url:
        return RAW["gdn"]
    raise SourceError("HTTP 404")


feeds.get_bytes = fake_bytes
two = [("BBC Sport", "rss", "https://feeds.bbci.co.uk/a"), ("BBC Sport", "rss", "https://feeds.bbci.co.uk/b"),
       ("The Guardian", "rss", "https://www.theguardian.com/football/rss"), ("The Guardian", "rss", "https://www.theguardian.com/football/arsenal/rss")]
got = feeds.fetch_all(two)
check("one feed failing does not stop the others, and a link seen twice appears once", len(got) == len(bbc) + len(gdn) and len({i["link"] for i in got}) == len(got), len(got))
check("items come out newest first", [i["published"] for i in got] == sorted((i["published"] for i in got), reverse=True))
try:
    feeds.fetch_all([("X", "rss", "https://nope/zzz")])
    check("all feeds failing raises one clear error", False)
except SourceError:
    check("all feeds failing raises one clear error", True)

# ---- The code filter ----
NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
NAMES = news.club_aliases({"eng.1": [{"team": "Nottingham Forest", "short": "Forest"}]})
mk = lambda title, text="", hours=2, link=None, source="BBC Sport": {"source": source, "title": title, "text": text,  # noqa: E731
                                                                      "link": link or f"https://x/{title}", "published": NOW - timedelta(hours=hours)}
check("club names include our 17, nicknames and the league tables' names", {"Arsenal", "Spurs", "Real Madrid", "Nottingham Forest", "Forest"} <= NAMES)
check("a club is found by whole name only", news.mentioned(mk("Comoros beat Italy"), NAMES) == [] and "Como" in news.mentioned(mk("Como sign a striker"), NAMES))
check("'Inter' is not found inside 'International'", news.mentioned(mk("International break begins"), NAMES) == [])
check("categories by priority: a sacking beats a transfer word", news.category(mk("Forest sack manager after transfer row")) == "managerial")
check("transfer_done, injury and transfer_talk are recognised",
      (news.category(mk("Arsenal complete signing of striker")), news.category(mk("Saka ruled out for a month")), news.category(mk("Chelsea linked with a bid"))) == ("transfer_done", "injury", "transfer_talk"))
check("a match report with no news words is not a candidate", news.candidates([mk("Arsenal beat Liverpool 1-0")], NAMES, NOW) == [])
cs = news.candidates([mk("Arsenal complete signing of striker"), mk("Arsenal complete signing of striker", hours=40, link="https://x/old"),
                      mk("Arsenal sign keeper", link="https://x/seen"), mk("Strikers sign deals", "no club named here")], NAMES, NOW, seen_links={"https://x/seen"})
check("recent, unseen, club-naming news is kept; old, already-seen and club-less is dropped", [c["link"] for c in cs] == ["https://x/Arsenal complete signing of striker"], [c["link"] for c in cs])
check("an item dated in the future is ignored", news.candidates([mk("Arsenal sign keeper", hours=-5)], NAMES, NOW) == [])
real = news.candidates(sorted(bbc + gdn + esp, key=lambda i: i["published"], reverse=True), NAMES, max(i["published"] for i in bbc + gdn + esp))
check("on the real samples the filter narrows many items to a handful", 0 < len(real) < 15, len(real))


# ---- Claude (fake) ----
class Fake:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.beta = NS(messages=NS(create=self._create))
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def reply(entries, stop="end_turn"):
    return NS(stop_reason=stop, usage=NS(input_tokens=900, output_tokens=120), content=[NS(type="text", text=json.dumps({"items": entries}))])


A = {**mk("Arsenal complete signing of Spanish midfielder", "The Gunners have announced the arrival of a Spanish midfielder on a four-year deal."),
     "hint": "transfer_done", "clubs": ["Arsenal"]}
B = {**mk("Forest sack Glasner after another defeat", "Nottingham Forest have parted company with head coach Glasner.", link="https://x/forest"),
     "hint": "managerial", "clubs": ["Nottingham Forest"]}
C = {**mk("Glasner fears he will be next Forest sacking", "The Forest boss admits pressure is growing.", link="https://x/pressure"),
     "hint": "managerial", "clubs": ["Nottingham Forest"]}
good = {"link": A["link"], "kind": "transfer_confirmed", "club": "Arsenal", "summary": "Arsenal have signed a Spanish midfielder to a four-year contract."}
sack = {"link": B["link"], "kind": "manager_sacked", "club": "Nottingham Forest", "summary": "Nottingham Forest have parted ways with head coach Glasner."}
none = {"link": C["link"], "kind": "none", "club": "", "summary": ""}
c = Fake([reply([good, sack, none])])
res, usage = news.classify(c, [A, B, C])
check("good classifications are kept; 'under pressure' is classed none", res[A["link"]]["kind"] == "transfer_confirmed" and res[B["link"]]["kind"] == "manager_sacked" and res[C["link"]]["kind"] == "none", res)
check("one call for all candidates, on the news model, with headline and blurb only",
      len(c.calls) == 1 and c.calls[0]["model"] == settings.NEWS_MODEL and "blurb" in c.calls[0]["messages"][0]["content"] and "full_text" not in c.calls[0]["messages"][0]["content"])
check("no candidates means no call", news.classify(Fake([]), [])[0] == {})
invented = {**good, "summary": "Arsenal have signed Mikel Merino to a four-year contract."}
c = Fake([reply([invented, sack]), reply([good])])
res, _ = news.classify(c, [A, B])
check("a summary with an invented name is retried, with the problem named, for that item only",
      len(c.calls) == 2 and "Merino" in c.calls[1]["messages"][0]["content"] and B["link"] not in c.calls[1]["messages"][0]["content"] and res[A["link"]]["summary"] == good["summary"], res)
c = Fake([reply([invented]), reply([invented])])
res, _ = news.classify(c, [A])
check("still invented after the retry: no summary (the page will show the headline link instead)", res[A["link"]]["summary"] is None and res[A["link"]]["problems"], res)
copied = {**good, "summary": "The Gunners have announced the arrival of a Spanish midfielder on a four-year deal, it says."}
res, _ = news.classify(Fake([reply([copied]), reply([copied])]), [A])
check("copying six or more words of the blurb is rejected", res[A["link"]]["summary"] is None and any("copies" in p for p in res[A["link"]]["problems"]), res)
res, _ = news.classify(Fake([reply([{**good, "club": "Chelsea"}]), reply([{**good, "club": "Chelsea"}])]), [A])
check("a club that is not one of the item's clubs is rejected", res[A["link"]]["summary"] is None)
check("an API failure gives nothing (no news is better than unchecked news)", news.classify(Fake([RuntimeError("x")] * 2), [A])[0] == {})
long = {**good, "summary": " ".join(["word"] * 50)}
check("a summary over the word limit is rejected", any("over the limit" in p for p in news.check_summary(long["summary"], A)))
rumour_hype = news.check_summary("Arsenal are reportedly set to complete a stunning record signing.", A)
check("hype and record claims are rejected", any("hype" in p for p in rumour_hype) or any("history" in p for p in rumour_hype), rumour_hype)

# ---- D's rules ----
def R(link, kind, club, title="t"):
    return {"link": link, "title": title, "source": "BBC Sport", "published": NOW, "clubs": [club]}, {"kind": kind, "club": club, "summary": "S."}


def shown(*pairs):
    cands, res = [p[0] for p in pairs], {p[0]["link"]: p[1] for p in pairs}
    return {i["link"] for i in news.apply_rules(cands, res)}


check("Arsenal: confirmed transfer, rumour, sacking and injury are all kept", shown(R("1", "transfer_confirmed", "Arsenal"), R("2", "transfer_rumour", "Arsenal"), R("3", "manager_sacked", "Arsenal"), R("4", "injury", "Arsenal")) == {"1", "2", "3", "4"})
check("a rumour about any other club is dropped", shown(R("1", "transfer_rumour", "Barcelona"), R("2", "transfer_rumour", "Chelsea")) == set())
check("another listed club's confirmed transfer is kept", shown(R("1", "transfer_confirmed", "Barcelona")) == {"1"})
check("a confirmed transfer at a club we don't list is dropped", shown(R("1", "transfer_confirmed", "Nottingham Forest")) == set())
check("a sacking or appointment at any covered club is kept", shown(R("1", "manager_sacked", "Nottingham Forest"), R("2", "manager_appointed", "Girona")) == {"1", "2"})
check("an injury at a Premier League club is dropped (FPL covers those); at Barcelona it is kept", shown(R("1", "injury", "Chelsea")) == set() and shown(R("2", "injury", "Barcelona")) == {"2"})
check("'none' is never shown", shown(R("1", "none", "Arsenal")) == set())

# ---- Display ----
items = news.apply_rules([A, B], {A["link"]: {"kind": "transfer_confirmed", "club": "Arsenal", "summary": "Arsenal have announced a Spanish midfielder."},
                                  B["link"]: {"kind": "manager_sacked", "club": "Nottingham Forest", "summary": None}})
ah, fh = news.html(items, "arsenal", "Team News"), news.html(items, "football", "Transfers And Managers")
check("Arsenal's item goes in the Arsenal block with a tag and a source link", "Team News" in ah and "Transfer" in ah and 'rel="noopener">BBC Sport</a>' in ah and "Forest" not in ah, ah)
check("with no summary the headline is shown as the fallback", "Forest sack Glasner after another defeat" in fh and "Sacked" in fh, fh)
check("no items for a section means no block", news.html(items, "arsenal", "x") != "" and news.html([], "arsenal", "x") == "")
check("rumours are clearly tagged", "Rumour" in news.html(news.apply_rules([A], {A["link"]: {"kind": "transfer_rumour", "club": "Arsenal", "summary": "Arsenal are reportedly interested."}}), "arsenal", "Team News"))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
