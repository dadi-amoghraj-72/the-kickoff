"""UFC (checkpoint 12, D's rules of 2026-11-05): every UFC event, numbered ones (UFC 330) and Fight Nights alike (added the same day), three fights, each in its own box: the main event, the co-main event and
the top bout of the Prelims.

The box is built like an NBA game: the winner on the left, "def." in the middle, the loser on the right, each name with his ranking in square brackets ([3], or [C] for a champion), and under it in the
same box the details: how the fight was won (Decision - Unanimous, KO/TKO ...), the weight class and whether a belt was at stake. Above the three boxes: "UFC 330 · Las Vegas · Sun 8 Nov" (the date
in Singapore time; a Fight Night is headed with its name, "UFC Fight Night: Cortes Acosta vs. Walker · Las Vegas · Sun 8 Nov").

One source for the fight details: UFC.com's own event page (the official one): card sections (Main Card, Prelims, Early Prelims), ranks as the card listed them, the title-bout label, who won, how, the
round and the time. ESPN's free scoreboard only finds which numbered event has just finished (and its city and date) and, if UFC.com cannot be read, gives the bare result (winner, weight class,
round, time) without ranks or the belt. A page laid out differently gives nothing rather than a wrong line."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from kickoff import render as r

SGT = ZoneInfo("Asia/Singapore")
RECENT = timedelta(days=3)
LABELS = ("Main Event", "Co-Main Event", "Prelims · Top Bout")          # Title Case, like every table title


def text_of(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment or "")).replace("&#039;", "'").replace("&amp;", "&").replace("&quot;", '"').strip()


def rank_text(s):
    """'C' for a champion, '8' for a ranked fighter (shown as [8], like every rank and seed), '' for an unranked one."""
    t = text_of(s)
    return t if t == "C" else t[1:] if re.fullmatch(r"#\d+", t) else ""


def fight_of(block):
    """One fight from its UFC.com html block: {"class_text", "weight", "title", "interim", "red": {...}, "blue": {...}, "round", "time", "method", "finished"}."""
    cls = re.search(r'c-listing-fight__class-text">(.*?)</div>', block, re.S)
    class_text = text_of(cls.group(1)) if cls else ""
    ranks_row = re.search(r'c-listing-fight__ranks-row">(.*?)</div>\s*\n\s*\n?\s*<div class="c-listing-fight__banner--live', block, re.S)
    ranks = [rank_text(x) for x in re.findall(r'js-listing-fight__corner-rank[^"]*">\s*(?:<span>(.*?)</span>)?\s*</div>', ranks_row.group(1) if ranks_row else "", re.S)]
    ranks = (ranks + ["", ""])[:2]

    def corner(color):
        m = re.search(rf'c-listing-fight__corner-name--{color}">(.*?)</a>', block, re.S)
        if not m:
            return ""
        given = re.search(r'corner-given-name">(.*?)</span>', m.group(1), re.S)
        family = re.search(r'corner-family-name">(.*?)</span>', m.group(1), re.S)
        if given or family:
            return " ".join(x for x in (text_of(given.group(1)) if given else "", text_of(family.group(1)) if family else "") if x)
        return text_of(m.group(1))                  # a fighter with a long name is written as plain text inside the link, not in given and family spans

    outcomes = re.findall(r"c-listing-fight__outcome--(\w+)", block)
    outcomes = (outcomes + ["", ""])[:2]
    get = lambda cls_: (text_of(re.search(rf'result-text {cls_}[^>]*>(.*?)</div>', block, re.S).group(1)) if re.search(rf'result-text {cls_}[^>]*>(.*?)</div>', block, re.S) else "")  # noqa: E731
    weight = re.sub(r"\s*(?:Interim )?Title Bout$|\s*Bout$", "", class_text).strip()
    return {"class_text": class_text, "weight": weight, "title": "Title" in class_text, "interim": "Interim" in class_text,
            "red": {"name": corner("red"), "rank": ranks[0], "outcome": outcomes[0]}, "blue": {"name": corner("blue"), "rank": ranks[1], "outcome": outcomes[1]},
            "round": get("round"), "time": get("time"), "method": get("method"), "finished": "win" in outcomes}


def parse(html):
    """{"main": [fights], "prelims": [...], "early": [...]} from a UFC.com event page, each in the order of the page (the billing order: the main event first)."""
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'id="(main-card|prelims-card|early-prelims)"', html)]
    out = {"main": [], "prelims": [], "early": []}
    starts = [m.start() for m in re.finditer(r'<div class="c-listing-fight" data-fmid', html)]
    for i, s in enumerate(starts):
        block = html[s:starts[i + 1] if i + 1 < len(starts) else len(html)]
        section = next((name for pos, name in reversed(marks) if pos < s), None)
        key = {"main-card": "main", "prelims-card": "prelims", "early-prelims": "early"}.get(section)
        if key:
            f = fight_of(block)
            if f["red"]["name"] and f["blue"]["name"]:
                out[key].append(f)
    return out


def three(parsed):
    """[(label, fight)] for the main event, the co-main event and the top bout of the Prelims, only those that are finished."""
    picks = []
    main, prelims = parsed.get("main", []), parsed.get("prelims", [])
    for label, f in ((LABELS[0], main[0] if main else None), (LABELS[1], main[1] if len(main) > 1 else None), (LABELS[2], prelims[0] if prelims else None)):
        if f and f["finished"]:
            picks.append((label, f))
    return picks


def how(f):
    """How the fight was won, as D asked ('Decision - Unanimous', 'Decision - Split', 'KO/TKO, round 3 (4:29)', 'Submission, round 1 (2:44)'): a decision says its type, a finish says when."""
    method = f["method"] or "Result"
    if "decision" in method.lower():
        return method
    return f"{method}" + (f", round {f['round']}" if f["round"] else "") + (f" ({f['time']})" if f["time"] else "")


def name_html(c, bold):
    rank = f' <span class="muted">[{r.esc(c["rank"])}]</span>' if c["rank"] else ""
    return f"<strong>{r.esc(c['name'])}</strong>{rank}" if bold else f"{r.esc(c['name'])}{rank}"


def box_html(label, f):
    """One fight in its box: the title row, the winner / def. / the loser, then the details."""
    win = f["red"] if f["red"]["outcome"] == "win" else f["blue"] if f["blue"]["outcome"] == "win" else None
    if win is None:
        return ""
    lose = f["blue"] if win is f["red"] else f["red"]
    belt = "Yes (interim)" if f["interim"] else "Yes" if f["title"] else "No"
    rows = (f'<tr class="vs"><td class="wn">{name_html(win, True)}</td><td class="df">def.</td><td class="ls">{name_html(lose, False)}</td></tr>'
            f'<tr class="dt"><td class="k">Method</td><td class="v" colspan="2">{r.esc(how(f))}</td></tr>'
            f'<tr class="dt"><td class="k">Weight class</td><td class="v" colspan="2">{r.esc(f["weight"])}</td></tr>'
            f'<tr class="dt"><td class="k">Title fight</td><td class="v" colspan="2">{belt}</td></tr>')
    return (f'<div class="ufc"><table><colgroup><col style="width:41%"><col style="width:14%"><col style="width:45%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="3">{r.esc(label)}</th></tr></thead><tbody>{rows}</tbody></table></div>')


def header(event):
    """'UFC 330 · Las Vegas · Sun 8 Nov' for a numbered event, 'UFC Fight Night: Cortes Acosta vs. Walker · Las Vegas · Sun 8 Nov' for the others (the date in Singapore time)."""
    n = re.match(r"^(UFC \d+)", event["name"])
    venue = (event.get("venues") or [{}])[0]
    city = (venue.get("address") or {}).get("city", "")
    when = datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(SGT)
    return " \u00b7 ".join(x for x in (n.group(1) if n else event["name"], city, f"{when:%a} {when.day} {when:%b}") if x)


def slugs(event, listing=()):
    """The UFC.com addresses to try for an event, best first: a numbered event is 'ufc-330' (sometimes with a sponsor in front, 'cryptocom-ufc-331', found in the events list); a Fight Night is
    'ufc-fight-night-november-07-2026' named for the day it was held where it was held, so the day of the start and the days either side are tried."""
    out = []
    n = re.match(r"^UFC (\d+)", event["name"])
    started = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
    if n:
        out += [x for x in listing if re.search(rf"(^|-)ufc-{n.group(1)}$", x)] + [f"ufc-{n.group(1)}"]
    else:
        for delta in (0, -1, 1):
            d = (started + timedelta(days=delta)).date()
            out.append(f"ufc-fight-night-{d:%B}-{d:%d}-{d:%Y}".lower())
    return list(dict.fromkeys(out))


def title_stories(event, parsed):
    """[text] for every finished title fight on the card (D, 2026-11-05: a title result is Big Stuff): 'UFC 330: Jon Jones def. Stipe Miocic for the heavyweight title (KO/TKO, round 3 (4:29))'."""
    n = re.match(r"^(UFC \d+)", event["name"])
    name = n.group(1) if n else event["name"]
    out = []
    for f in parsed.get("main", []) + parsed.get("prelims", []) + parsed.get("early", []):
        if not (f["title"] and f["finished"]):
            continue
        win = f["red"] if f["red"]["outcome"] == "win" else f["blue"] if f["blue"]["outcome"] == "win" else None
        if win is None:
            continue
        lose = f["blue"] if win is f["red"] else f["red"]
        out.append(f"{name}: {win['name']} def. {lose['name']} for the {'interim ' if f['interim'] else ''}{f['weight'].lower()} title ({how(f)})")
    return out


def espn_fallback(event):
    """The same three boxes from ESPN's scoreboard alone when UFC.com cannot be read: winner, weight class, round and time; no ranks, no belt (so those rows are left out), no method."""
    cs = event.get("competitions") or []
    picks = [(LABELS[0], cs[-1] if cs else None), (LABELS[1], cs[-2] if len(cs) > 1 else None)]
    out = []
    for label, c in picks:
        if not c or not c["status"]["type"].get("completed"):
            continue
        win = next((x for x in c["competitors"] if x.get("winner")), None)
        lose = next((x for x in c["competitors"] if not x.get("winner")), None)
        if not win or not lose:
            continue
        period, clock = c["status"].get("period"), c["status"].get("displayClock")
        weight = ((c.get("type") or {}).get("abbreviation")) or ""
        rows = (f'<tr class="vs"><td class="wn"><strong>{r.esc(win["athlete"]["displayName"])}</strong></td><td class="df">def.</td><td class="ls">{r.esc(lose["athlete"]["displayName"])}</td></tr>'
                + (f'<tr class="dt"><td class="k">Weight class</td><td class="v" colspan="2">{r.esc(weight)}</td></tr>' if weight else "")
                + (f'<tr class="dt"><td class="k">Ended</td><td class="v" colspan="2">round {period} ({r.esc(clock or "")})</td></tr>' if period else ""))
        out.append(f'<div class="ufc"><table><colgroup><col style="width:41%"><col style="width:14%"><col style="width:45%"></colgroup><thead><tr><th class="tt" colspan="3">{r.esc(label)}</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table></div>')
    return out


