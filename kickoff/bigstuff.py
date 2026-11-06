"""The Big Stuff: the top block of the edition, picked by code from the stories every sport reports (kickoff/events.py, scored by kickoff/importance.py).

  Key overnight scores     the best stories of the morning, Arsenal's result always first; more lines on a heavy weekend morning, fewer on a quiet one
  Biggest news             transfers, sackings, appointments the football section already collected (with their source links)
  Major injuries           listed clubs' and tracked players' injuries the football section already collected
  Stars Of The Night       up to three individual performances on one 0-100 scale across sports (below the bar: none)
  Major Events             an F1 race or a Grand Slam from the quarter-finals (added by kickoff/order.py)

Everything chosen is explained in `why` for the dev log (never shown on the page): D will judge the ranking for a month and change numbers in importance.py."""
import re

from kickoff import importance
from kickoff import render as r

MAX_NEWS = 2
MAX_INJURIES = 2
STARS_MAX, STARS_PER_SPORT, STARS_MILESTONE_MAX = 3, 2, 5
SPORT_HEADER = {"cricket": "Cricket", "nfl": "NFL", "mlb": "MLB", "nba": "NBA", "f1": "F1"}


def names_of(text):
    return {w for w in re.findall(r"\b[A-Z][a-z]{2,}\b", text)}


def dedupe_news(items):
    """The same story from two sources (BBC and ESPN both on one contract) is shown once: an item that shares two or more names with an earlier one is dropped."""
    out = []
    for i in items:
        if not any(len(names_of(i["text"]) & names_of(o["text"])) >= 2 for o in out):
            out.append(i)
    return out


def select(stories, weekday):
    """The stories that make the list, best first. Arsenal's result ("first") leads; the cap depends on the weekday; a sport is limited to PER_SPORT lines unless the
    story is D's team's or a final (those are never squeezed out); a story under MIN_SCORE is dropped (a quiet morning has fewer lines)."""
    cap = importance.CAP.get(weekday, 5)
    ranked = sorted((s for s in stories if s.get("kind", "result") == "result" and s["score"] >= importance.MIN_SCORE and not s.get("promote")),   # F1 and tennis have Major Events
                    key=lambda s: (not s.get("first"), -s["score"], s["text"]))
    per, out = {}, []
    for s in ranked:
        n = per.get(s["sport"], 0)
        protected = s.get("mine") or s.get("stage") == "final"
        if len(out) >= cap and not (protected and len(out) < cap + 3):
            continue
        if n >= importance.PER_SPORT and not protected:
            continue
        per[s["sport"]] = n + 1
        out.append({**s, "why": f"score {s['score']}, {s['stage']}{', mine' if s.get('mine') else ''}, {s['sport']} #{n + 1}"})
    return out


def stars(perfs, limit=STARS_MAX):
    """Stars Of The Night (D, 2026-11-05: was one Performance of the Day): up to three individual performances on the common 0-100 scale, each at least PERFORMANCE_MIN, best first (D's own
    players win ties); at most two from one sport, so one sport cannot fill the list."""
    best = sorted((p for p in perfs if p.get("kind") == "perf" and p["score"] >= importance.PERFORMANCE_MIN), key=lambda p: (-p["score"], not p.get("mine", False), p["text"]))
    out, per = [], {}
    for p in best:
        if len(out) < limit and per.get(p["sport"], 0) < STARS_PER_SPORT:
            per[p["sport"]] = per.get(p["sport"], 0) + 1
            out.append(p)
    for p in best:                                          # a century or a five-wicket haul always makes it (D, 2026-11-05), up to five stars in all
        if p.get("milestone") and p not in out and len(out) < STARS_MILESTONE_MAX:
            out.append(p)
    return out


def html(stories, stars_=(), news=(), injuries=()):
    """The block's inner html. Empty string when there is nothing at all (a section appears only when it has something in it)."""
    out = ""
    if stories:
        out += "<h3>Key Overnight Scores</h3>" + _grouped(stories)
    if news:
        out += "<h3>Biggest News</h3>" + _list_html(dedupe_news(list(news))[:MAX_NEWS])
    if injuries:
        out += "<h3>Major Injuries</h3>" + _list_html(injuries[:MAX_INJURIES])
    if stars_:
        out += "<h3>Stars Of The Night</h3>" + _list_gold(p["text"] for p in stars_)
    return out


def split_story(s):
    """(header, line): 'Champions League', 'Arsenal 2\u20131 Slavia Prague' from the story 'Champions League: Arsenal 2\u20131 Slavia Prague'; a story whose text does not begin with its competition keeps
    the whole text under the competition's name."""
    label = SPORT_HEADER.get(s["sport"])
    if label and s["text"].startswith(label + ": "):          # cricket's competition is "International" or "IPL"; the header is the sport (D, 2026-11-05)
        return label, s["text"][len(label) + 2:]
    comp = s.get("comp") or s["sport"].upper()
    return (comp, s["text"][len(comp) + 2:]) if s["text"].startswith(comp + ": ") else (comp, s["text"])


