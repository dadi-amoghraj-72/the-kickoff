"""Tests for grid penalties under qualifying (kickoff/f1grid.py, D 2026-11-08), on the real São Paulo GP 2026 situation: Verstappen and Hamilton to the back of the grid,
Russell five places, Leclerc a penalty of unreported size. Claude is replaced by a fake that returns what a reader of those reports would.
Run: .venv/bin/python scripts/test_f1grid.py"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import f1, f1grid  # noqa: E402

results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {str(detail)[:400]}"))
    results.append(ok)


QUALI = [("Lando", "Norris", "McLaren"), ("George", "Russell", "Mercedes"), ("Andrea Kimi", "Antonelli", "Mercedes"), ("Charles", "Leclerc", "Ferrari"),
         ("Liam", "Lawson", "Racing Bulls"), ("Nico", "Hülkenberg", "Audi"), ("Isack", "Hadjar", "Red Bull"), ("Oliver", "Bearman", "Haas F1 Team"),
         ("Fernando", "Alonso", "Aston Martin"), ("Alexander", "Albon", "Williams"), ("Lewis", "Hamilton", "Ferrari"), ("Oscar", "Piastri", "McLaren"),
         ("Max", "Verstappen", "Red Bull")]
ROWS = [{"position": str(i), "Driver": {"givenName": g, "familyName": f, "driverId": f.lower(), "code": f[:3].upper()}, "Constructor": {"name": t}, "Q3": "1:27.000"}
        for i, (g, f, t) in enumerate(QUALI, 1)]
NOW = datetime(2026, 11, 7, 23, 30, tzinfo=timezone.utc)
item = lambda t, x, h=6: {"source": "ESPN", "title": t, "text": x, "link": t, "published": NOW - timedelta(hours=h)}  # noqa: E731
ITEMS = [item("Max Verstappen, Lewis Hamilton, Charles Leclerc to take grid penalties in Brazil", "Max Verstappen and both Ferrari drivers will incur grid penalties after new power unit components were fitted"),
         item("Hamilton & Verstappen to start from back in Brazil", "Red Bull's Max Verstappen and Ferrari's Lewis Hamilton will start from the back of the grid."),
         item("George Russell hit with five-place grid penalty for São Paulo Grand Prix", "after his Mercedes team fitted another new engine", h=30),
         item("Norris takes pole in the rain", "a wet qualifying"), item("Old penalty story", "grid penalty last week", h=24 * 9)]

check("only the weekend's penalty reports are read (not the pole story, not last week's)", [i["title"][:20] for i in f1grid.reports(ITEMS, NOW)] == ["Max Verstappen, Lewi", "Hamilton & Verstappe", "George Russell hit w"])

CLAUDE = [{"driver": "Max Verstappen", "kind": "back", "places": 0, "reason": "new power unit parts"}, {"driver": "Lewis Hamilton", "kind": "back", "places": 0, "reason": "new power unit parts"},
          {"driver": "George Russell", "kind": "places", "places": 5, "reason": "five-place penalty"}, {"driver": "Charles Leclerc", "kind": "unsized", "places": 0, "reason": "new power unit parts"},
          {"driver": "Fernando Alonso", "kind": "places", "places": 3, "reason": "impeding"},            # in no report: dropped
          {"driver": "Toto Wolff", "kind": "back", "places": 0, "reason": "x"}, {"driver": "Oscar Piastri", "kind": "places", "places": 99, "reason": "x"}]
f1grid.notes.call_json = lambda client, system, schema, content, model=None: ({"penalties": CLAUDE}, {"input": 100, "output": 20})
pens, usage = f1grid.find(object(), "São Paulo Grand Prix", ROWS, ITEMS, NOW)
check("only what the reports back is kept: Verstappen, Hamilton, Russell, Leclerc (not Alonso, not a name off the sheet, not 99 places)", sorted(pens) == ["Charles Leclerc", "George Russell", "Lewis Hamilton", "Max Verstappen"], pens)
check("no Claude or no penalty report: nothing, and no call", f1grid.find(None, "x", ROWS, ITEMS, NOW) == ({}, {"input": 0, "output": 0}) and f1grid.find(object(), "x", ROWS, ITEMS[3:4], NOW)[0] == {})
grid = f1grid.provisional(ROWS, pens)
check("provisional grid: Russell (2nd) drops five to 7th, those behind move up; Leclerc's unsized penalty does not move him; Hamilton and Verstappen at the back in their qualifying order",
      grid[:8] == ["Lando Norris", "Andrea Kimi Antonelli", "Charles Leclerc", "Liam Lawson", "Nico Hülkenberg", "Isack Hadjar", "George Russell", "Oliver Bearman"]
      and grid[-2:] == ["Lewis Hamilton", "Max Verstappen"] and len(grid) == len(ROWS), grid)
check("two drivers landing on the same place: the higher qualifier first", f1grid.provisional(ROWS[:6], {"Lando Norris": {"kind": "places", "places": 3}, "George Russell": {"kind": "places", "places": 2}})[:5]
      == ["Andrea Kimi Antonelli", "Charles Leclerc", "Liam Lawson", "Lando Norris", "George Russell"])
h = f1grid.html(ROWS, pens, f1.short_name)
check("the block: each penalty in one line with its cause (a 'reason' that only repeats the penalty is dropped: Russell), the provisional grid titled as our calculation, the note", "<strong>Hamilton:</strong> back of the grid (new power unit parts)" in h
      and "<strong>Russell:</strong> 5-place grid penalty</li>" in h and "size not reported" in h and "Provisional grid (our calculation)" in h and "official grid can differ" in h, h[:500])
q = f1.qualifying_table(ROWS, set(pens))
check("the official qualifying table stars the penalised drivers and no one else", q.count(" *<") == 4 and "L. Norris *" not in q, q.count(" *<"))
check("no penalties: no block, the table unstarred", f1grid.html(ROWS, {}, f1.short_name) == "" and " *" not in f1.qualifying_table(ROWS))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
