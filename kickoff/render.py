"""Turns edition data into web pages. Standard library only."""
import html
import json
import math
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
DATA_DIR = ROOT / "data" / "editions"
DOCS_DIR = ROOT / "docs"
WORDS_PER_MINUTE = 230

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Josefin+Sans:wght@400;600;700&family=Newsreader:wght@600&display=swap\">"
)

SUN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
       'stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
       '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')
MOON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>')


class Raw(str):
    """Text that is already HTML (a cell with a gold span in it): esc() leaves it as it is."""


def dash(text):
    """A score or a range written with a hyphen between digits gets the en dash ('3-2' -> '3–2', '2026-27' -> '2026–27'): one dash in every score the page shows (D, 2026-11-05). Records (W-L) are written
    without it by their own modules."""
    return re.sub(r"(?<=\d)-(?=\d)", "\u2013", text)


def esc(text):
    return str(text) if isinstance(text, Raw) else html.escape(str(text), quote=True)


# ---- Building blocks used inside sections -------------------------------------------------

def table(caption, columns, rows, zones=None, legend=None, row_classes=None):
    """columns: [(label, is_number)]. rows: list of lists. zones: per-row 'blue'/'lilac'/'rose'/None.
    legend: [(zone, text)] shown under the table."""
    head = "".join(f'<th class="{"n" if num else ""}">{esc(label)}</th>' for label, num in columns)
    body = []
    for i, row in enumerate(rows):
        zone = zones[i] if zones and zones[i] else None
        classes = ([f"z-{zone}"] if zone else []) + ((row_classes[i] or "").split() if row_classes else [])
        cells = "".join(f'<td class="{"n" if columns[j][1] else ""}">{esc(v)}</td>' for j, v in enumerate(row))
        body.append(f'<tr class="{" ".join(classes)}">{cells}</tr>' if classes else f"<tr>{cells}</tr>")
    out = (f'<div class="table-wrap"><table><caption>{esc(caption)}</caption>'
           f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>")
    if legend:
        items = "".join(f'<li><i class="z-{z}"></i>{esc(t)}</li>' for z, t in legend)
        out += f'<ul class="legend">{items}</ul>'
    return out


def series_head(title, left, right, left_n, right_n, word, sub=""):
    """The top of a series table: the title, then each side's name centred over its own big score, the word between the scores ('series', 'aggregate') with
    a small line under it ('best of 5'). The two names sit in boxes of equal width either side of a fixed gap, and so do the two scores, so each score is
    directly under its name; a name too long for its box wraps and stays centred."""
    gap = '<span class="gap"></span>'
    mid = f'<span class="gap"><span class="lab">{esc(word)}</span>' + (f'<span class="bo">{esc(sub)}</span>' if sub else "") + "</span>"
    return (f'<tr><th class="tt" colspan="3">{esc(title)}</th></tr>'
            f'<tr class="sh"><th colspan="3"><div class="hd"><span class="tn">{esc(left)}</span>{gap}<span class="tn">{esc(right)}</span></div></th></tr>'
            f'<tr class="sc"><th colspan="3"><div class="hd"><span class="ws">{esc(left_n)}</span>{mid}<span class="ws">{esc(right_n)}</span></div></th></tr>')


def series_table(title, left, right, left_n, right_n, word, rows, cls="", sub=""):
    """A series-style table (the house pattern for anything played in several games: NBA playoff series, two-legged ties, Test series): a title row,
    the two sides' names, their running score in large numbers either side of `word` ('series', 'aggregate'), then one row per game made in
    advance. rows: [{"mid": text between the scores, "a": left score or None, "b": right score or None, "win": "a" | "b" | None,
    "notes": [html lines under the game], "pre": True for a game still to play (one centred line)}]. sub: the small line under the word ('best of 5')."""
    body = []
    for x in rows:
        notes = x.get("notes") or []
        if x.get("pre"):
            body.append(f'<tr class="one end pre"><td class="mid" colspan="3">{esc(x["mid"])}</td></tr>')
            continue
        w = lambda side: " w" if x.get("win") == side else ""  # noqa: E731
        body.append(f'<tr class="one{"" if notes else " end"}"><td class="aw{w("a")}">{esc(x["a"])}</td><td class="mid">{esc(x["mid"])}</td><td class="hm{w("b")}">{esc(x["b"])}</td></tr>')
        if notes:
            body.append('<tr class="note end"><td colspan="3">' + "".join(f'<div class="pl"><span class="t">{n}</span></div>' for n in notes) + "</td></tr>")
    head = series_head(title, left, right, left_n, right_n, word, sub)
    return (f'<div class="nflsb nbaone ser{" " + cls if cls else ""}"><table><colgroup><col style="width:30%"><col style="width:40%"><col style="width:30%"></colgroup>'
            f'<thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>')


def move(n):
    """Places moved since the last table shown: ▲n up, ▼n down, – level."""
    return "–" if not n else (f"▲{n}" if n > 0 else f"▼{-n}")


def compact(html, widths, extra=""):
    """Wrap a table from table() in the compact fixed-layout style (even column widths in per cent): the caption becomes a centred title
    row across the top of the table, and the widths go in a colgroup because a fixed layout reads them from the first row (the title)."""
    cols = "".join(f'<col style="width:{w}%">' for w in widths)
    html = re.sub(r"<caption>(.*?)</caption><thead>", lambda m: f'<colgroup>{cols}</colgroup><thead><tr><th class="tt" colspan="{len(widths)}">{m.group(1)}</th></tr>', html, count=1)
    return f'<div class="pts f1{extra}">{html}</div>'


def on_today(items):
    """items: [(kind 'up'|'overnight', time text, description)]."""
    rows = []
    for kind, when, what in items:
        icon, label = (SUN, "While you're up") if kind == "up" else (MOON, "Overnight")
        rows.append(f'<li><time>{esc(when)}</time><span>{what}</span>'
                    f'<span class="tag">{icon}{label}</span></li>')
    return f'<ul class="today">{"".join(rows)}</ul>'


def standouts(lines):
    return '<ol class="standouts">' + "".join(f"<li>{line}</li>" for line in lines) + "</ol>"


def join_names(names):
    """'A', 'A and B', 'A, B and C'."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


def summary_box(items):
    """The small summary box above a scoreboard (the same in football, the NFL and any sport that wants one): rows of a label, a highlighted figure, some
    text and a small second line. items: [(label, figure, text, sub)]; '' when there are none."""
    rows = ""
    for label, fig, text, sub in items:
        figure = '<span class="n">' + esc(fig) + "</span> " if fig else ""
        under = f'<span class="sub">{esc(sub)}</span>' if sub else ""
        rows += f'<li><span class="lbl">{esc(label)}</span><span class="who">{figure}{esc(text)}{under}</span></li>'
    return f'<ul class="roundup">{rows}</ul>' if rows else ""


def potd(title, text):
    return f'<div class="potd"><span class="label">Performance of the Day</span><strong>{esc(title)}</strong><p>{text}</p></div>'


def no_data(sport=None):
    who = f"{sport}: " if sport else ""
    return f'<p><span class="nodata">{esc(who)}No data this morning</span></p>'


def _name_variants(names):
    """The names to bold: each full name, plus its first word when that is unambiguous (so 'LASK' for 'LASK Linz'
    and 'Sporting' for 'Sporting CP', but not 'Manchester' when City and United both appear, or a bare 'Real')."""
    names = {n for n in names if n}
    firsts = {}
    for n in names:
        firsts.setdefault(n.split()[0], set()).add(n)
    variants = set(names)
    for first, owners in firsts.items():
        if len(owners) == 1 and len(first) >= 4 and first.lower() not in {"real", "club", "city", "united", "inter", "sporting cp"}:
            variants.add(first)
    return variants


def _person_variants(people):
    """Each player's full name and his surname (the last word, when it is four letters or more and no other player shares it): 'Viktor Gy\u00f6keres' and 'Gy\u00f6keres'."""
    people = {p.strip() for p in people if p and p.strip()}
    lasts = {}
    for p in people:
        lasts.setdefault(p.split()[-1], set()).add(p)
    return people | {last for last, owners in lasts.items() if len(owners) == 1 and len(last) >= 4}


def bold_names(text, names, people=()):
    """Escape a note for the page and put the given team names (and, with `people`, the players' names) in bold, wherever they appear."""
    out = esc(text)
    for name in sorted(_name_variants(names) | _person_variants(people), key=len, reverse=True):
        out = re.sub(rf"(?<![\w>]){re.escape(esc(name))}(?![\w<])", lambda m: f"<strong>{m.group(0)}</strong>", out)
    return out


def link(url, text):
    return f'<a href="{esc(url)}" rel="noopener">{esc(text)}</a>'


# ---- Pages --------------------------------------------------------------------------------

def nice_date(iso):
    d = date.fromisoformat(iso)
    return f"{d:%A} {d.day} {d:%B %Y}"


def word_count(fragment):
    return len(re.sub(r"<[^>]+>", " ", fragment).split())


def _page(title, topbar, body, script=""):
    css = (STATIC / "style.css").read_text()
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '<meta name="robots" content="noindex, nofollow">'
        '<meta name="color-scheme" content="dark light">'
        f"<title>{esc(title)}</title>{FONTS}<style>{css}</style></head><body>"
        f"{topbar}{body}{script}</body></html>"
    )


