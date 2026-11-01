"""Cricket: which matches belong in the digest, how they are ranked, and how a result reads.

Scope (from the spec): the 12 Test-playing nations, men's and women's, all formats; the IPL, BBL and The Hundred; and
the women's competitions WPL, WBBL and the women's Hundred. Everything else is left out."""
import re
from datetime import datetime, timedelta, timezone

from kickoff import render as r

TEST_NATIONS = {"australia", "england", "india", "new zealand", "pakistan", "south africa", "sri lanka", "west indies",
                "bangladesh", "zimbabwe", "afghanistan", "ireland"}
# Checked in this order, so "women's" is tested before the men's version of the same name.
LEAGUES = [("WPL", r"women'?s premier league", 50), ("WBBL", r"women'?s big bash", 50), ("Women's Hundred", r"the hundred women|women'?s hundred", 50),
           ("IPL", r"indian premier league", 60), ("BBL", r"big bash league", 60), ("The Hundred", r"the hundred", 60)]
FORMAT = re.compile(r"\b(T20I|ODI|Test|Tri-Series|World Cup|Asia Cup|Ashes|Champions Trophy)\b", re.I)
EXCLUDE = re.compile(r"\b(sixes|unofficial|under[- ]?19|u19|emerging|legends|masters|academy)\b", re.I)
HIGHLIGHT = {"india", "sunrisers hyderabad"}
DURATION = {"t20": timedelta(hours=4), "odi": timedelta(hours=9)}


def strip_women(team):
    return re.sub(r"\s+women$", "", team.strip(), flags=re.I)


def classify(m):
    """{"kind": "international" | "league" | None, "women", "label", "priority"} for a match from the list."""
    name = m.get("name", "")
    teams = m.get("teams") or []
    women = any(re.search(r"\bwomen", t, re.I) for t in teams) or bool(re.search(r"\bwomen'?s\b", name, re.I))
    if EXCLUDE.search(name) or any(re.search(r"\sA$", t) for t in teams):
        return {"kind": None}
    for label, pattern, priority in LEAGUES:
        if re.search(pattern, name, re.I):
            return {"kind": "league", "women": women or label in ("WPL", "WBBL", "Women's Hundred"), "label": label, "priority": priority}
    if m.get("matchType") in ("t20", "odi", "test") and FORMAT.search(name) and any(strip_women(t).lower() in TEST_NATIONS for t in teams):
        is_test = m.get("matchType") == "test"
        return {"kind": "international", "women": women, "label": "Women's international" if women else "International",
                "priority": (95 if women else 100) if is_test else (70 if women else 80)}
    return {"kind": None}


def innings_line(score):
    """'India 191/8 (20)' from a score entry like {'r': 191, 'w': 8, 'o': 20, 'inning': 'India Inning 1'}."""
    team = re.sub(r"\s+Inning\s+\d+$", "", score.get("inning", "")).strip()
    wickets = "" if score.get("w") == 10 else f"/{score.get('w')}"
    overs = score.get("o")
    return f"{team} {score.get('r')}{wickets}" + (f" ({overs:g})" if isinstance(overs, (int, float)) else "")


def started(m):
    return datetime.strptime(m["dateTimeGMT"], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def pick(matches, now, window_start, seen=None, last_status=None):
    """The matches for this edition, most important first, each with its classification.
    - finished matches that ended since the last edition (estimated from the start time and format) and are not seen before;
    - live men's or women's Tests whose status line has changed since last time (each day's play is reported once)."""
    seen, last_status, out = set(seen or ()), last_status or {}, []
    for m in matches:
        c = classify(m)
        if c["kind"] is None:
            continue
        begin = started(m)
        if m.get("matchEnded"):
            ends = begin + DURATION.get(m["matchType"], timedelta(hours=10))
            if m["id"] in seen or not (window_start <= ends <= now):
                continue
        elif m.get("matchStarted") and m["matchType"] == "test" and c["kind"] == "international":
            if last_status.get(m["id"]) == m.get("status"):
                continue
        else:
            continue
        out.append({**m, "class": c})
    return sorted(out, key=lambda x: (-x["class"]["priority"], x["dateTimeGMT"]), reverse=False)


def title(m):
    """'New Zealand v India' and the rest of the name ('5th T20I, India tour of New Zealand 2026')."""
    parts = [p.strip() for p in m["name"].split(",")]
    teams = parts[0].replace(" vs ", " v ")
    return teams, ", ".join(parts[1:])


def result_html(m):
    teams, rest = title(m)
    names = r.esc(teams)
    for t in m.get("teams") or []:
        if strip_women(t).lower() in HIGHLIGHT:
            names = names.replace(r.esc(t), f"<strong>{r.esc(t)}</strong>")
    scores = " · ".join(r.esc(innings_line(s)) for s in m.get("score") or [])
    live = "" if m.get("matchEnded") else '<span class="tag">Live</span> '
    return (f'<li><span class="cm">{names}</span><span class="cs">{scores}</span>'
            f'<span class="cr">{live}{r.esc(m.get("status") or "")}</span><span class="ct">{r.esc(rest)}</span></li>')


def results_html(picked):
    """Matches grouped under International, Women's international, and each league, in priority order. '' if none."""
    groups, order = {}, []
    for m in picked:
        label = m["class"]["label"]
        if label not in groups:
            groups[label] = []
            order.append(label)
        groups[label].append(m)
    out = ""
    for label in order:
        out += f"<h3>{r.esc(label)}</h3><ul class=\"cricket\">{''.join(result_html(m) for m in groups[label])}</ul>"
    return out
