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

from kickoff import awards, budget, cricket, cricketcache, f1, football, mlb, nba, nfl, order, preview, render, tennis
from kickoff import state as state_files
from kickoff.sources import espn, espn_cricket, espn_mlb, espn_nba, espn_nfl, espn_tennis, feeds, jolpica
from kickoff.sources import cricket as cricket_source

FOOTBALL_STATE = ["tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs", "top30"]
STATE_NAMES = FOOTBALL_STATE + ["cricket", "f1", "tennis", "nfl", "nba", "mlb"]


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
                "stats": got.get("stats", {})}
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
        out = football.run(day, client=client, st={n: st.get(n) or {} for n in FOOTBALL_STATE}, now=now)
        return {"sections": out["sections"], "state": {n: out["new_state"][n] for n in FOOTBALL_STATE if n in out["new_state"]},
                "headlines": out["headlines"], "problems": out["problems"], "stats": {**out["stats"], "claude_cost": out["ledger"].total()}}

    def cricket_go(now, day, st):
        get_matches = backup_matches(env)
        espn_src = espn_cricket.Source()
        card, table, series = cricketcache.getters(cricketcache.fresh(cricketcache.load(), now), espn_src)    # the Mac's cache first (GitHub cannot read ESPN's pages)
        old = copy.deepcopy(st.get("cricket") or {})
        got = cricket.run(now, espn.window_start(day), old, get_matches, cricket_source.get_scorecard, cricket_source.scorecards_affordable,
                          espn_card=card, espn_table=table, espn_series=series, espn_extra=lambda ms: cricket.espn_matches(espn_cricket.Feed()))
        new = dict(got["state"])
        new["cards"] = dict(list({**old.get("cards", {}), **new.get("cards", {})}.items())[-60:])   # bought scorecards are never paid for twice
        return {"sections": [{"id": "cricket", "title": "Cricket", "html": got["html"]}] if got["html"] else [], "state": {"cricket": new},
                "stats": {**got["stats"], "calls_used_today": got["used"]}}

    return [
        ("football", "Football", football_go),
        ("cricket", "Cricket", cricket_go),
        _simple("f1", "F1", lambda now, day, s: f1.run(now, espn.window_start(day), s, jolpica.Api()), "f1"),
        _simple("tennis", "Tennis", lambda now, day, s: tennis.run(now, s, espn_tennis.Source(), fetch_news=lambda: feeds.fetch_all(tennis.FEEDS)), "tennis"),
        _simple("nfl", "NFL", _with_extras(lambda now, day, s: nfl.run(now, day, s, espn_nfl.Source()), "nfl", "football", "NFL", client), "nfl"),
        _simple("nba", "NBA", _with_extras(lambda now, day, s: nba.run(now, day, s, espn_nba.Source()), "nba", "basketball", "NBA", client), "nba"),
        _simple("mlb", "MLB", lambda now, day, s: mlb.run(now, day, s, espn_mlb.Source()), "mlb"),
    ]


# ---- The edition --------------------------------------------------------------------------------

def build_edition(now, day, st, adapters, mode="normal"):
    """Run every adapter. Returns {"edition", "state", "problems", "failed", "stats"}.
    edition: the dict the site renders; state: the new state for every sport (a failed sport keeps its old state); failed: the adapters that raised."""
    content, new_state, problems, failed, headlines, stats = {}, copy.deepcopy(st), [], [], [], {}
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
        problems += got.get("problems", [])
        stats[sid] = got.get("stats", {})
    sections = order.assemble(content)
    if not sections:
        sections = [{"id": "quiet", "title": "A quiet morning", "html": "<p>Nothing finished overnight in the sports we follow.</p>"}]
    edition = {"date": day.isoformat(), "dummy": False, "headlines": list(dict.fromkeys(headlines))[:3], "sections": sections,
               "built": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "claude": mode}
    return {"edition": edition, "state": new_state, "problems": problems, "failed": failed, "stats": stats}


def make_client(b, env, use_claude):
    """The Anthropic client, or None when Claude is not wanted, the key is missing or the budget is used up (plain notes written by code)."""
    if not use_claude or b["mode"] == "plain" or not env.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic
    return anthropic.Anthropic()


def run_day(now, day, st, make_adapters, use_claude=False, env=None):
    """The budget guard, then build_edition. make_adapters(client) -> the adapter list (real_adapters for a real run). Returns build_edition's dict plus
    "budget" (see budget.status) and "client_used"."""
    env = os.environ if env is None else env
    b = budget.status(st.get("costs"), day)
    client = make_client(b, env, use_claude)
    with budget.models(b["mode"]):
        out = build_edition(now, day, st, make_adapters(client), b["mode"] if client else "plain" if use_claude else "off")
    out["budget"], out["client_used"] = b, client is not None
    return out


def edition_exists(day, data_dir=None):
    return ((data_dir or render.DATA_DIR) / f"{day.isoformat()}.json").exists()
