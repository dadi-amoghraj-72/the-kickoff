"""The major events of the sports without a proper data feed, read from Wikipedia's free API (checkpoint 12, second pass, 2026-11-05).

A calendar of the events in SPEC.md ("Around the sporting world") says which Wikipedia pages to look at and in which months (so a quiet month costs no requests). The infobox with a champion
(darts, handball, field hockey, chess, women's football: "winner", "champion" or "champions") is understood, tested on real 2025 pages. Badminton has its own module (kickoff/badminton.py).
An event is reported once, when its end date has passed (within the last three days) and a champion is there. Volunteers edit these pages and sometimes rename them: a page that is missing or laid out differently gives nothing, never a wrong line."""
import re
from datetime import date, timedelta

WINDOW = timedelta(days=3)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
SPOT_FLAGS = {"IND": "India", "SGP": "Singapore", "MAS": "Malaysia", "INA": "Indonesia", "IDN": "Indonesia", "THA": "Thailand", "PHI": "Philippines", "VIE": "Vietnam"}
COUNTRY = {"NED": "Netherlands", "DEN": "Denmark", "ARG": "Argentina", "AUS": "Australia", "BEL": "Belgium", "ENG": "England", "ESP": "Spain", "GER": "Germany", "IND": "India", "FRA": "France",
           "NOR": "Norway", "SWE": "Sweden", "CRO": "Croatia", "EGY": "Egypt", "POR": "Portugal", "SLO": "Slovenia", "ISL": "Iceland", "KOR": "South Korea", "JPN": "Japan", "CHN": "China",
           "MAS": "Malaysia", "INA": "Indonesia", "THA": "Thailand", "SGP": "Singapore", "PHI": "Philippines", "VIE": "Vietnam", "USA": "United States", "CAN": "Canada", "NZL": "New Zealand",
           "RSA": "South Africa", "ITA": "Italy", "BRA": "Brazil", "HUN": "Hungary", "SRB": "Serbia", "POL": "Poland", "AUT": "Austria", "SUI": "Switzerland", "CZE": "Czech Republic",
           "PAK": "Pakistan", "IRL": "Ireland", "SCO": "Scotland", "WAL": "Wales", "JOR": "Jordan", "QAT": "Qatar", "BHR": "Bahrain", "TPE": "Chinese Taipei", "HKG": "Hong Kong"}
# (sport key, event name, [page titles to try, {y} the year], months it can be on (with a margin), layout)
CALENDAR = [
    ("darts", "PDC World Championship", ["{y} PDC World Darts Championship"], {12, 1, 2}, "infobox"),
    ("darts", "World Matchplay", ["{y} World Matchplay"], {7, 8}, "infobox"),
    ("darts", "Grand Slam of Darts", ["{y} Grand Slam of Darts"], {11, 12}, "infobox"),
    ("darts", "Premier League Darts", ["{y} Premier League Darts"], {5, 6}, "infobox"),
    ("chess", "World Chess Championship", ["World Chess Championship {y}"], {11, 12, 4, 5}, "infobox"),
    ("chess", "Candidates Tournament", ["{y} Candidates Tournament"], {3, 4, 5}, "infobox"),
    ("chess", "Chess Olympiad", ["{y} Chess Olympiad"], {9, 10}, "infobox"),
    ("chess", "Women's World Chess Championship", ["Women's World Chess Championship {y}"], {6, 7, 8, 9}, "infobox"),
    ("chess", "Tata Steel Chess Tournament", ["Tata Steel Chess Tournament {y}"], {1, 2}, "infobox"),
    ("chess", "Norway Chess", ["{y} Norway Chess", "Norway Chess {y}"], {5, 6, 7}, "infobox"),
    ("hockey", "Men's FIH Hockey World Cup", ["{y} Men's FIH Hockey World Cup", "{y} FIH Men's Hockey World Cup"], {1, 8, 9}, "infobox"),
    ("hockey", "Women's FIH Hockey World Cup", ["{y} Women's FIH Hockey World Cup", "{y} FIH Women's Hockey World Cup"], {8, 9}, "infobox"),
    ("hockey", "Men's Hockey Asia Cup", ["{y} Men's Hockey Asia Cup"], {8, 9, 10}, "infobox"),
    ("hockey", "Women's Hockey Asia Cup", ["{y} Women's Hockey Asia Cup"], {9, 10, 11}, "infobox"),
    ("handball", "World Men's Handball Championship", ["{y} World Men's Handball Championship"], {1, 2}, "infobox"),
    ("handball", "World Women's Handball Championship", ["{y} World Women's Handball Championship"], {11, 12}, "infobox"),
    ("handball", "European Men's Handball Championship", ["{y} European Men's Handball Championship"], {1, 2}, "infobox"),
    ("handball", "European Women's Handball Championship", ["{y} European Women's Handball Championship"], {11, 12}, "infobox"),
    ("womens-football", "UEFA Women's Euro", ["UEFA Women's Euro {y}"], {7, 8}, "infobox"),
    ("womens-football", "FIFA Women's World Cup", ["{y} FIFA Women's World Cup"], {7, 8, 9}, "infobox"),
]


