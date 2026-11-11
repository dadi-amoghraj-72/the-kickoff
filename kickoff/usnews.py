"""NFL and NBA moves for Biggest News (D, 2026-11-11: Kirk Cousins was traded to the Vikings and the edition never said; Biggest News read football only).

  1. ESPN's NFL and NBA news, its own hard-news items only (type HeadlineNews: no videos, columns, fantasy or 'what it means' pieces), published in the 24 hours
     before the run, whose headline says a move happened: a trade, a signing, a coach fired or hired, a release, a retirement, a suspension. Nothing that
     cites 'sources', asks a question or says 'could'.
  2. Claude picks, per sport, the one move a casual fan would want to know (a starting quarterback, an All-Star, a head coach), or none. No Claude: none.
  3. At most one NFL/NBA item reaches Biggest News, in its second place (football keeps the first; see bigstuff.html).
One small Claude call a day, only when step 1 finds something."""
import re
from datetime import datetime, timedelta

from kickoff import http, notes, settings

URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/news?limit=50"
SPORTS = (("NFL", "football/nfl"), ("NBA", "basketball/nba"))
WINDOW = timedelta(hours=24)
MOVE = re.compile(r"\b(trade[sd]?|trading|acquir\w+|sign(?:s|ed)?|agree\w* to|fire[sd]?|hire[sd]?|names?|named|waive[sd]?|release[sd]?|cut|cuts|retire[sd]?|retiring|suspend\w*|"
                  r"head coach|dismiss\w*|part ways)\b", re.I)
NOT_YET = re.compile(r"\?|\b(sources?|reportedly|report|rumou?r\w*|could|would|might|may|expected|eyes?|eyeing|interest\w*|called .* to ask|considering|explor\w*|"
                     r"remain|remains|stay|stays|no deal|nears?|close to|in talks)\b", re.I)

SYSTEM = """You pick the biggest confirmed NFL or NBA move from ESPN headlines for a sports fan in Singapore who follows the leagues casually.
A move is big when a casual fan would know the player or coach: a starting quarterback, an All-Star or All-Pro, a former MVP, a head coach fired or hired.
Depth players, backups, draft picks and assistant coaches are not big. The headline must say the move happened, not that it might.
For each sport give "pick": the number of the one big move, or 0 when none is big."""
SCHEMA = {"type": "object", "properties": {"nfl": {"type": "integer"}, "nba": {"type": "integer"}}, "required": ["nfl", "nba"], "additionalProperties": False}


def candidates(articles, now, label):
    """The hard-news moves of the last day: [{"text", "link", "source", "us"}]."""
    out = []
    for a in articles or []:
        try:
            published = datetime.fromisoformat(a["published"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        head = (a.get("headline") or "").strip()
        if a.get("type") != "HeadlineNews" or not timedelta(0) <= now - published <= WINDOW or not MOVE.search(head) or NOT_YET.search(head):
            continue
        link = ((a.get("links") or {}).get("web") or {}).get("href") or ""
        out.append({"text": f"{label}: {head}", "link": link, "source": "ESPN", "us": True})
    return out


def find(client, now, get_json=http.get_json):
    """(items, usage): at most one picked move per sport, NFL first."""
    found = {}
    for label, path in SPORTS:
        try:
            found[label] = candidates((get_json(URL.format(path=path)) or {}).get("articles"), now, label)[:12]
        except Exception:
            found[label] = []
    none = {"input": 0, "output": 0}
    if not client or not any(found.values()):
        return [], none
    listing = "\n\n".join(f"{label}:\n" + "\n".join(f"{n}. {i['text'].split(': ', 1)[1]}" for n, i in enumerate(items, 1)) for label, items in found.items() if items)
    obj, usage = notes.call_json(client, SYSTEM, SCHEMA, listing, model=settings.NEWS_MODEL)
    out = []
    for label, _ in SPORTS:
        n = int((obj or {}).get(label.lower()) or 0)
        if 1 <= n <= len(found[label]):
            out.append(found[label][n - 1])
    return out, usage or none
