"""The UFC rankings table (D, 2026-11-05): once a month, from UFC.com's own rankings page (which UFC updates every Tuesday).

The men's and the women's pound-for-pound lists (the top 10 of each) and, for each of the 11 divisions, the champion and the next two (#1 and #2). Every name carries how far it moved since the table was
last shown (▲n, ▼n, – for no change, NEW for a name that was not in that list before; a new champion is NEW), so the monthly table is also a "who moved" view. A new champion is also visible at once in
the title-fight box of the fights; the table is not repeated after every event (twice a month it would be the same names).

When: on the first Wednesday of the month (Singapore time; UFC's Tuesday update is then in), or the first edition after it when that one was missed; once a month. State: {"month", "snapshot"}."""
import html as htmllib
import re
from datetime import date, timedelta

from kickoff import render as r

P4P = ("Men's Pound-for-Pound", "Women's Pound-for-Pound")
MEN = ("Flyweight", "Bantamweight", "Featherweight", "Lightweight", "Welterweight", "Middleweight", "Light Heavyweight", "Heavyweight")
WOMEN = ("Women's Strawweight", "Women's Flyweight", "Women's Bantamweight")
DIVISIONS = MEN + WOMEN
# D's order (2026-11-05): all the men's first (the men's pound-for-pound, then the eight weight classes from the lightest), a break, then the women's (the women's pound-for-pound, then their three classes)
ORDER = (P4P[0], *MEN, P4P[1], *WOMEN)
P4P_ROWS = 10
DIVISION_ROWS = 2        # the champion and #1 and #2


def clean(text):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


def parse(page):
    """{"Flyweight": {"champion": 'Joshua Van', "ranks": ['Alexandre Pantoja', ...]}, "Men's Pound-for-Pound": {"champion": top rank, "ranks": [...]}} from UFC.com's rankings page. The page repeats its blocks
    for the phone layout; the first of each is used."""
    out = {}
    for m in re.finditer(r'<div class="view-grouping-header">(.*?)</div>\s*<div class="view-grouping-content">(.*?)(?=<div class="view-grouping">|\Z)', page, re.S):
        name = clean(re.sub(r"<span>.*?</span>", "", m.group(1)))
        if name in out or not name:
            continue
        champ = re.search(r"<h5><a[^>]*>([^<]+)</a>", m.group(2))
        rows = re.findall(r'weight-class-rank">\s*(\d+)\s*</td>\s*<td class="views-field views-field-title"><a[^>]*>([^<]+)</a>', m.group(2))
        if champ and rows:
            out[name] = {"champion": clean(champ.group(1)), "ranks": [clean(n) for _, n in rows]}
    return out


def updated(page):
    """'Tuesday, Nov. 03' from the page's own 'updated:' line, or ''."""
    m = re.search(r"updated: ([A-Za-z]+, [A-Za-z.]+ \d+)", page)
    return m.group(1) if m else ""


def listing(groups):
    """The names shown for each list, in order: {"Men's Pound-for-Pound": [10 names], "Flyweight": [champion, #1, #2], ...}."""
    out = {}
    for name in ORDER:
        if name in groups:
            out[name] = groups[name]["ranks"][:P4P_ROWS] if name in P4P else [groups[name]["champion"]] + groups[name]["ranks"][:DIVISION_ROWS]
    return out


def move(name, before, now_index, champion_slot=False):
    """How a name moved since the list was last shown: '▲2', '▼1', '–', or 'NEW' (not in the old list; a changed champion)."""
    if before is None:
        return ""
    if name not in before:
        return "NEW"
    delta = before.index(name) - now_index
    return f"▲{delta}" if delta > 0 else f"▼{-delta}" if delta < 0 else "–"


def due(today, state):
    """True on the first Wednesday of a month, or the first edition after it when that one was missed, once a month."""
    key = f"{today.year}-{today.month:02d}"
    first = date(today.year, today.month, 1)
    first_wed = first + timedelta(days=(2 - first.weekday()) % 7)
    return (state or {}).get("month") != key and today >= first_wed


def table_html(lists, before):
    """One compact table: a sub-heading for each list, then its names with the rank (C for a champion) and the move."""
    rows, classes = [], []
    for name, names in lists.items():
        if name == P4P[1]:                       # the break between the men's and the women's
            rows.append(["", "", ""])
            classes.append("gap")
        rows.append(["", name, ""])
        classes.append("sub")
        old = (before or {}).get(name)
        for i, n in enumerate(names):
            champion = name in DIVISIONS and i == 0
            rows.append(["C" if champion else str(i + 1 - (0 if name in P4P else 1)), n, move(n, old, i)])
            classes.append("")
    html = r.table("UFC rankings", [("#", False), ("Fighter", False), ("Move", True)], rows, row_classes=classes)
    return r.compact(html, [12, 66, 22], " ufcrank")


def run(source, today, state, fails=None):
    """{"blocks": [html], "state"}. today: the edition's date in Singapore. source.ufc_rankings_page() -> UFC.com's rankings page html. Shown once a month (see `due`)."""
    state = dict(state or {})
    if not due(today, state):
        return {"blocks": [], "state": state}
    try:
        page = source.ufc_rankings_page()
        lists = listing(parse(page))
    except Exception:
        (fails if fails is not None else []).append("ufc")
        return {"blocks": [], "state": state}
    if len(lists) < len(P4P) + len(DIVISIONS):
        return {"blocks": [], "state": state}                 # a page laid out differently: nothing rather than a half table
    when = updated(page)
    head = f'<p class="subhead">UFC rankings{" · updated " + r.esc(when) if when else ""}</p>'
    return {"blocks": [head + table_html(lists, state.get("snapshot"))], "state": {"month": f"{today.year}-{today.month:02d}", "snapshot": lists}}
