"""Grid penalties under qualifying (D, 2026-11-08: Verstappen, Hamilton and Leclerc to the back and Russell five places down at the São Paulo GP, and the edition said
nothing, so Hamilton starting last would have made no sense on race day).

  1. The reports: BBC Sport, The Guardian and ESPN F1 headlines and blurbs from the race weekend that talk about grid penalties (code picks them).
  2. Claude reads only those and lists each driver's penalty: so many places, or the back of the grid / the pit lane, with the reason in a few words. Code checks every
     entry: the driver is on the qualifying sheet, the report names the driver or the team, the places are a plain number. Anything that fails is dropped.
  3. The edition shows the official qualifying table with * on each penalised driver, one line per penalty, and a provisional grid worked out from them:
     a place penalty moves the driver down that many places (those behind move up); back-of-grid drivers go to the end in their qualifying order. It says it is
     our calculation. The FIA sometimes orders several penalties differently; that is why it is provisional.
One small Claude call per race weekend, only when a report mentions penalties. No Claude, no reports, or nothing that passes the checks: no block, the table as before."""
import re
from datetime import timedelta

from kickoff import notes, settings
from kickoff import render as r

WINDOW = timedelta(days=3)          # the weekend's reports: Friday's engine changes are still news on Sunday morning
WORDS = re.compile(r"grid penalt|place penalt|back of the grid|start from the back|pit ?lane start|from the pit ?lane|grid drop", re.I)

SYSTEM = """You list F1 grid penalties for one race from news headlines and blurbs. Use ONLY the text given; add nothing from memory.
For each driver the text says will take a grid penalty at this race, give: "driver" (exactly as written in the drivers list given), "kind" ("places" for an
N-place drop, "back" for the back of the grid, "pitlane" for a pit lane start), "places" (the number for "places", else 0) and "reason" (at most six words, from the
text, e.g. "new power unit parts", "new engine"). "Both Ferrari drivers" means each Ferrari driver in the list. If the text does not say it clearly, leave the driver out."""
SCHEMA = {"type": "object", "properties": {"penalties": {"type": "array", "items": {"type": "object", "properties": {
    "driver": {"type": "string"}, "kind": {"type": "string", "enum": ["places", "back", "pitlane"]}, "places": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["driver", "kind", "places", "reason"], "additionalProperties": False}}}, "required": ["penalties"], "additionalProperties": False}


def reports(items, now):
    """The weekend's reports about grid penalties."""
    return [i for i in items if timedelta(0) <= now - i["published"] <= WINDOW and WORDS.search(f"{i['title']} {i['text']}")]


def drivers_of(rows):
    """{full name: (surname, team)} for the qualifying sheet (Jolpica rows)."""
    return {f"{x['Driver']['givenName']} {x['Driver']['familyName']}": (x["Driver"]["familyName"], x["Constructor"]["name"]) for x in rows}


def checked(found, rows, items):
    """Only the entries the reports back: a driver on the sheet, named (or their team named) in a report, a sane number of places; one entry a driver."""
    who = drivers_of(rows)
    text = " ".join(f"{i['title']} {i['text']}" for i in items).lower()
    out = {}
    for p in found or []:
        name = p.get("driver", "")
        if name not in who or name in out:
            continue
        surname, team = who[name]
        if surname.lower() not in text and team.split()[0].lower() not in text:
            continue
        if p.get("kind") == "places" and not (1 <= int(p.get("places") or 0) <= 30):
            continue
        reason = " ".join((p.get("reason") or "").split()[:6])
        if re.search(r"penalt|place|grid|back of", reason, re.I):             # the cause, never the penalty again ('five-place penalty' says nothing new)
            reason = ""
        out[name] = {"kind": p["kind"], "places": int(p.get("places") or 0), "reason": reason}
    return out


def find(client, race, rows, items, now):
    """({full name: penalty}, usage): the checked penalties for this race, or ({}, no usage) when there is nothing to read or no Claude."""
    rep = reports(items, now)
    if not (client and rep and rows):
        return {}, {"input": 0, "output": 0}
    listing = "\n".join(f"- [{i['source']}] {i['title']} | {i['text']}" for i in rep[:12])
    content = f"Race: {race}\nDrivers: {', '.join(drivers_of(rows))}\nReports:\n{listing}"
    obj, usage = notes.call_json(client, SYSTEM, SCHEMA, content, model=settings.NEWS_MODEL)
    return checked((obj or {}).get("penalties"), rows, rep), usage


def provisional(rows, pens):
    """The grid after the penalties, as full names in starting order. Place drops first (each to its qualifying place plus the drop, the higher qualifier first
    when two land on the same place), then the back-of-grid and pit-lane drivers in their qualifying order."""
    order = [f"{x['Driver']['givenName']} {x['Driver']['familyName']}" for x in rows]
    back = [d for d in order if pens.get(d, {}).get("kind") in ("back", "pitlane")]
    dropped = [d for d in order if pens.get(d, {}).get("kind") == "places"]
    grid = [d for d in order if d not in back and d not in dropped]
    same = {}
    for d in sorted(dropped, key=lambda d: (order.index(d) + pens[d]["places"], order.index(d))):
        target = order.index(d) + pens[d]["places"]
        grid.insert(min(target + same.get(target, 0), len(grid)), d)    # a second driver aiming at the same place goes behind the first
        same[target] = same.get(target, 0) + 1
    return grid + back


def penalty_text(p):
    what = {"back": "back of the grid", "pitlane": "pit lane start", "unsized": "grid penalty, size not reported (not moved below)"}.get(p["kind"]) or f"{p['places']}-place grid penalty"
    return what + (f" ({p['reason']})" if p.get("reason") else "")


def html(rows, pens, short_name):
    """The lines and the provisional grid under the qualifying table; '' with no penalties."""
    if not pens:
        return ""
    surname = {f"{x['Driver']['givenName']} {x['Driver']['familyName']}": x["Driver"]["familyName"] for x in rows}
    lines = "".join(f"<li><strong>{r.esc(surname[d])}:</strong> {r.esc(penalty_text(p))}</li>" for d, p in pens.items())
    grid = provisional(rows, pens)
    row_of = {f"{x['Driver']['givenName']} {x['Driver']['familyName']}": x for x in rows}
    body = []
    for i, d in enumerate(grid, 1):
        q = int(row_of[d]["position"])
        body.append([i, short_name(row_of[d]["Driver"]) + (" *" if d in pens else ""), (f"{q - i:+d}" if q != i else "")])
    table = r.compact(r.table("Provisional grid (our calculation)", [("P", True), ("Driver", False), ("+/-", True)], body), (14, 62, 24))
    return (f'<p class="muted">* grid penalty:</p><ul class="standouts">{lines}</ul>' + table
            + '<p class="muted">Worked out from the qualifying times and the reported penalties; the official grid can differ when several penalties are applied.</p>')
