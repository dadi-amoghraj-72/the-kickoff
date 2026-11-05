"""Badminton (checkpoint 12, D's rules of 2026-11-05, revised the same day after he saw the demo): the BWF World Tour Super 1000 events (All England, Malaysia Open, Indonesia Open, China Open), the
World Championships, the World Tour Finals, the Singapore Open and the India Open, read from each event's Wikipedia draw pages.

What is shown (D):
  1. a one-line notice in the week before an event: "All England Open (BWF World Tour Super 1000) starts on Tuesday 11 March" (no list of who is in the draw: it was too long to read);
  2. in the early rounds, the matches that involve a player from India or Southeast Asia, or one of the top three seeds of the men's and of the women's singles, grouped by discipline in the fixed order
     men's singles, women's singles, men's doubles, women's doubles, mixed doubles, each group titled with its discipline and round, each match one bullet in ONE standard form, whoever the players are:
     the winner first, in bold, with his country, then "def." and the loser ("Lakshya Sen (IND) def. Jonatan Christie (INA) 21-13, 21-10");
  3. from the semi-finals on, every match of the five disciplines in a table (two rows a match, the winner above and bold, a column for each game), and the final the same way.
Round names are the official ones (Round of 32, Round of 16, Quarter-finals, Semi-finals, Final), worked out from the draw's shape, not copied from Wikipedia's "First round".
The countries: India, Singapore, Malaysia, Indonesia, Thailand, the Philippines, Vietnam, Brunei, Cambodia, Myanmar, Laos and Timor-Leste; doubles count as much as singles. The top three seeds of each
singles draw stand for the top three ranked players (BWF's own ranking page blocks scripts; the seeds follow the ranking at entry, so the list revolves by itself).
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
LATE = ("Semi-finals", "Final")
ROUND_ORDER = ["Round of 64", "Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]
NOTICE_DAYS = 7
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
    """{"names": [...], "flag": 'IND' or '', "bold": bool} from a bracket cell: names are the wiki links' targets (the full names), the flag the first flag template."""
    names = []
    for m in re.finditer(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", cell):
        n = re.sub(r"\s*\([^)]*\)$", "", m.group(1).strip())      # the link's target is the full name ('Lakshya Sen'); the display text in a first round is abbreviated ('L Sen')
        if n and not n.startswith(("File:", "Image:")):
            names.append(n)
    flags = re.findall(r"\{\{(?:flagicon|flag)\|([A-Z]{3})", cell)
    return {"names": names, "flag": flags[0] if flags else "", "bold": "'''" in cell}


def official_rounds(titles):
    """{RD number: official name} for one bracket. Wikipedia calls the early rounds 'First round', 'Second round'; the official names count back from the quarter-finals: the round before them is the
    Round of 16, before that the Round of 32, then the Round of 64. A bracket with no quarter-finals (the finals bracket) keeps its names."""
    order = sorted(titles)
    names = [titles[i] for i in order]
    out = {i: titles[i] for i in order}
    if "Quarter-finals" in names:
        q = names.index("Quarter-finals")
        for idx, i in enumerate(order):
            if idx < q:
                out[i] = f"Round of {16 * 2 ** (q - 1 - idx)}"
    return out


def matches_of(block):
    """[{"round", "a", "b", "games", "winner", "retired"}] for every played match of one bracket template (RD1, RD2 ... with team1, team2 ... and scores)."""
    f = {m.group(1): m.group(2).strip() for m in re.finditer(r"^[ \t]*\|[ \t]*(RD\d+(?:-[a-z]+\d+(?:-\d+)?)?)[ \t]*=[ \t]*(.*?)[ \t]*$", block, re.M)}
    rounds = sorted({int(k[2:].split("-")[0]) for k in f if k.startswith("RD")})
    names = official_rounds({rd: f.get(f"RD{rd}", "") for rd in rounds})
    out = []
    for rd in rounds:
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
                out.append({"round": names[rd], "a": a, "b": b, "games": games, "winner": win, "retired": max(wa, wb) < 2})
            k += 2
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
        seen, matches = set(), []
        for t in re.finditer(r"\{\{\d+TeamBracket-Tennis3", sec):
            for m in matches_of(balanced(sec, t.start())):
                key = (m["round"], tuple(m["a"]["names"]), tuple(m["b"]["names"]))
                if key not in seen:
                    seen.add(key)
                    matches.append(m)
        seed_of = {name: i for i, (name, _) in enumerate(seeds, 1)}          # the Seeds list is in seed order (1, 2, 3 ...)
        for m in matches:
            for k in ("a", "b"):
                m[k] = {**m[k], "seed": seed_of.get(" / ".join(m[k]["names"]))}
        out[title] = {"seeds": seeds, "matches": matches}
    return out


def level_of(text):
    """'BWF World Tour Super 1000' for a World Tour event page (the page says '... Super 1000 event'), else None (the Finals and the World Championships need no level)."""
    m = re.search(r"\[\[BWF World Tour Super (1000|750|500|300|100)\]\] event", text[:8000])      # 'BWF points system for the BWF World Tour Super 1000 event' (the Finals page only lists other events' levels)
    return f"BWF World Tour Super {m.group(1)}" if m else None


# ---- Choosing and showing -----------------------------------------------------------------------------

def label(s):
    """'Lakshya Sen (IND)', 'Shi Yuqi (CHN) [1]' (the seed in square brackets, as D's figures are) or 'Kim Won-ho / Seo Seung-jae (KOR) [2]'."""
    return " / ".join(s["names"]) + (f" ({s['flag']})" if s["flag"] else "") + (f" [{s['seed']}]" if s.get("seed") else "")


def priority(m):
    """Who D looks at first: Singapore (0), then India (1), then the other listed countries (2, any order), then the rest (3: a top seed against an unlisted player)."""
    def one(s):
        return 0 if s["flag"] == "SGP" else 1 if s["flag"] == "IND" else 2 if s["flag"] in SPOT else 3
    return min(one(m["a"]), one(m["b"]))


def by_priority(matches):
    """The matches with Singapore's first, then India's, then the other Southeast Asian countries', then the rest; otherwise in the order of the draw."""
    return sorted(matches, key=priority)


def top_seeds(parsed, n=3):
    """{discipline: set of names} for the top n seeds of each singles draw (stand for the top ranked players)."""
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


def line(m):
    """The one standard form, whoever the players are: 'Lakshya Sen (IND) def. Jonatan Christie (INA) 21–13, 21–10' (the winner first, always)."""
    win, lose = (m["a"], m["b"]) if m["winner"] == "a" else (m["b"], m["a"])
    return f"{label(win)} def. {label(lose)} {score_text(m)}"


def line_html(m):
    """The same line with the winner in bold."""
    win, lose = (m["a"], m["b"]) if m["winner"] == "a" else (m["b"], m["a"])
    return f"<strong>{r.esc(label(win))}</strong> def. {r.esc(label(lose))} {r.esc(score_text(m))}"


def late_table(disc, rnd, matches):
    """One table: two rows a match (the winner above, in bold), a column for each of up to three games."""
    rows = ""
    for m in matches:
        win, lose = (m["a"], m["b"]) if m["winner"] == "a" else (m["b"], m["a"])
        wg = m["games"] if m["winner"] == "a" else [(y, x) for x, y in m["games"]]
        for is_w, s in ((True, win), (False, lose)):
            cells = "".join(f'<td class="s">{(g[0] if is_w else g[1])}</td>' for g in wg) + "".join('<td class="s"></td>' for _ in range(3 - len(wg)))
            names = ("<br>".join(r.esc(n) for n in s["names"]) + (f' <span class="muted">{r.esc(s["flag"])}</span>' if s["flag"] else "") + (f' <span class="muted">[{s["seed"]}]</span>' if s.get("seed") else "")
                     + (' <span class="muted">ret.</span>' if m.get("retired") and not is_w else ""))
            rows += f'<tr class="{"w" if is_w else "l"}"><td class="pl">{names}</td>{cells}</tr>'
    return (f'<div class="tennis"><table><colgroup><col style="width:64%"><col style="width:12%"><col style="width:12%"><col style="width:12%"></colgroup><thead><tr><th class="tt" colspan="4">'
            f'{r.esc(disc)} · {r.esc(rnd)}</th></tr></thead><tbody>{rows}</tbody></table></div>')


def event_html(name, new_matches, tops, notice=None):
    """The event's block: the notice (first time), then the early-round matches of interest grouped by discipline (fixed order) and round, then the tables of the new semi-finals and final."""
    out = ""
    if notice:
        out += f'<ul class="standouts bd"><li>{r.esc(notice)}</li></ul>'
    groups = ""
    for d in DISCIPLINES:
        mine = by_priority([m for m in new_matches.get(d, []) if m["round"] not in LATE and interesting(m, d, tops)])
        for rnd in ROUND_ORDER:
            ms = [m for m in mine if m["round"] == rnd]
            if ms:
                groups += f'<p class="subhead">{r.esc(d)} · {r.esc(rnd)}</p><ul class="standouts bd">' + "".join(f"<li>{line_html(m)}</li>" for m in ms) + "</ul>"
    if groups:
        out += f'<p class="subhead">{r.esc(name)}</p>' + groups
    for rnd in LATE:
        for d in DISCIPLINES:
            ms = by_priority([m for m in new_matches.get(d, []) if m["round"] == rnd])
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


def notice_text(name, level, start):
    return f"{name}{f' ({level})' if level else ''} starts on {start:%A} {start.day} {start:%B}"


def run(wiki, today, state, fails=None):
    """{"blocks": [(page title, html)], "state"}: for every event of the calendar that is on: the notice once in the week before its start, then from the day before the start to two days after the
    final the new early-round lines of interest and the new semi-final and final tables, each match once. wiki.wikitext(title) -> text ('' when missing).
    state: {page title: {"seen": [match ids], "announced": bool}}."""
    st = {k: {"seen": list(v.get("seen", [])), "announced": bool(v.get("announced") or v.get("noted"))} for k, v in (state or {}).items()}
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
                if not start or not end:
                    continue
                mine = st.setdefault(title, {"seen": [], "announced": False})
                notice = None
                if not mine["announced"] and timedelta(0) < start - today <= timedelta(days=NOTICE_DAYS):
                    notice = notice_text(name, level_of(text), start)
                    mine["announced"] = True
                new, tops = {}, {}
                if start - timedelta(days=1) <= today <= end + timedelta(days=2):
                    parsed = parse(text)
                    tops = top_seeds(parsed)
                    for d, info in parsed.items():
                        fresh = [m for m in info["matches"] if mid(m) not in mine["seen"] and (m["round"] in LATE or interesting(m, d, tops))]
                        if fresh:
                            new[d] = fresh
                html = event_html(name, new, tops, notice)
                if html:
                    blocks.append((title, html))
                    mine["seen"] += [mid(m) for ms in new.values() for m in ms]
                mine["seen"] = mine["seen"][-400:]
            except Exception:
                (fails if fails is not None else []).append("badminton")
    return {"blocks": blocks, "state": dict(list(st.items())[-12:])}
