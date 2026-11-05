"""Badminton (checkpoint 12, D's rules of 2026-11-05): the BWF Super 1000 events (All England, Malaysia Open, Indonesia Open, China Open), the World Championships, the World Tour Finals, the
Singapore Open and the India Open, read from each event's Wikipedia draw pages.

What is shown, in this order (D):
  1. at the start of an event, who from India and Southeast Asia (and the top three seeds of the men's and the women's singles) is in the draw;
  2. in the early rounds, ONE short line for each match that involves one of those players, win or lose ("First round: Lakshya Sen (IND) beat X 21-15, 21-18");
  3. from the semi-finals on, EVERY match of the five disciplines in a table (two rows a match, a column for each game, the winner in bold) and the final the same way.
The players: India, Singapore, Malaysia, Indonesia, Thailand, the Philippines, Vietnam, Brunei, Cambodia, Myanmar, Laos and Timor-Leste; doubles count as much as singles. The top three seeds
of each singles draw stand for the top three ranked players (BWF's own ranking page blocks scripts; the seeds follow the ranking at entry, so the list revolves by itself).
Each match is shown once (state), when its page has the scores; Wikipedia can lag by a day, in which case the news feeds give a headline and the table follows. A page laid out differently gives
nothing, never a wrong line."""
import re
from datetime import timedelta

from kickoff import majors
from kickoff import render as r

SPOT = {"IND": "India", "SGP": "Singapore", "MAS": "Malaysia", "INA": "Indonesia", "IDN": "Indonesia", "THA": "Thailand", "PHI": "Philippines", "VIE": "Vietnam", "BRU": "Brunei",
        "CAM": "Cambodia", "KHM": "Cambodia", "MYA": "Myanmar", "LAO": "Laos", "TLS": "Timor-Leste"}
DISCIPLINES = ("Men's singles", "Women's singles", "Men's doubles", "Women's doubles", "Mixed doubles")
SINGLES = ("Men's singles", "Women's singles")
CODE = {"Men's singles": "MS", "Women's singles": "WS", "Men's doubles": "MD", "Women's doubles": "WD", "Mixed doubles": "XD"}
LATE = ("Semi-finals", "Final")
# (event name, titles to try ({y} = the year), months it can be on (with a margin)): Wikipedia's draw page of each event
CALENDAR = [
    ("All England Open", ["{y} All England Open"], {3, 4}),
    ("Malaysia Open", ["{y} Malaysia Open (badminton)", "{y} Malaysia Open"], {1, 2}),
    ("India Open", ["{y} India Open (badminton)", "{y} India Open"], {1, 2}),
    ("Indonesia Open", ["{y} Indonesia Open (badminton)", "{y} Indonesia Open"], {6, 7}),
    ("Singapore Open", ["{y} Singapore Open (badminton)", "{y} Singapore Open"], {5, 6, 7}),
    ("China Open", ["{y} China Open (badminton)", "{y} China Open"], {7, 8, 11, 12}),      # July in 2025, November in 2024
    ("BWF World Championships", ["{y} BWF World Championships"], {8, 9}),
    ("BWF World Tour Finals", ["{y} BWF World Tour Finals"], {12, 1}),
]
MONTHS = majors.MONTHS


# ---- Reading a draw page --------------------------------------------------------------------------

def balanced(text, start):
    """The text of the {{ ... }} template that opens at `start`."""
    depth, j = 0, start
    while j < len(text):
        if text.startswith("{{", j):
            depth += 1
            j += 2
        elif text.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                return text[start:j]
        else:
            j += 1
    return text[start:]


