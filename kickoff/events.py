"""Turns each sport's finished games into story candidates for The Big Stuff (kickoff/bigstuff.py): plain dicts, scored by kickoff/importance.py.

A story: {"sport", "comp", "text", "score", "mine", "stage", "first"?, "promote"?, "why"}.
A performance: {"kind": "perf", "sport", "text", "score" (0-100 on one scale for every sport), "mine"}.

Each sport's run() calls its converter on the games it has already read, so The Big Stuff and the sport's own section always agree and nothing is fetched twice."""
import re

from kickoff import champions, clubs, importance, overview
from kickoff import cricket as cricket_mod
from kickoff import tennis as tennis_mod

DASH = "–"
ARSENAL_IDS = {"359", "19973"}                      # Arsenal and Arsenal Women (ESPN team ids)
MY_FOOTBALL = ARSENAL_IDS
MY_NFL = {"JAX", "PIT"}                             # the Jaguars (Trevor Lawrence) and the Steelers (Aaron Rodgers)
LAD = "19"                                           # the Dodgers' ESPN team id: D's team in the MLB postseason only
KOHLI = re.compile(r"\bkohli\b", re.I)
MINE_CRICKET = re.compile(r"^(india|sunrisers hyderabad|royal challengers (bangalore|bengaluru))$", re.I)    # India men, Sunrisers, Royal Challengers (Kohli's team)
KNOCKOUT_WORDS = re.compile(r"\b(qualifier|eliminator|semi-?final|quarter-?final|play-?off|super (over|four|eight))\b", re.I)


def story(sport, comp, text, score, mine=False, stage="regular", **extra):
    return {"kind": "result", "sport": sport, "comp": comp, "text": text, "score": score, "mine": mine, "stage": stage, **extra}


def perf(sport, text, score, mine=False):
    return {"kind": "perf", "sport": sport, "text": text, "score": round(min(score, 100), 1), "mine": mine}


# ---- Football ---------------------------------------------------------------------------------

def football_stage(comp, m):
    slug = m.get("stage", "")
    if comp in ("Champions League", "UEFA Champions League"):
        return ("final" if slug == "final" else "knockout") if slug in champions.KNOCKOUT_STAGES else "top"        # a league-phase night is a big competition moment
    if comp == "FA Cup":
        return "final" if slug == "final" else "regular"
    return "regular"


def winner_first(m):
    """'Galatasaray 4–2 Lille' for an away win (the winner first, with his score first, as every summary line reads; D, 2026-11-05), 'Arsenal 2–1 Brentford' for a home win and 'Bayern Munich 2–2 Arsenal'
    (home first) for a draw."""
    h, a, hs, as_ = m["home"]["name"], m["away"]["name"], m["home_score"], m["away_score"]
    return f"{a} {as_}{DASH}{hs} {h}" if as_ > hs else f"{h} {hs}{DASH}{as_} {a}"


def late_winner(m):
    """True when the match was won (not drawn) by a goal in the 90th minute or later that made it a one-goal game or gave the lead: a stoppage-time winner."""
    hs, as_ = m.get("home_score"), m.get("away_score")
    if hs is None or as_ is None or hs == as_ or abs(hs - as_) > 1:
        return False
    win_side = "home" if hs > as_ else "away"
    goals = [g for g in (m.get("goals") or []) if g.get("side") == win_side]
    last = max((g for g in goals), key=lambda g: g.get("minute") or 0, default=None)
    try:
        minute = int(str(last.get("minute")).split("+")[0].replace("'", "")) if last else 0
    except ValueError:
        minute = 0
    return minute >= 90


def football(comps, weekday):
    """comps: [(competition name, [match dicts from espn.parse_match])]. Finished matches only. Arsenal's (men and women) is flagged "first"."""
    out = []
    for comp, matches in comps:
        for m in matches:
            if not m.get("completed", True):
                continue
            ids = [str(m["home"].get("id")), str(m["away"].get("id"))]
            d = overview.drama(m)
            mine = any(i in MY_FOOTBALL for i in ids)
            listed = any(clubs.is_listed(i) for i in ids)
            bonus = min(0.5 * d["margin"] + 0.3 * d["total_goals"] + (1 if d["comeback"] else 0), 4)
            wow = d["margin"] >= 5 or (d["comeback"] and d["total_goals"] >= 5)
            drama = late_winner(m)
            stage = football_stage(comp, m)
            text = f"{comp.replace('UEFA ', '')}: {winner_first(m)}"
            e = story("football", comp, text, importance.story_score("football", stage, mine, listed, margin_bonus=bonus, wow=wow, weekday=weekday, drama=drama), mine, stage)
            if any(i == "359" for i in ids):
                e["first"] = True
            out.append(e)
    return out


