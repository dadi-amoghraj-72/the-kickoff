"""Athletics and swimming: only what is worth a look (D, 2026-11-08). Not every meet, only:
  athletics  a world record (anywhere), a world lead or meeting/championship record at a top meet, and a close finish in a running final at a top meet
  swimming   a world record (long or short course, individual or relay)
  both       a youth record: the official World U20 record in athletics, the world junior record in swimming (D, 2026-11-08)

Sources, all public Wikipedia pages (no keys; the results bodies' own data services are not public): the official world-record lists, whose rows carry the date each
record was set; the season's Diamond League calendar and each meeting's page (every final in full: place, athlete, mark, and the official notes WR/WL/MR/SB copied from
the result sheets); and the championships' pages (the medal summary: gold, silver and bronze with marks and notes). Volunteers fill these pages, usually within hours, so a
line can come a morning late, never wrong: a page or row that cannot be read gives nothing.

Top meets: the Diamond League, the World Championships, World Indoor Championships, European Championships, European Indoor Championships, the Olympics, the Commonwealth Games
and the Asian Games. A close finish (D's margins): 1st to 2nd within 0.03s up to 400m (and the 4x100m), 0.5s for 800m to 1500m (and the 4x400m), 1.5s for anything longer."""
import re
from datetime import date, timedelta

from kickoff.majors import COUNTRY

WINDOW = timedelta(days=3)                 # a record or a final is news for three days (a skipped morning is caught up); each is said once
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
MON3 = {m[:3]: i for m, i in MONTHS.items()}

# (page title with {y}, the short name after the city, the months it can be on)
CHAMPIONSHIPS = [("{y} World Athletics Championships", "World Championships", {8, 9}),
                 ("{y} World Athletics Indoor Championships", "World Indoor Championships", {2, 3}),
                 ("{y} European Athletics Championships", "European Championships", {6, 7, 8}),
                 ("{y} European Athletics Indoor Championships", "European Indoor Championships", {2, 3}),
                 ("Athletics at the {y} Summer Olympics", "Olympics", {7, 8}),
                 ("Athletics at the {y} Commonwealth Games", "Commonwealth Games", {7, 8}),
                 ("Athletics at the {y} Asian Games", "Asian Games", {9, 10})]
DL_MONTHS = {4, 5, 6, 7, 8, 9}
WR_PAGES = [("athletics", "List of world records in athletics", "World record"), ("swimming", "List of world records in swimming", "World record"),
            ("athletics", "List of world under-20 records in athletics", "World U20 record"),          # youth records too (D, 2026-11-08): the official under-20 records
            ("swimming", "List of world junior records in swimming", "World junior record")]


# ---- Reading wikitext ---------------------------------------------------------------------------------