def side(cell):
    """{"names": [...], "flag": 'IND' or '', "bold": bool} from a bracket cell: names are the wiki links, the flag the first flag template."""
    names = []
    for m in re.finditer(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", cell):
        n = re.sub(r"\s*\([^)]*\)$", "", m.group(1).strip())      # the link's target is the full name ('Lakshya Sen'); the display text in a first round is abbreviated ('L Sen')
        if n and not n.startswith(("File:", "Image:")):
            names.append(n)
    flags = re.findall(r"\{\{(?:flagicon|flag)\|([A-Z]{3})", cell)
    return {"names": names, "flag": flags[0] if flags else "", "bold": "'''" in cell}


def matches_of(block):
    """[{"round", "a", "b", "games", "winner"}] for every played match of one bracket template (RD1, RD2 ... with team1, team2 ... and scores)."""
    f = {m.group(1): m.group(2).strip() for m in re.finditer(r"^[ \t]*\|[ \t]*(RD\d+(?:-[a-z]+\d+(?:-\d+)?)?)[ \t]*=[ \t]*(.*?)[ \t]*$", block, re.M)}
    out = []
    for rd in sorted({int(k[2:].split("-")[0]) for k in f if k.startswith("RD")}):
        title = f.get(f"RD{rd}", "")
        k = 1
        while f.get(f"RD{rd}-team{k}") is not None and f.get(f"RD{rd}-team{k + 1}") is not None:
            a, b = side(f[f"RD{rd}-team{k}"]), side(f[f"RD{rd}-team{k + 1}"])
            games, wa, wb = [], 0, 0
            for g in (1, 2, 3):
                x, y = re.sub(r"[']", "", f.get(f"RD{rd}-score{k}-{g}", "")).strip(), re.sub(r"[']", "", f.get(f"RD{rd}-score{k + 1}-{g}", "")).strip()
                if x.isdigit() and y.isdigit():
                    games.append((int(x), int(y)))
                    wa, wb = wa + (int(x) > int(y)), wb + (int(y) > int(x))
            if a["names"] and b["names"] and games and (wa >= 2 or wb >= 2 or a["bold"] != b["bold"]):
                win = "a" if (wa > wb if wa != wb else a["bold"]) else "b"
                out.append({"round": title, "a": a, "b": b, "games": games, "winner": win, "retired": max(wa, wb) < 2})
            k += 2
    return out


def entrants(block):
    """The sides named in the first round of a bracket (played or not yet), for the 'who is in the draw' note."""
    out = []
    for m in re.finditer(r"^[ \t]*\|[ \t]*RD1-team\d+[ \t]*=[ \t]*(.*?)[ \t]*$", block, re.M):
        s = side(m.group(1))
        if s["names"]:
            out.append(s)
    return out


def parse(w):
    """{discipline: {"seeds": [(name, flag)] in seed order, "matches": [...]}} from a whole event page. Only the five disciplines' sections are read."""
    out = {}
    for sec in re.split(r"(?m)^== ", w)[1:]:
        title = sec.split("==", 1)[0].strip()
        if title not in DISCIPLINES:
            continue
        seeds = []
        sm = re.search(r"=== Seeds ===(.*?)(?=^===? |\Z)", sec, re.S | re.M)
        for line in (sm.group(1) if sm else "").split("\n"):
            if re.match(r"^\s*#", line):
                s = side(line)
                if s["names"]:
                    seeds.append((" / ".join(s["names"]), s["flag"]))
        seen, matches, field = set(), [], []
        for t in re.finditer(r"\{\{\d+TeamBracket-Tennis3", sec):
            block = balanced(sec, t.start())
            field += entrants(block)
            for m in matches_of(block):
                key = (m["round"], tuple(m["a"]["names"]), tuple(m["b"]["names"]))
                if key not in seen:
                    seen.add(key)
                    matches.append(m)
        out[title] = {"seeds": seeds, "matches": matches, "field": field}
    return out


# ---- Choosing and showing -----------------------------------------------------------------------------

def label(s):
    """'Lakshya Sen (IND)' or 'Kim Won-ho / Seo Seung-jae (KOR)'."""
    return " / ".join(s["names"]) + (f" ({s['flag']})" if s["flag"] else "")


def top_seeds(parsed, n=3):
    """{(discipline): set of names} for the top n seeds of each singles draw (stand for the top ranked players)."""
    return {d: {name for name, _ in parsed.get(d, {}).get("seeds", [])[:n]} for d in SINGLES}


def interesting(m, disc, tops):
    """A match involves an Indian or Southeast Asian player, or one of the top three singles seeds."""
    for s in (m["a"], m["b"]):
        if s["flag"] in SPOT or (disc in SINGLES and " / ".join(s["names"]) in tops.get(disc, set())):
            return True
    return False


def mid(m):
    return "|".join([m["round"], " / ".join(m["a"]["names"]), " / ".join(m["b"]["names"])])


def score_text(m):
    games = m["games"] if m["winner"] == "a" else [(y, x) for x, y in m["games"]]
    return ", ".join(f"{x}–{y}" for x, y in games) + (" (retired)" if m.get("retired") else "")


def lost_line(m):
    """From the loser's side when the player of interest lost: 'First round: Lakshya Sen (IND) lost to X (JPN) 15–21, 18–21'."""
    win, lose = (m["a"], m["b"]) if m["winner"] == "a" else (m["b"], m["a"])
    games = m["games"] if m["winner"] == "b" else [(y, x) for x, y in m["games"]]
    return f"{m['round']}: {label(lose)} lost to {label(win)} " + ", ".join(f"{x}–{y}" for x, y in games) + (" (retired)" if m.get("retired") else "")


def line(m):
    win, lose = (m["a"], m["b"]) if m["winner"] == "a" else (m["b"], m["a"])
    if lose["flag"] in SPOT and win["flag"] not in SPOT:
        return lost_line(m)
    return f"{m['round']}: {label(win)} beat {label(lose)} " + score_text(m)


def draw_note(parsed, tops):
    """Who is in the draw, as [{"head": 'India', "rows": [('MS', 'Lakshya Sen, Prannoy H. S.'), ('WS', ...)]}]: India first, the other countries alphabetically, then the top singles seeds."""
    by_country = {}
    for disc in DISCIPLINES:
        entered = [(" / ".join(s["names"]), s["flag"]) for s in parsed.get(disc, {}).get("field", [])] + list(parsed.get(disc, {}).get("seeds", []))
        for name, flag in entered:
            if flag in SPOT:
                names = by_country.setdefault(SPOT[flag], {}).setdefault(CODE[disc], [])
                if name not in names:
                    names.append(name)
    join = lambda names: ("; " if any(" / " in n for n in names) else ", ").join(names)  # noqa: E731      pairs are separated by a semicolon so a pair is never read as two players
    out = [{"head": c, "rows": [(CODE[d], join(by_country[c][CODE[d]])) for d in DISCIPLINES if CODE[d] in by_country[c]]} for c in sorted(by_country, key=lambda c: (c != "India", c))]
    seeds = []
    for d in SINGLES:
        order = [name for name, _ in parsed.get(d, {}).get("seeds", [])]
        names = sorted(tops.get(d, []), key=lambda n: order.index(n) if n in order else 9)
        if names:
            seeds.append((CODE[d], ", ".join(names)))
    if seeds:
        out.append({"head": "Top seeds", "rows": seeds})
    return out


def note_text(note):
    """The draw note as plain lines ('India: MS Lakshya Sen, Prannoy H. S.; WS ...') for tests and logs."""
    return [f"{x['head']}: " + "; ".join(f"{c} {names}" for c, names in x["rows"]) for x in note]


def late_table(disc, rnd, matches):
    """One table: two rows a match (the winner above, in bold), a column for each of up to three games."""
    rows = ""
    for m in matches:
        win, lose = (m["a"], m["b"]) if m["winner"] == "a" else (m["b"], m["a"])
        wg = m["games"] if m["winner"] == "a" else [(y, x) for x, y in m["games"]]
        for is_w, s in ((True, win), (False, lose)):
            cells = "".join(f'<td class="s">{(g[0] if is_w else g[1])}</td>' for g in wg) + "".join('<td class="s"></td>' for _ in range(3 - len(wg)))
            names = "<br>".join(r.esc(n) for n in s["names"]) + (f' <span class="muted">{r.esc(s["flag"])}</span>' if s["flag"] else "") + (' <span class="muted">ret.</span>' if m.get("retired") and not is_w else "")
            rows += f'<tr class="{"w" if is_w else "l"}"><td class="pl">{names}</td>{cells}</tr>'
    return (f'<div class="tennis"><table><colgroup><col style="width:64%"><col style="width:12%"><col style="width:12%"><col style="width:12%"></colgroup><thead><tr><th class="tt" colspan="4">'
            f'{r.esc(disc)} · {r.esc(rnd)}</th></tr></thead><tbody>{rows}</tbody></table></div>')


def event_html(name, parsed, new_matches, note_lines, tops):
    """The event's block: the draw note (first time), one line for each new early-round match of interest, then the tables of the new semi-finals and final."""
    out = ""
    early = [(d, m) for d in DISCIPLINES for m in new_matches.get(d, []) if m["round"] not in LATE and interesting(m, d, tops)]
    if note_lines:
        items = "".join(f"<li><strong>{r.esc(x['head'])}</strong>" + "".join(f"<br>{r.esc(c)}: {r.esc(names)}" for c, names in x["rows"]) + "</li>" for x in note_lines)
        out += f"<p class=\"subhead\">{r.esc(name)}: who is in the draw</p><ul class=\"standouts\">{items}</ul>"
    if early:
        out += f"<p class=\"subhead\">{r.esc(name)}</p>" + '<ul class="standouts">' + "".join(f"<li>{r.esc(line(m))}</li>" for _, m in early) + "</ul>"
    for rnd in LATE:
        for d in DISCIPLINES:
            ms = [m for m in new_matches.get(d, []) if m["round"] == rnd]
            if ms:
                out += late_table(d, f"{name} · {rnd}", ms)
    return out


# ---- The run ----------------------------------------------------------------------------------------------

def span(box_dates, year):
    """(start, end) dates from an infobox date text, or (None, None)."""
    end = majors.end_date(box_dates, year)
    text = re.sub(r"\{\{[^|}]*\||[{}]|<[^>]+>|&nbsp;", " ", box_dates or "")
    m = re.search(r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?", text)
    start = None
    if m and m.group(3).lower() in MONTHS:
        from datetime import date
        try:
            start = date(int(m.group(4) or year), MONTHS[m.group(3).lower()], int(m.group(1)))
        except ValueError:
            pass
    return start or end, end


def run(wiki, today, state, fails=None):
    """{"lines": [], "blocks": [html], "state"}: for every event of the calendar that is on (the day before its start to two days after its end): the draw note once, new early-round lines of
    interest and new semi-final and final tables, each match once. wiki.wikitext(title) -> text ('' when missing). state: {event title: {"seen": [match ids], "noted": bool}}."""
    st = {k: {"seen": list(v.get("seen", [])), "noted": bool(v.get("noted"))} for k, v in (state or {}).items()}
    blocks = []
    for name, titles, months in CALENDAR:
        years = {today.year} | ({today.year + 1} if today.month >= 11 and 1 in months else set())
        if today.month not in months:
            continue
        for year in sorted(years):
            text, title = "", None
            for t in [x.format(y=year) for x in titles]:
                try:
                    text = wiki.wikitext(t)
                except Exception:
                    (fails if fails is not None else []).append("badminton")
                    continue
                if text:
                    title = t
                    break
            if not text:
                continue
            try:
                box = majors.infobox(text)
                start, end = span(box.get("dates") or box.get("date"), year)
                if not start or not end or not (start - timedelta(days=1) <= today <= end + timedelta(days=2)):
                    continue
                parsed = parse(text)
                if not parsed:
                    continue
                tops = top_seeds(parsed)
                mine = st.setdefault(title, {"seen": [], "noted": False})
                new = {}
                for d, info in parsed.items():
                    fresh = [m for m in info["matches"] if mid(m) not in mine["seen"] and (m["round"] in LATE or interesting(m, d, tops))]
                    if fresh:
                        new[d] = fresh
                note = [] if mine["noted"] else draw_note(parsed, tops)
                html = event_html(name, parsed, new, note, tops)
                if html:
                    blocks.append((title, html))
                    mine["noted"] = mine["noted"] or bool(note)
                    mine["seen"] += [mid(m) for ms in new.values() for m in ms]
                elif note:
                    mine["noted"] = True
                mine["seen"] = mine["seen"][-400:]
            except Exception:
                (fails if fails is not None else []).append("badminton")
    return {"blocks": blocks, "state": dict(list(st.items())[-12:])}