def _masthead(dateline):
    return ('<header class="masthead"><h1>The Kickoff</h1><div class="rule"></div>'
            f'<p class="dateline">{esc(dateline)}</p></header>')


def render_edition(ed):
    sections = ed["sections"]
    n = len(sections)
    total_words = sum(word_count(s["html"]) for s in sections)
    minutes = max(1, math.ceil(total_words / WORDS_PER_MINUTE))
    home = ed.get("home", "../../index.html")
    topbar = (f'<div class="topbar"><a href="{home}">Archive</a>'
              f'<span class="chip" id="chip">{minutes} min read</span></div>')
    banner = (f'<p class="banner">{esc(ed["banner"])}</p>' if ed.get("banner") else
              ('<p class="banner">Dummy edition. Everything below is placeholder text to test the '
               "design. No real scores or news.</p>") if ed.get("dummy") else "")
    secs = "".join(f'<section id="{esc(s["id"])}"><h2>{esc(s["title"])}</h2>{s["html"]}</section>'
                   for s in sections)
    ticks = "".join(
        f'<a class="rail-tick" href="#{esc(s["id"])}" style="top:{i / n * 100:.2f}%" '
        f'aria-label="Jump to {esc(s["title"])}" title="{esc(s["title"])}"></a>'
        for i, s in enumerate(sections))
    rail = f'<nav class="rail" aria-label="Sections"><div class="rail-fill" id="rail-fill"></div>{ticks}</nav>'
    end = '<div class="theend"><span class="ln"></span><b>The End</b><span class="ln"></span></div>'        # a gold line, "The End", a gold line (D, 2026-11-05)
    footer = f'<footer><a href="{home}">All editions</a> · The Kickoff, your daily sports digest.</footer>'
    body = f"<main>{_masthead(nice_date(ed['date']))}{banner}{secs}{end}{footer}</main>{rail}"
    script = f"<script>{(STATIC / 'rail.js').read_text()}</script>"
    return _page(f"The Kickoff · {nice_date(ed['date'])}", topbar, body, script)


