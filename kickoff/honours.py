"""Honours ESPN does not carry, read from Wikipedia's wikitext (kickoff.sources.wikipedia): the AP All-Pro teams, the NBA All-Star selections, the Pro Bowl
selections and the NBA Coach of the Year. Each parser knows one page layout and returns nothing ({} or None) when the page does not look like it; a missing honour
is better than a wrong one. Names are written 'M. Stafford' (first initial and the rest), like the NBA and NFL sections' standout lines."""
import re

POS = {"quarterback": "QB", "running back": "RB", "fullback": "FB", "all-purpose": "APU", "wide receiver": "WR", "tight end": "TE", "left tackle": "LT",
       "left guard": "LG", "center": "C", "right guard": "RG", "right tackle": "RT", "edge rusher": "EDGE", "interior lineman": "DT", "linebacker": "LB",
       "cornerback": "CB", "safety": "S", "kicker": "K", "punter": "P", "long snapper": "LS", "kick returner": "KR", "punt returner": "PR", "returner": "RET",
       "special teamer": "ST", "defensive end": "DE", "defensive tackle": "DT", "inside linebacker": "ILB", "outside linebacker": "OLB"}


def initial_name(full):
    """'Matthew Stafford' -> 'M. Stafford'; 'Amon-Ra St. Brown' -> 'A. St. Brown'; a single word stays as it is."""
    parts = full.split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else full


