"""Grand Slam tennis: new completed singles matches as scoreboards, standouts, and top-10 withdrawals. All by code from exact data, so
no Claude cost.

Rules (D's): men's and women's singles only. Rounds 1 to 3 show only matches with at least one seeded player; the last 16 onwards
show every match. Standouts: top-10 seeds knocked out, comebacks from two sets down, and milestones. Withdrawals of top-10 players
before a Slam come from the news feeds.

Which matches are new is decided by the state ({"reported": [match ids]}), not by the clock, so a late-finishing match is never lost
and nothing is shown twice. Matches completed more than LOOKBACK ago are not shown."""
import re
from datetime import datetime, timedelta, timezone

from kickoff import render as r
from kickoff.sources import espn_tennis

FEEDS = [("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/tennis/rss.xml"), ("The Guardian", "rss", "https://www.theguardian.com/sport/tennis/rss"),
         ("ESPN", "espn", "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/news")]
LOOKBACK = timedelta(days=3)
NEWS_RECENT = timedelta(hours=36)
TOP_SEED = 10
STAGES = {"Round 1": "R1", "Round 2": "R2", "Round 3": "R3", "Round 4": "R4", "Quarterfinal": "QF", "Semifinal": "SF", "Final": "F"}
ORDER = ["R1", "R2", "R3", "R4", "QF", "SF", "F"]
STAGE_NAME = {"R1": "First Round", "R2": "Second Round", "R3": "Third Round", "R4": "Fourth Round", "QF": "Quarter-finals", "SF": "Semi-finals", "F": "Final"}
PER_DRAW = {"R1": 64, "R2": 32, "R3": 16, "R4": 8, "QF": 4, "SF": 2, "F": 1}  # matches in each round of a 128-player singles draw
REACHES = {"R4": "the quarter-finals", "QF": "the semi-finals", "SF": "the final"}  # what winning that round means
DRAW = {"mens-singles": "Men's Singles", "womens-singles": "Women's Singles"}
LABELS = ("Top Seed Out", "Comeback", "Milestone", "Withdrawal")
NOTE = re.compile(r"^(?:\((\d+)\)\s+)?.+?\s+\([A-Z]{2,3}\)\s+bt\s+(?:\((\d+)\)\s+)?.+?\s+\([A-Z]{2,3}\)")
COMPLETED = ("STATUS_FINAL", "STATUS_RETIRED", "STATUS_WALKOVER")


def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


# ---- Reading a match ------------------------------------------------------------------------------

def _sets(win, lose):
    """Each set from the match winner's side: games for him, games for his opponent, the loser's tie-break points (None without a
    tie-break), and whether he won the set. Sets are read pairwise from the two players' line scores."""
    out = []
    for a, b in zip(win.get("linescores") or [], lose.get("linescores") or []):
        if int(a["value"]) == 0 and int(b["value"]) == 0:  # a set that never started (retired before it began)
            continue
        tbs = [x["tiebreak"] for x in (a, b) if x.get("tiebreak") is not None]
        out.append({"w": int(a["value"]), "l": int(b["value"]), "tb": min(tbs) if tbs else None, "won": bool(a.get("winner"))})
    return out


def score(m, tb=True):
    """'6-3 7-6(2) 5-7 6-2', with ' ret.' after a retirement and 'w/o' for a walkover."""
    if m["status"] == "walkover":
        return "w/o"
    text = " ".join(f"{s['w']}-{s['l']}" + (f"({s['tb']})" if tb and s["tb"] is not None else "") for s in m["sets"])
    return text + (" ret." if m["status"] == "retired" else "")


