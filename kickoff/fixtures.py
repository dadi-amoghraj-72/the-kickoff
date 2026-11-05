"""What is coming up: the games and sessions that are still to be played, for "On Today" (the next 24 hours) and "Games to Watch" (the week, on Mondays).

Each sport is read behind its own guard from a `Sources` object (the real one below, or a fake in tests), so one sport down never costs the others.
A fixture: {"sport", "comp", "text", "when" (UTC datetime), "score", "mine", "stage", "flags" (a set: clash, derby, stars)}.
Which games matter (D, 2026-11-05): D's teams and players; every playoff, play-off and knockout game (NBA, NFL, MLB, IPL, Champions League, cups), not only his teams'; Grand Slam
quarter-finals and later; every F1 session; a ordinary league game only when one of the 17 listed clubs plays."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from kickoff import champions, clubs, events, importance
from kickoff import cricket as cricket_mod
from kickoff import f1 as f1_mod
from kickoff import nba as nba_mod
from kickoff import nfl as nfl_mod
from kickoff import tennis as tennis_mod
from kickoff.sources import espn

ET = ZoneInfo("America/New_York")
SGT = ZoneInfo("Asia/Singapore")

# Derbies and classics among the listed clubs, by ESPN team id.
DERBIES = {frozenset(p) for p in (("359", "367"), ("359", "363"), ("367", "363"), ("364", "368"), ("382", "360"), ("364", "360"), ("83", "86"), ("86", "1068"), ("103", "110"),
                                  ("132", "124"), ("111", "110"), ("111", "114"))}
TOP = 4                    # two teams from the top four of their league meeting is a top-of-the-table clash


def fixture(sport, comp, text, when, score, mine=False, stage="regular", flags=()):
    return {"sport": sport, "comp": comp, "text": text, "when": when, "score": score, "mine": mine, "stage": stage, "flags": set(flags)}


# ---- The real sources -----------------------------------------------------------------------------

class Sources:
    """Everything fixtures needs from the outside world, one method per sport. Tests pass their own object with the same methods."""

    def __init__(self, nba_source, nfl_source, mlb_source, cricket_feed, f1_api, tennis_source):
        self.nba_s, self.nfl_s, self.mlb_s, self.cricket_f, self.f1_a, self.tennis_s = nba_source, nfl_source, mlb_source, cricket_feed, f1_api, tennis_source

    def football(self, league, utc_date):
        return espn.get_matches_on(league, utc_date)

    def table(self, league):
        return espn.get_table(league)

    def nba(self, day):
        return self.nba_s.scoreboard(day)

    def nfl(self, week=None, season_type=None):
        return self.nfl_s.scoreboard(week, season_type) if week else self.nfl_s.scoreboard()

    def mlb(self, day):
        return self.mlb_s.scoreboard(day)

    def cricket(self):
        return self.cricket_f.upcoming(lambda d: cricket_mod.classify(d)["kind"] is not None)

    def f1(self, season):
        return self.f1_a.schedule(season)

    def tennis(self, now):
        return self.tennis_s.slam_events(now)


# ---- Producers ----------------------------------------------------------------------------------

def _days(now, end, tz):
    d, last = now.astimezone(tz).date(), end.astimezone(tz).date()
    while d <= last:
        yield d
        d += timedelta(days=1)


def football(src, now, end, weekday, watch=False):
    out, tables = [], {}
    comps = [(lg, n) for lg, n in espn.LEAGUES.items()] + [(espn.CHAMPIONS_LEAGUE, "Champions League"), (espn.FA_CUP, "FA Cup"), (espn.WSL, "Women's Super League")]
    for lg, name in comps:
        for d in _days(now, end, timezone.utc):
            try:
                matches = src.football(lg, d)
            except Exception:
                continue
            for m in matches:
                when = espn.parse_time(m["kickoff"])
                if m.get("completed") or not (now <= when < end):
                    continue
                ids = [str(m["home"]["id"]), str(m["away"]["id"])]
                mine = any(i in events.MY_FOOTBALL for i in ids)
                listed = any(clubs.is_listed(i) for i in ids)
                stage = events.football_stage(name, m)
                flags = set()
                if lg == espn.WSL and not mine:
                    continue
                if lg == espn.CHAMPIONS_LEAGUE:
                    if stage == "top" and not (listed or mine):                    # a league-phase game without a listed club
                        continue
                elif lg == espn.FA_CUP:
                    if stage == "regular" and not (mine or listed):
                        continue
                elif lg != espn.WSL and not (mine or listed):
                    continue
                if frozenset(ids) in DERBIES:
                    flags.add("derby")
                if watch and lg in espn.LEAGUES:
                    if lg not in tables:
                        try:
                            tables[lg] = {r["id"]: r["rank"] for r in src.table(lg)}
                        except Exception:
                            tables[lg] = {}
                    if all(tables[lg].get(i, 99) <= TOP for i in ids):
                        flags.add("clash")
                score = importance.story_score("football", stage, mine, listed, margin_bonus=2 if flags else 0, weekday=weekday)
                out.append(fixture("football", name, f"{name.replace('UEFA ', '')}: {m['home']['name']} v {m['away']['name']}", when, score, mine, stage, flags))
    return out


def nba(src, now, end, weekday, mine_teams=(), tracked_teams=(), watch_stars=False):
    out = []
    for d in _days(now, end, ET):
        try:
            sb = src.nba(d)
        except Exception:
            continue
        for e in sb.get("events", []):
            g = nba_mod.parse_game(e)
            if g["status"] != "scheduled" or g["phase"] == "preseason" or not (now <= g["date"] < end):
                continue
            a, h = g["away"], g["home"]
            mine = a["abbr"] in mine_teams or h["abbr"] in mine_teams
            stage = "playoff" if g["phase"] == "playoffs" else "knockout" if g["phase"] == "playin" or g.get("cup") in ("Quarterfinals", "Semifinals") else "final" if g.get("cup") == "Championship" else "regular"
            flags = {"stars"} if a["abbr"] in tracked_teams and h["abbr"] in tracked_teams else set()
            if stage == "regular" and not (mine or watch_stars and flags):         # a plain regular-season game: D's five teams only (the stars' clashes only for Games to Watch)
                continue
            out.append(fixture("nba", "NBA", f"NBA: {a['name']} at {h['name']}" + (f" · {g['series']}" if g.get("series") else ""), g["date"],
                               importance.story_score("nba", stage, mine, margin_bonus=6 if flags else 0, weekday=weekday), mine, stage, flags))
    return out


def nfl(src, now, end, weekday):
    out = []
    try:
        sb = src.nfl()
    except Exception:
        return out
    season_type, week = (sb.get("season") or {}).get("type"), (sb.get("week") or {}).get("number")
    if season_type == 1:
        return out
    boards = [sb]
    if end - now > timedelta(days=2) and week:                  # a week ahead: next week's board too
        try:
            boards.append(src.nfl(week + 1, season_type))
        except Exception:
            pass
    for b in boards:
        for e in b.get("events", []):
            g = nfl_mod.parse_game(e)
            if g["status"] != "scheduled" or not (now <= g["date"] < end):
                continue
            a, h = g["away"], g["home"]
            mine = a["abbr"] in events.MY_NFL or h["abbr"] in events.MY_NFL
            stage = ("final" if (b.get("week") or {}).get("number") == 5 else "playoff") if season_type == 3 else "regular"
            night = nfl_mod.slot(g)[1] == "night"
            if stage == "regular" and not (mine or night):
                continue
            out.append(fixture("nfl", "NFL", f"NFL: {a['name']} at {h['name']}", g["date"], importance.story_score("nfl", stage, mine, weekday=weekday), mine, stage))
    return out


def mlb(src, now, end, weekday):
    from kickoff import mlb as mlb_mod
    out = []
    for d in _days(now, end, ET):
        try:
            sb = src.mlb(d)
        except Exception:
            continue
        for e in sb.get("events", []):
            g = mlb_mod.parse_game(e)
            if g["status"] != "scheduled" or g["phase"] != "post" or not (now <= g["date"] < end):      # postseason only: every game counts; the regular season is not daily news
                continue
            a, h = g["away"], g["home"]
            mine = events.LAD in (a["id"], h["id"])
            stage = "final" if "world series" in (g.get("headline") or "").lower() else "playoff"
            out.append(fixture("mlb", "MLB", f"MLB: {a['name']} at {h['name']}" + (f" · {g['headline']}" if g.get("headline") else ""), g["date"],
                               importance.story_score("mlb", stage, mine, weekday=weekday), mine, stage))
    return out


def cricket(src, now, end, weekday):
    out = []
    try:
        drafts = src.cricket()
    except Exception:
        return out
    for m in drafts:
        c = cricket_mod.classify(m)
        try:
            when = cricket_mod.started(m)
        except Exception:
            continue
        if c["kind"] is None or not (now <= when < end):
            continue
        m = {**m, "class": c}
        mine = events.is_mine_cricket(m)
        name = m.get("name", "")
        stage = "final" if re.search(r"\bfinal\b", name, re.I) and not re.search(r"semi|quarter", name, re.I) else "knockout" if events.KNOCKOUT_WORDS.search(name) else "regular"
        if not (mine or stage != "regular"):
            continue
        teams, first = cricket_mod.heading(m)
        label = c.get("label", "")
        out.append(fixture("cricket", label or "Cricket", f"Cricket: {teams}" + (f" · {first}" if first else "") + (f" ({label})" if label and label != "International" else ""),
                           when, importance.story_score("cricket", stage, mine, weekday=weekday), mine, stage))
    return out


def f1(src, now, end, weekday):
    out = []
    try:
        schedule = src.f1(now.year)
    except Exception:
        return out
    names = {"Qualifying": "Qualifying", "Sprint": "Sprint", "race": "Race"}
    for race in schedule:
        for key, label in names.items():
            when = f1_mod.start_of(race, key)
            if when and now <= when < end:
                out.append(fixture("f1", "F1", f"F1: {race['raceName']} · {label}", when, importance.story_score("f1", "final" if key == "race" else "knockout", weekday=weekday),
                                   False, "final" if key == "race" else "knockout"))
    return out


def tennis(src, now, end, weekday):
    out, seen = [], {}
    try:
        slams = src.tennis(now)
    except Exception:
        return out
    late = {"QF": "quarter-finals", "SF": "semi-finals", "F": "final"}
    for e in slams:
        for g in e.get("groupings", []):
            if g["grouping"]["slug"] not in tennis_mod.DRAW:
                continue
            for c in g.get("competitions", []):
                stage = tennis_mod.STAGES.get((c.get("round") or {}).get("displayName"))
                if stage in late and c["status"]["type"].get("state") == "pre":
                    when = tennis_mod.utc(c["date"])
                    if now <= when < end:
                        key = (e["name"], stage)
                        seen[key] = min(seen.get(key, when), when)
    for (name, stage), when in seen.items():
        out.append(fixture("tennis", name, f"Tennis: {name} {late[stage]}", when, importance.story_score("tennis", "final" if stage == "F" else "knockout"), False, "final" if stage == "F" else "knockout"))
    return out


def golf(src, now, end, weekday):
    """A men's major or THE PLAYERS Championship that starts in the window (from the PGA Tour's season calendar): 'Golf: Masters Tournament starts (US Thursday)'."""
    from kickoff import golf as golf_mod
    out = []
    try:
        board = src.golf("pga")
    except Exception:
        return out
    for c in ((board.get("leagues") or [{}])[0].get("calendar") or []):
        if not golf_mod.MEN.search(c.get("label", "")):
            continue
        start = golf_mod._utc(c["startDate"]) if hasattr(golf_mod, "_utc") else datetime.fromisoformat(c["startDate"].replace("Z", "+00:00"))
        if now <= start < end:
            out.append(fixture("golf", "Golf", f"Golf: {c['label']} starts ({start:%A}, US time)", start, importance.story_score("golf", "final"), False, "final"))
    return out


def collect(src, now, end, weekday, mine_nba=(), watch=False, tracked_nba=()):
    """Every fixture that matters between now and end (UTC datetimes). Returns (fixtures sorted by time, [sports that failed])."""
    out, failed = [], []
    for sport, fn in (("football", lambda: football(src, now, end, weekday, watch)), ("nba", lambda: nba(src, now, end, weekday, set(mine_nba), set(tracked_nba), watch)), ("nfl", lambda: nfl(src, now, end, weekday)),
                      ("mlb", lambda: mlb(src, now, end, weekday)), ("cricket", lambda: cricket(src, now, end, weekday)), ("f1", lambda: f1(src, now, end, weekday)),
                      ("tennis", lambda: tennis(src, now, end, weekday)), ("golf", lambda: golf(src, now, end, weekday))):
        try:
            out += fn()
        except Exception:
            failed.append(sport)
    return sorted(out, key=lambda f: (f["when"], -f["score"])), failed
