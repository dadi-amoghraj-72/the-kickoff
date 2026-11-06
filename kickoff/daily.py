"""The daily run: every sport built so far, one after another, into one edition.

  load the saved state  ->  run each sport behind its own guard  ->  put the sections in order  ->  write the edition and the state

A sport that raises costs its own section only: the edition shows a short "No data this morning" line for it and its saved state stays exactly as it
was, so tomorrow it picks up where it left off. Nothing is sent or published here: this module builds the edition dict and the new state, and the script
(scripts/daily.py) writes the files; the GitHub workflow publishes and pings.

Each sport is an adapter: (state id list, section id, title, function(now, day, st) -> {"sections", "state", "headlines", "problems"}).
Adapters take the real data sources through `real_adapters()`; tests pass fake ones."""
import copy
import os
from datetime import datetime, timezone

from kickoff import around, awards, bigstuff, budget, ontoday, young_sports, youngguns, cricket, cricketcache, f1, football, football_season, ipl, mlb, nba, nfl, order, preview, render, tennis
from kickoff import notes, settings
from kickoff import state as state_files
from kickoff.sources import espn, espn_cricket, espn_mlb, espn_nba, espn_nfl, espn_tennis, feeds, jolpica, wikipedia
from kickoff.sources import cricket as cricket_source
from kickoff.sources import other_sports

FOOTBALL_STATE = ["tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs", "top30", "seasons"]
STATE_NAMES = FOOTBALL_STATE + ["cricket", "f1", "tennis", "nfl", "nba", "mlb", "youngguns", "around"]


def load_state(directory=None):
    return {n: state_files.load(n, directory=directory) for n in STATE_NAMES}


def save_state(new, old, directory=None):
    """Write only the state files that changed. Returns their names."""
    changed = [n for n in STATE_NAMES if new.get(n) != old.get(n)]
    for n in changed:
        state_files.save(n, new[n], directory)
    return changed


# ---- The sports ---------------------------------------------------------------------------------

def _simple(section_id, title, call, state_id):
    """An adapter for a sport whose run returns {"html", "state"}: its state is the whole state file."""
    def go(now, day, st):
        got = call(now, day, copy.deepcopy(st.get(state_id) or {}))
        return {"sections": [{"id": section_id, "title": title, "html": got["html"]}] if got.get("html") else [], "state": {state_id: got["state"]},
                "stats": got.get("stats", {}), "events": got.get("events", []), "young_in": got.get("young_in", {})}
    return (section_id, title, go)


def _with_extras(call, league, sport, name, client=None):
    """Wrap a sport's run (now, day, state) so its section also carries, above its games: the "season is coming" note in the week before the season (kickoff.preview,
    Claude writes it, once a season) and the awards table on a day something new was announced (kickoff.awards). Their states live inside the sport's own state under
    'awards' and 'previewed' (the sport's run does not know them, so they are put back here). Neither can cost the sport its games: any failure leaves them out."""
    def go(now, day, st):
        got = call(now, day, st)
        old_awards, old_prev = copy.deepcopy((st or {}).get("awards")), list((st or {}).get("previewed") or [])
        html_a, new_awards = "", old_awards
        html_p, new_prev, cost = "", old_prev, 0.0
        try:
            html_a, new_awards = awards.block(league, sport, f"{name} Awards", day, old_awards)
        except Exception:
            pass
        try:
            html_p, new_prev, cost = preview.block(league, sport, name, awards.season_of(league, day), day, old_prev, client)
        except Exception:
            pass
        out = dict(got)
        out["state"] = {**got["state"], **({"awards": new_awards} if new_awards is not None else {}), "previewed": new_prev}
        out["html"] = html_p + html_a + (got.get("html") or "")
        out["stats"] = {**got.get("stats", {}), "preview_cost": round(cost, 5)}
        return out
    return go