def _grouped(stories):
    """The sport named once as a header, its games as gold-diamond bullets under it (D, 2026-11-05); the groups in the order of their best story (Arsenal's result leads)."""
    groups = {}
    for s in stories:
        head, line = split_story(s)
        groups.setdefault(head, []).append(line)
    return "".join(f'<p class="subhead">{r.esc(h)}</p>' + _list(lines) for h, lines in groups.items())


def gold_figures(text):
    """The main figure of a star line in gold (D, 2026-11-06): a cricketer's '111* (171)' or '4/35', and '52 pts', '3 goals' style figures for the other sports; the rest is plain."""
    out = r.esc(text)
    out = re.sub(r"(?<=: )(\*?\d+\*? \(\d+\)|\d+/\d+)", lambda m: f'<span class="n">{m.group(1)}</span>', out, count=1)
    return re.sub(r"(\d+) (pts|reb|ast|stl|blk|goals?|assists?|saves?)\b", r'<span class="n">\1 \2</span>', out)


def _list_gold(texts):
    return '<ul class="standouts bigstuff">' + "".join(f"<li>{gold_figures(t)}</li>" for t in texts) + "</ul>"


def _list(texts):
    return '<ul class="standouts bigstuff">' + "".join(f"<li>{r.esc(t)}</li>" for t in texts) + "</ul>"


def _list_html(items):
    """items: [{"text", "link"?, "source"?}]"""
    rows = ""
    for i in items:
        link = f' <a href="{r.esc(i["link"])}">{r.esc(i.get("source") or "source")}</a>' if i.get("link") else ""
        rows += f"<li>{r.esc(i['text'])}{link}</li>"
    return f'<ul class="standouts bigstuff">{rows}</ul>'


def headlines(stories, limit=3):
    """The Telegram ping's top lines: the first stories, with the sport prefix kept ('Football: ...')."""
    return [s["text"] for s in stories[:limit]]


def fill_headlines(selected, stories, stars_, limit=3):
    """The Telegram ping's headlines can never be empty (D, 2026-11-05: a quiet Friday sent the date and a link): the key scores first, then the Stars Of The Night, then the best of
    the rest of the finished games even if they are below the bar (that is how the Heat's overtime game would have got there)."""
    out = [s["text"] for s in selected[:limit - 1]]                     # two team scores ...
    top = next((p for p in stars_ if p.get("milestone")), None)         # ... then the best milestone Star (a hundred, 150+, ten in a match) in the third slot (D, 2026-11-06)
    if top is not None:
        out.append(f"Star Of The Night: {top['text']}")
    for s in selected[limit - 1:limit]:
        if len(out) < limit:
            out.append(s["text"])
    for p in stars_:
        if len(out) < limit and f"Star Of The Night: {p['text']}" not in out:
            out.append(f"Star Of The Night: {p['text']}")
    for s in sorted((x for x in stories if x["text"] not in out), key=lambda x: (-x["score"], x["text"])):
        if len(out) < limit:
            out.append(s["text"])
    return out[:limit]


def lead_sport(stories):
    """Which sport group leads (kickoff/order.py ids). Plain rules from SPEC: D's teams first; among several, the most important stage then the score; else a big
    competition moment (a knockout or playoff story); else None (normal order)."""
    stage_rank = {"final": 4, "knockout": 3, "playoff": 3, "top": 2, "regular": 1}
    mine = [s for s in stories if s.get("mine") and s.get("kind", "result") == "result"
            and not (s["sport"] == "mlb" and s.get("stage") == "regular")]        # baseball never leads in the regular season
    pool = mine or [s for s in stories if s.get("stage") in ("final", "knockout", "playoff") and s["sport"] != "mlb" and s.get("kind", "result") == "result"]
    if not pool:
        return None
    normal = {"football": 0, "cricket": 1, "nba": 2, "nfl": 3, "mlb": 4}          # the normal order of the sports breaks a tie between equally important matches
    best = max(pool, key=lambda s: (stage_rank.get(s["stage"], 0), -normal.get(s["sport"], 9), s["score"]))
    return {"football": "arsenal" if best.get("first") or (best["sport"] == "football" and best.get("mine")) else "football"}.get(best["sport"], best["sport"])


def promoted(stories):
    """Which of 'f1' / 'tennis' had a major moment this morning."""
    return [p for p in ("f1", "tennis") if any(s.get("promote") == p for s in stories)]


def build(events, news=(), injuries=(), weekday=1):
    """Everything the edition needs from the day's events: {"html", "headlines", "lead", "promoted", "majors" ({"f1": text}), "selected", "stars"}."""
    stories = [e for e in events if e.get("kind", "result") == "result"]
    selected = select(stories, weekday)
    star_list = stars([e for e in events if e.get("kind") == "perf"])
    major = {p: next(s["text"].split(": ", 1)[-1] for s in stories if s.get("promote") == p) for p in promoted(stories)}
    return {"html": html(selected, star_list, news, injuries), "headlines": fill_headlines(selected, stories, star_list), "quiet": len(selected) < 3, "lead": lead_sport(stories), "promoted": list(major),
            "majors": major, "selected": selected, "stars": star_list}
