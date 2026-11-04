"""League awards (D, 2026-11-04): a running Awards table inside the sport's section, shown only on a day when something was announced, cumulative with the
newest at the top and the older awards still below it, winners only. It stays after the season's closing note and starts afresh at the sport's next season
(the first award of a higher ESPN season).

ESPN gives no announcement date, so "new" means "not in the state saved yesterday"; the first time a sport is seen its existing awards are saved silently (a
league's old awards are not news). A winner list that changes later (an All-Star replaced after an injury) counts as news again and says who came in for whom.
All by code from exact data, so no Claude cost. Sources: kickoff.sources.espn_awards (ESPN) and kickoff.sources.wikipedia_awards (what ESPN does not carry)."""
import re
from datetime import datetime

from kickoff import honours
from kickoff import render as r

SKIP = {"NBA Cup MVP", "NBA Cup All-Tournament Team"}      # D wants the conference finals MVPs but not the in-season Cup
LABELS = {"Twyman-Stokes Teammate of the Year Award": "Teammate of the Year"}


def label(name):
    """'NBA Western Conference Finals MVP' -> 'Western Conference Finals MVP', 'Walter Payton NFL Man of the Year' -> 'Walter Payton Man of the Year'."""
    if name in LABELS:
        return LABELS[name]
    out = re.sub(r"(?<![-\w])(NBA|NFL|MLB)\s+", "", name)
    return re.sub(r"\s+Award$", "", out).strip()


def winner_text(names, team=""):
    """One winner: 'Shai Gilgeous-Alexander (OKC)'; a team of players: 'G. Antetokounmpo, N. Jokic, ...' (the short names, to keep the line short)."""
    return f"{names[0]}" + (f" ({team})" if team else "") if len(names) == 1 else ", ".join(names)


def season_of(league, today):
    """The season whose honours are being announced, named as ESPN does (the calendar year the season ends in for the NBA, the year it starts in for the NFL and MLB):
    NBA 2026-27 is 2027 from August 2026; the NFL's 2025 season is 2025 until the following March; MLB's 2026 season is 2026 until the following March."""
    if league == "nba":
        return today.year + 1 if today.month >= 8 else today.year
    return today.year if today.month >= 3 else today.year - 1


def diff_note(old, new):
    """'In: M. Stafford · out: J. Allen' from two name lists; '' when the same people (or no lists to compare)."""
    if old is None or new is None:
        return ""
    ins, outs = [honours.initial_name(n) for n in new if n not in old], [honours.initial_name(n) for n in old if n not in new]
    return " · ".join(x for x in (f"In: {', '.join(ins)}" if ins else "", f"out: {', '.join(outs)}" if outs else "") if x)


def update(state, season, items):
    """The new state and what is new today. state: {"season", "seen": {key: signature}, "rows": [{"key", "label", "text", "sig", "note"}] newest first, "names"} or {};
    items: this season's honours that have winners, in order: [{"key", "label", "sig", "text", "names"}] (text is only needed for new or changed keys; names, optional, a
    list of people so that a change can say who came in and who went out). Returns (state, new): new is the rows announced or changed since the last run."""
    if not state or "season" not in state:                       # first sight of this sport: remember what exists, say nothing
        return {"season": season, "seen": {i["key"]: i["sig"] for i in items}, "rows": [], "names": {i["key"]: i["names"] for i in items if i.get("names")}}, []
    if season > state["season"]:                                 # a new season's honours: start afresh, everything is news
        state = {"season": season, "seen": {}, "rows": [], "names": {}}
    elif season < state["season"]:                               # the source went back a season: leave things as they are
        return state, []
    seen, rows, new, names = dict(state["seen"]), list(state["rows"]), [], dict(state.get("names", {}))
    for i in items:
        old = seen.get(i["key"])
        if old == i["sig"]:
            continue
        row = {"key": i["key"], "label": i["label"], "text": i["text"], "sig": i["sig"], "note": ""}
        if old is not None:
            row["note"] = diff_note(names.get(i["key"]), i.get("names")) or "updated"
            rows = [x for x in rows if x["key"] != i["key"]]
        seen[i["key"]] = i["sig"]
        if i.get("names"):
            names[i["key"]] = i["names"]
        new.append(row)
    return {"season": season, "seen": seen, "rows": new + rows, "names": names}, new


def table_html(title, rows):
    """The cumulative table: Award, Winner, newest first. A changed row carries its note under the winners ('In: X · out: Y')."""
    body = [[x["label"], r.Raw(r.esc(x["text"]) + (f' <span class="muted">· {r.esc(x["note"])}</span>' if x.get("note") else ""))] for x in rows]
    return r.compact(r.table(title, [("Award", False), ("Winner", False)], body), (40, 60), " awards") if body else ""


