"""Football's season rhythm (D, 2026-11-04): for the Premier League a "season is coming" note a week before the first match, a closing note when the last day is
played (champions, the top four, the three relegated), and the main awards as they are announced; and a closing note for the FA Cup and the Champions League when their
finals are played. All by code from exact data except the preview (kickoff.preview: Claude, from cited items). The Premier League awards come from Wikipedia
(kickoff.honours), which ESPN has no feed for; the Golden Boot is the table's own winner there too, so it is not computed here."""
import re

from kickoff import awards, honours, preview
from kickoff import render as r
from kickoff.clubs import code
from kickoff.sources import espn

PL_PAGES = {"Player": "Premier League Player of the Season", "Young Player": "Premier League Young Player of the Season", "Manager": "Premier League Manager of the Season",
            "Golden Boot": "Premier League Golden Boot", "Golden Glove": "Premier League Golden Glove"}


def label(year):
    return f"{year}-{str(year + 1)[2:]}"


def pl_closing(rows, year):
    """'That's the 2025-26 Premier League season. Arsenal are champions with 85 points. Man City, Man Utd and Aston Villa complete the top four. West Ham, Burnley and Wolves are relegated.' once every club has played 38, else ''. rows: espn.get_table rows."""
    if len(rows) != 20 or any(x["played"] != 38 for x in rows):
        return ""
    names = lambda xs: r.join_names([x["short"] for x in xs])  # noqa: E731
    top, bottom = rows[:4], rows[-3:]
    text = (f"That's the {label(year)} Premier League season. {rows[0]['short']} are champions with {rows[0]['points']} points. "
            f"{names(top[1:])} complete the top four. {names(bottom)} are relegated.")
    return f"<p>{r.esc(text)}</p>"


def final_note(competition, matches, year):
    """'That's the 2025-26 FA Cup. Manchester City are the winners, beating Chelsea 1-0.' / '... Paris Saint-Germain are champions, beating Arsenal on penalties after a 1-1
    draw.' from a finished match whose stage is 'final'; '' when there is none or no winner. matches: espn.parse_match rows."""
    for m in matches or []:
        if m.get("stage") != "final" or not m.get("completed") or m.get("winner") not in ("home", "away"):
            continue
        win, lose = (m["home"], m["away"]) if m["winner"] == "home" else (m["away"], m["home"])
        hs, as_ = m["home_score"], m["away_score"]
        w_score, l_score = (hs, as_) if m["winner"] == "home" else (as_, hs)
        status = (m.get("status") or "").lower()
        if "penalt" in status:
            how = f"on penalties after a {hs}\u2013{as_} draw"
        elif "extra" in status:
            how = f"{w_score}\u2013{l_score} after extra time"
        else:
            how = f"{w_score}\u2013{l_score}"
        word = "champions" if competition == "Champions League" else "the winners"
        return f"<p>{r.esc(f'''That's the {label(year)} {competition}. {win['name']} are {word}, beating {lose['name']} {how}.''')}</p>"
    return ""


def pl_award_items(wiki, year, codes=None):
    """The Premier League's main awards for the season from Wikipedia's award pages, as awards items: Player, Young Player, Manager, Golden Boot, Golden Glove. A page that
    is down or does not hold this season's row yet gives no item."""
    items = []
    for lab, page in PL_PAGES.items():
        try:
            got = honours.pl_award(wiki.wikitext(page), label(year).replace("-", "–"))
        except Exception:
            continue
        if got:
            items.append({"key": f"pl:{lab}", "label": lab, "sig": got["name"], "kind": "single", "data": {"name": got["name"], "team": (codes or {}).get(got["club"], got["club"])}, "text": f"{got['name']} ({got['club']})"})
    return items


def build(day, now, rows, fa_cup, cl_matches, state, client=None, wiki=None, season_source=None, award_state_default=True):
    """{"pl": html, "fa": html, "cl": html, "state": new state, "cost": dollars}. state: {"pl_closed": year, "fa_closed": year, "cl_closed": year, "awards": awards state,
    "previewed": [seasons]}. Each part is on its own and never raises."""
    from kickoff.sources import wikipedia
    year = espn.season_year(day)
    st, pl, cost = dict(state or {}), "", 0.0
    out = {"pl": "", "fa": "", "cl": ""}
    try:                                                    # the Premier League's last day
        note = pl_closing(rows or [], year)
        if note and st.get("pl_closed") != year:
            pl += note
            st["pl_closed"] = year
    except Exception:
        pass
    for key, comp, matches in (("fa", "FA Cup", fa_cup), ("cl", "Champions League", cl_matches)):
        try:
            note = final_note(comp, matches, year)
            if note and st.get(f"{key}_closed") != year:
                out[key] = note
                st[f"{key}_closed"] = year
        except Exception:
            pass
    try:                                                    # the Premier League awards, as announced (Wikipedia)
        wiki = wiki or wikipedia.Source()
        prev = st.get("awards") or ({"season": year, "seen": {}, "rows": [], "names": {}} if award_state_default else {})
        if day.month in (5, 6, 7) or st.get("awards"):
            html_a, st["awards"] = awards.run(None, "Premier League Awards", prev, year, extra=pl_award_items(wiki, year, {x['team']: code(x['id'], x['abbr']) for x in rows or []}))
            pl = html_a + pl
    except Exception:
        pass
    try:                                                    # the "season is coming" note
        html_p, st["previewed"], cost = preview.block("epl", "soccer", "Premier League", year if day.month >= 7 else year + 1, day, st.get("previewed"), client,
                                                       source=season_source, league_code="eng.1")
        pl = html_p + pl
    except Exception:
        pass
    out["pl"], out["state"], out["cost"] = pl, st, cost
    return out