def parse_match(comp, draw, qualifiers=frozenset(), stages=None):
    """A match as plain data, or None for qualifying rounds, doubles, unfinished or unreadable matches. stages: round names to stage codes (the Slams' by default)."""
    stage = (stages or STAGES).get((comp.get("round") or {}).get("displayName"))
    if not stage or comp["status"]["type"]["name"] not in COMPLETED or comp["status"]["type"].get("state") != "post":
        return None
    people = comp.get("competitors") or []
    wins = [p for p in people if p.get("winner")]
    if len(people) != 2 or len(wins) != 1:
        return None
    win, lose = wins[0], next(p for p in people if not p.get("winner"))
    note = NOTE.match(((comp.get("notes") or [{}])[0]).get("text", ""))
    seeds = (int(note.group(1)) if note and note.group(1) else None, int(note.group(2)) if note and note.group(2) else None)
    who = lambda p, seed: {"id": p["id"], "name": p["athlete"]["displayName"], "short": p["athlete"]["shortName"], "seed": seed,  # noqa: E731
                           "qualifier": p["id"] in qualifiers}
    return {"id": comp["id"], "date": utc(comp["date"]), "draw": draw, "stage": stage, "status": {"STATUS_FINAL": "final", "STATUS_RETIRED": "retired",
            "STATUS_WALKOVER": "walkover"}[comp["status"]["type"]["name"]], "winner": who(win, seeds[0]), "loser": who(lose, seeds[1]),
            "sets": _sets(win, lose)}


def matches_of(event):
    """Every finished singles match of a Slam event, as plain data. Qualifiers are the players who won a qualifying final."""
    out = []
    for g in event["groupings"]:
        slug = g["grouping"]["slug"]
        if slug not in DRAW:
            continue
        qualifiers = {p["id"] for c in g["competitions"] if (c.get("round") or {}).get("displayName") == "Qualifying Final"
                      for p in c.get("competitors") or [] if p.get("winner")}
        out += [m for m in (parse_match(c, slug, qualifiers) for c in g["competitions"]) if m]
    return out


def stage_reached(event, now=None):
    """The furthest round with a match played or started in either singles draw ('R1' ... 'F'), or None. With `now`, matches dated
    later than now do not count."""
    best = -1
    for g in event["groupings"]:
        if g["grouping"]["slug"] not in DRAW:
            continue
        for c in g["competitions"]:
            st = STAGES.get((c.get("round") or {}).get("displayName"))
            if st and c["status"]["type"].get("state") in ("in", "post") and (now is None or utc(c["date"]) <= now):
                best = max(best, ORDER.index(st))
    return ORDER[best] if best >= 0 else None


# ---- What to show ---------------------------------------------------------------------------------

def seeded(m):
    return m["winner"]["seed"] is not None or m["loser"]["seed"] is not None


def shown(m):
    """D's rule: rounds 1 to 3 only with a seeded player; the last 16 onwards everything."""
    return ORDER.index(m["stage"]) >= ORDER.index("R4") or seeded(m)


def pick(matches, now, reported):
    """New matches to show: started no later than now and within the lookback, not reported before, and passing the seeding rule. Latest round first, and
    within a round the best-seeded match first."""
    new = [m for m in matches if m["id"] not in set(reported) and timedelta(0) <= now - m["date"] <= LOOKBACK and shown(m)]
    best = lambda m: min((s for s in (m["winner"]["seed"], m["loser"]["seed"]) if s is not None), default=999)  # noqa: E731
    return sorted(new, key=lambda m: (-ORDER.index(m["stage"]), best(m), m["date"]))


SGT = timezone(timedelta(hours=8))


def dates_line(matches):
    """'Sun 13 – Mon 14 Sep SGT' (a muted line under a tournament's heading): the first and last day, in Singapore time, of the matches shown; one day when they share it."""
    if not matches:
        return ""
    days = sorted({m["date"].astimezone(SGT).date() for m in matches})
    first, last = days[0], days[-1]
    fmt = lambda d: f"{d:%a} {d.day}"  # noqa: E731
    text = f"{fmt(first)} {first:%b}" if first == last else (f"{fmt(first)} – {fmt(last)} {last:%b}" if first.month == last.month else f"{fmt(first)} {first:%b} – {fmt(last)} {last:%b}")
    return f'<p class="muted">{text} SGT</p>'


def name(p, short=True):
    return (f"({p['seed']}) " if p["seed"] else "") + (p["short"] if short else p["name"])


# ---- Standouts ------------------------------------------------------------------------------------

