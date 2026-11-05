"""Which pages can feed 'Around the Sporting World'? Tries each candidate with The Kickoff's honest identity (no disguise) and reports: answered or not, how many items, how fresh.

  .venv/bin/python scripts/probe_other_sports.py        prints a table; nothing is saved
A page that blocks scripts (403) is simply marked blocked: the project does not get around that."""
import json
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff.http import get_bytes  # noqa: E402

BBC = "https://feeds.bbci.co.uk/sport/{}/rss.xml"
GU = "https://www.theguardian.com/{}/rss"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/{}"
CANDIDATES = [
    ("rugby", "BBC rugby union", BBC.format("rugby-union")), ("rugby", "BBC rugby league", BBC.format("rugby-league")), ("rugby", "Guardian rugby union", GU.format("sport/rugby-union")),
    ("rugby", "ESPN rugby news", ESPN.format("rugby/news")), ("rugby", "ESPN rugby scoreboard (all)", ESPN.format("rugby/scoreboard")),
    ("golf", "BBC golf", BBC.format("golf")), ("golf", "Guardian golf", GU.format("sport/golf")), ("golf", "ESPN PGA scoreboard", ESPN.format("golf/pga/scoreboard")),
    ("golf", "ESPN LPGA scoreboard", ESPN.format("golf/lpga/scoreboard")), ("golf", "ESPN golf news", ESPN.format("golf/news")),
    ("ufc", "ESPN UFC scoreboard", ESPN.format("mma/ufc/scoreboard")), ("ufc", "ESPN MMA news", ESPN.format("mma/news")), ("ufc", "Guardian UFC", GU.format("sport/ufc")),
    ("badminton", "BBC badminton", BBC.format("badminton")), ("badminton", "Guardian badminton", GU.format("sport/badminton")), ("badminton", "BWF news feed", "https://bwfbadminton.com/feed/"),
    ("athletics", "BBC athletics", BBC.format("athletics")), ("athletics", "Guardian athletics", GU.format("sport/athletics")),
    ("handball", "Guardian handball", GU.format("sport/handball")), ("handball", "EHF news", "https://www.eurohandball.com/en/news/"),
    ("hockey", "BBC hockey", BBC.format("hockey")), ("hockey", "Guardian hockey", GU.format("sport/hockey")), ("hockey", "FIH news", "https://www.fih.hockey/news"),
    ("chess", "Guardian chess", GU.format("sport/chess")), ("chess", "Lichess broadcasts", "https://lichess.org/api/broadcast?nb=5"), ("chess", "ChessBase feed", "https://en.chessbase.com/feed"),
    ("chess", "Chess.com news", "https://www.chess.com/rss/news"),
    ("darts", "BBC darts", BBC.format("darts")), ("darts", "Guardian darts", GU.format("sport/darts")), ("darts", "PDC news", "https://www.pdc.tv/news"),
    ("games", "BBC Olympics", BBC.format("olympics")), ("games", "Guardian Olympics", GU.format("sport/olympic-games")), ("games", "BBC Commonwealth Games", BBC.format("commonwealth-games")),
    ("womens football", "BBC women's football", BBC.format("football/womens")), ("womens football", "Guardian women's football", GU.format("football/womensfootball")),
    ("all", "Wikipedia current events (today)", "https://en.wikipedia.org/w/api.php?action=parse&page=Portal:Current_events&prop=wikitext&format=json&formatversion=2"),
    ("all", "BBC sport (all)", BBC.format("").replace("sport//", "sport/")), ("all", "Guardian sport (all)", GU.format("sport")), ("all", "ESPN top news", ESPN.format("../../../apis/site/v2/sports/news") if False else "https://site.api.espn.com/apis/site/v2/sports/soccer/news"),
]


def newest(body):
    """(items, newest timestamp) for an RSS/Atom feed, ESPN JSON or Lichess NDJSON; (None, None) when it is something else."""
    text = body.decode("utf-8", "replace")
    stamps = []
    try:
        root = ET.fromstring(body)
        items = list(root.iter("item")) or list(root.iter("{http://www.w3.org/2005/Atom}entry"))
        for it in items:
            for tag in ("pubDate", "{http://www.w3.org/2005/Atom}updated", "{http://www.w3.org/2005/Atom}published"):
                t = it.findtext(tag)
                if t:
                    try:
                        stamps.append(parsedate_to_datetime(t))
                    except (TypeError, ValueError):
                        stamps.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
                    break
        return len(items), max(stamps) if stamps else None
    except ET.ParseError:
        pass
    try:
        j = json.loads(text)
        n = len(j.get("articles") or j.get("events") or j.get("items") or []) if isinstance(j, dict) else len(j)
        dates = re.findall(r'"(?:published|lastModified|date)"\s*:\s*"(20\d\d-[^"]+)"', text)
        return n, max(datetime.fromisoformat(d.replace("Z", "+00:00")) for d in dates if re.match(r"20\d\d-\d\d-\d\dT", d)) if dates else None
    except Exception:
        pass
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("{")]
    if lines:
        return len(lines), None
    return None, None


def probe(c):
    group, name, url = c
    try:
        body = get_bytes(url, retries=0, timeout=15)
    except Exception as e:
        return group, name, str(e), None, None, None
    n, ts = newest(body)
    return group, name, "answers", n, ts, len(body)


now = datetime.now(timezone.utc)
with ThreadPoolExecutor(8) as ex:
    rows = list(ex.map(probe, CANDIDATES))
print(f"{'sport':16} {'page':34} {'result':10} {'items':>5}  newest")
for group, name, result, n, ts, size in rows:
    age = ""
    if ts:
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        h = (now - ts).total_seconds() / 3600
        age = f"{h:.0f}h ago" if h < 48 else f"{h / 24:.0f}d ago"
    print(f"{group:16} {name:34} {result:10} {'' if n is None else n:>5}  {age}")
