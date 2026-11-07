"""Around The Sporting World and Interesting Stories (checkpoint 12): the major events of the sports we do not cover in full (SPEC.md, "Around the sporting world").

Structured results from ESPN (rugby internationals, numbered UFC events) are written by code; golf (kickoff/golf.py) and badminton (kickoff/badminton.py) have their own tables. Everything else is picked from the news feeds
(kickoff/sources/other_sports.py): code narrows the last 36 hours' headlines to those about a covered event, or about an Indian or Southeast Asian athlete in the later rounds
(the spotlight rule); Claude then sorts each as a result, news or neither and writes one sentence in its own words, checked like every other note. Without Claude the source's
own headline is shown under a link, but only when it reads like a result. Each line carries its source link. A quiet day shows nothing, and a sport with nothing is not listed.

Interesting Stories: three to five picks across everything read, two or three sentences each in our own words with the link; Claude only (no Claude, no stories), never one
already featured in the last week."""
import json
import re
from datetime import datetime, timedelta, timezone

from kickoff import badminton, chess_live, golf, importance, majors, notes, rugbytables, settings
from kickoff import ufc as ufc_mod
from kickoff import ufcrank
from kickoff import render as r
from kickoff.sources import other_sports
from kickoff.sources.other_sports import RUGBY_LEAGUES

# Multi-sport Games (D, 2026-11-08: the Youth Olympics were on and the page only had one line that did not even name its sport). While one is on, Other Sports opens with it:
# its name, host and day, then its lines, each starting with its sport. Only Games whose dates are fixed are listed; add the next ones when they are.
GAMES = [("Youth Olympic Games", "Dakar", "2026-10-31", "2026-11-13"),
         ("Olympic Games", "Los Angeles", "2028-07-14", "2028-07-30"),
         ("Paralympic Games", "Los Angeles", "2028-08-15", "2028-08-27"),
         ("Winter Olympic Games", "French Alps", "2030-02-01", "2030-02-17")]


def games_on(day):
    """(name, host, day number, days in all, last day) for a Games on `day` (a date in Singapore), or None."""
    from datetime import date as date_
    for name, host, a, b in GAMES:
        start, end = date_.fromisoformat(a), date_.fromisoformat(b)
        if start <= day <= end:
            return name, host, (day - start).days + 1, (end - start).days + 1, end
    return None


def games_html(on):
    name, host, n, total, end = on
    return f'<p class="games-sub">{r.esc(host)} \u00b7 Day {n} of {total} \u00b7 until {end:%a} {end.day} {end:%b}</p>'


RECENT = timedelta(hours=36)                                 # feed items
RESULTS_RECENT = timedelta(days=3)                              # rugby results: a skipped day is caught up (each is shown once)
PER_SPORT = 3                 # lines per sport
MAX_CANDIDATES = 20           # headlines sent to Claude in one call
STORY_POOL = 40
STORY_DAYS = 7

# (key, heading, sport words, the events that count). Sport words keep "world championships" from matching the wrong sport.
RULES = [
    ("golf", "Golf", r"\bgolf|\bpga\b|\blpga\b|ryder cup|solheim cup", r"ryder cup|solheim cup"),
    ("badminton", "Badminton", r"badminton|shuttler|\bbwf\b", r"world championships?|world tour finals|super ?(1000|750)|all england|indonesia open|china open|malaysia open|japan open"),
    ("athletics", "Athletics", r"athletics|diamond league|sprinter|world athletics", r"diamond league|world (athletics )?(indoor )?championships?"),
    ("handball", "Handball", r"handball", r"world championships?|european championships?|euros?\b|champions league|final four"),
    ("hockey", "Field hockey", r"field hockey|\bhockey\b|\bfih\b", r"pro league|world cup|asia cup|champions trophy|nations cup|asian games|olympic"),
    ("chess", "Chess", r"\bchess\b|\bfide\b|grandmaster", r"world (chess )?championship|candidates|olympiad|tata steel|norway chess|grand chess tour|sinquefield|women'?s world"),
    ("darts", "Darts", r"\bdarts?\b|\bpdc\b", r"world (darts )?championship|world matchplay|grand slam of darts|premier league|ally pally|alexandra palace"),
    ("games", "Multi-sport games", r"games|olympic|olympics", r"\b(asian|sea|southeast asian|commonwealth|olympic|paralympic|youth olympic) games\b|\bolympics\b"),
    ("womens-football", "Women's football", r"women'?s (world cup|euro)|\bwwc\b", r"women'?s (world cup|euro)|\bfinal\b"),
]
ORDER = ["rugby", "golf", "ufc", "badminton", "athletics", "handball", "hockey", "chess", "darts", "games", "womens-football", "spotlight"]
HEADING = {"rugby": "Rugby", "ufc": "UFC", "spotlight": "Spotlight", **{k: h for k, h, _, _ in RULES}}