def seeds_out(matches):
    out = []
    for m in matches:
        s = m["loser"]["seed"]
        if s is not None and s <= TOP_SEED and m["stage"] != "F":     # the beaten finalist is the champion's milestone line, not a shock
            how = {"final": "beaten by", "retired": "retired against", "walkover": "withdrew before facing"}[m["status"]]
            out.append(f"Top Seed Out: {name(m['loser'])} {how} {name(m['winner'])} in the {STAGE_NAME[m['stage']].lower()}"
                       + ("" if m["status"] == "walkover" else f", {score(m)}") + ".")
    return out


def comebacks(matches):
    """Men's best-of-five only: lost the first two sets, won the match 3-2."""
    out = []
    for m in matches:
        s = m["sets"]
        if (m["draw"] == "mens-singles" and m["status"] == "final" and len(s) == 5 and not s[0]["won"] and not s[1]["won"]
                and sum(x["won"] for x in s) == 3):
            out.append(f"Comeback: {name(m['winner'])} came back from two sets down to beat {name(m['loser'])}, {score(m)}, in the {STAGE_NAME[m['stage']].lower()}.")
    return out


def milestones(matches, event):
    out = []
    defending = {p["displayName"] for p in event.get("previousWinners") or []}
    slug_of = {p["displayName"]: p["type"]["slug"] for p in event.get("previousWinners") or []}
    for m in matches:
        if m["stage"] == "F" and m["status"] == "final":
            out.append(f"Milestone: {m['winner']['name']} wins the {event['name']} {DRAW[m['draw']].lower()} title, beating {m['loser']['name']} {score(m)}.")
        if m["loser"]["name"] in defending and slug_of.get(m["loser"]["name"]) == m["draw"]:
            out.append(f"Milestone: defending champion {m['loser']['name']} is out in the {STAGE_NAME[m['stage']].lower()}.")
        if m["winner"]["qualifier"] and m["stage"] in REACHES:
            out.append(f"Milestone: qualifier {m['winner']['name']} reaches {REACHES[m['stage']]}.")
    return out


# ---- Withdrawals from the news --------------------------------------------------------------------

WITHDRAW = re.compile(r"\b(withdr[ae]\w*|pulls? out|pulled out|ruled out of|to miss|will miss|misses|skips?|skipping)\b", re.I)


def withdrawals(items, now, top10, seen=()):
    """News items from the last 36 hours about a top-10 player withdrawing from a Slam: [(line, link)]. Headlines are shown as written.
    top10() returns the current top-ten names; it is only called (once) when a headline already looks like a Slam withdrawal."""
    slam = re.compile("|".join(re.escape(s) for s in espn_tennis.SLAMS) + "|French Open|Roland.Garros", re.I)
    out, names = [], None
    for i in items:
        if (i["link"] in seen or now - i["published"] > NEWS_RECENT or i["published"] > now + timedelta(hours=1)
                or not WITHDRAW.search(i["title"]) or not slam.search(i["title"])):
            continue
        if names is None:
            names = top10()
        text = f"{i['title']} {i['text']}"
        if any(re.search(rf"(?<!\w){re.escape(p.split()[-1])}(?!\w)", text, re.I) for p in names):
            out.append((f"Withdrawal: {i['title']} ({i['source']})", i["link"]))
    return out


# ---- Page -----------------------------------------------------------------------------------------

def _label(text):
    head, sep, rest = text.partition(": ")
    return f"<strong>{r.esc(head)}:</strong> {r.esc(rest)}" if sep and head in LABELS else r.esc(text)


def _list(items):
    return '<ul class="standouts">' + "".join(f"<li>{_label(i)}</li>" for i in items) + "</ul>" if items else ""


def _games(s, winner_row):
    """One set's games for one player; the tie-break points sit small beside the games of whoever lost that set."""
    mine, theirs = (s["w"], s["l"]) if winner_row else (s["l"], s["w"])
    sup = f"<sup>{s['tb']}</sup>" if s["tb"] is not None and mine < theirs else ""
    return f"{mine}{sup}"


def progress_of(matches, now=None):
    """{(draw, stage): matches finished so far}, counting only matches that have started by `now`."""
    done = {}
    for m in matches:
        if now is None or m["date"] <= now:
            done[(m["draw"], m["stage"])] = done.get((m["draw"], m["stage"]), 0) + 1
    return done


