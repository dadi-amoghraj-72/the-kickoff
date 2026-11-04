"""League awards (D, 2026-11-04): a running Awards table inside the sport's section, shown only on a day when something was announced, cumulative with the
newest at the top and the older awards still below it, winners only. It stays after the season's closing note and starts afresh at the sport's next season
(the first award of a higher ESPN season).

ESPN gives no announcement date, so "new" means "not in the state saved yesterday"; the first time a sport is seen its existing awards are saved silently (a
league's old awards are not news). A winner list that changes later (an All-Star replaced after an injury) counts as news again and says who came in for whom.
All by code from exact data, so no Claude cost. Sources: kickoff.sources.espn_awards (ESPN) and kickoff.sources.wikipedia_awards (what ESPN does not carry)."""
import json
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
        row = {"key": i["key"], "label": i["label"], "text": i["text"], "sig": i["sig"], "note": "", "kind": i.get("kind"), "data": i.get("data")}
        if old is not None:
            row["note"] = "" if i.get("quiet") else (diff_note(names.get(i["key"]), i.get("names")) or "updated")
            rows = [x for x in rows if x["key"] != i["key"]]
        seen[i["key"]] = i["sig"]
        if i.get("names"):
            names[i["key"]] = i["names"]
        new.append(row)
    return {"season": season, "seen": seen, "rows": new + rows, "names": names}, new


BLOCKS = ("team", "asg", "pos")                    # rows shown as a full-width block, and only on the morning they land or on the final awards day
FINAL_LABELS = {"MVP"}                             # the awards whose morning counts as "the final awards day" (D: the NFL Honors day)
TONES = {"1st": "gold", "2nd": "silver", "3rd": "bronze"}
SHORT_POS = {"placekicker": "K", "kickoff returner": "KR", "slot cornerback": "Slot CB"}


def is_mvp(label_):
    return "MVP" in label_ or "Most Valuable" in label_


def tone_of(label_):
    m = re.search(r"\b(1st|2nd|3rd)\b", label_)
    return TONES[m.group(1)] if m else "gold"


def abbreviate(names):
    """{full name: how it is written} for a group of players: first initial and surname ('V. Wembanyama', 'K-A. Towns'), but the full name for any two that would
    come out the same."""
    def short(n):
        first, _, rest = n.partition(" ")
        return (f"{'-'.join(p[0] for p in first.split('-'))}. {rest}" if rest else n)
    shorts = {n: short(n) for n in names}
    clash = {s for s in shorts.values() if list(shorts.values()).count(s) > 1}
    return {n: (n if s in clash else s) for n, s in shorts.items()}


def numbered(pairs):
    """[(position, name)] -> [(label, name)]: a position that appears more than once is numbered ('WR 1', 'WR 2'); 'APU' reads 'Utility'."""
    pairs = [("Utility" if p == "APU" else SHORT_POS.get(p.lower(), p), n) for p, n in pairs]
    total = {p: sum(1 for q, _ in pairs if q == p) for p, _ in pairs}
    seen, out = {}, []
    for p, n in pairs:
        seen[p] = seen.get(p, 0) + 1
        out.append((f"{p} {seen[p]}" if total[p] > 1 else p, n))
    return out


def _esc(x):
    return r.esc(x)


def winner_cell(row):
    """The winner cell of a one-winner row: the name in gold (in the iridescent MVP colour for every MVP), the team beside it."""
    d = row.get("data") or {}
    name = d.get("name") or row.get("text", "")
    cls = "wn mvp" if is_mvp(row["label"]) else "wn"
    team = f' <span class="tc">({_esc(d["team"])})</span>' if d.get("team") else ""
    return f'<span class="{cls}">{_esc(name)}</span>{team}'


def block_html(row):
    """A full-width block: a title row, then the content (All-NBA team: five lines; All-Star conference: Starters and Reserves; All-Pro: one row per position)."""
    d = row["data"]
    note = f' <span class="muted">· {_esc(row["note"])}</span>' if row.get("note") and row["note"] != "updated" else ""
    if row["kind"] == "team":
        lines = "".join(f'<div class="pl"><span class="wn {d["tone"]}">{_esc(p["name"])}</span>' + (f' <span class="ct">({p["count"]})</span>' if p.get("count") else "")
                        + (f' <span class="tc">— {_esc(p["team"])}</span>' if p.get("team") else "") + "</div>" for p in d["players"])
        body = f'<div class="lines">{lines}</div>'
    elif row["kind"] == "asg":
        full = [p["name"] for g in ("starters", "reserves") for p in d[g]]
        short = abbreviate(full)

        def col(title, players):
            items = "".join(f'<div class="pl">{_esc(short[p["name"]])}' + (f' <span class="fl">({"Out" if p["flag"] == "out" else "In"})</span>' if p.get("flag") else "") + "</div>" for p in players)
            return f'<div class="col"><div class="ch">{title}</div>{items}</div>'
        body = f'<div class="asg">{col("Starters", d["starters"])}{col("Reserves", d["reserves"])}</div>'
    else:
        body = '<table class="pos"><tbody>' + "".join(f'<tr><td class="pp">{_esc(p)}</td><td><span class="wn">{_esc(n)}</span></td></tr>' for p, n in d["rows"]) + "</tbody></table>"
    sub = f'<div class="bs muted">{_esc(d["sub"])}</div>' if d.get("sub") else ""
    return f'<tr class="blk"><td colspan="2"><div class="bt">{_esc(row["label"])}{note}</div>{sub}{body}</td></tr>'