def football_perf(comp, performers_list):
    """performers_list: kickoff.performers.best output ({"id", "text", "score"}): one scale for all sports (x6: a hat-trick is about 100)."""
    return [perf("football", f"{x['text']}", x["score"] * 6) for x in performers_list]


# ---- NBA ---------------------------------------------------------------------------------------

def nba(games, mine_teams, weekday):
    """games: nba.parse_game dicts (final ones are used). mine_teams: codes of the teams with a tracked player on them. Every playoff and play-in game counts."""
    out = []
    for g in games:
        if g["status"] != "final":
            continue
        a, h = g["away"], g["home"]
        win, lose = (a, h) if a["score"] > h["score"] else (h, a)
        margin = abs(a["score"] - h["score"])
        if g["phase"] == "playoffs":
            stage = "final" if "finals" in (g.get("headline") or "").lower() and "conf" not in (g.get("headline") or "").lower() and "east" not in (g.get("headline") or "").lower() \
                and "west" not in (g.get("headline") or "").lower() else "playoff"
        elif g["phase"] == "playin" or g.get("cup") in ("Quarterfinals", "Semifinals"):
            stage = "knockout"
        elif g.get("cup") == "Championship":
            stage = "final"
        else:
            stage = "regular"
        mine = a["abbr"] in mine_teams or h["abbr"] in mine_teams
        text = f"NBA: {win['name']} {win['score']}{DASH}{lose['score']} {lose['name']}" + (" (OT)" if g.get("ot") else "")
        if g.get("series"):
            text += f" · {g['series']}"
        wow = margin >= 35
        bonus = (0.5 if g.get("ot") else 0) + (0.05 * max(margin - 20, 0))
        drama = bool(g.get("clutch")) or (bool(g.get("ot")) and margin <= 3) or margin <= 1             # a game-winner in the last seconds, a close overtime, a one-point game
        out.append(story("nba", "NBA", text, importance.story_score("nba", stage, mine, margin_bonus=bonus, wow=wow, weekday=weekday, drama=drama), mine, stage))
    return out


def nba_perf(rows):
    """rows: [(text, weight)] the day's tracked-or-standout lines with nba.weight (about 70 for a monster night)."""
    return [perf("nba", t, w) for t, w in rows]


# ---- NFL ---------------------------------------------------------------------------------------

def nfl(games, season_type, week, weekday):
    out = []
    for g in games:
        if g["status"] != "final":
            continue
        a, h = g["away"], g["home"]
        win, lose = (a, h) if a["score"] > h["score"] else (h, a)
        margin = abs(a["score"] - h["score"])
        stage = ("final" if week == 5 else "playoff") if season_type == 3 else "regular"
        mine = a["abbr"] in MY_NFL or h["abbr"] in MY_NFL
        text = f"NFL: {win['name']} {win['score']}{DASH}{lose['score']} {lose['name']}" + (" (OT)" if g.get("ot") else "")
        bonus = (0.5 if g.get("ot") else 0) + min(0.1 * margin, 2)
        out.append(story("nfl", "NFL", text, importance.story_score("nfl", stage, mine, margin_bonus=bonus, wow=margin >= 35, weekday=weekday), mine, stage))
    return out


# ---- MLB ---------------------------------------------------------------------------------------

def mlb(games, weekday):
    """Postseason games all count (the World Series is a final); the Dodgers are D's team in the postseason only."""
    out = []
    for g in games:
        if g["status"] != "final":
            continue
        a, h = g["away"], g["home"]
        win, lose = (a, h) if a["score"] > h["score"] else (h, a)
        post = g["phase"] == "post"
        stage = ("final" if "world series" in (g.get("headline") or "").lower() else "playoff") if post else "regular"
        mine = post and LAD in (a["id"], h["id"])
        extra = f" ({g['innings']})" if g.get("innings", 0) > 9 else ""
        text = f"MLB: {win['name']} {win['score']}{DASH}{lose['score']} {lose['name']}{extra}" + (f" · {g['headline']}" if post and g.get("headline") else "")
        out.append(story("mlb", "MLB", text, importance.story_score("mlb", stage, mine, margin_bonus=0.5 if extra else 0, wow=g.get("innings", 0) >= 13, weekday=weekday), mine, stage))
    return out


# ---- Cricket -----------------------------------------------------------------------------------

def is_mine_cricket(m):
    """India men, Sunrisers Hyderabad or Royal Challengers: women's sides ('India Women') do not count as D's teams."""
    teams = m.get("teams") or []
    if m.get("class", {}).get("women"):
        return False
    return any(MINE_CRICKET.match(t.strip()) for t in teams)