# ---- Reading wikitext ---------------------------------------------------------------------------

def infobox(w):
    """The first infobox as {field: raw text}; {} without one. Nested templates inside values are kept as they are."""
    i = w.find("{{Infobox")
    if i < 0:
        i = w.find("{{infobox")
    if i < 0:
        return {}
    depth, j = 0, i
    while j < len(w):
        if w.startswith("{{", j):
            depth += 1
            j += 2
        elif w.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                break
        else:
            j += 1
    out, field, buf, depth = {}, None, [], 0
    for line in w[i + 2:j - 2].split("\n")[1:]:
        m = re.match(r"^\s*\|\s*([\w\- ]+?)\s*=\s*(.*)$", line) if depth == 0 else None
        if m:
            if field:
                out[field] = " ".join(buf).strip()
            field, buf = m.group(1).strip().lower(), [m.group(2)]
        elif field:
            buf.append(line)
        depth += line.count("{{") - line.count("}}")
    if field:
        out[field] = " ".join(buf).strip()
    return out


def name_of(text):
    """A person's or a team's name from a cell of wikitext: the first wiki link's display text, else a country code in a flag template ('{{fhw|NED}}'), else the plain text."""
    m = re.search(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", text)
    if m:
        return re.sub(r"\s*\((?:badminton|darts player|chess|handball|field hockey)[^)]*\)$", "", (m.group(2) or m.group(1)).strip())
    codes = re.findall(r"\b([A-Z]{3})\b", re.sub(r"<[^>]+>", "", text))
    if codes:
        return COUNTRY.get(codes[-1], codes[-1])
    t = re.sub(r"[{}'\[\]]|<[^>]+>|&nbsp;", " ", text)
    return re.sub(r"\s+", " ", t).strip()


def end_date(dates, title_year):
    """The last day of an event from its infobox date text ('8–16 November 2025', '15 December 2024 – {{nowrap|3 January 2025}}', '9–17 August'); None when unreadable."""
    text = re.sub(r"\{\{[^|}]*\||[{}]|<[^>]+>|&nbsp;", " ", dates or "")
    found = re.findall(r"(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?", text)
    found = [(int(d), MONTHS[m.lower()], int(y) if y else None) for d, m, y in found if m.lower() in MONTHS]
    if not found:
        found = [(int(d), MONTHS[m.lower()], int(y) if y else None) for m, d, y in re.findall(r"([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?", text) if m.lower() in MONTHS]
    if not found:
        return None
    d, m, y = found[-1]
    try:
        return date(y or title_year, m, d)
    except ValueError:
        return None


def champion_of(box):
    for key in ("winner", "champion", "champions", "gold", "winners"):
        v = box.get(key, "")
        if v and not re.search(r"\b(tbd|tba|vacant|none)\b", v, re.I) and not v.startswith("<!--"):
            return name_of(v)
    return None


# ---- The run ------------------------------------------------------------------------------------

def candidates(today):
    """The calendar entries to look at today: (sport, name, titles, layout, year) for the current month (and next year's titles in November and December for events that run into January)."""
    out = []
    for sport, name, titles, months, layout in CALENDAR:
        if today.month in months:
            years = {today.year}
            if today.month >= 11 and 1 in months:
                years.add(today.year + 1)             # the PDC World Championship of December is titled with the next year
            for y in sorted(years):
                out.append((sport, name, [t.format(y=y) for t in titles], layout, y))
    return out


def run(wiki, today, fails=None):
    """[(sport key, line, unique id, link)] for the events that ended in the last three days with a champion on their page. wiki.wikitext(title) -> text ('' when missing)."""
    lines = []
    for sport, name, titles, layout, year in candidates(today):
        text = ""
        for t in titles:
            try:
                text = wiki.wikitext(t)
            except Exception:
                (fails if fails is not None else []).append(sport)
                continue
            if text:
                title = t
                break
        if not text:
            continue
        link = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
        try:
            box = infobox(text)
            end = end_date(box.get("dates") or box.get("date"), year)
            champ = champion_of(box)
            if end and champ and timedelta(0) <= today - end <= WINDOW:
                lines.append((sport, f"{name} {year}: {champ} won", f"maj:{title}", link))
        except Exception:
            (fails if fails is not None else []).append(sport)
    return lines