# The spotlight rule: an Indian or Southeast Asian athlete reaching a semi-final, final or podium at a notable event gets a line even below the usual bar.
SPOT_PLACE = re.compile(r"\b(india|indian|singapore|singaporean|malaysia|malaysian|indonesia|indonesian|thailand|thai|philippines|filipino|vietnam|vietnamese)\b", re.I)
SPOT_NAMES = re.compile(r"\b(sindhu|satwik|chirag shetty|lakshya sen|prannoy|treesa jolly|gayatri gopichand|neeraj chopra|gukesh|praggnanandhaa|arjun erigaisi|koneru humpy|divya deshmukh|vaishali|"
                        r"manu bhaker|sreeshankar|avinash sable|loh kean yew|carlos yulo|joseph schooling|ng on yee|jonatan christie|anthony ginting|kunlavut vitidsarn)\b", re.I)
SPOT_STAGE = re.compile(r"semi-?final|\bfinal\b|\bmedal|podium|bronze|silver|\bgold\b|\btitle\b|champion|crowned|wins?\b|won\b", re.I)
# D (2026-11-08): India and Singapore reaching a semi-final or final, or a medal, in any of these sports' tournaments gets a line even when the event is not on the list above
# (at most two lines a sport, like every feed line): India's hockey team won the Asian Champions Trophy at home and nothing said so.
OURS = re.compile(r"\b(india|indian|indians|singapore|singaporean)\b", re.I)
OURS_STAGE = re.compile(r"semi-?finals?|\bfinals?\b|\bgold\b|\bsilver\b|\bbronze\b|\bmedal|\btitle\b|\bchampions?\b|\bcrowned\b|\blift(s|ed)?\b", re.I)
NOT_SPOT = re.compile(r"\b(cricket|ipl|test match|odi|t20|football|premier league|nba|nfl|formula|f1|tennis|rugby|golf)\b", re.I)    # sports we cover in full elsewhere
RESULT = re.compile(r"\b(wins?|won|beats?|beat|defeats?|champion|title|crowned|claims?|retains?|seals?|clinch|secures?|medal|gold|silver|bronze|reaches?|into the final|semi-?final|"
                    r"knockout|thrash|stun|triumph|victory|lifts?)\b", re.I)
MAJORS = re.compile(r"masters tournament|pga championship|u\.?s\.? open|the open championship|chevron championship|women'?s pga|evian|women'?s open|ryder cup|solheim cup", re.I)
# Without Claude (plain mode) a headline needs an outcome verb, not just a medal word: "Olympic gold stolen" and "Asian Games gold boosts a basketball season" are not results.
STRICT = re.compile(r"\b(wins?|won|beats?|defeats?|champions?|crowned|claims? (?:the )?(?:title|gold|silver|bronze|crown)|retains?|clinch\w*|secures?|lifts?|reaches? (?:the )?(?:\w+ )?final|into the final|storms into|triumph|victory|thrash\w*|stuns?)\b", re.I)
NEGATIVE = re.compile(r"\b(stolen|theft|robbery|burgled|arrested|funeral|obituary|tribute)\b", re.I)         # in the news, but not sport
NEWS = re.compile(r"\b(withdraws?|withdrawn|ruled out|banned|ban\b|retires?|retirement|confirmed|confirms|doping|injur\w+|suspended)\b", re.I)
EXCLUDE = {"games": re.compile(r"medall?ists?\b|\bstolen\b|\bformer\b|\blegend|\bdoping\b|\bwhereabouts\b", re.I)}      # a past medallist in the news is not the Games being played
# D (2026-11-05): the feed headlines were tabloid noise (a Facebook post with emojis). Now: only these outlets, only for sports that have no structured source of their own, only when Claude has
# written a checked sentence (no Claude, no feed lines), at most two a sport, and no 'Spotlight' section.
WHITELIST = re.compile(r"\b(bbc|guardian|espn|straits times|the hindu|chessbase)\b", re.I)
NO_FEED = {"badminton", "golf", "ufc", "spotlight"}
FEED_PER_SPORT = 2
KINDS = ["result", "news", "none"]