def plain(text):
    """Wikitext to plain text: links to their label, templates and refs gone, bold and italics gone."""
    text = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text or "", flags=re.S)
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"\{\{#invoke:sort\|name\|([^|}]+)\|([^|}]+)[^}]*\}\}", r"\1 \2", text)
    text = re.sub(r"\{\{(?:nowrap|right|small|sort\|[^|}]*)\|([^{}]*)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"'{2,}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def notes_of(text):
    """The official notes on a mark: {{AthAbbr|WR}}, {{AthAbbr|WL}}, {{AthAbbr|MR}}, {{AthAbbr|CR|...}} -> {"WR", "WL", "MR", "CR"}."""
    return set(re.findall(r"\{\{AthAbbr\|([A-Z]{1,3})", text or ""))


def seconds(mark):
    """A running time in seconds ('9.77', '1:41.86', '12:58.30', '2:06:30'), or None for a distance, points or anything else."""
    m = re.fullmatch(r"(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)", (mark or "").strip())
    if not m or "." not in mark and ":" not in mark:
        return None
    parts = [float(x) for x in m.groups() if x is not None]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def metres(event):
    """The race distance in metres from an event name ('200 metres', '3000 metres steeplechase', '4 × 400 metres relay', 'Marathon'), or None for a field event."""
    e = event.lower()
    if "marathon" in e:
        return 42195
    if "race walk" in e or "kilometres" in e:
        km = re.search(r"([\d.]+)\s*kilomet", e)
        return int(float(km.group(1)) * 1000) if km else 20000
    relay = re.search(r"4\s*[x×]\s*(\d+)", e)
    if relay:
        return int(relay.group(1))                      # a relay is judged by its leg: 4x100 like a sprint, 4x400 like an 800
    m = re.search(r"([\d,]+)\s*met(?:re|er)s?", e) or re.search(r"\b([\d,]+)\s*m\b", e)
    if m:
        return int(m.group(1).replace(",", ""))
    if re.search(r"\bmile\b", e):
        return 1609
    return None


def margin_needed(distance):
    """D's close-finish margins: 0.03s up to 400m, 0.5s for 800m to 1500m (the mile too), 1.5s for anything longer."""
    return 0.03 if distance <= 400 else 0.5 if distance <= 1609 else 1.5


def short_event(event, sex):
    """'Men's 200m', 'Women's 3000m steeplechase', 'Men's pole vault'."""
    e = re.sub(r"\s*metres?\b|(?<=\d) m\b", "m", event.strip(), flags=re.I)
    e = re.sub(r"(\d),(\d)", r"\1\2", e)
    e = e[:1].lower() + e[1:] if not re.match(r"\d", e) else e
    return f"Mixed {e}" if sex == "Mixed" else f"{sex}' {e}" if sex.endswith("s") else f"{sex}'s {e}" if sex else e


def show_mark(mark, event):
    """A field event's mark with its unit ('6.30m'); a time or points as they are."""
    mark = re.sub(r"\s*m$", "", (mark or "").strip())
    return f"{mark}m" if metres(event) is None and re.fullmatch(r"\d+\.\d+", mark) and not re.search(r"athlon", event, re.I) else mark


# ---- A Diamond League meeting page: every final in full ------------------------------------------------------

def meeting_finals(wikitext):
    """[{"sex", "event", "rows": [(place, athlete, mark, notes)]}] from a meeting page's results tables (=== Men's === / === Women's ===, one table per event)."""
    out, sex = [], ""
    for part in re.split(r"(^===?\s*(?:Men|Women)[^=]*===?\s*$)", wikitext, flags=re.M):
        head = re.match(r"^===?\s*(Men|Women)", part)
        if head:
            sex = head.group(1)
            continue
        if not sex:
            continue
        for table in re.findall(r"\{\|.*?\n\|\}", part, re.S):
            cap = re.search(r"^\|\+\s*(.+)$", table, re.M)
            if not cap:
                continue
            head_cells = [plain(h).lower() for h in re.findall(r"^!(?:[^|\n]*\|)?\s*(.+)$", table, re.M)]
            if "athlete" not in head_cells or not any(h in head_cells for h in ("time", "mark", "result", "height", "distance", "points")):
                continue
            col_mark = next(i for i, h in enumerate(head_cells) if h in ("time", "mark", "result", "height", "distance", "points"))
            col_ath = head_cells.index("athlete")
            col_place = head_cells.index("place") if "place" in head_cells else 0
            col_notes = head_cells.index("notes") if "notes" in head_cells else None
            rows = []
            for row in table.split("\n|-")[1:]:
                cells = [c.strip() for c in re.findall(r"^\|(?!\+|-|\})\s*(.*)$", row, re.M)]
                cells = [re.sub(r"^align=\"?\w+\"?\s*\|\s*", "", c) for c in cells]
                if len(cells) <= max(col_mark, col_ath) or "sortbottom" in row:
                    continue
                pl = cells[col_place]
                place = 1 if "Gold1" in pl else 2 if "Silver2" in pl else 3 if "Bronze3" in pl else int(pl) if pl.isdigit() else None
                rows.append((place, plain(cells[col_ath]), plain(cells[col_mark]), notes_of(cells[col_notes]) if col_notes is not None and col_notes < len(cells) else set()))
            out.append({"sex": sex, "event": plain(cap.group(1)), "rows": rows})
    return out


# ---- A championship page: the medal summary -----------------------------------------------------------------

def medal_finals(wikitext):
    """[{"sex", "event", "rows": [(place, athlete, mark, notes)]}] from the '== Medal summary ==' tables: each event then gold, silver and bronze with mark and notes."""
    i = wikitext.find("Medal summary")
    if i < 0:
        return []
    out, sex = [], ""
    body = wikitext[i:]
    end = re.search(r"^==[^=]", body[20:], re.M)
    body = body[:20 + end.start()] if end else body
    for part in re.split(r"(^===?\s*(?:Men|Women|Mixed)[^=]*===?\s*$)", body, flags=re.M):
        head = re.match(r"^===?\s*(Men|Women|Mixed)", part)
        if head:
            sex = head.group(1)
            continue
        for block in part.split("\n|-")[1:]:
            ev = re.search(r"\{\{(?:EventLink|AthleticsLink)\|([^|}]+)", block) or re.search(r"^\|\s*\[\[(?:[^|\]]*\|)?([^\]]+)\]\]\s*$", block, re.M)
            if not ev:
                continue
            medals = re.findall(r"^\|\s*(.*?)\s*\|\|\s*(.+)$", block, re.M)
            rows = []
            for n, (who, rest) in enumerate(medals[:3], 1):
                mark = re.match(r"\s*([\d:.,]+)", plain(rest))
                team = re.search(r"\{\{flag\w*team\|([A-Z]{3})", who, re.I)
                name = COUNTRY.get(team.group(1), team.group(1)) if team else plain(re.sub(r"\{\{(?:FlagIOC2medalist|Flag medalist)\|(.*?)\|[A-Z]{3}(?:\|[^}]*)?\}\}", r"\1", who))
                rows.append((n, name, mark.group(1) if mark else "", notes_of(rest)))
            if rows:
                out.append({"sex": sex, "event": plain(ev.group(1)), "rows": rows})
    return out


# ---- What is worth a line --------------------------------------------------------------------------------------

def findings(finals, meet, record_word="meeting record"):
    """[(kind, text, uid)] for one meet: kind 'wr' (a world record), 'close' (a close finish), 'mark' (a world lead and/or the meet's record)."""
    out = []
    for f in finals:
        rows = [x for x in f["rows"] if x[0]]
        if not rows:
            continue
        rows.sort(key=lambda x: x[0])
        ev = short_event(f["event"], f["sex"])
        for place, who, mark, notes in rows:
            if "WR" in notes:
                out.append(("wr", f"World record: {who}, {ev}, {show_mark(mark, f['event'])} ({meet})", wr_uid(ev, mark)))
        first = rows[0]
        marks = [w for w, k in (("world lead", "WL"), (record_word, "MR"), (record_word, "CR")) if k in first[3]]
        if marks and "WR" not in first[3]:
            out.append(("mark", f"{meet} · {ev}: {first[1]} {show_mark(first[2], f['event'])}, " + " and ".join(dict.fromkeys(marks)), f"mark:{meet}:{ev}"))
        dist = metres(f["event"])
        if dist and len(rows) >= 2 and rows[1][0] == 2:
            a, b = seconds(first[2]), seconds(rows[1][2])
            if a is not None and b is not None and 0 <= b - a <= margin_needed(dist) + 1e-9:
                out.append(("close", f"{meet} · {ev} final: {surname(first[1])} {first[2]}, {surname(rows[1][1])} {rows[1][2]}", f"close:{meet}:{ev}"))
    return out


def wr_uid(event, mark):
    """One id for one record however it is written ('6.31' at the meeting, '6.31 m' on the list), so it is said once."""
    return f"wr:{event.lower()}:{re.sub(r'[^0-9.:]', '', mark)}"


def surname(name):
    parts = name.split()
    return parts[-1] if parts else name


# ---- The calendars -------------------------------------------------------------------------------------------

def dl_meetings(wikitext, year):
    """[(page title, city, last day)] from the season page's calendar table: '[[2025 Memorial Van Damme|13]]', '{{Sort|08-22|22 August}}', '[[Brussels]]'."""
    out = []
    for row in wikitext.split("\n|-"):
        page = re.search(r"\[\[(\d{4} [^|\]]+)\|\d+\]\]", row)
        when = re.search(r"\{\{Sort\|(\d{2})-(\d{1,2})\|([^}]*)\}\}", row)
        if not (page and when):
            continue
        cells = re.findall(r"^\|\s*(.*)$", row, re.M)
        city = plain(cells[4]) if len(cells) > 4 else ""            # Leg, Date, Meet, Stadium, City, Country
        month, day_ = int(when.group(1)), int(when.group(2))
        span = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})", when.group(3))
        last = int(span.group(2)) if span else day_
        try:
            out.append((page.group(1), city, date(year, month, last)))
        except ValueError:
            continue
    return out


