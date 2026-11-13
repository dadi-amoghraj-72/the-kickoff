"""Assembles the Arsenal and Football sections for one edition from everything built so far.

Every source is called through a guard: if it fails, that block is skipped and the rest of the edition stands.
Claude is optional: with client=None every note and overview is the plain version written by code (free).
State is passed in and handed back, never written here, so a test run can't disturb the real state files."""
import copy
import re
from datetime import datetime, timezone

from kickoff import champions, events, facup, focus, fplcorner, headlines, injuries, international, leaders, news, notes, overview, performers, roundup, scoreboard, settings, tables
from kickoff import render as r
from kickoff.http import safe
from kickoff.sources import espn, feeds, fpl

LEAGUE_ORDER = ["eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "tur.1"]
COVERED = set(LEAGUE_ORDER) | {espn.CHAMPIONS_LEAGUE, espn.FA_CUP, espn.WSL}   # the competitions whose results the football run reads; an Arsenal game anywhere else comes from the Arsenal section (D, 2026-11-13: Arsenal Women 1-1 Barcelona was missing)


class Ledger:
    """Every Claude call, with its tokens and cost, so a month of running shows what each section really costs."""

    def __init__(self):
        self.rows = []

    def add(self, label, model, usage):
        if usage and (usage["input"] or usage["output"]):
            self.rows.append({"label": label, "model": model, "input": usage["input"], "output": usage["output"],
                              "cost": round(notes.cost(usage, model), 5)})

    def total(self):
        return round(sum(x["cost"] for x in self.rows), 5)

    def lines(self):
        return [f"  {x['label']:34} {x['model']:19} {x['input']:>6} in {x['output']:>5} out  ${x['cost']:.4f}" for x in self.rows]


FORM_WORDS = re.compile(r"\b(climbed|dropped|rose|fell|moved|table|points?|last five|unbeaten|undefeated|winless|league phase|ranked|position|run of)\b", re.I)
GOAL_WORDS = re.compile(r"\b(minute|scored|scorer|assist\w*|goal|equali[sz]\w*|pulled one back|penalty|opener|winner|header|brace|hat-trick)\b", re.I)


def short_form(text):
    """'3 won, 2 drawn, 0 lost' (or '3 wins, 2 draws and 0 defeats') becomes '3W 2D 0L': the record as it is written everywhere else on the page (D, 2026-11-05)."""
    return re.sub(r"\b(\d+) (?:won|wins?),? (\d+) (?:drawn|draws?),? (?:and )?(\d+) (?:lost|losses|defeats?)\b", r"\1W \2D \3L", text, flags=re.I)


def split_note(note, goals, home, away):
    """A match note as short paragraphs (D, 2026-11-05, his red lines on the Arsenal note): the first side's goals, then the other side's goals, then the table and form. Whatever
    Claude wrote, code does the splitting: a goal sentence names its scorer (from the match's own goals) and so its side; a new paragraph starts when that side changes and before
    the first table-or-form sentence. A note with one sentence, or no goals to read, stays one paragraph."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", note.strip())
    if len(sentences) < 3:
        return [note.strip()]
    side_of = {}
    for g in goals:
        for who in (g.get("player"), g.get("assist")):
            if who:
                side_of.setdefault(who.split()[-1].lower(), g["side"] if who == g.get("player") else None)
                side_of.setdefault(who.lower(), g["side"] if who == g.get("player") else None)
    paras, last_side, seen_form = [[]], None, False
    for s in sentences:
        is_form = bool(FORM_WORDS.search(s)) and not re.search(r"\bminute\b", s, re.I)
        side = next((side_of[w] for w in re.findall(r"[\w\u00c0-\u024f'-]+", s.lower()) if side_of.get(w)), None) if GOAL_WORDS.search(s) and not is_form else None
        if (is_form and not seen_form and paras[-1]) or (side and last_side and side != last_side and paras[-1] and not seen_form):
            paras.append([])
        seen_form = seen_form or is_form
        last_side = side or last_side
        paras[-1].append(s)
    return [" ".join(p) for p in paras if p]


def _paragraphs(written, match_by_id):
    out = ""
    for mid, w in written.items():
        m = match_by_id[mid]
        teams = (m["home"]["name"], m["away"]["name"], m["home"]["short"], m["away"]["short"])
        people = [x for g in m.get("goals", []) for x in (g.get("player"), g.get("assist"))]
        for para in split_note(short_form(w["note"]), m.get("goals", []), m["home"]["name"], m["away"]["name"]):
            out += f"<p>{r.dash(r.bold_names(para, teams, people))}</p>"
    return out


def run(day, client=None, st=None, now=None, demo=False, seasonal=None):
    """Build both sections. demo=True makes the FPL corner show everything it can, whatever the deadline. st: {"tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs"} (copied, not changed).
    seasonal: kickoff.football_season.build or None: the Premier League's preview, closing note and awards, and the FA Cup and Champions League closing notes.
    Returns {"sections", "headlines", "new_state", "ledger", "problems", "stats"}."""
    now = now or datetime.now(timezone.utc)
    st = copy.deepcopy(st or {})
    new = copy.deepcopy(st)
    ledger, problems = Ledger(), []

    def guard(name, fn, *a, **k):
        out = safe(name, fn, *a, **k)
        if out is None:
            problems.append(name)
        return out

    leagues = dict(espn.LEAGUES)
    rows = {lg: guard(f"{n} table", espn.get_table, lg) for lg, n in leagues.items()}
    rows[espn.WSL] = guard("WSL table", espn.get_table, espn.WSL)
    rows[espn.CHAMPIONS_LEAGUE] = guard("Champions League table", espn.get_table, espn.CHAMPIONS_LEAGUE)
    results = {lg: guard(f"{n} results", espn.recent_results, lg, day) for lg, n in leagues.items()}
    cl_matches = guard("Champions League results", champions.results, day) or []
    saved_tables = st.get("tables", {})
    previous = {lg: {x[0]: x[1] for x in saved_tables.get(lg, {}).get("rows", [])} for lg in rows}
    overviews = {}
    seen_players = {}

    def cached_players(league, event_id):                # one request per match, shared by the best performers and Young Guns
        if (league, event_id) not in seen_players:
            seen_players[(league, event_id)] = espn.get_player_stats(league, event_id)
        return seen_players[(league, event_id)]

    perf_lists = []                                      # the best performers of the Premier League and the Champions League, for the Performance of the Day

    # Clean sheets: add today's shutouts to the running count (each match is counted once, ever)
    cs = new.get("clean_sheets", {})
    for lg in leagues:
        if results[lg]:
            cs = leaders.count_clean_sheets(cs, lg, results[lg], lambda m, lg=lg: espn.get_starting_keepers(lg, m["id"]))
    new["clean_sheets"] = cs

    def write_notes_for(label, facts, match_by_id, claude_only=False):
        """Paragraphs of notes. claude_only=True (league blocks) shows only notes Claude wrote and that passed the
        checks: the scoreboard already shows every fact a plain note would repeat. Arsenal keeps its plain fallback."""
        if not facts:
            return ""
        if client:
            written, usage = notes.write_notes(client, facts)
            ledger.add(label, settings.CLAUDE_MODEL, usage)
        else:
            written = {f["id"]: {"note": notes.plain_note(f), "source": "plain", "problems": []} for f in facts}
        if claude_only:
            written = {k: v for k, v in written.items() if v["source"] == "claude"}
        return _paragraphs(written, match_by_id)

    def round_up(label, competition, matches, league_slug, table_rows, period="day"):
        """The round-up box. Odds are fetched here; the numbers and the game of the day come from code, not Claude."""
        odds = overview.collect_odds(league_slug, matches)
        facts = overview.matchday_facts(competition, matches, odds, table_rows)
        overviews[competition] = facts
        size = max(1, len(table_rows) // 2) if table_rows else len(matches)
        info = None
        if table_rows and (league_slug != espn.CHAMPIONS_LEAGUE or champions.in_league_phase(matches)):
            info = roundup.round_info(table_rows, "Matchday" if league_slug == espn.CHAMPIONS_LEAGUE else "Game week",
                                      8 if league_slug == espn.CHAMPIONS_LEAGUE else None)
        return roundup.html(facts, size, period, info)

    # ---- The Football section ----
    fa_cup = guard("FA Cup results", espn.recent_results, espn.FA_CUP, day) or []   # the FA Cup: its own block, after the leagues
    season_out = {"pl": "", "fa": "", "cl": ""}
    if seasonal:                                         # the Premier League's season notes, and the FA Cup and Champions League closing notes
        got = guard("season notes", seasonal, day, now, rows["eng.1"], fa_cup, cl_matches, st.get("seasons"), client)
        if got:
            season_out = got
            new["seasons"] = got["state"]
    football, quiet = (f"<h3>Premier League season</h3>{season_out['pl']}" if season_out["pl"] else ""), []
    for lg in LEAGUE_ORDER:
        name, res, tbl = leagues[lg], results[lg] or [], rows[lg]
        parts = ""
        if res:
            parts += guard(f"{name} round-up", round_up, name, name, res, lg, tbl) or ""
            parts += scoreboard.scores_html(res)
            if lg == "eng.1":                    # the best performers of the day: the Premier League and the Champions League only
                best_pl = guard("Premier League performers", performers.best, lg, res, cached_players) or []
                perf_lists.append(best_pl)
                parts += performers.html(best_pl)
        chosen = notes.select(lg, res)
        if chosen:
            facts = [notes.match_facts(m, t, tbl, previous[lg], name) for m, t in chosen]
            parts += write_notes_for(f"{name} notes", facts, {m["id"]: m for m, _ in chosen}, claude_only=True)
        if tbl:
            html, entry = tables.one("Table", tbl, saved_tables.get(lg), day,
                                     leaders_fn=lambda lg=lg, tbl=tbl: guard(f"{leagues[lg]} leaders", leaders.league_block, lg,
                                                                              espn.season_year(day), tbl, cs))
            if entry or res or parts:
                parts += html
            else:
                quiet.append(name)               # no games and the table has not changed: one line for all such leagues, at the end
            if entry:
                new.setdefault("tables", {})[lg] = entry
        if parts:
            football += f"<h3>{r.esc(name)}</h3>{parts}"
    if fa_cup:
        pyr = facup.pyramid(lambda lg: rows["eng.1"] if lg == "eng.1" and rows.get("eng.1") else espn.get_table(lg))
        fa_cup = [m for m in fa_cup if facup.matters(m, pyr)]          # only the ties that matter (D, 2026-11-08); the stories below use this list too
    if fa_cup:
        top_ids = {k for k, v in pyr.items() if v <= 44}
        football += facup.html(fa_cup, top_ids) + season_out["fa"]
        overviews["FA Cup"] = overview.matchday_facts("FA Cup", fa_cup, {}, None)      # so its big results can make the headlines
    wsl_res = guard("Women's Super League results", espn.recent_results, espn.WSL, day) or []
    wsl_parts = ""
    if wsl_res:
        wsl_parts += guard("Women's Super League round-up", round_up, "Women's Super League", "Women's Super League", wsl_res, espn.WSL,
                           rows[espn.WSL]) or ""
        wsl_parts += scoreboard.scores_html(wsl_res)
    if rows[espn.WSL]:
        html, entry = tables.one("Table", rows[espn.WSL], saved_tables.get(espn.WSL), day)
        if entry or wsl_res or wsl_parts:
            wsl_parts += html
        else:
            quiet.append("Women's Super League")
        if entry:
            new.setdefault("tables", {})[espn.WSL] = entry
    if wsl_parts:
        football += f"<h3>Women's Super League</h3>{wsl_parts}"
    if cl_matches:
        cl_box = guard("Champions League round-up", round_up, "Champions League", champions.COMPETITION, cl_matches,
                       espn.CHAMPIONS_LEAGUE, rows[espn.CHAMPIONS_LEAGUE], "night") or ""
        cl_rows = rows[espn.CHAMPIONS_LEAGUE]
        best_cl = guard("Champions League performers", performers.best, espn.CHAMPIONS_LEAGUE, cl_matches, cached_players) or []
        perf_lists.append(best_cl)
        football += champions.section_html(cl_matches, cl_rows, None, cl_box, tables.before_of(saved_tables.get(espn.CHAMPIONS_LEAGUE)),
                                           legs_fn=espn.get_tie_legs, goals_fn=lambda leg_id: espn.get_match_details(leg_id, espn.CHAMPIONS_LEAGUE),
                                           performers=performers.html(best_cl))
        football += season_out["cl"]
        if cl_rows and champions.in_league_phase(cl_matches):   # remembered so the next league-phase table can show who moved
            new.setdefault("tables", {})[espn.CHAMPIONS_LEAGUE] = {"published": day.isoformat(), "rows": tables.signature(cl_rows)}
    if quiet:
        football += '<h3>Other football leagues</h3><p class="muted">No new games: ' + r.esc(r.join_names(quiet)) + ".</p>"

    # ---- International football: only around a break, only competitive games ----
    intl = guard("international football", international.run, day, now, client, st.get("top30"))
    if intl:
        football += intl["html"]
        ledger.add("Nations League lines", settings.NEWS_MODEL, intl["usage"])
        problems += intl["problems"]
        if intl["top30"]:
            new["top30"] = intl["top30"]

    # ---- Injuries (Premier League, official FPL status) ----
    boot = guard("FPL data", fpl.get_bootstrap)
    fixtures = guard("FPL fixtures", fpl.get_fixtures) if boot else None
    players = fpl.players(boot, fixtures) if boot else []
    inj_items = []
    if players:
        inj_items, new["injuries"] = injuries.detect(players, st.get("injuries", {}), day)
    football += injuries.html(inj_items, exclude_team="ARS")

    # ---- News ----
    shown_news = []
    items = guard("news feeds", feeds.fetch_all) or []
    seen = dict(st.get("news_seen", {}))
    all_rows = {lg: v for lg, v in rows.items() if v}
    cands = news.candidates(items, news.club_aliases(all_rows), now, seen_links=set(seen))
    if cands and client:
        verdicts, usage = news.classify(client, cands)
        ledger.add("news classification", settings.NEWS_MODEL, usage)
        shown_news = news.apply_rules(cands, verdicts)
    elif cands:                                          # no Claude (off, no key, budget used up): at least the manager stories, as the source's headline
        shown_news = news.plain_managerial(cands)
    shown_links = {i["link"] for i in shown_news}
    for c in cands:
        if client or c["link"] in shown_links:           # an item nobody has judged is not "seen": a run with Claude may still want it (36 hours)
            seen[c["link"]] = now.isoformat()
    cutoff = (now.timestamp() - 14 * 86400)
    new["news_seen"] = {k: v for k, v in seen.items() if datetime.fromisoformat(v).timestamp() >= cutoff}
    football += news.html(shown_news, "football", "Transfers And Managers")

    # ---- FPL corner ----
    if boot:
        event = fplcorner.current_event(boot)
        eid, did = settings.FPL_CLASSIC_TEAM_ID, settings.FPL_DRAFT_LEAGUE_ID
        entry = guard("FPL classic team", fpl.get_entry, eid)
        picks = guard("FPL picks", fpl.get_picks, eid, event["id"])
        history = guard("FPL history", fpl.get_history, eid)
        live = guard("FPL live points", fpl.get_live, event["id"])
        draft = guard("FPL draft league", fpl.get_draft_league, did)
        def trend():
            """Points and minutes for the last three finished gameweeks (fetched only when the hints are due)."""
            done = sorted(e["id"] for e in boot["events"] if e["finished"])[-3:]
            got = {gw: guard(f"FPL gameweek {gw}", fpl.get_live_stats, gw) for gw in done}
            return {gw: v for gw, v in got.items() if v}

        html, new["fpl"] = fplcorner.build(boot, players, entry, picks, history, live, draft, settings.FPL_DRAFT_ENTRY_ID,
                                           st.get("fpl", {}), now, trend_fn=trend, demo=demo)
        football += html

    # ---- The Arsenal section ----
    arsenal, headline_result, arsenal_extra = "", None, []
    for club, tier in ((focus.ARSENAL, "arsenal"), (focus.ARSENAL_WOMEN, "women")):
        block = guard(club["name"], focus.build, club, day, all_rows, previous, now, tier)
        if not block:
            continue
        arsenal_extra += [(g.get("competition") or "", [g]) for g in block.get("games") or [] if g.get("league") not in COVERED]   # the Women's Champions League, the League Cup
        match_by_id = {f["id"]: {"home": {"name": f["home"], "short": f["home"]}, "away": {"name": f["away"], "short": f["away"]},
                                 "goals": [{"player": g["scorer"], "assist": g.get("assist"), "side": "home" if g["for"] == f["home"] else "away"} for g in f["goals"]]}
                       for f in block["facts"]}
        body = write_notes_for(f"{club['name']} note", block["facts"], match_by_id)
        if body:
            body = focus.score_lines_html(block["facts"]) + body          # the score first, then the story (D, 2026-11-13)
        if block["facts"] and club is focus.ARSENAL:
            f = block["facts"][0]
            headline_result = f"{f['home']} {f['final_score'].replace('-', '–')} {f['away']}"
        if body:
            body += focus.next_up_html(block["next"])
        if club is focus.ARSENAL_WOMEN and body:
            body = f"<h3>Arsenal Women</h3>{body}"
        arsenal += body
    ars_inj = injuries.html([i for i in inj_items if i["team"] == "ARS"])
    ars_news = news.html(shown_news, "arsenal", "Team News")
    if arsenal or ars_inj or ars_news:
        arsenal += ars_inj + ars_news

    # ---- Headlines for the Telegram ping and the archive ----
    unique = headlines.pick(overviews, headline_result)

    sections = []
    if arsenal:
        sections.append({"id": "arsenal", "title": "Arsenal", "html": arsenal})
    if football:
        sections.append({"id": "football", "title": "Football", "html": football})
    month = day.strftime("%Y-%m")
    costs = new.setdefault("costs", {}).setdefault(month, {"spent": 0.0, "calls": 0, "days": {}})
    costs["spent"] = round(costs["spent"] + ledger.total(), 5)
    costs["calls"] += len(ledger.rows)
    costs["days"][day.isoformat()] = {"spent": ledger.total(), "calls": len(ledger.rows)}
    stats = {"matches": {**{leagues[lg]: len(results[lg] or []) for lg in LEAGUE_ORDER}, "Women's Super League": len(wsl_res)},
             "cl_matches": len(cl_matches),
             "season_cost": round(season_out.get("cost", 0.0), 5), "news_candidates": len(cands), "news_shown": len(shown_news), "injury_items": len(inj_items)}
    comps = [(leagues[lg], results[lg] or []) for lg in LEAGUE_ORDER] + [("Champions League", cl_matches), ("FA Cup", fa_cup), ("Women's Super League", wsl_res)] + arsenal_extra
    try:                                                 # the stories and facts The Big Stuff picks from (kickoff/bigstuff.py); never costs the section its games
        story_events = events.football(comps, day.weekday()) + [p for lst in perf_lists for p in events.football_perf("", lst)]
        big_news, big_injuries = events.football_news(shown_news), events.football_injuries(inj_items)
    except Exception:
        story_events, big_news, big_injuries = [], [], []
    for lg_ in LEAGUE_ORDER:                             # Young Guns reads every league's goalscorers and assisters too, not only the Premier League's (D, 2026-11-08)
        for m in results[lg_] or []:
            if m.get("completed") and m.get("goals"):
                guard(f"{leagues[lg_]} players", cached_players, lg_, m["id"])
    match_of = {m["id"]: overview.label(m).replace("-", "\u2013") for m in [*cl_matches, *[x for lg_ in leagues for x in (results[lg_] or [])]]}
    young_players = [{**pl, "match": match_of.get(ev_)} for (lg_, ev_), pls in seen_players.items() for pl in pls]       # every player of the league and Champions League matches read above
    return {"sections": sections, "headlines": unique, "new_state": new, "ledger": ledger, "problems": problems, "stats": stats,
            "events": story_events, "news": big_news, "injuries": big_injuries, "young_in": {"soccer": young_players}}