def table_html(title, rows, show_blocks=True):
    """The cumulative table, newest first: Award and Winner for one-winner rows; full-width blocks for the team awards (only when show_blocks)."""
    body = ""
    for x in rows:
        if x.get("kind") in BLOCKS:
            if show_blocks:
                body += block_html(x)
            continue
        note = f' <span class="muted">· {_esc(x["note"])}</span>' if x.get("note") and x["note"] != "updated" else ""
        cell = winner_cell(x) if x.get("data") else f'<span class="wn">{_esc(x["text"])}</span>'
        body += f'<tr><td>{_esc(x["label"])}</td><td class="win">{cell}{note}</td></tr>'
    if not body:
        return ""
    return (f'<div class="pts f1 awards"><table><colgroup><col style="width:60%"><col style="width:40%"></colgroup><thead><tr><th class="tt" colspan="2">{_esc(title)}</th></tr>'
            f'<tr><th>Award</th><th>Winner</th></tr></thead><tbody>{body}</tbody></table></div>')


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
            if not (c and c["season"] == f"{season - 1}–{str(season)[2:]}"):
                return []
            return [{"key": "wiki:coy", "label": "Coach of the Year", "sig": c["coach"], "kind": "single", "data": {"name": c["coach"], "team": c["team"]},
                     "text": f"{c['coach']} ({c['team']})"}]

        def stars():
            a = honours.all_stars(wiki.wikitext(f"{season} NBA All-Star Game"))
            out = []
            for conf in ("East", "West"):
                if a.get(conf):
                    data = {**a[conf], "sub": f"Game: {_day(a['date'])} (US)"}
                    out.append({"key": f"wiki:asg:{conf}", "label": f"NBA All-Star Selections — {conf}", "sig": json.dumps(a[conf], sort_keys=True), "kind": "asg", "data": data,
                                "quiet": True, "text": ", ".join(p["name"] for g in ("starters", "reserves") for p in a[conf][g])})
            return out
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
                        out.append({"key": f"wiki:ap:{team}:{unit}", "label": f"All-Pro {team.capitalize()} Team — {unit}", "sig": "|".join(n for _, n in rows), "kind": "pos",
                                    "data": {"rows": numbered(rows)}, "text": ", ".join(n for _, n in rows)})
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


ALLNBA = ("44", "45", "46")        # ESPN's award ids for the All-NBA first, second and third teams
FIRST_SEASON = 1947


def allnba_counts(source, season, cache):
    """({athlete id: All-NBA selections through `season`}, cache) from ESPN's lists of every earlier season, fetched once and kept in `cache` ({"seasons": {year: [ids]}}).
    None for the counts (and the cache unchanged) when any season could not be read: a count that is too low is worse than none."""
    seasons = dict((cache or {}).get("seasons", {}))
    try:
        for y in range(season, FIRST_SEASON - 1, -1):
            if str(y) not in seasons or y == season:
                seasons[str(y)] = sorted({i for a in ALLNBA for i in source.winners(y, a)})
    except Exception:
        return None, cache
    counts = {}
    for y, ids in seasons.items():
        if int(y) <= season:
            for i in ids:
                counts[i] = counts.get(i, 0) + 1
    return counts, {"seasons": seasons}


def run(source, title, state, season, extra=(), skip=SKIP):
    """(html, new state). The table of ESPN's awards for `season` plus `extra` items (wiki_items); names are looked up only for ESPN awards that are new or whose
    winners changed. The full-width team blocks are shown on the morning they are announced and on the morning of the MVP (the final awards day), not on the days
    between. Never raises: a source failure leaves the state as it was and shows nothing."""
    try:
        got = [a for a in source.awards(season) if a["winners"] and a["name"] not in skip]
        old = state or {}
        fresh = "season" not in old
        seen = old.get("seen", {}) if old.get("season") == season else {}
        cache = old.get("allnba")
        items = []
        for a in got:
            sig = ",".join(w["athlete"] for w in a["winners"])
            lab = label(a["name"])
            it = {"key": a["id"], "label": lab, "sig": sig, "text": ""}
            if not fresh and seen.get(a["id"]) != sig:
                infos = [source.athlete(season, w["athlete"]) for w in a["winners"]]
                teams = [source.team(season, w["team"]) if w["team"] else "" for w in a["winners"]]
                if len(infos) == 1:
                    it.update(kind="single", data={"name": infos[0]["name"], "team": teams[0]}, text=winner_text([infos[0]["name"]], teams[0]))
                else:
                    counts = None
                    if lab.startswith("All-NBA"):
                        counts, cache = allnba_counts(source, season, cache)
                    players = [{"name": i["name"], "team": t, "count": (counts or {}).get(w["athlete"])} for i, t, w in zip(infos, teams, a["winners"])]
                    it.update(kind="team", data={"tone": tone_of(lab), "players": players}, text=", ".join(i["name"] for i in infos))
            items.append(it)
        new_state, new = update(state, season, items + list(extra))
        if cache:
            new_state["allnba"] = cache
        show_blocks = any(x["label"] in FINAL_LABELS for x in new) or any(x.get("kind") in BLOCKS for x in new)
        return (table_html(title, new_state["rows"], show_blocks) if new else ""), new_state
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