def champ_dates_city(wikitext, year):
    """(last day, host city) from a championship page's infobox ('| dates = 13–21 September', '| host city = [[Tokyo]], Japan'), or (None, '')."""
    d = re.search(r"^\|\s*dates?\s*=\s*(.+)$", wikitext, re.M | re.I)
    c = re.search(r"^\|\s*(?:host[_ ]city|city|venue)\s*=\s*(.+)$", wikitext, re.M | re.I)
    city = plain(c.group(1)).split(",")[0].strip() if c else ""
    if not d:
        return None, city
    t = plain(d.group(1))
    m = re.findall(r"(\d{1,2})\s+([A-Za-z]{3,})", t)
    if not m:
        return None, city
    day_, month = m[-1]
    try:
        return date(year, MON3[month[:3].lower()], int(day_)), city
    except (KeyError, ValueError):
        return None, city


# ---- World-record lists ------------------------------------------------------------------------------------

def recent_records(sport, wikitext, today, label="World record"):
    """[(text, uid)] for the world records on the official list set in the last three days. Athletics: the table rows ({{#invoke:dts|main|12 Mar 2026}}); swimming: the
    {{swimmingrecord ...}} entries (long course, then short course)."""
    out, rec_label = [], label
    if sport == "swimming":
        course = ""
        for chunk in re.split(r"(^==\s*(?:Long|Short) course[^=]*==\s*$)", wikitext, flags=re.M | re.I):
            hc = re.match(r"^==\s*(Long|Short)", chunk, re.I)
            if hc:
                course = "long course" if hc.group(1) == "Long" else "short course"
                continue
            if not course:
                continue
            sex = ""
            for part in re.split(r"(^===\s*(?:Men|Women|Mixed|Boys|Girls)[^=]*===\s*$)", chunk, flags=re.M):
                hs = re.match(r"^===\s*(Men|Women|Mixed|Boys|Girls)", part)
                if hs:
                    sex = hs.group(1)
                    continue
                for rec in re.findall(r"\{\{[Ss]wimmingrecord(.*?)\n?\}\}(?=\s*(?:\{\{[Ss]wimmingrecord|\{\{|\|\}|$))", part, re.S):
                    f = {k.strip(): v.strip() for k, v in re.findall(r"\|\s*(\w+)\s*=\s*((?:[^|{}\[\]]|\{\{[^{}]*\}\}|\[\[[^\]]*\]\])*)", rec)}
                    when = _parse_date(plain(f.get("date", "")))
                    if not when or not (timedelta(0) <= today - when <= WINDOW):
                        continue
                    who = plain(f.get("chinesename") or "") or f"{plain(f.get('firstname', ''))} {plain(f.get('lastname', ''))}".strip() or plain(f.get("club", ""))
                    ev = plain(f.get("event", ""))
                    meet = ", ".join(x for x in (plain(f.get("meet", "")), plain(f.get("city", ""))) if x)
                    label_ = short_event(ev, sex) if sex else ev
                    out.append((f"{rec_label}: {who}, {label_} ({course}), {plain(f.get('time', ''))}" + (f" ({meet})" if meet else ""), f"wr:swim:{rec_label}:{course}:{label_}:{plain(f.get('time', ''))}"))
        return out
    if label != "World record":                            # the under-20 list: a plain table (Event, Record, Athlete, Nationality, Date, Meet, Place), outdoor then indoor
        return u20_records(wikitext, today, label)
    i = wikitext.find("==World records==")
    j = wikitext.find("==World best performances==")
    body = wikitext[i:j if j > i else None] if i >= 0 else ""
    sex = ""
    for part in re.split(r"(^===\s*(?:Men|Women|Mixed)\s*===\s*$)", body, flags=re.M):
        hs = re.match(r"^===\s*(Men|Women|Mixed)", part)
        if hs:
            sex = hs.group(1)
            continue
        for row in part.split("\n|-"):
            d = re.search(r"\{\{#invoke:dts\|main\|([^}|]+)\}\}", row)
            ev = re.search(r"\{\{#invoke:sort\|sort\|[^|]*\|\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", row)
            if not (d and ev and sex):
                continue
            when = _parse_date(d.group(1))
            if not when or not (timedelta(0) <= today - when <= WINDOW):
                continue
            mark = re.search(r"\{\{nowrap\|([\d:.,]+\s*(?:m|pts)?)\}\}", row) or re.search(r"\|\s*([\d:.]+)\s*$", row, re.M)
            who = re.search(r"\{\{#invoke:sort\|name\|([^|}]+)\|([^|}]+)", row)
            cells = [c.strip() for c in re.findall(r"^\|(?!-)\s*(.*)$", row, re.M)]
            di = next((k for k, c in enumerate(cells) if "#invoke:dts" in c), None)
            meet = plain(cells[di + 1]) if di is not None and di + 1 < len(cells) else ""
            city = plain(cells[di + 2]) if di is not None and di + 2 < len(cells) else ""
            mk = show_mark((mark.group(1) if mark else "").replace(" ", ""), plain(ev.group(1)))
            name = f"{who.group(1)} {who.group(2)}" if who else "?"
            e = short_event(plain(ev.group(1)), sex if sex != "Mixed" else "")
            where = ", ".join(x for x in (meet, city) if x)
            out.append((f"World record: {name}, {e}, {mk}" + (f" ({where})" if where else ""), wr_uid(e, mk)))
    return out