def backup_matches(env):
    """CricketData's match list (the backup: ESPN's feed is the main source), or an empty list when there is no key."""
    return cricket_source.get_matches if env.get("CRICKET_DATA_API_KEY") else (lambda: ([], 0))


def real_adapters(client=None, env=None):
    """The seven sports with their real sources, football first. client: an Anthropic client or None (no Claude, plain notes). Cricket needs its API key
    (CRICKET_DATA_API_KEY) and is reported as a problem, not an error, when it is missing."""
    env = os.environ if env is None else env

    def football_go(now, day, st):
        out = football.run(day, client=client, st={n: st.get(n) or {} for n in FOOTBALL_STATE}, now=now, seasonal=football_season.build)
        return {"sections": out["sections"], "state": {n: out["new_state"][n] for n in FOOTBALL_STATE if n in out["new_state"]},
                "headlines": out["headlines"], "problems": out["problems"], "stats": {**out["stats"], "claude_cost": out["ledger"].total()},
                "events": out.get("events", []), "news": out.get("news", []), "injuries": out.get("injuries", []), "young_in": out.get("young_in", {})}

    def cricket_go(now, day, st):
        get_matches = backup_matches(env)
        espn_src = espn_cricket.Source()
        card, table, series = cricketcache.getters(cricketcache.fresh(cricketcache.load(), now), espn_src)    # the Mac's cache first (GitHub cannot read ESPN's pages)
        old = copy.deepcopy(st.get("cricket") or {})
        wiki = wikipedia.Source()
        got = cricket.run(now, espn.window_start(day), old, get_matches, cricket_source.get_scorecard, cricket_source.scorecards_affordable,
                          espn_card=card, espn_table=table, espn_series=series, espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed()),
                          extras_fn=ipl.extras_for(day.year, wiki) if day.month in (3, 4, 5, 6) else None)
        new = dict(got["state"])
        html_awards = ""
        if day.month in (4, 5, 6):                                  # the IPL's end-of-season awards, the first morning the season page has them
            try:
                prev = old.get("ipl_awards") or {"season": day.year, "seen": {}, "rows": [], "names": {}}
                html_awards, new["ipl_awards"] = ipl.awards_block(day.year, prev, wiki)
            except Exception:
                new["ipl_awards"] = old.get("ipl_awards")
        got = {**got, "html": html_awards + got["html"]}
        new["cards"] = dict(list({**old.get("cards", {}), **new.get("cards", {})}.items())[-60:])   # bought scorecards are never paid for twice
        return {"sections": [{"id": "cricket", "title": "Cricket", "html": got["html"]}] if got["html"] else [], "state": {"cricket": new},
                "stats": {**got["stats"], "calls_used_today": got["used"]}, "events": got.get("events", [])}

    def around_go(now, day, st):
        got = around.run(now, copy.deepcopy(st.get("around") or {}), other_sports.Source(), client)
        return {**got, "events": got.get("events", [])}

    return [
        ("football", "Football", football_go),
        ("cricket", "Cricket", cricket_go),
        _simple("f1", "F1", lambda now, day, s: f1.run(now, espn.window_start(day), s, jolpica.Api()), "f1"),
        _simple("tennis", "Tennis", lambda now, day, s: tennis.run(now, s, espn_tennis.Source(), fetch_news=lambda: feeds.fetch_all(tennis.FEEDS)), "tennis"),
        _simple("nfl", "NFL", _with_extras(lambda now, day, s: nfl.run(now, day, s, espn_nfl.Source()), "nfl", "football", "NFL", client), "nfl"),
        _simple("nba", "NBA", _with_extras(lambda now, day, s: nba.run(now, day, s, espn_nba.Source()), "nba", "basketball", "NBA", client), "nba"),
        _simple("mlb", "MLB", _with_extras(lambda now, day, s: mlb.run(now, day, s, espn_mlb.Source()), "mlb", "baseball", "MLB", client), "mlb"),
        ("around", "Other Sports", around_go),
    ]


