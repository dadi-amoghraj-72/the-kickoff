"""Assembles the Arsenal and Football sections for one edition from everything built so far.

Every source is called through a guard: if it fails, that block is skipped and the rest of the edition stands.
Claude is optional: with client=None every note and overview is the plain version written by code (free).
State is passed in and handed back, never written here, so a test run can't disturb the real state files."""
import copy
from datetime import datetime, timezone

from kickoff import champions, focus, fplcorner, injuries, leaders, news, notes, overview, roundup, scoreboard, settings, tables
from kickoff import render as r
from kickoff.http import safe
from kickoff.sources import espn, feeds, fpl

LEAGUE_ORDER = ["eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "tur.1"]


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


def _paragraphs(written, match_by_id):
    out = ""
    for mid, w in written.items():
        m = match_by_id[mid]
        out += f"<p>{r.bold_names(w['note'], (m['home']['name'], m['away']['name'], m['home']['short'], m['away']['short']))}</p>"
    return out


def run(day, client=None, st=None, now=None, demo=False):
    """Build both sections. demo=True makes the FPL corner show everything it can, whatever the deadline. st: {"tables", "clean_sheets", "injuries", "fpl", "news_seen", "costs"} (copied, not changed).
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
    football = ""
    for lg in LEAGUE_ORDER:
        name, res, tbl = leagues[lg], results[lg] or [], rows[lg]
        parts = ""
        if res:
            parts += guard(f"{name} round-up", round_up, name, name, res, lg, tbl) or ""
            parts += scoreboard.scores_html(res)
        chosen = notes.select(lg, res)
        if chosen:
            facts = [notes.match_facts(m, t, tbl, previous[lg], name) for m, t in chosen]
            parts += write_notes_for(f"{name} notes", facts, {m["id"]: m for m, _ in chosen}, claude_only=True)
        if tbl:
            html, entry = tables.one("Table", tbl, saved_tables.get(lg), day,
                                     leaders_fn=lambda lg=lg, tbl=tbl: guard(f"{leagues[lg]} leaders", leaders.league_block, lg,
                                                                              espn.season_year(day), tbl, cs))
            parts += html
            if entry:
                new.setdefault("tables", {})[lg] = entry
        if parts:
            football += f"<h3>{r.esc(name)}</h3>{parts}"
    wsl_res = guard("Women's Super League results", espn.recent_results, espn.WSL, day) or []
    wsl_parts = ""
    if wsl_res:
        wsl_parts += guard("Women's Super League round-up", round_up, "Women's Super League", "Women's Super League", wsl_res, espn.WSL,
                           rows[espn.WSL]) or ""
        wsl_parts += scoreboard.scores_html(wsl_res)
    if rows[espn.WSL]:
        html, entry = tables.one("Table", rows[espn.WSL], saved_tables.get(espn.WSL), day)
        wsl_parts += html
        if entry:
            new.setdefault("tables", {})[espn.WSL] = entry
    if wsl_parts:
        football += f"<h3>Women's Super League</h3>{wsl_parts}"
    if cl_matches:
        cl_box = guard("Champions League round-up", round_up, "Champions League", champions.COMPETITION, cl_matches,
                       espn.CHAMPIONS_LEAGUE, rows[espn.CHAMPIONS_LEAGUE], "night") or ""
        football += champions.section_html(cl_matches, rows[espn.CHAMPIONS_LEAGUE], None, cl_box)

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
    for c in cands:
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
    arsenal, headline_result = "", None
    for club, tier in ((focus.ARSENAL, "arsenal"), (focus.ARSENAL_WOMEN, "women")):
        block = guard(club["name"], focus.build, club, day, all_rows, previous, now, tier)
        if not block:
            continue
        match_by_id = {f["id"]: {"home": {"name": f["home"], "short": f["home"]}, "away": {"name": f["away"], "short": f["away"]}}
                       for f in block["facts"]}
        body = write_notes_for(f"{club['name']} note", block["facts"], match_by_id)
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
    heads = []
    if headline_result:
        heads.append(f"Arsenal: {headline_result}")
    if champions.COMPETITION in overviews and overviews[champions.COMPETITION].get("game_of_the_night"):
        heads.append(f"Champions League: {overviews[champions.COMPETITION]['game_of_the_night']}")
    for comp, f in overviews.items():
        for row in f["matches"]:
            if row.get("result_vs_expectation") in ("upset", "big_upset"):
                heads.append(f"Upset in the {comp}: {row['match']}")
    for lg in LEAGUE_ORDER:
        f = overviews.get(leagues[lg])
        if f and f.get("game_of_the_night"):
            heads.append(f"{leagues[lg]}: {f['game_of_the_night']}")
    own = (headline_result or "").replace("–", "-")
    heads = [h for h in heads if not (own and h.split(": ", 1)[-1].replace("–", "-") == own and not h.startswith("Arsenal"))]
    unique = list(dict.fromkeys(heads))[:3]

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
             "news_candidates": len(cands), "news_shown": len(shown_news), "injury_items": len(inj_items)}
    return {"sections": sections, "headlines": unique, "new_state": new, "ledger": ledger, "problems": problems, "stats": stats}
