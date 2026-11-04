"""The IPL's extras (D, 2026-11-04): the Orange Cap and Purple Cap leaders in the IPL's block on every morning it has matches, a closing note when the final is
played, and at the very end the Most Valuable Player and Emerging Player awards (in an Awards table, once).

ESPN gives no stats page we can read from GitHub (Cricinfo and ESPN's stats pages refuse it), so the leaders and the end-of-season awards come from the season page on
Wikipedia, which is updated match by match and cites Cricinfo: a 'Most runs' and a 'Most wickets' table (the top five), and an 'End of season awards' table. A page that
does not look as tested gives nothing: no caps are better than wrong ones. The closing note comes from ESPN's own final."""
import re

from kickoff import honours
from kickoff import render as r

CODES = {"Chennai Super Kings": "CSK", "Delhi Capitals": "DC", "Gujarat Titans": "GT", "Kolkata Knight Riders": "KKR", "Lucknow Super Giants": "LSG", "Mumbai Indians": "MI",
         "Punjab Kings": "PBKS", "Rajasthan Royals": "RR", "Royal Challengers Bengaluru": "RCB", "Royal Challengers Bangalore": "RCB", "Sunrisers Hyderabad": "SRH"}
GOLD_TEAMS = {"SRH"}           # D: Sunrisers Hyderabad's row in gold in the official league (points) table, nowhere else


def season_page(year):
    return f"{year} Indian Premier League"


def stats(text):
    """{"runs": [(runs, player, team code)], "wickets": [...]} from the page's 'Most runs' and 'Most wickets' tables (the top five; players level on a number share it),
    or {} when either is missing."""
    out = {}
    for t in honours.tables(text):
        key = {"most runs": "runs", "most wickets": "wickets"}.get(re.sub(r"<ref.*", "", t["caption"], flags=re.S).strip().lower())
        if not key:
            continue
        rows, number = [], None
        for row in t["rows"]:
            c = row["cells"]
            if len(c) >= 3 and re.fullmatch(r"\d+", c[0].strip()):
                number, c = int(c[0]), c[1:]
            elif len(c) < 2:
                continue
            who, club = honours.link_text(c[0]), honours.link_text(c[1]) or ""
            if who and number is not None:
                rows.append((number, who, CODES.get(club, club)))
        if rows:
            out[key] = rows
    return out if {"runs", "wickets"} <= set(out) else {}


ORDER = ["MVP", "Orange Cap", "Purple Cap", "Emerging", "Super Striker", "Most Sixes", "Most Fours", "Dot Balls", "Best Catch", "Fair Play", "Final POTM"]
WIKI_NAMES = {"most valuable player": "MVP", "orange cap": "Orange Cap", "purple cap": "Purple Cap", "emerging player": "Emerging", "highest batting strike rate": "Super Striker",
              "most sixes": "Most Sixes", "most fours": "Most Fours", "most dot balls": "Dot Balls", "catch of the season": "Best Catch", "team fairplay": "Fair Play"}
YAHOO_NAMES = {"mvp award": "MVP", "orange cap": "Orange Cap", "purple cap": "Purple Cap", "emerging player award": "Emerging", "super striker of the season": "Super Striker",
               "super sixes": "Most Sixes", "most fours": "Most Fours", "green dot ball": "Dot Balls", "catch of the season": "Best Catch", "fairplay award": "Fair Play",
               "player of the match (final)": "Final POTM"}


def _key(name, names):
    n = re.sub(r"\s+", " ", name.strip().lower())
    return next((v for k, v in names.items() if n.startswith(k)), None)


def end_awards(text):
    """{label: {"name", "team", "detail"}} from the Wikipedia page's 'End of season awards' table once it is on the page (MVP, Orange Cap, Purple Cap, Emerging, Super Striker,
    Most Sixes, Most Fours, Dot Balls, Best Catch, Fair Play), else {}."""
    out = {}
    for t in honours.tables(text):
        if t["caption"].lower().startswith("end of season awards"):
            for row in t["rows"]:
                c = row["cells"]
                if len(c) >= 4:
                    key = _key(c[0], WIKI_NAMES)
                    who, club = honours.link_text(c[2]), honours.link_text(c[3]) or ""
                    if key and (who or club):
                        out[key] = {"name": who or club, "team": CODES.get(club, "") if who else "", "detail": ""}
    return out