SYSTEM = """You sort and summarise sports news items for The Kickoff, a personal daily digest. Each item is only a headline and a short blurb from BBC Sport, The Guardian,
ChessBase or Chess.com. You see nothing else, so know nothing else.

For every item choose one "kind":
- result: the text says a named person or team has won, lost, reached a stage or claimed a title or medal in a major event, and the outcome is DONE.
- news: a major, concrete development (a star withdraws, a champion retires, a host or date is confirmed, a ban). Not opinion, not speculation, not a preview.
- none: anything else. Previews, opinion, interviews, "could" and "may", lists, and anything you are unsure about are "none". When in doubt, "none".

For result and news give a "summary": ONE sentence of at most 30 words in your own words, using only the headline and blurb; add nothing from memory; never copy a run of more than
five words; no hype, no emojis. Also give "sport": the sport the item is about, in one or two words with a capital letter (Badminton, Athletics, Swimming, Field hockey), only when
the headline or blurb says it or names its event; otherwise "". Return one entry per item, using the item's link as its id."""
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "link": {"type": "string"}, "kind": {"type": "string", "enum": KINDS}, "summary": {"type": "string"}, "sport": {"type": "string"}}, "required": ["link", "kind", "summary", "sport"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}

STORY_SYSTEM = """You pick the most interesting stories for The Kickoff, a personal daily sports digest read by one fan in Singapore, from a numbered list of headlines and blurbs.
Pick three to five that a keen sports fan would most enjoy: human-interest stories, surprises, records, features and big non-routine news from any sport. Skip match reports that
the digest already covers, previews, routine transfer talk and anything you are unsure about. For each pick write TWO or THREE sentences (at most 60 words) in your own words from
the headline and blurb only, adding nothing from memory and never copying a run of more than five words. No hype, no emojis. Return the item's number and the text. If fewer than
three items deserve a place, return fewer."""
STORY_SCHEMA = {"type": "object", "properties": {"picks": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["n", "text"], "additionalProperties": False}}}, "required": ["picks"], "additionalProperties": False}


# ---- Structured sports (code only) ---------------------------------------------------------------

def _utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def rugby(source, now, fails=None):
    """Finished internationals and World Cup matches of the last 39 hours: [('Ireland 43–21 Scotland (Six Nations)', unique id)]."""
    out = []
    for league, name in RUGBY_LEAGUES.items():
        try:
            events = source.rugby(league).get("events", [])
        except Exception:
            (fails if fails is not None else []).append("rugby")
            continue
        for e in events:
            try:
                c = e["competitions"][0]
                if e["status"]["type"].get("name") != "STATUS_FINAL" or not (timedelta(0) <= now - _utc(e["date"]) <= RESULTS_RECENT):
                    continue
                side = {x["homeAway"]: x for x in c["competitors"]}
                out.append((f"{side['home']['team']['displayName']} {int(side['home']['score'])}–{int(side['away']['score'])} {side['away']['team']['displayName']} ({name})", f"rugby:{e['id']}"))
            except (KeyError, ValueError, TypeError, IndexError):          # one odd event costs only itself
                continue
    return out


# ---- Feed items -----------------------------------------------------------------------------------

def sport_of(item):
    """(sport key, spotlight?) for a headline, or (None, False) when it is about no covered event."""
    text = f"{item['title']} {item['text']}"
    if NEGATIVE.search(text):
        return None, False
    for key, _, words, events in RULES:
        if re.search(words, text, re.I) and (re.search(events, text, re.I) or (OURS.search(text) and OURS_STAGE.search(text))) and not (key in EXCLUDE and EXCLUDE[key].search(text)):
            return key, bool(SPOT_PLACE.search(text) or SPOT_NAMES.search(text))
    if (SPOT_PLACE.search(text) or SPOT_NAMES.search(text)) and SPOT_STAGE.search(text) and not NOT_SPOT.search(text):
        for key, _, words, _e in RULES:
            if re.search(words, text, re.I):
                return key, True
        if SPOT_NAMES.search(text):
            return "spotlight", True
    return None, False


