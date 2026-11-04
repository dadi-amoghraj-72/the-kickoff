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
GOLD_TEAMS = {"SRH"}           # D: Sunrisers Hyderabad's row in gold, in every IPL table


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


def end_awards(text):
    """{"MVP": (player, team code), "Emerging": (...)} from the 'End of season awards' table once it is on the page, else {}."""
    out = {}
    for t in honours.tables(text):
        if t["caption"].lower().startswith("end of season awards"):
            for row in t["rows"]:
                c = row["cells"]
                if len(c) >= 4:
                    who, club = honours.link_text(c[2]), honours.link_text(c[3]) or ""
                    if who and c[0].lower().startswith("most valuable player"):
                        out["MVP"] = (who, CODES.get(club, club))
                    elif who and c[0].lower().startswith("emerging player"):
                        out["Emerging"] = (who, CODES.get(club, club))
    return out


def caps_html(st, limit=3):
    """Two small tables, 'Orange Cap · most runs' and 'Purple Cap · most wickets', the top `limit` of each, Sunrisers Hyderabad's row in gold."""
    out = ""
    for key, title, unit in (("runs", "Orange Cap · most runs", "Runs"), ("wickets", "Purple Cap · most wickets", "Wkts")):
        rows = st.get(key, [])[:limit]
        if not rows:
            continue
        body = [[n, who, team] for n, who, team in rows]
        classes = ["hl" if team in GOLD_TEAMS else "" for _, _, team in rows]
        out += r.compact(r.table(title, [(unit, True), ("Player", False), ("Team", False)], body, row_classes=classes), (22, 52, 26), " caps")
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


def awards_block(year, state, wiki, title="IPL Awards"):
    """(html, state): the end-of-season awards (Most Valuable Player and Emerging Player) as a one-off Awards table the first morning the Wikipedia page has them.
    state is kickoff.awards' state; the year is the IPL season (the table is simply absent before the final)."""
    from kickoff import awards
    items = []
    got = end_awards(wiki.wikitext(season_page(year)))
    for key, label in (("MVP", "MVP"), ("Emerging", "Emerging")):
        if key in got:
            who, team = got[key]
            items.append({"key": f"ipl:{key}", "label": label, "sig": who, "kind": "single", "data": {"name": who, "team": team}, "text": f"{who} ({team})"})
    new_state, new = awards.update(state or {}, year, items)
    return (awards.table_html(title, new_state["rows"]) if new else ""), new_state