def run(source, now, state, fails=None):
    """{"blocks": [html], "state": {"done": [event ids]}}. source.ufc() -> ESPN's scoreboard json; source.ufc_page(slug) -> UFC.com's event page html; source.ufc_listing() (optional) -> the addresses on
    UFC.com's events list. A UFC event (numbered or a Fight Night) that finished within the last three days is shown once."""
    done = list((state or {}).get("done") or [])
    blocks, stories = [], []
    try:
        events = source.ufc().get("events", [])
    except Exception:
        (fails if fails is not None else []).append("ufc")
        return {"blocks": [], "stories": [], "state": {"done": done}}
    for e in events:
        try:
            started = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            if not re.match(r"^UFC\b", e["name"]) or e["id"] in done or e["status"]["type"].get("state") != "post" or not (timedelta(0) <= now - started <= RECENT):
                continue
            boxes, listing, parsed = [], [], {}
            try:
                listing = source.ufc_listing() if hasattr(source, "ufc_listing") else []
            except Exception:
                listing = []
            for slug in slugs(e, listing):                  # the first address whose page has finished fights
                try:
                    parsed = parse(source.ufc_page(slug))
                    boxes = [b for b in (box_html(label, f) for label, f in three(parsed)) if b]
                except Exception:
                    continue
                if boxes:
                    break
            if not boxes:
                (fails if fails is not None else []).append("ufc")
                boxes = espn_fallback(e)
            if boxes:
                blocks.append(f'<p class="subhead">{r.esc(header(e))}</p>' + "".join(boxes))
                done.append(e["id"])
                stories += title_stories(e, parsed)
        except Exception:
            (fails if fails is not None else []).append("ufc")
    return {"blocks": blocks, "stories": stories, "state": {"done": done[-20:]}}
