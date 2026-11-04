"""The Big Stuff: the top block of the edition, picked by code from the stories every sport reports (kickoff/events.py, scored by kickoff/importance.py).

  Key overnight scores     the best stories of the morning, Arsenal's result always first; more lines on a heavy weekend morning, fewer on a quiet one
  Biggest news             transfers, sackings, appointments the football section already collected (with their source links)
  Major injuries           listed clubs' and tracked players' injuries the football section already collected
  Performance of the Day   one line, the best performance on one 0-100 scale across sports (below the bar: none)
  Major Events             an F1 race or a Grand Slam from the quarter-finals (added by kickoff/order.py)

Everything chosen is explained in `why` for the dev log (never shown on the page): D will judge the ranking for a month and change numbers in importance.py."""
from kickoff import importance
from kickoff import render as r

MAX_NEWS = 2
MAX_INJURIES = 2


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


def performance(perfs):
    """The one Performance of the Day, or None: the highest score on the common scale, at least PERFORMANCE_MIN; D's own players win ties."""
    best = [p for p in perfs if p.get("kind") == "perf" and p["score"] >= importance.PERFORMANCE_MIN]
    return max(best, key=lambda p: (p["score"], p.get("mine", False)), default=None)


def html(stories, perf=None, news=(), injuries=()):
    """The block's inner html. Empty string when there is nothing at all (a section appears only when it has something in it)."""
    out = ""
    if stories:
        out += "<h3>Key Overnight Scores</h3>" + _list(s["text"] for s in stories)
    if news:
        out += "<h3>Biggest News</h3>" + _list_html(news[:MAX_NEWS])
    if injuries:
        out += "<h3>Major Injuries</h3>" + _list_html(injuries[:MAX_INJURIES])
    if perf:
        out += f'<h3>Performance Of The Day</h3><p class="pod">{r.esc(perf["text"])}</p>'
    return out


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
    """Everything the edition needs from the day's events: {"html", "headlines", "lead", "promoted", "majors" ({"f1": text}), "selected", "perf"}."""
    stories = [e for e in events if e.get("kind", "result") == "result"]
    selected = select(stories, weekday)
    perf = performance([e for e in events if e.get("kind") == "perf"])
    major = {p: next(s["text"].split(": ", 1)[-1] for s in stories if s.get("promote") == p) for p in promoted(stories)}
    return {"html": html(selected, perf, news, injuries), "headlines": headlines(selected), "lead": lead_sport(stories), "promoted": list(major),
            "majors": major, "selected": selected, "perf": perf}