def english(title):
    """True when the headline is (almost) all Latin letters: Google News also finds Korean, Vietnamese and other-language outlets, which the digest does not use."""
    letters = [c for c in title if c.isalpha()]
    return not letters or sum(1 for c in letters if c.isascii()) / len(letters) >= 0.9


def candidates(items, now, seen=()):
    """Fresh headlines (36 hours, not shown before) about a covered event: [{**item, "sport", "spotlight"}], newest first."""
    seen = set(seen)
    out, titles = [], set()
    for i in items:
        if i["link"] in seen or not (timedelta(0) <= now - i["published"] <= RECENT) or not english(i["title"]):
            continue
        key = re.sub(r"[^a-z0-9]", "", i["title"].lower())[:60]          # the same story from two outlets (or twice from one search) is one candidate
        if key in titles:
            continue
        titles.add(key)
        key, spot = sport_of(i)
        if key in NO_FEED or not WHITELIST.search(i["source"]):
            continue
        if key and (RESULT.search(i["title"]) or NEWS.search(i["title"])):            # a preview or a feature is not a result; Claude then sorts the rest
            out.append({**i, "sport": key, "spotlight": spot})
    return out[:MAX_CANDIDATES]


def check_summary(summary, item):
    facts = {"headline": item["title"], "blurb": item["text"], "clubs": [], "source": item["source"], "length": notes.TIERS["news"][0]}
    problems = notes.check_note(summary, facts)
    if notes.copied_run(summary, [item["title"], item["text"]]):
        problems.append("copies a run of six or more words from the source")
    return problems


def classify(client, cands):
    """({link: {"kind", "summary"}}, usage) for the candidates Claude kept (result or news); a summary that fails its checks twice is None (the headline is shown instead)."""
    if not cands:
        return {}, {"input": 0, "output": 0}
    by_link = {c["link"]: c for c in cands}
    pending = [{"link": c["link"], "source": c["source"], "headline": c["title"], "blurb": c["text"]} for c in cands]
    out, total = {}, {"input": 0, "output": 0}
    for attempt in (1, 2):
        extra = "" if attempt == 1 else "Your earlier summaries for these items broke a rule (see problems). Rewrite them, or choose kind none if the text cannot support them.\n"
        obj, usage = notes.call_json(client, SYSTEM, SCHEMA, extra + "Items:\n" + json.dumps(pending, ensure_ascii=False, indent=1), model=settings.NEWS_MODEL)
        total = {k: total[k] + usage[k] for k in total}
        redo = []
        for x in (obj or {}).get("items", []) if isinstance(obj, dict) else []:
            item = by_link.get(x.get("link"))
            if not item:
                continue
            if x.get("kind") not in ("result", "news"):
                out[item["link"]] = {"kind": "none", "summary": None}
                continue
            problems = check_summary(x.get("summary", ""), item)
            if problems:
                out[item["link"]] = {"kind": x["kind"], "summary": None}
                redo.append({**next(p for p in pending if p["link"] == item["link"]), "problems": problems})
            else:
                out[item["link"]] = {"kind": x["kind"], "summary": x["summary"].strip(), "sport": sport_named(x.get("sport", ""), item)}
        pending = redo
        if not pending:
            break
    return out, total


def sport_named(sport, item):
    """Claude's sport for an item, kept only when the headline or blurb backs it (the word itself, or a word of it); '' otherwise. Never from memory."""
    sport = (sport or "").strip()
    text = f"{item['title']} {item['text']}".lower()
    words = [w for w in re.findall(r"[a-z]+", sport.lower()) if len(w) > 3]
    return sport[:1].upper() + sport[1:] if sport and words and any(w[:5] in text for w in words) else ""


def line_html(text, link=None, source=None, split=False, lead=""):
    """One list item. split=True (a line of several results, 'Title: a; b; c') puts the title in bold and each result on its own line, so it reads on a phone."""
    tail = f' <a href="{r.esc(link)}" rel="noopener">{r.esc(source)}</a>' if link else ""
    if split and "; " in text and ": " in text:
        head, rest = text.split(": ", 1)
        body = f"<strong>{r.esc(head)}</strong>" + "".join(f"<br>{r.esc(part)}" for part in rest.split("; "))
        return f"<li>{body}{tail}</li>"
    return f"<li>{f'<strong>{r.esc(lead)}:</strong> ' if lead else ''}{r.esc(text)}{tail}</li>"