def yahoo_awards(page):
    """The same awards from Yahoo Sports' article (a table of Award and Winner; Yahoo carries Cricket News' list, 'IPL 2026 awards list'): {label: {"name", "team", "detail"}}, with
    the Player of the Match of the final as well. A winner reads 'Name (Team)', 'Name (Team) - 172 dot balls (3268 planted)' or 'Name (RCB vs KKR - Tim David's dismissal)'; what is not a
    team goes in 'detail'. {} when the page has no such table."""
    import html as _html
    m = re.search(r'<table class="content-table".*?</table>', page, re.S)
    if not m:
        return {}
    out = {}
    for tr in re.findall(r"<tr.*?</tr>", m.group(0), re.S):
        cells = [_html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 2:
            continue
        key = _key(cells[0], YAHOO_NAMES)
        if not key:
            continue
        text = cells[1]
        mm = re.match(r"^(.+?) \((.+?)\)(?: - (.+))?$", text)
        name, inner, tail = (mm.group(1), mm.group(2), mm.group(3)) if mm else (text, "", "")
        team = CODES.get(inner, inner if inner in CODES.values() else "")
        detail = re.sub(r"\s*\(\d[^)]*\)$", "", tail or "").strip() if team or not inner else inner
        out[key] = {"name": name.strip(), "team": team, "detail": detail}
    return out


def merged_awards(wiki_page, yahoo_page=""):
    """Wikipedia's awards, with Yahoo's filling what Wikipedia lacks (the Final's Player of the Match and any award not yet in its table); on a clash Wikipedia's name stands."""
    y, w = yahoo_awards(yahoo_page or ""), end_awards(wiki_page)
    got = {**y, **w}
    for k, v in w.items():                       # Wikipedia's name stands, Yahoo's detail ('172 dot balls') is kept
        if k in y and y[k].get("detail") and not v.get("detail"):
            got[k] = {**v, "detail": y[k]["detail"]}
    return {k: got[k] for k in ORDER if k in got}


def caps_html(st, limit=3):
    """Two small tables, 'Orange Cap · most runs' in orange and 'Purple Cap · most wickets' in purple (D: they are named after colours), the top `limit` of each. No gold
    here: Sunrisers Hyderabad's gold row is for the official league table only."""
    out = ""
    for key, title, unit, tone in (("runs", "Orange Cap · most runs", "Runs", "orange"), ("wickets", "Purple Cap · most wickets", "Wkts", "purple")):
        rows = st.get(key, [])[:limit]
        if not rows:
            continue
        out += r.compact(r.table(title, [(unit, True), ("Player", False), ("Team", False)], [[n, who, team] for n, who, team in rows]), (22, 52, 26), f" caps {tone}")
    return out


def closing_html(m):
    """The IPL's closing note from ESPN's own final (a finished match whose heading is 'Final'): 'That's IPL 2026. Royal Challengers Bengaluru are champions, winning
    the final by 5 wickets.' '' when the match is not a finished final or has no winner."""
    from kickoff import cricket
    teams, number = cricket.heading(m)
    status = (m.get("status") or "").strip()
    won = re.match(r"(.+?) won by (.+)$", status)
    if number.lower() != "final" or not m.get("matchEnded") or not won:
        return ""
    year = re.search(r"\b(20\d\d)\b", m.get("name", ""))
    text = f"That's IPL {year.group(1) if year else ''}".replace("IPL ", "IPL ").rstrip() + f". {won.group(1)} are champions, winning the final by {cricket.short_result(status).split(' won by ')[-1]}."
    return f"<p>{r.esc(text)}</p>"


def extras_for(year, wiki):
    """extras_fn for cricket.run: for the 'IPL' league, the cap leaders and, on the morning the final is reported, the closing note (said once: state['closed'] holds the
    year). Every part is on its own: a page that is down or changed gives no caps and nothing else is lost."""
    def go(label, matches, state):
        if label != "IPL":
            return "", state
        html, state = "", dict(state)
        try:
            html += caps_html(stats(wiki.wikitext(season_page(year))))
        except Exception:
            pass
        for m in matches:
            note = closing_html(m)
            if note and state.get("closed") != year:
                html += note
                state["closed"] = year
        return html, state
    return go


def awards_block(year, state, wiki, title="IPL Awards", yahoo_page=""):
    """(html, state): the end-of-season awards as an Awards table, newest first, the first morning the Wikipedia page (or the Yahoo article, when settings.IPL_AWARDS_URLS has one
    for the year and the caller passes its page) has them: MVP, Orange Cap, Purple Cap, Emerging Player, Super Striker, Most Sixes, Most Fours, Dot Balls, Best Catch, Fair Play and the
    final's Player of the Match. Said once per award; a later one joins the table. state is kickoff.awards' state."""
    from kickoff import awards
    items = []
    for key, v in merged_awards(wiki.wikitext(season_page(year)), yahoo_page).items():
        items.append({"key": f"ipl:{key}", "label": key, "sig": v["name"], "kind": "single", "data": v,
                      "text": f"{v['name']} ({v['team']})" if v["team"] else v["name"]})
    new_state, new = awards.update(state or {}, year, items)
    return (awards.table_html(title, new_state["rows"]) if new else ""), new_state
