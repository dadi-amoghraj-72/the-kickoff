"""Tests for the section-order rules. Run: python3 scripts/test_order.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff.order import assemble  # noqa: E402

ALL = ["big-stuff", "on-today", "arsenal", "football", "cricket", "nba", "nfl", "mlb",
       "young-guns", "f1", "tennis", "other-sports", "stories"]
TITLES = {"f1": "F1", "other-sports": "Other Sports", "big-stuff": "The Big Stuff", "on-today": "On Today",
          "young-guns": "Young Guns", "nba": "NBA", "nfl": "NFL"}
FULL = {k: {"title": TITLES.get(k, k.title()), "html": f"<p>{k}</p>",
            "headline": f"{TITLES.get(k, k.title())} headline"} for k in ALL}


def ids(content, **kw):
    return [s["id"] for s in assemble(content, **kw)]


def check(name, got, want):
    ok = got == want
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        print("   got: ", got, "\n   want:", want)
    return ok


results = [
    check("default order",
          ids(FULL),
          ["big-stuff", "on-today", "arsenal", "football", "cricket", "nba", "nfl", "mlb",
           "young-guns", "f1", "tennis", "around", "stories"]),
    check("cricket lead moves cricket above football",
          ids(FULL, lead="cricket")[:5], ["big-stuff", "on-today", "cricket", "arsenal", "football"]),
    check("arsenal lead keeps Arsenal and Football together, first",
          ids(FULL, lead="arsenal")[:4], ["big-stuff", "on-today", "arsenal", "football"]),
    check("F1 race: own section right after the lead group, gone from Around",
          ids(FULL, promoted=["f1"])[:5], ["big-stuff", "on-today", "arsenal", "football", "f1"]),
    check("F1 race with cricket lead: F1 comes after cricket",
          ids(FULL, lead="cricket", promoted=["f1"])[:4], ["big-stuff", "on-today", "cricket", "f1"]),
    check("Slam QF+ and F1 together: both promoted, F1 first",
          ids(FULL, promoted=["f1", "tennis"])[4:6], ["f1", "tennis"]),
]

# Big Stuff always carries the promoted event's headline
big = next(s for s in assemble(FULL, promoted=["f1", "tennis"]) if s["id"] == "big-stuff")
results.append(check("Big Stuff mentions F1 and tennis",
                     ["F1 headline" in big["html"], "Tennis headline" in big["html"]], [True, True]))

# Without a promotion, F1 and tennis are still their own sections (D, 2026-11-08: the rail showed no helmet when F1 sat inside Around), before Around, which keeps the other sports
around = next(s for s in assemble(FULL) if s["id"] == "around")
results.append(check("F1 and tennis are their own sections in Around's place; Around holds only the other sports",
                     ["<h3>F1</h3>" in around["html"], "<h3>Tennis</h3>" in around["html"], "<h3>Other Sports</h3>" in around["html"],
                      ids(FULL).index("f1") < ids(FULL).index("tennis") < ids(FULL).index("around")], [False, False, True, True]))

# Missing content is skipped, and a promotion with no Big Stuff creates one
thin = {k: FULL[k] for k in ("on-today", "f1", "stories")}
results.append(check("empty sections are left out, Big Stuff created for a promoted event",
                     ids(thin, promoted=["f1"]), ["big-stuff", "on-today", "f1", "stories"]))
results.append(check("unknown lead is ignored", ids(FULL, lead="curling"), ids(FULL)))

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