def u20_records(wikitext, today, label):
    """[(text, uid)] for the under-20 records set in the last three days: each row's date is a plain '16 June 2026'; the event cell can span two rows."""
    out, sex, event = [], "", ""
    for part in re.split(r"(^===\s*(?:Men|Women|Mixed)\s*===\s*$)", wikitext, flags=re.M):
        hs = re.match(r"^===\s*(Men|Women|Mixed)", part)
        if hs:
            sex = hs.group(1)
            continue
        for row in part.split("\n|-"):
            cells = [c.strip() for c in re.findall(r"^\|(?![-+}])\s*(.*)$", row, re.M)]
            cells = [re.sub(r'^(?:rowspan|style|align)="?[^|]*\|\s*', "", c) for c in cells]
            di = next((k for k, c in enumerate(cells) if re.fullmatch(r"\d{1,2} [A-Z][a-z]+ \d{4}", plain(c))), None)
            if di is None or di < 3 or not sex:
                if cells and di is None and len(cells) > 3:
                    event = plain(cells[0])
                continue
            if di >= 4:
                event = plain(cells[di - 4])
            when = _parse_date(plain(cells[di]))
            if not when or not (timedelta(0) <= today - when <= WINDOW) or "background:pink" in row:
                continue
            mark = re.match(r"\s*([\d:.,]+)", plain(cells[di - 3]))
            who, meet = plain(cells[di - 2]), plain(cells[di + 1]) if di + 1 < len(cells) else ""
            e = short_event(event, sex if sex != "Mixed" else "")
            mk = show_mark(mark.group(1) if mark else "", event)
            out.append((f"{label}: {who}, {e}, {mk}" + (f" ({meet})" if meet else ""), "u20:" + wr_uid(e, mk)))
    return out