def real_today(now, day, st):
    """On Today and Games to Watch from the real sources: {"html", "failed"} (see kickoff.ontoday). The teams with a tracked NBA player come from the NBA state."""
    from kickoff import fixtures
    tracked_teams = set(dict(nba.TEAMS, **((st.get("nba") or {}).get("teams") or {})).values())        # every team with a tracked player (for "stars facing each other")
    src = fixtures.Sources(espn_nba.Source(), espn_nfl.Source(), espn_mlb.Source(), espn_cricket.Feed(), jolpica.Api(), espn_tennis.Source(), other_sports.Source())
    return ontoday.build(src, now, day, set(nba.FIRST), tracked_teams)


# ---- The edition --------------------------------------------------------------------------------

def build_edition(now, day, st, adapters, mode="normal", today=None, client=None, age_lookup=None):
    """Run every adapter. Returns {"edition", "state", "problems", "failed", "stats"}.
    edition: the dict the site renders; state: the new state for every sport (a failed sport keeps its old state); failed: the adapters that raised."""
    content, new_state, problems, failed, headlines, stats = {}, copy.deepcopy(st), [], [], [], {}
    events, news, injuries, young_in = [], [], [], {}
    for sid, title, go in adapters:
        try:
            got = go(now, day, st)
        except Exception as e:                                   # one sport down never stops the others
            failed.append(sid)
            problems.append(f"{sid} ({type(e).__name__})")
            content[sid] = {"title": title, "html": render.no_data(title)}
            continue
        for s in got.get("sections", []):
            if s.get("html"):
                content[s["id"]] = {"title": s["title"], "html": s["html"]}
        new_state.update(got.get("state", {}))
        headlines += got.get("headlines", [])
        events += got.get("events", [])
        news += got.get("news", [])
        injuries += got.get("injuries", [])
        for k_, v_ in (got.get("young_in") or {}).items():
            young_in.setdefault(k_, []).extend(v_)
        problems += got.get("problems", [])
        stats[sid] = got.get("stats", {})
    try:                                                         # Young Guns: rookies and under-21s who did something notable (kickoff/youngguns.py)
        yst = copy.deepcopy(st.get("youngguns") or {})
        found = []
        for sport_, fn_ in (("nba", young_sports.nba), ("nfl", young_sports.nfl), ("soccer", young_sports.soccer), ("tennis", young_sports.tennis)):
            if young_in.get(sport_):
                found += fn_(young_in[sport_], yst, day, age_lookup)
        for rows_, race_ in young_in.get("f1", []):
            found += young_sports.f1(rows_, race_, day)
        yg = youngguns.build(found, yst, day, client)
        yg_state = {"watch": yg["state"].get("watch", {}), "ages": dict(list((yst.get("ages") or {}).items())[-3000:])}
        new_state["youngguns"] = yg_state
        if yg["html"]:
            content["young-guns"] = {"title": "Young Guns", "html": yg["html"]}
        stats["youngguns"] = {"candidates": len(found), "why": yg["why"], "lines": yg["lines"], "plain": yg["plain"], "claude_usage": yg["usage"]}
    except Exception as e:
        problems.append(f"young guns ({type(e).__name__})")
    today_fixtures, ping_today = [], []
    if today:                                                    # On Today (and on Mondays Games to Watch): what is still to come, in Singapore time
        try:
            got_today = today(now, day, st)
            today_fixtures = got_today.get("today") or []
            if got_today["html"]:
                content["on-today"] = {"title": "On Today", "html": got_today["html"]}
            problems += [f"on today: {s_}" for s_ in got_today["failed"]]
        except Exception as e:
            problems.append(f"on today ({type(e).__name__})")
    lead, promoted = None, ()
    try:                                                         # The Big Stuff and the section order: plain rules over the day's stories (bigstuff.py, importance.py)
        big = bigstuff.build(events, news, injuries, day.weekday())
        if big["html"]:
            content["big-stuff"] = {"title": "The Big Stuff", "html": big["html"]}
        for p_, text in big["majors"].items():
            if p_ in content:
                content[p_]["headline"] = text
        if big["headlines"]:
            headlines = big["headlines"]
        if big.get("quiet") and today_fixtures:                  # a quiet morning: the ping also says what is on today (D, 2026-11-05); a busy one stays short
            ping_today = [ontoday.plain_line(f_) for f_ in ontoday.pick_today(today_fixtures, 3)]
        lead, promoted = big["lead"], big["promoted"]
        stats["bigstuff"] = {"stories": len(events), "shown": [s["why"] for s in big["selected"]], "lead": lead, "promoted": promoted, "stars": [p_["text"] for p_ in big["stars"]]}
    except Exception as e:
        problems.append(f"big stuff ({type(e).__name__})")
    try:
        record_extra_costs(new_state, stats, day)
    except Exception as e:
        problems.append(f"costs ({type(e).__name__})")
    sections = order.assemble(content, lead, promoted)
    if not sections:
        sections = [{"id": "quiet", "title": "A quiet morning", "html": "<p>Nothing finished overnight in the sports we follow.</p>"}]
    edition = {"date": day.isoformat(), "dummy": False, "headlines": list(dict.fromkeys(headlines))[:3], **({"ping_today": ping_today} if ping_today else {}), "sections": sections,
               "built": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "claude": mode}
    return {"edition": edition, "state": new_state, "problems": problems, "failed": failed, "stats": stats}