def progress_text(stage, done):
    """'2/4 played', or '4/4 complete' once the round is finished."""
    total = PER_DRAW[stage]
    return f"{done}/{total} {'complete' if done >= total else 'played'}"


def stage_table(draw, stage, matches, done=None, title=None, sets=None):
    """One table for a draw and round: two rows per match (winner above), a column for each possible set. A retirement or walkover is
    tagged in the empty set cells of the loser's row, or after his name when every set cell is used. title: replaces "Men's Singles · Third Round";
    sets: the most sets a match can have (best of five in a men's Slam, three otherwise, and three at the tour finals)."""
    n = sets or (5 if draw == "mens-singles" else 3)
    sw = 9 if n == 5 else 12
    widths = [100 - sw * n] + [sw] * n
    cols = "".join(f'<col style="width:{w}%">' for w in widths)
    rows = []
    for m in matches:
        for winner_row, p in ((True, m["winner"]), (False, m["loser"])):
            played = len(m["sets"])
            tag = {"retired": "ret.", "walkover": "w/o"}.get(m["status"]) if not winner_row else None
            cells = "".join(f'<td class="s">{_games(m["sets"][i], winner_row)}</td>' for i in range(played))
            after = ""
            if tag and played < n:  # the tag sits in the first empty set cell and may spill over the empty ones beside it
                cells += f'<td class="tag">{tag}</td>' + "".join('<td class="s"></td>' for _ in range(n - played - 1))
            else:
                cells += "".join('<td class="s"></td>' for _ in range(n - played))
                after = f' <span class="muted">{tag}</span>' if tag else ""
            rows.append(f'<tr class="{"w" if winner_row else "l"}"><td class="pl">{r.esc(name(p))}{after}</td>{cells}</tr>')
    sub = f'<span class="prog">{progress_text(stage, done)}</span>' if done is not None else ""
    return (f'<div class="tennis"><table><colgroup>{cols}</colgroup><thead><tr><th class="tt" colspan="{n + 1}">{r.esc(title or f"{DRAW[draw]} · {STAGE_NAME[stage]}")}{sub}</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def event_html(event, new, progress=None):
    html = f"<h3>{r.esc(event['name'])}</h3>" + dates_line(new)
    for draw in DRAW:
        mine = [m for m in new if m["draw"] == draw]
        if not mine:
            continue
        for stage in reversed(ORDER):
            part = [m for m in mine if m["stage"] == stage]
            if part:
                html += stage_table(draw, stage, part, (progress or {}).get((draw, stage)))
        html += _list(seeds_out(mine) + comebacks(mine) + milestones(mine, event))
    return html


# ---- The tour finals: the ATP Finals and the WTA Finals ---------------------------------------------
# Eight players in two round-robin groups of four (6 matches a group), the top two of each into the semi-finals, then the final. ESPN gives the groups no names, so a group is found
# from who played whom and called A (the group of the best seed) and B.

TOUR_STAGES = {"Group Stage": "G", "Semifinal": "SF", "Final": "F"}
TOUR_NAME = {"G": "Group Stage", "SF": "Semi-finals", "F": "Final"}
TOUR_ORDER = ["G", "SF", "F"]


def finals_matches_of(event):
    """Every finished singles match of a tour-finals event (group stage, semi-finals, final) as plain data."""
    out = []
    for g in event["groupings"]:
        slug = g["grouping"]["slug"]
        if slug in DRAW:
            out += [m for m in (parse_match(c, slug, stages=TOUR_STAGES) for c in g["competitions"]) if m]
    return out


def finals_tour(event):
    return "ATP Finals" if re.search(r"\bATP Finals\b", event["name"]) else "WTA Finals"


def finals_groups(matches):
    """The round-robin groups from the group-stage matches: [{"name": 'Group A', "players": {id: name dict}, "matches": [...]}], A being the group of the best seed. Players who
    have met belong together (a group is a connected set of players); a group with fewer than four players seen so far is still shown as it stands."""
    games = [m for m in matches if m["stage"] == "G"]
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for m in games:
        parent[find(m["winner"]["id"])] = find(m["loser"]["id"])
    groups = {}
    for m in games:
        gr = groups.setdefault(find(m["winner"]["id"]), {"players": {}, "matches": []})
        gr["players"][m["winner"]["id"]], gr["players"][m["loser"]["id"]] = m["winner"], m["loser"]
        gr["matches"].append(m)
    best = lambda gr: min((p["seed"] for p in gr["players"].values() if p["seed"]), default=99)  # noqa: E731
    ordered = sorted(groups.values(), key=best)
    return [{"name": f"Group {'AB'[i] if i < 2 else i + 1}", **gr} for i, gr in enumerate(ordered)]


def standings(group):
    """[{"p", "played", "w", "l", "sw", "sl", "gw", "gl"}] best first: wins, then (a tie between two) the match between them, then the difference in sets, then in games. Retirements
    and walkovers count as the win and loss they are, with the sets as played."""
    rows = {pid: {"p": p, "played": 0, "w": 0, "l": 0, "sw": 0, "sl": 0, "gw": 0, "gl": 0} for pid, p in group["players"].items()}
    for m in group["matches"]:
        w, l = rows[m["winner"]["id"]], rows[m["loser"]["id"]]
        w["played"] += 1
        l["played"] += 1
        w["w"] += 1
        l["l"] += 1
        for s in m["sets"]:
            for side, other, mine, theirs in ((w, l, s["w"], s["l"]), (l, w, s["l"], s["w"])):
                side["gw"] += mine
                side["gl"] += theirs
                if mine > theirs:
                    side["sw"] += 1
                else:
                    side["sl"] += 1
    beat = {(m["winner"]["id"], m["loser"]["id"]) for m in group["matches"]}

    def key(x):
        tied = [y for y in rows.values() if y["w"] == x["w"]]
        h2h = 0
        if len(tied) == 2:
            other = next(y for y in tied if y is not x)
            h2h = 1 if (x["p"]["id"], other["p"]["id"]) in beat else 0
        return (-x["w"], -h2h, -(x["sw"] - x["sl"]), -(x["gw"] - x["gl"]), x["p"]["name"])
    return sorted(rows.values(), key=key)


def group_table(tour, group):
    """'ATP Finals · Group A': Player, P, W, L and sets won-lost for each of the four, in standing order. The top two (the semi-finalists) are marked once the group is complete."""
    rows = standings(group)
    done = all(x["played"] == 3 for x in rows) and len(rows) == 4
    body = ""
    for i, x in enumerate(rows):
        mark = ' <span class="muted">Q</span>' if done and i < 2 else ""
        body += f'<tr class="{"w" if done and i < 2 else "l"}"><td class="pl">{r.esc(name(x["p"]))}{mark}</td><td class="s">{x["played"]}</td><td class="s">{x["w"]}</td><td class="s">{x["l"]}</td><td class="s">{x["sw"]}-{x["sl"]}</td></tr>'
    played = sum(x["played"] for x in rows) // 2
    status = "complete: the top two go through" if done else f"{played}/6 played"
    title = f"{tour} · {group['name']}"
    return (f'<div class="tennis"><table><colgroup><col style="width:46%"><col style="width:12%"><col style="width:12%"><col style="width:12%"><col style="width:18%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="5">{r.esc(title)}<span class="prog">{status}</span></th></tr>'
            f'<tr><th></th><th class="s">P</th><th class="s">W</th><th class="s">L</th><th class="s">Sets</th></tr></thead><tbody>{body}</tbody></table></div>')


def finals_closing(event, matches):
    """'That's the 2025 ATP Finals. (2) J. Sinner wins the title, beating (1) C. Alcaraz 7-6 7-5.' once the final is played; '' before. The year is the event's."""
    final = next((m for m in matches if m["stage"] == "F" and m["status"] == "final"), None)
    if not final:
        return ""
    year = (event.get("date") or "")[:4]
    text = f"That's the {year} {finals_tour(event)}. {final['winner']['name']} wins the title, beating {final['loser']['name']} {score(final, tb=False)}."
    return f"<p>{r.esc(text)}</p>"


def finals_html(event, new, all_matches):
    """The ATP Finals or WTA Finals block for a morning: the new matches by stage (the latest first), with the group tables after any new group-stage match."""
    tour = finals_tour(event)
    html = f"<h3>{r.esc(tour)}</h3>" + dates_line(new)
    draw = "mens-singles" if tour == "ATP Finals" else "womens-singles"
    for stage in reversed(TOUR_ORDER):
        part = [m for m in new if m["stage"] == stage]
        if part:
            html += stage_table(draw, stage, part, title=f"{DRAW[draw]} · {TOUR_NAME[stage]}", sets=3)
    if any(m["stage"] == "G" for m in new):
        html += "".join(group_table(tour, g) for g in finals_groups(all_matches))
    return html


def pick_finals(matches, now, reported):
    """New tour-finals matches: not reported before, started no later than now and within the lookback; the final first, then the semi-finals, then the group stage."""
    new = [m for m in matches if m["id"] not in set(reported) and timedelta(0) <= now - m["date"] <= LOOKBACK]
    return sorted(new, key=lambda m: (-TOUR_ORDER.index(m["stage"]), m["date"]))


# ---- The whole block ------------------------------------------------------------------------------

def run(now, st, source, fetch_news=None):
    """{"html", "state", "stats", "slams"}. st: {"reported": [match ids], "seen_news": [links]}. A failing source never raises: tennis is
    left out and `failed` says so. "slams" lists each Slam running now with its furthest round, for the ordering rules (Checkpoint 13)."""
    reported, seen_news = list(st.get("reported", [])), list(st.get("seen_news", []))
    stats = {"slams": 0, "matches": 0, "shown": 0, "withdrawals": 0, "failed": 0, "calls": 0}
    html, slams, shown_matches = "", [], []
    try:
        events = source.slam_events(now)
    except Exception:
        events, stats["failed"] = [], 1
    for e in sorted(events, key=lambda e: e["date"]):
        stats["slams"] += 1
        reached = stage_reached(e, now)
        slams.append({"name": e["name"], "stage": reached, "major": reached in ("QF", "SF", "F")})
        matches = matches_of(e)
        stats["matches"] += len(matches)
        new = pick(matches, now, reported)
        if new:
            html += event_html(e, new, progress_of(matches, now))
            reported += [m["id"] for m in new]
            stats["shown"] += len(new)
            shown_matches += [(e["name"], m) for m in new]
    closed = list(st.get("closed", []))
    try:                                                 # the ATP Finals and the WTA Finals (D, 2026-11-04): a permanent part of the tennis coverage
        finals = source.finals_events(now) if hasattr(source, "finals_events") else []
    except Exception:
        finals, stats["failed"] = [], stats["failed"] + 1
    for e in sorted(finals, key=lambda e: e["date"]):
        matches = finals_matches_of(e)
        new = pick_finals(matches, now, reported)
        note = finals_closing(e, matches) if e["id"] not in closed else ""
        if new or note:
            html += (finals_html(e, new, matches) if new else f"<h3>{r.esc(finals_tour(e))}</h3>") + note
            reported += [m["id"] for m in new]
            stats["shown"] += len(new)
        if note:
            closed.append(e["id"])
        slams.append({"name": finals_tour(e), "stage": None, "major": False, "finals": True})
    if fetch_news:
        try:
            lines = withdrawals(fetch_news(), now, lambda: source.top10("atp") + source.top10("wta"), seen_news)
        except Exception:
            lines, stats["failed"] = [], stats["failed"] + 1
        if lines:
            html += "<h3>Grand Slam withdrawals</h3>" + _list([t for t, _ in lines])
            seen_news += [link for _, link in lines]
            stats["withdrawals"] = len(lines)
    stats["calls"] = getattr(source, "calls", 0)
    try:                                                 # for The Big Stuff: Slam matches from the quarter-finals on, and the promotion of the tennis block
        from kickoff import events
        story_events = events.tennis(slams, shown_matches)
    except Exception:
        story_events = []
    return {"html": html, "state": {"reported": reported[-800:], "seen_news": seen_news[-100:], "closed": closed[-20:]}, "stats": stats, "slams": slams, "events": story_events,
            "young_in": {"tennis": [m for _, m in shown_matches]}}