def _parse_date(text):
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,})\.?\s+(\d{4})", text or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), MON3[m.group(2)[:3].lower()], int(m.group(1)))
    except (KeyError, ValueError):
        return None


# ---- The morning -------------------------------------------------------------------------------------------

def run(source, today, fails=None):
    """{"athletics": [(kind, text, uid)], "swimming": [(kind, text, uid)]} for the morning of `today` (a date in Singapore). source.wikitext(title) -> '' when missing.
    A page that fails is skipped and counted in `fails`; nothing raises."""
    fails = fails if fails is not None else []
    got = {"athletics": [], "swimming": []}
    for sport, title, label in WR_PAGES:
        try:
            got[sport] += [("wr" if label == "World record" else "youth", t, u) for t, u in recent_records(sport, source.wikitext(title), today, label)]
        except Exception:
            fails.append(title)
    year = today.year
    pages = []
    if today.month in DL_MONTHS:
        try:
            for page, city, last in dl_meetings(source.wikitext(f"{year} Diamond League"), year):
                if timedelta(0) <= today - last <= WINDOW:
                    pages.append((page, f"{city} Diamond League", "meeting record", meeting_finals))
        except Exception:
            fails.append(f"{year} Diamond League")
    for title, short, months in CHAMPIONSHIPS:
        if today.month not in months:
            continue
        t = title.format(y=year)
        try:
            text = source.wikitext(t)
            if not text:
                continue
            last, city = champ_dates_city(text, year)
            if last and -timedelta(days=12) <= today - last <= WINDOW:      # a championship's results are read while it is on (up to 12 days) and three days after
                got["athletics"] += findings(medal_finals(text), f"{city} {short}".strip(), "championship record")
        except Exception:
            fails.append(t)
    for page, meet, word, parse in pages:
        try:
            got["athletics"] += findings(parse(source.wikitext(page)), meet, word)
        except Exception:
            fails.append(page)
    seen, out = set(), {"athletics": [], "swimming": got["swimming"]}
    for k, t, u in sorted(got["athletics"], key=lambda x: {"wr": 0, "close": 1, "mark": 2, "youth": 3}[x[0]]):
        if u.startswith("wr:"):
            key = u.lower()
            if key in seen:
                continue
            seen.add(key)
        out["athletics"].append((k, t, u))
    return out
