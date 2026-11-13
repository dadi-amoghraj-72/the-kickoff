"""The other sports' big news for Biggest News: NFL, NBA, F1 and cricket (D, 2026-11-11: the Kirk Cousins trade; 2026-11-13: Harry Kane's caps record,
F1 seats like Liam Lawson's and Arvid Lindblad's, and the IPL's Hardik Pandya-Arshdeep Singh swap were all missed; Biggest News read football only).

  1. The sources: ESPN's NFL, NBA and F1 news (its own hard news only, type HeadlineNews), BBC Sport and The Guardian on F1 and cricket, and ESPNcricinfo.
     Items of the last LOOKBACK not judged before (state "seen"), without the plain noise: nothing that cites 'sources', asks a question, says 'could',
     or is a live blog, a podcast, a video or a column.
  2. Claude picks at most two, most important first, that a fan of that sport would call big, and writes one plain sentence for each (checked by code like the
     football news). No Claude: nothing.
  3. Biggest News shows them after football's best item (bigstuff.top_news).
One small Claude call a day, only when step 1 finds something."""
import re
from datetime import datetime, timedelta

from kickoff import http, notes, settings
from kickoff.sources import feeds

ESPN = "https://site.api.espn.com/apis/site/v2/sports/{path}/news?limit=50"
SOURCES = {
    "NFL": [("ESPN", "json", "football/nfl")],
    "NBA": [("ESPN", "json", "basketball/nba")],
    "F1": [("ESPN", "json", "racing/f1"), ("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/formula1/rss.xml"),
           ("The Guardian", "rss", "https://www.theguardian.com/sport/formulaone/rss")],
    "Cricket": [("ESPNcricinfo", "rss", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml"), ("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/cricket/rss.xml"),
                ("The Guardian", "rss", "https://www.theguardian.com/sport/cricket/rss")],
}
LOOKBACK = timedelta(hours=72)    # once a day can miss a story published just after a run; "seen" stops a story being judged twice
PER_SPORT = 80                    # newest first; Claude reads only headlines and short blurbs, so this stays a small call
MAX_PICKS = 2
NOT_YET = re.compile(r"\?|\b(sources?|reportedly|rumou?r\w*|could|would|might|expected|eyes?|eyeing|interest(?:ed)? in|considering|in talks|close to|nears?|"
                     r"live|as it happened|verdict|talking points|podcast|quiz|predictions?|ratings|preview|what we learned|explained|q&a|chequered flag|"
                     r"video|in pictures|gallery|highlights)\b|\s\|\s", re.I)        # ' | ' ends a Guardian column's title with its writer's name

SYSTEM = """You pick the biggest news of the last few days in the NFL, the NBA, Formula 1 and cricket for a sports fan in Singapore who follows India's
cricket closely and the other sports as a keen fan. Each item is only a headline and a short blurb. You see nothing else, so know nothing else.
Pick at most two items, most important first, and only items that report something that HAS happened and that a fan of that sport would call big:
- a trade or signing of a star (a starting quarterback, an All-Star, an IPL trade of an India player), a driver's seat or contract for next season,
  a head coach, team principal or national captain appointed or sacked;
- a historic record or milestone actually reached (most caps, an all-time record, a first ever), or a great player retiring.
Depth players, assistant coaches, match reports, previews, opinion and anything that might happen are not big. Picking nothing is fine.
For each pick give "n" (the item's number) and "summary": ONE sentence of at most 30 words in your own words, from the headline and blurb only.
Start with the team or the person and their role, and say plainly what happened: "Mumbai Indians and Punjab Kings have swapped Hardik Pandya and
Arshdeep Singh for IPL 2027." Never copy a run of more than five words. No hype."""
SCHEMA = {"type": "object", "properties": {"picks": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}, "summary": {"type": "string"}},
                                                                                "required": ["n", "summary"], "additionalProperties": False}}},
          "required": ["picks"], "additionalProperties": False}


def from_espn(body, source):
    """ESPN's own hard news only (no videos, columns or fantasy pieces), as feed items."""
    out = []
    for a in (body or {}).get("articles") or []:
        if a.get("type") != "HeadlineNews":
            continue
        try:
            published = datetime.fromisoformat(a["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        link = ((a.get("links") or {}).get("web") or {}).get("href") or ""
        if a.get("headline") and link:
            out.append({"source": source, "title": a["headline"].strip(), "text": (a.get("description") or "").strip(), "link": link, "published": published})
    return out


def fetch(get_json=http.get_json, fetch_feeds=feeds.fetch_all):
    """{sport: [feed items]} from every source that answers; a source that fails gives nothing."""
    out = {}
    for sport, srcs in SOURCES.items():
        items = []
        for source, kind, where in srcs:
            try:
                items += from_espn(get_json(ESPN.format(path=where)), source) if kind == "json" else fetch_feeds([(source, "rss", where)])
            except Exception:
                pass
        out[sport] = items
    return out


def candidates(by_sport, now, seen=()):
    """[(sport, item)]: the last LOOKBACK's items not judged before, without the plain noise (live blogs, podcasts, videos, columns, 'could', 'sources'),
    newest first, at most PER_SPORT a sport. Claude decides what actually happened and is big (a word list missed 'Lawson and Lindblad to continue at Racing Bulls')."""
    out = []
    for sport, items in by_sport.items():
        keep = [i for i in items if i["link"] not in seen and timedelta(0) <= now - i["published"] <= LOOKBACK
                and not NOT_YET.search(i["title"])]
        keep.sort(key=lambda i: i["published"], reverse=True)
        out += [(sport, i) for i in list({i["link"]: i for i in keep}.values())[:PER_SPORT]]
    return out


def check(summary, item):
    """The football news checks (invented names or numbers, copying, length)."""
    from kickoff import news
    return news.check_summary(summary, {**item, "clubs": []})


def find(client, now, st, fetched=None):
    """(items for Biggest News, new state, usage). items: [{"text", "link", "source", "us": True}], most important first."""
    seen = dict((st or {}).get("seen") or {})
    cands = candidates(fetched if fetched is not None else fetch(), now, seen)
    none = {"input": 0, "output": 0}
    if not client or not cands:
        return [], {"seen": prune(seen, now)}, none
    listing = "\n".join(f"{n}. [{sport}] {i['title']} | {i['text'][:300]}" for n, (sport, i) in enumerate(cands, 1))
    obj, usage = notes.call_json(client, SYSTEM, SCHEMA, listing, model=settings.NEWS_MODEL)
    if obj is None:                                        # a failed call judges nothing: tomorrow may try again
        return [], {"seen": prune(seen, now)}, usage or none
    out = []
    for p in (obj.get("picks") or [])[:MAX_PICKS]:
        n = int(p.get("n") or 0)
        if not 1 <= n <= len(cands):
            continue
        sport, item = cands[n - 1]
        summary = (p.get("summary") or "").strip()
        text = summary if summary and not check(summary, item) else item["title"]     # a summary that fails the checks: the source's own headline
        out.append({"text": f"{sport}: {text}", "link": item["link"], "source": item["source"], "us": True})
    for _, i in cands:
        seen[i["link"]] = now.isoformat()
    return out, {"seen": prune(seen, now)}, usage or none


def prune(seen, now):
    return {k: v for k, v in seen.items() if now - datetime.fromisoformat(v) <= timedelta(days=7)}