def render_archive(editions):
    items = []
    for ed in sorted(editions, key=lambda e: e["date"], reverse=True):
        tag = " (dummy)" if ed.get("dummy") else ""
        first = esc(ed["headlines"][0]) if ed.get("headlines") else ""
        items.append(f'<li><a class="d" href="editions/{esc(ed["date"])}/index.html">'
                     f'{esc(nice_date(ed["date"]))}{tag}</a><span class="muted">{first}</span></li>')
    listing = f'<ul class="archive">{"".join(items)}</ul>' if items else "<p>No editions yet.</p>"
    body = f"<main>{_masthead('Archive')}<section style=\"border-top:0;margin-top:24px\">{listing}</section></main>"
    return _page("The Kickoff · Archive", "", body)


def load_editions(data_dir=None):
    return [json.loads(p.read_text()) for p in sorted((data_dir or DATA_DIR).glob("*.json"))]


def build_site(data_dir=None, docs_dir=None):
    """Write every edition page plus the archive into docs/ (or docs_dir). Returns the edition dates."""
    docs_dir = docs_dir or DOCS_DIR
    editions = load_editions(data_dir)
    for ed in editions:
        out = docs_dir / "editions" / ed["date"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(render_edition(ed))
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "index.html").write_text(render_archive(editions))
    return [e["date"] for e in editions]