# ---- Stories ----------------------------------------------------------------------------------------

def story_pool(items, now, shown):
    pool = [i for i in items if i["link"] not in shown and timedelta(0) <= now - i["published"] <= timedelta(hours=48)]
    return pool[:STORY_POOL]


def stories(client, items, now, shown):
    """(picks [{"text", "link", "source"}], usage): three to five interesting stories, or none. Each text is checked against its own headline and blurb."""
    pool = story_pool(items, now, shown)
    if not client or len(pool) < 3:
        return [], {"input": 0, "output": 0}
    listing = "\n".join(f"{n}. [{p['source']}] {p['title']} — {p['text']}" for n, p in enumerate(pool, 1))
    obj, usage = notes.call_json(client, STORY_SYSTEM, STORY_SCHEMA, "Items:\n" + listing, model=settings.NEWS_MODEL)
    out = []
    for x in (obj or {}).get("picks", []) if isinstance(obj, dict) else []:
        if not (1 <= x.get("n", 0) <= len(pool)):
            continue
        p = pool[x["n"] - 1]
        facts = {"headline": p["title"], "blurb": p["text"], "clubs": [], "source": p["source"], "length": notes.TIERS["standard"][0]}
        if not notes.check_note(x["text"], facts) and not notes.copied_run(x["text"], [p["title"], p["text"]]):
            out.append({"text": x["text"].strip(), "link": p["link"], "source": p["source"]})
    return (out[:5] if len(out) >= 3 else []), usage


def stories_html(picks):
    return '<ul class="standouts stories">' + "".join(line_html(p["text"], p["link"], p["source"]) for p in picks) + "</ul>" if picks else ""


# ---- The block --------------------------------------------------------------------------------------