def extra_costs(stats):
    """(dollars, calls) of the Claude calls made outside the football run: the season previews, Young Guns phrasing, the Around feed sorting and Interesting Stories."""
    total, calls = 0.0, 0
    for s in stats.values():
        if isinstance(s, dict) and s.get("preview_cost"):
            total += float(s["preview_cost"])
            calls += 1
    for sid, model in (("youngguns", None), ("around", settings.NEWS_MODEL)):
        usage = (stats.get(sid) or {}).get("claude_usage")
        if usage and (usage.get("input") or usage.get("output")):
            total += notes.cost(usage, model)
            calls += 1
    return total, calls


def record_extra_costs(new_state, stats, day):
    """Adds those costs to the month's total in state["costs"] (where the football run already put its own), so the budget guard sees every Claude call."""
    spent, calls = extra_costs(stats)
    if not calls:
        return
    month = day.strftime("%Y-%m")
    c = new_state.setdefault("costs", {}).setdefault(month, {"spent": 0.0, "calls": 0, "days": {}})
    c["spent"] = round(c.get("spent", 0.0) + spent, 5)
    c["calls"] = c.get("calls", 0) + calls
    today_ = c.setdefault("days", {}).setdefault(day.isoformat(), {"spent": 0.0, "calls": 0})
    today_["spent"] = round(today_.get("spent", 0.0) + spent, 5)
    today_["calls"] = today_.get("calls", 0) + calls


def make_client(b, env, use_claude):
    """The Anthropic client, or None when Claude is not wanted, the key is missing or the budget is used up (plain notes written by code)."""
    if not use_claude or b["mode"] == "plain" or not env.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def run_day(now, day, st, make_adapters, use_claude=False, env=None, today=None):
    """The budget guard, then build_edition. make_adapters(client) -> the adapter list (real_adapters for a real run). Returns build_edition's dict plus
    "budget" (see budget.status) and "client_used"."""
    env = os.environ if env is None else env
    b = budget.status(st.get("costs"), day)
    client = make_client(b, env, use_claude)
    with budget.models(b["mode"]):
        out = build_edition(now, day, st, make_adapters(client), b["mode"] if client else "plain" if use_claude else "off", today, client)
    out["budget"], out["client_used"] = b, client is not None
    return out


def edition_exists(day, data_dir=None):
    return ((data_dir or render.DATA_DIR) / f"{day.isoformat()}.json").exists()