def kohli_innings(entry):
    """[(runs, balls, not out)] for every innings of Virat Kohli in a saved scorecard entry (cricket.slim_card), else []."""
    out = []
    for inn in (entry or {}).get("innings") or []:
        for b in inn.get("batting") or []:
            if KOHLI.search(b.get("name", "")):
                out.append((b.get("r") or 0, b.get("b") or 0, "not out" in (b.get("out") or "").lower() or b.get("mark") == "*"))
    return out


def kohli_perf(runs):
    """His innings on the 0-100 Performance of the Day scale: 30 plus 0.9 a run plus 15 because he is D's favourite player. A duck stays under the bar; 28 runs clears it."""
    return 30 + 0.9 * runs + 15


def kohli_text(innings):
    return ", ".join(f"Virat Kohli {r}{'*' if n else ''} ({b})" for r, b, n in innings)


def cricket(picked, cards, weekday, reported=(), changed=None, now=None):
    """picked: cricket.pick output (ended matches are results; every match with a scorecard can give milestones). cards: {match id: saved scorecard entry}. A match with Virat Kohli in it gets
    his figures on its line and his own score bonus; a Kohli innings is also a Star Of The Night candidate.
    Milestones (D, 2026-11-05) come from live matches too, so a day-one Test century is news the same morning, once: a hundred and then 150, 200, 250, 300 each get one announcement;
    five wickets and ten in a match once; a T20 fast fifty once. `reported`: the keys already announced. Key Overnight Scores are team scores (D, 2026-11-06): a finished match's result,
    and for a Test in progress its team scores and day, on the mornings its score moved (`changed`: the ids; None means every one); the individual performances are the Stars (short team codes).
    Returns (stories, performances, the new keys)."""
    reported, new_keys = set(reported), set()
    out, perfs = [], []
    for m in picked:
        ended = bool(m.get("matchEnded"))
        teams, rest = cricket_mod.title(m)
        label = (m.get("class") or {}).get("label", "")
        mine = is_mine_cricket(m)
        k = kohli_innings(cards.get(m["id"]))
        name = m.get("name", "")
        stage = "final" if re.search(r"\bfinal\b", name, re.I) and not re.search(r"semi|quarter", name, re.I) else "knockout" if KNOCKOUT_WORDS.search(name) else "regular"
        if ended:
            result = cricket_mod.short_result(m.get("status"))
            text = f"Cricket: {teams}" + (f" ({label})" if label and label != "International" else "") + (f", {result}" if result else "") + (f" \u00b7 {kohli_text(k)}" if k else "")
            sc = importance.story_score("cricket", stage, mine, kohli=bool(k), weekday=weekday)
            out.append(story("cricket", label or "Cricket", text, sc, mine or bool(k), stage, kohli=bool(k)))
        card_standouts = (cards.get(m["id"]) or {}).get("standouts", [])
        if not ended and m.get("matchType") == "test" and m.get("score") and (changed is None or m["id"] in changed):
            day = cricket_mod.day_of(m, cards.get(m["id"]), now)
            scores = ", ".join(cricket_mod.wname(cricket_mod.innings_line(x, m.get("teams") or [])) for x in m["score"])
            out.append(story("cricket", label or "Cricket", f"Cricket: {teams}" + (f" \u00b7 Day {day}" if day else "") + f": {scores}", 6, mine, "regular"))
        if ended:
            for r_, b_, n_ in k:
                mine_k = next((o for o in card_standouts if o["kind"] in ("kohli", "century") and cricket_mod.KOHLI.search(o["name"]) and o["runs"] == r_), None)
                perfs.append(perf("cricket", cricket_mod.standout_text(mine_k, short=True) if mine_k else f"Virat Kohli {r_}{'*' if n_ else ''} ({b_} balls) in {teams}", kohli_perf(r_), True))
        is_test = m.get("matchType") == "test"
        bonus = 10 if mine else 0
        for o in card_standouts:
            if ended and cricket_mod.KOHLI.search(o.get("name", "")):          # his own innings is the Kohli performance above
                continue
            kind, who = o["kind"], o["name"]
            if kind == "century":
                steps = [s_ for s_ in cricket_mod.LADDER if o["runs"] >= s_]
                top = steps[-1]
                key = f"{m['id']}|{who}|bat{top}"
                if key in reported:
                    continue
                new_keys.update(f"{m['id']}|{who}|bat{s_}" for s_ in steps)
                score = min(100, 85 + 0.3 * (o["runs"] - 100) + bonus + (8 if top >= 150 else 0))
                p = {**perf("cricket", cricket_mod.standout_text(o, short=True), score, mine), "milestone": True}
            elif kind == "five-for":
                key = f"{m['id']}|{who}|5w"
                if key in reported or f"{m['id']}|{who}|10w" in reported:
                    continue
                new_keys.add(key)
                p = {**perf("cricket", cricket_mod.standout_text(o, short=True), 80 + 5 * (o["wickets"] - 5) + bonus, mine), "milestone": True}
            elif kind == "ten-for":
                key = f"{m['id']}|{who}|10w"
                if key in reported:
                    continue
                new_keys.update({key, f"{m['id']}|{who}|5w"})
                p = {**perf("cricket", cricket_mod.standout_text(o, short=True), 92 + bonus, mine), "milestone": True}
            elif kind == "fast fifty":
                key = f"{m['id']}|{who}|ff{o['runs']}"
                if key in reported:
                    continue
                new_keys.add(key)
                p = perf("cricket", cricket_mod.standout_text(o, short=True), min(95, 72 + 0.2 * (o["runs"] - 50) + 0.4 * (cricket_mod.FAST_FIFTY_BALLS - o["balls"]) + bonus), mine)
            else:
                continue
            perfs.append(p)
    return out, perfs, new_keys