def _day(text):
    """'February 15, 2026' -> '15 Feb'; the text unchanged when it is not that form."""
    try:
        d = datetime.strptime(text.strip(), "%B %d, %Y")
        return f"{d.day} {d:%b}"
    except ValueError:
        return text.strip()


def wiki_items(league, season, wiki):
    """The honours ESPN does not carry, from Wikipedia (kickoff.honours), as awards items. Every piece is on its own: a page that is missing, changed or down
    just gives no item."""
    items = []

    def attempt(fn):
        try:
            items.extend(fn())
        except Exception:
            pass

    if league == "nba":
        def coach():
            c = honours.coach_of_the_year(wiki.wikitext("NBA Coach of the Year Award"))
            return [{"key": "wiki:coy", "label": "Coach of the Year", "sig": c["coach"], "text": f"{c['coach']} ({c['team']})"}] if c and c["season"] == f"{season - 1}–{str(season)[2:]}" else []

        def stars():
            a = honours.all_stars(wiki.wikitext(f"{season} NBA All-Star Game"))
            if not a:
                return []
            names = a["East"] + a["West"]
            ini = lambda xs: ", ".join(honours.initial_name(n) for n in xs)  # noqa: E731
            return [{"key": "wiki:asg", "label": "All-Star selections", "sig": "|".join(names), "names": names,
                     "text": f"East: {ini(a['East'])}. West: {ini(a['West'])}. Game: {_day(a['date'])} (US)."}]
        attempt(coach)
        attempt(stars)
    if league == "nfl":
        def allpro():
            ap = honours.all_pro(wiki.wikitext(f"{season} All-Pro Team"))
            out = []
            for team in ("first", "second"):
                for unit in ("Offense", "Defense", "Special teams"):
                    rows = ap.get(team, {}).get(unit) or []
                    if rows:
                        out.append({"key": f"wiki:ap:{team}:{unit}", "label": f"All-Pro {team.capitalize()} Team · {unit}", "sig": "|".join(n for _, n in rows),
                                    "names": [n for _, n in rows], "text": ", ".join(f"{p} {honours.initial_name(n)}" for p, n in rows)})
            return out

        def probowl():
            p = honours.pro_bowl(wiki.wikitext(f"{season + 1} Pro Bowl Games"))
            if not p:
                return []
            names = p["AFC"] + p["NFC"]
            return [{"key": "wiki:pb", "label": "Pro Bowl selections", "sig": "|".join(names), "names": names,
                     "text": f"AFC {len(p['AFC'])} players, NFC {len(p['NFC'])}. Games: {_day(p['date'])} (US)."}]
        attempt(allpro)
        attempt(probowl)
    return items


def run(source, title, state, season, extra=(), skip=SKIP):
    """(html, new state). The table of ESPN's awards for `season` plus `extra` items (wiki_items); names are looked up only for ESPN awards that are new or whose
    winners changed. Never raises: a source failure leaves the state as it was and shows nothing."""
    try:
        got = [a for a in source.awards(season) if a["winners"] and a["name"] not in skip]
        old = state or {}
        fresh = "season" not in old
        seen = old.get("seen", {}) if old.get("season") == season else {}
        items = []
        for a in got:
            sig = ",".join(w["athlete"] for w in a["winners"])
            it = {"key": a["id"], "label": label(a["name"]), "sig": sig, "text": ""}
            if not fresh and seen.get(a["id"]) != sig:
                names = [source.athlete(season, w["athlete"]) for w in a["winners"]]
                team = source.team(season, a["winners"][0]["team"]) if len(a["winners"]) == 1 and a["winners"][0]["team"] else ""
                it["text"] = winner_text([n["name"] for n in names] if len(names) == 1 else [n["short"] for n in names], team)
            items.append(it)
        new_state, new = update(state, season, items + list(extra))
        return (table_html(title, new_state["rows"]) if new else ""), new_state
    except Exception:
        return "", state


def block(league, sport, title, day, state, source=None, wiki=None):
    """(html, new state) for one league on one morning: ESPN's awards for the season being announced plus the Wikipedia honours, as the cumulative table when
    something is new. day: the edition's date. source/wiki: injectable for tests."""
    from kickoff.sources import espn_awards, wikipedia
    season = season_of(league, day)
    source = source or espn_awards.Source(sport, league)
    wiki = wiki or wikipedia.Source()
    return run(source, title, state, season, extra=wiki_items(league, season, wiki))
