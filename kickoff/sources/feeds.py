"""News headlines and short blurbs from BBC Sport, The Guardian and ESPN. Headline and blurb only, never full text."""
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from kickoff.http import SourceError, get_bytes, safe

FEEDS = [
    ("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
    ("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/football/teams/arsenal/rss.xml"),
    ("The Guardian", "rss", "https://www.theguardian.com/football/rss"),
    ("The Guardian", "rss", "https://www.theguardian.com/football/arsenal/rss"),
    ("ESPN", "espn", "https://site.api.espn.com/apis/site/v2/sports/soccer/all/news"),
    ("ESPN", "espn", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/news"),
    ("ESPN", "espn", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/news?team=359"),
]


def clean(text):
    """Plain text: tags removed, entities decoded, whitespace squeezed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _when(text):
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat((text or "").replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_rss(body, source):
    root = ET.fromstring(body)
    items = []
    for it in root.iter("item"):
        get = lambda tag: (it.findtext(tag) or "").strip()  # noqa: E731
        items.append({"source": source, "title": clean(get("title")), "text": clean(get("description")),
                      "link": get("link"), "published": _when(get("pubDate"))})
    return [i for i in items if i["title"] and i["link"] and i["published"]]


def parse_gnews(body, source):
    """Google News's search feed: the title ends ' - Publisher', and the item names the publisher in <source>. The publisher becomes the item's source and leaves the title; the link is
    Google's redirect to the publisher's article. The description is a list of related headlines, so it is dropped (only the headline is used)."""
    root = ET.fromstring(body)
    items = []
    for it in root.iter("item"):
        get = lambda tag: (it.findtext(tag) or "").strip()  # noqa: E731
        publisher = get("source")
        title = clean(get("title"))
        if publisher and title.endswith(f" - {publisher}"):
            title = title[:-len(publisher) - 3].strip()
        items.append({"source": publisher or source, "title": title, "text": "", "link": get("link"), "published": _when(get("pubDate"))})
    return [i for i in items if i["title"] and i["link"] and i["published"]]


def parse_espn(body, source):
    items = []
    for a in json.loads(body).get("articles", []):
        link = ((a.get("links") or {}).get("web") or {}).get("href", "")
        items.append({"source": source, "title": clean(a.get("headline")), "text": clean(a.get("description")),
                      "link": link, "published": _when(a.get("published") or a.get("lastModified"))})
    return [i for i in items if i["title"] and i["link"] and i["published"]]


PARSERS = {"rss": parse_rss, "espn": parse_espn, "gnews": parse_gnews}


def fetch_all(feeds=FEEDS):
    """Every item from every feed that answers. A feed that fails is skipped with a warning, never fatal.
    Duplicates (the same link from two feeds) are removed."""
    seen, out = set(), []
    for source, kind, url in feeds:
        body = safe(f"{source} feed", get_bytes, url)
        if body is None:
            continue
        items = safe(f"{source} feed parse", PARSERS[kind], body, source)
        for i in items or []:
            if i["link"] not in seen:
                seen.add(i["link"])
                out.append(i)
    if not out:
        raise SourceError("no news feed answered")
    return sorted(out, key=lambda i: i["published"], reverse=True)