def link_text(cell):
    """The display text of the first wiki link in a cell: '[[Josh Allen]]' and '[[James Cook (running back)|James Cook]]' -> the name; None without one."""
    m = re.search(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", cell)
    return (m.group(2) or m.group(1)).strip() if m else None


def tables(text):
    """Every wikitable (nested ones too) as {"caption", "rows": [{"head": bool, "cells": [text]}]}, in order of appearance."""
    out, stack = [], []
    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.startswith("{|"):
            stack.append({"caption": "", "rows": [], "cur": None})
        elif line.startswith("|}") and stack:
            t = stack.pop()
            if t["cur"] is not None:
                t["rows"].append(t["cur"])
            out.append({"caption": t["caption"], "rows": [x for x in t["rows"] if x["cells"]]})
        elif not stack:
            continue
        elif line.startswith("|+"):
            stack[-1]["caption"] = line[2:].strip()
        elif line.startswith("|-"):
            t = stack[-1]
            if t["cur"] is not None:
                t["rows"].append(t["cur"])
            t["cur"] = {"head": False, "cells": []}
        elif line[:1] in "|!":
            t = stack[-1]
            if t["cur"] is None:
                t["cur"] = {"head": False, "cells": []}
            head = line[0] == "!"
            for c in re.split(r"\|\||!!", line[1:]):
                c = c.strip()
                if re.match(r"^[\w-]+\s*=\s*\"[^\"]*\"[^|\[{]*\|", c):          # cell attributes: style="..."|text
                    c = c.split("|", 1)[1].strip()
                t["cur"]["cells"].append(c)
                t["cur"]["head"] = t["cur"]["head"] or head
        elif stack and stack[-1]["cur"] and stack[-1]["cur"]["cells"]:
            stack[-1]["cur"]["cells"][-1] += " " + line.strip()                  # a cell continued on the next line
    return out


def _pos(cell):
    name = (link_text(cell) or re.sub(r"[^A-Za-z -]", "", cell)).strip()
    return POS.get(name.lower(), name)


def _entries(cell):
    """[(name, [tags])] from an All-Pro cell: 'Name, Team (AP, PFWA, TSN)' entries separated by <br>."""
    out = []
    for part in re.split(r"<br\s*/?>", cell):
        name = link_text(part)
        tags = re.search(r"\(([^()]*)\)\s*$", part.strip())
        if name:
            out.append((name, [t.strip() for t in tags.group(1).split(",")] if tags else []))
    return out


def all_pro(text):
    """The AP All-Pro teams: {"first": {"Offense": [(pos, name)], "Defense": [...], "Special teams": [...]}, "second": {...}, "teams": {name: full team name}}, or {} when the page is not the expected one.
    A player is on the AP first team when 'AP' is among the selectors listed after his name, on the second team when 'AP-2' is."""
    first, second, teams = {}, {}, {}
    for t in tables(text):
        head = next((r["cells"][0] for r in t["rows"] if r["head"] and len(r["cells"]) == 1), "")
        unit = re.sub(r"\s+", " ", head).strip().capitalize()
        if unit not in ("Offense", "Defense", "Special teams"):
            continue
        for r in t["rows"]:
            if r["head"] or len(r["cells"]) != 3:
                continue
            pos = _pos(r["cells"][0])
            for part in re.split(r"<br\s*/?>", r["cells"][1] + "<br>" + r["cells"][2]):          # the team each player played for, from its season page link
                who, club = link_text(part), re.search(r"\[\[\d{4} ([^\]|]+?) season", part)
                if who and club:
                    teams[who] = club.group(1)
            first.setdefault(unit, []).extend((pos, n) for n, tags in _entries(r["cells"][1]) if "AP" in tags)
            second.setdefault(unit, []).extend((pos, n) for n, tags in _entries(r["cells"][2]) if "AP-2" in tags)
    if not all(first.get(u) for u in ("Offense", "Defense")):
        return {}
    return {"first": first, "second": second, "teams": teams}


def _first_names(rows, col):
    return [link_text(r["cells"][col]) for r in rows if not r["head"] and len(r["cells"]) > col and link_text(r["cells"][col])]


def all_stars(text):
    """The NBA All-Star selections from the 'Eastern Conference All-Stars' and 'Western Conference All-Stars' tables, as the page splits them:
    {"date": 'February 15, 2026', "East": {"starters": [{"name", "flag"}], "reserves": [...]}, "West": {...}}, or {} when those tables are not on the page.
    flag is 'out' for a player the page marks as unable to play (an INJ note), 'in' for a replacement (a REP note), else ''."""
    out = {}
    for t in tables(text):
        m = re.match(r"(Eastern|Western) Conference All-Stars", t["caption"])
        if not m:
            continue
        groups, which = {"starters": [], "reserves": []}, "starters"
        for r in t["rows"]:
            if r["head"]:
                which = "reserves" if r["cells"][0].lower().startswith("reserve") else "starters"
                continue
            name = link_text(r["cells"][1]) if len(r["cells"]) > 1 else None
            if name:
                cell = r["cells"][1]
                groups[which].append({"name": name, "flag": "out" if re.search(r"\{\{ref\|inj", cell) else "in" if re.search(r"\{\{ref\|rep", cell) else ""})
        out["East" if m.group(1) == "Eastern" else "West"] = groups
    date = re.search(r"^\|\s*date\s*=\s*(.+)$", text, re.M)
    if not all(out.get(c, {}).get("starters") and out.get(c, {}).get("reserves") for c in ("East", "West")):
        return {}
    return {"date": date.group(1).strip() if date else "", **out}


def pro_bowl(text):
    """The Pro Bowl Games selections: {"date", "AFC": [starters and reserves], "NFC": [...]} read from the tables under '===AFC===' and '===NFC===' (the Starter(s)
    and Reserve(s) columns, not the alternates), or {} when the page is not the expected one. Only players who were selected, in the order of the page."""
    out = {}
    for conf in ("AFC", "NFC"):
        m = re.search(rf"^===\s*{conf}\s*===\s*$(.*?)(?=^===|^==[^=])", text, re.M | re.S)
        names = []
        for t in tables(m.group(1) if m else ""):
            for r in t["rows"]:
                if r["head"] or len(r["cells"]) < 3:
                    continue
                for cell in r["cells"][1:3]:
                    for part in re.split(r"<br\s*/?>", cell):
                        if re.search(r"ref label\|declined", part):             # selected but declined: not counted
                            continue
                        n = link_text(re.sub(r"\{\{[^}]*\}\}", "", part))
                        if n:
                            names.append(n)
        out[conf] = names
    date = re.search(r"^\|\s*date\s*=\s*(.+)$", text, re.M)
    if not (out["AFC"] and out["NFC"]):
        return {}
    return {"date": date.group(1).strip() if date else "", **out}


def coach_of_the_year(text):
    """The latest winner from the NBA Coach of the Year page's table: {"season": '2025–26', "coach": 'Joe Mazzulla', "team": 'Boston Celtics'}, or None."""
    last = None
    for t in tables(text):
        for r in t["rows"]:
            c = r["cells"]
            if len(c) >= 4 and re.search(r"\{\{nbay\|(\d{4})\}\}", c[0]):
                last = c
    if not last:
        return None
    year = int(re.search(r"\{\{nbay\|(\d{4})\}\}", last[0]).group(1))
    who = re.search(r"\{\{sortname\|([^|]*)\|([^|}]*)", last[1])
    team = re.search(r"\[\[[^\]|]*\|([^\]]*)\]\]", last[3] if len(last) > 3 else "")
    if not (who and team):
        return None
    return {"season": f"{year}–{str(year + 1)[2:]}", "coach": f"{who.group(1)} {who.group(2)}".strip(), "team": team.group(1).strip()}