def run(now, st, source, client=None):
    """{"sections", "state", "stats"}. st: {"seen": [links shown], "stories": {link: ISO date}}. Never raises: a failing page is skipped."""
    seen = list(st.get("seen") or [])
    story_log = {k: v for k, v in (st.get("stories") or {}).items() if now - _utc(v) <= timedelta(days=STORY_DAYS)}
    lines = {k: [] for k in ORDER}
    stats = {"candidates": 0, "shown": 0, "failed": 0, "claude_usage": {"input": 0, "output": 0}}
    rugby_shown = []
    for key, fn in (("rugby", rugby),):
        fails = []
        try:
            for text, uid in fn(source, now, fails):
                if uid not in seen:                       # a match, a result or a day's leader line is shown once
                    lines[key].append(line_html(text))
                    rugby_shown.append(text)
                    seen.append(uid)
        except Exception:
            stats["failed"] += 1
        stats["failed"] += len(fails)
    sgt_today = (now + timedelta(hours=8)).date()
    blocks = {"golf": [], "badminton": [], "ufc": [], "rugby": []}    # tables and notes that are not one-line items: the golf standings, the badminton draws and scorecards, rugby tables
    for league, name in rugbytables.TABLES.items():        # a competition that played this morning gets its table under the results (D, 2026-11-08)
        if any(t.endswith(f"({name})") for t in rugby_shown):
            try:
                blocks["rugby"].append(rugbytables.table_html(league, source.rugby_table(league)))
            except Exception:
                stats["failed"] += 1
    story_events = []
    boards = {}
    for tour in ("pga", "lpga"):
        try:
            boards[tour] = source.golf(tour)
        except Exception:
            stats["failed"] += 1
    golf_state = st.get("golf") or {}
    g = golf.run(boards, now, golf_state) if boards else {"lines": [], "blocks": [], "winners": [], "state": golf_state}
    for text, uid in g["lines"]:
        if uid not in seen:
            lines["golf"].append(line_html(text))
            seen.append(uid)
    blocks["golf"] += g["blocks"]
    ufc_state = st.get("ufc") or {}
    ufc_fails, ufc_stories, badminton_stories = [], [], []
    try:
        u = ufc_mod.run(source, now, ufc_state, ufc_fails)
        blocks["ufc"] = u["blocks"]
        ufc_state = u["state"]
        ufc_stories = u.get("stories", [])
    except Exception:
        stats["failed"] += 1
    stats["failed"] += min(len(ufc_fails), 1)
    rank_state = st.get("ufcrank") or {}
    try:
        rk = ufcrank.run(source, (now + timedelta(hours=8)).date(), rank_state)
        blocks["ufc"] += rk["blocks"]
        rank_state = rk["state"]
    except Exception:
        stats["failed"] += 1
    badminton_state = st.get("badminton") or {}
    wiki_fails = []
    try:
        b = badminton.run(source, (now + timedelta(hours=8)).date(), badminton_state, wiki_fails)
        blocks["badminton"] += [h for _, h in b["blocks"]]
        badminton_state = b["state"]
        badminton_stories = b.get("stories", [])
    except Exception:
        stats["failed"] += 1
    try:
        from kickoff import events as ev
        story_events = [ev.story("golf", "Golf", t, importance.story_score("golf", "final"), False, "final") for t in g["winners"]]
        story_events += [ev.story(sp_, name_, t, importance.story_score(sp_, "final"), False, "final") for sp_, name_, texts in (("ufc", "UFC", ufc_stories), ("badminton", "Badminton", badminton_stories)) for t in texts]
    except Exception:
        story_events = []
    for fn in (lambda: [(sp, t, uid, link, "Wikipedia") for sp, t, uid, link in majors.run(source, sgt_today, wiki_fails)],
               lambda: [("chess", t, uid, link, "Lichess") for t, uid, link in chess_live.run(source, now)]):
        try:                                           # the majors from Wikipedia and the chess from Lichess: exact lines, written by code
            for sp, text, uid, link, label in fn():
                if uid not in seen:
                    lines[sp].append(line_html(text, link, label, split=True))
                    seen.append(uid)
        except Exception:
            stats["failed"] += 1
    stats["failed"] += min(len(wiki_fails), 1)         # a page that did not answer, however many events looked at it
    items = []
    try:
        items = source.news()
    except Exception:
        stats["failed"] += 1
    cands = candidates(items, now, seen)
    stats["candidates"] = len(cands)
    feed_count = {}
    if cands:
        verdicts, usage = classify(client, cands) if client else ({}, {"input": 0, "output": 0})
        stats["claude_usage"] = usage
        for c in cands:
            v = verdicts.get(c["link"])
            if not v or v["kind"] == "none":
                continue
            if feed_count.get(c["sport"], 0) >= FEED_PER_SPORT:
                continue
            lead = v.get("sport") or ""
            if c["sport"] == "games" and not lead:               # a Games line always says its sport (D, 2026-11-08); when the source does not, the line is left out
                continue
            feed_count[c["sport"]] = feed_count.get(c["sport"], 0) + 1
            lines[c["sport"]].append(line_html(v["summary"] or c["title"], c["link"], c["source"], lead=lead if c["sport"] == "games" else ""))
            seen.append(c["link"])
    html = ""
    on = games_on(sgt_today)
    if on:                                             # a Games on: it leads Other Sports, named, with its day, even before its first result line
        blocks["games"] = [games_html(on)] + blocks.get("games", [])
    for key in (["games"] + [k for k in ORDER if k != "games"]) if on else ORDER:
        extra = "".join(blocks.get(key, []))
        if lines[key] or extra:
            shown = lines[key][:PER_SPORT]
            head = on[0] if key == "games" and on else HEADING[key]
            body = f'<ul class="standouts">{"".join(shown)}</ul>' if shown else ""
            html += f'<h4 class="sport{" first" if not html else ""}">{r.esc(head)}</h4>' + ((extra + body) if key == "games" else (body + extra))
            stats["shown"] += len(shown) + (1 if extra else 0)
    picks, usage2 = stories(client, items, now, set(seen) | set(story_log))
    stats["claude_usage"] = {k: stats["claude_usage"][k] + usage2[k] for k in usage2}
    for p in picks:
        story_log[p["link"]] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    sections = []
    if html:
        sections.append({"id": "other-sports", "title": "Other Sports", "html": html})
    if picks:
        sections.append({"id": "stories", "title": "Interesting Stories", "html": stories_html(picks)})
    return {"sections": sections, "state": {"around": {"seen": seen[-300:], "stories": story_log, "golf": g["state"], "badminton": badminton_state, "ufc": ufc_state, "ufcrank": rank_state}}, "stats": stats, "events": story_events}