# ---- F1 and tennis ------------------------------------------------------------------------------

def f1(races):
    """races: [(race name, winner's full name, constructor)] for each Grand Prix whose race result was shown this morning. Always a headline (D): promoted to its own section."""
    return [story("f1", "F1", f"F1: {w} wins the {name}" + (f" for {c}" if c else ""), importance.story_score("f1", "final"), False, "final", promote="f1") for name, w, c in races]


def tennis(slams, matches):
    """slams: tennis.run's list ({"name", "stage", "major"}); matches: [(slam name, tennis.parse_match dict)] shown this morning. Quarter-finals and later only (D)."""
    out = []
    late = {"QF": "quarter-final", "SF": "semi-final", "F": "final"}
    for name, m in matches:
        if m["stage"] not in late:
            continue
        sets = tennis_mod.score(m, tb=False)
        text = f"Tennis: {m['winner']['short']} beat {m['loser']['short']}" + (f" {sets}" if sets else "") + f" in the {name} {late[m['stage']]}"
        stage = "final" if m["stage"] == "F" else "knockout"
        out.append(story("tennis", name, text, importance.story_score("tennis", stage), False, stage, promote="tennis"))
    if not out and any(s.get("major") for s in slams):
        s = next(s for s in slams if s.get("major"))
        out.append(story("tennis", s["name"], f"Tennis: {s['name']} is in the {late.get(s['stage'], 'last eight')} stage", importance.story_score("tennis", "knockout"), False, "knockout", promote="tennis"))
    return out


# ---- News and injuries for The Big Stuff (collected by the football section) ----------------------

NEWS_RANK = {"manager_sacked": 0, "manager_appointed": 0, "manager_news": 0, "transfer_confirmed": 1, "injury": 2, "transfer_rumour": 3}


STRONG_NEWS = re.compile(r"\b(sack|appoint|confirm|named|unveil|head coach|new manager|signs?|agree|complete)", re.I)    # an item nobody has judged (Claude off) needs words like these ...
LIVE_BLOG = re.compile(r"\b(live|as it happened|minute-by-minute)\b|\bv\b", re.I)                                         # ... and must not be a live blog or a match preview


def football_news(shown):
    """The biggest news: Arsenal's stories first, then sackings and appointments, confirmed transfers, injuries; rumours last. [{"text", "link", "source"}]."""
    from kickoff import news as news_mod
    ranked = sorted((i for i in shown if not news_mod.is_renewal(i)), key=lambda i: (i.get("club") != "Arsenal", NEWS_RANK.get(i["kind"], 9), i["published"]))
    return [{"text": i["summary"] or i["headline"], "link": i["link"], "source": i["source"]} for i in ranked
            if (i["kind"] != "transfer_rumour" or i.get("club") == "Arsenal") and (i["summary"] or STRONG_NEWS.search(i["headline"]) and not LIVE_BLOG.search(i["headline"]))]


def football_injuries(items):
    """Major injuries: key players out or suspended (Arsenal's first). [{"text"}]."""
    keep = [i for i in items if i["kind"] in ("out", "suspended")]
    keep.sort(key=lambda i: (i["team"] != "ARS", i["name"]))
    return [{"text": f"{i['name']} ({i['team']}): {'suspended' if i['kind'] == 'suspended' else 'out'}" + (f", {i['detail']}" if i.get("detail") else "")} for i in keep]
