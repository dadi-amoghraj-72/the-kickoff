"""Tests for the progress rail's sport icon (D, 2026-11-05): which drawing leads the bar in which section, that it follows the fill, that balls turn and the others only sway, that Other Sports
changes the drawing by sport, and that the bar still works with no icon element. The real kickoff/static/rail.js and rail-icons.js run in macOS's own JavaScript engine (jsc) against a stand-in
page: no browser is needed. Run: .venv/bin/python scripts/test_rail.py"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


if not Path(JSC).exists():
    print("SKIP  jsc (macOS JavaScript shell) not found: the icon logic could not be run here")
    sys.exit(0)

ICONS = (ROOT / "kickoff/static/rail-icons.js").read_text()
RAIL = (ROOT / "kickoff/static/rail.js").read_text()

HARNESS = r"""
var window = this;
window.innerHeight = 800; window.innerWidth = 400; window.scrollY = 0;
var handlers = {};
window.addEventListener = function (n, f) { handlers[n] = f; };
window.requestAnimationFrame = function (f) { f(); };
window.matchMedia = function () { return { matches: false }; };
function box(top) { return function () { return { top: top - window.scrollY, height: 700 }; }; }
var SECTIONS = __SECTIONS__;
var secEls = SECTIONS.map(function (s) {
  return { id: s.id, getBoundingClientRect: box(s.y), querySelectorAll: function (sel) {
    return sel === "h4.sport" ? (s.h4 || []).map(function (h) { return { textContent: h.t, getBoundingClientRect: box(h.y) }; }) : []; } };
});
var fill = { style: {} }, chip = { textContent: "" };
var icon = __ICON__ ? { classList: { add: function () { this.on = true; } }, style: {}, firstChild: null } : null;
if (icon) Object.defineProperty(icon, "innerHTML", { set: function (v) { this._html = v; this.firstChild = { style: {} }; }, get: function () { return this._html; } });
var rail = { getBoundingClientRect: function () { return { height: window.innerHeight - 100, top: 64 }; } };
window.document = { documentElement: { scrollHeight: __TOTAL__ },
  querySelectorAll: function (sel) { return sel === "main section[id]" ? secEls : []; },
  querySelector: function (sel) { return sel === "main" ? { innerText: "word word word" } : sel === ".rail" ? rail : sel === ".theend" && __END__ ? { getBoundingClientRect: box(__END__) } : null; },
  getElementById: function (id) { return id === "rail-fill" ? fill : id === "chip" ? chip : id === "rail-icon" ? icon : null; },
  fonts: null };
var document = window.document;
__ICONS__
__RAIL__
function at(y) { window.scrollY = y; handlers.scroll(); }
var out = [];
var STEPS = __STEPS__;
STEPS.forEach(function (st) {
  var y = st; if (st instanceof Array) { y = st[0]; window.innerHeight = st[1]; }
  at(y);
  var key = "none";
  if (icon && icon._html) for (var k in window.RAIL_ICONS) if (icon._html.indexOf(window.RAIL_ICONS[k].svg) >= 0) key = k;
  out.push({ y: y, key: key, top: icon ? icon.style.transform : null, turn: icon && icon.firstChild ? icon.firstChild.style.transform : null, fill: fill.style.transform, on: icon ? !!icon.classList.on : null });
});
print(JSON.stringify(out));
"""


def run(sections, steps, with_icon=True, total=None, end=0):
    total = total or sections[-1]["y"] + 1400
    js = (HARNESS.replace("__SECTIONS__", json.dumps(sections)).replace("__ICON__", "true" if with_icon else "false").replace("__TOTAL__", str(total))
          .replace("__ICONS__", ICONS).replace("__RAIL__", RAIL).replace("__STEPS__", json.dumps(steps)).replace("__END__", str(end)))
    p = ROOT / "preview" / "rail_harness.js"
    p.parent.mkdir(exist_ok=True)
    p.write_text(js)
    got = subprocess.run([JSC, str(p)], capture_output=True, text=True, timeout=60)
    line = [ln for ln in got.stdout.splitlines() if ln.startswith("[")]
    return json.loads(line[-1]) if line else {"error": got.stdout + got.stderr}


SECS = [{"id": "big-stuff", "y": 0}, {"id": "on-today", "y": 1000}, {"id": "football", "y": 2000}, {"id": "cricket", "y": 3000}, {"id": "nba", "y": 4000}, {"id": "nfl", "y": 5000},
        {"id": "mlb", "y": 6000}, {"id": "f1", "y": 7000}, {"id": "young-guns", "y": 8000},
        {"id": "other-sports", "y": 9000, "h4": [{"t": "Rugby", "y": 9100}, {"t": "Golf", "y": 9500}, {"t": "UFC", "y": 9900}, {"t": "Badminton", "y": 10300}, {"t": "Chess", "y": 10700}]},
        {"id": "stories", "y": 11200}]
STEPS = [0, 1100, 2100, 3100, 4100, 5100, 6100, 7100, 8100, 8800, 9000, 9300, 9800, 10100, 10600, 11000, 11300, 12000]
got = run(SECS, STEPS + [12900, 13400], end=13100, total=13900)
if isinstance(got, dict):
    check("the harness ran", False, got)
    sys.exit(1)
keys = {g["y"]: g["key"] for g in got}
# the reading line is 35% of the window (800px = 280px) below the scroll position, so a section is current from 280px before its top
check("each section has its own drawing: Big Stuff trophy, On Today clock, Football football, Cricket ball, NBA basketball, NFL, MLB, F1 car, Young Guns star",
      [keys[y] for y in (0, 1100, 2100, 3100, 4100, 5100, 6100, 7100, 8100)] == ["trophy", "clock", "football", "cricket", "basketball", "nfl", "baseball", "f1", "star"], keys)
check("Other Sports changes the drawing by sport: rugby ball, golf ball, UFC glove, shuttlecock, chess king", [keys[y] for y in (9000, 9300, 9800, 10100, 10600)] == ["rugby", "golf", "ufc", "badminton", "chess"], keys)
check("Other Sports opens with its first sport's drawing (the rugby ball), not a generic one, from the moment the section is reached (D, 2026-11-05)", keys[8800] == "rugby", keys)
check("the Arsenal section has the cannon and the Football section the football", run([{"id": "arsenal", "y": 0}, {"id": "football", "y": 1000}], [0, 1100])[0]["key"] == "cannon" and run([{"id": "arsenal", "y": 0}, {"id": "football", "y": 1000}], [0, 1100])[1]["key"] == "football")
check("Interesting Stories gets the chess king", keys[11300] == "chess" and keys[12000] == "chess")
check("at the end of the page the chequered flag leads the bar (D, 2026-11-05): The End (at 13100) is in view from about 12420 up", keys[12900] == "flag" and keys[13400] == "flag" and keys[12000] == "chess", keys)
check("F1 has the helmet now, not the flag", keys[7100] == "f1" and "currentColor" in __import__("pathlib").Path(ROOT / "kickoff/static/rail-icons.js").read_text().split("f1: {")[1].split("\n")[0] and "x=\"5\" y=\"3\"" not in __import__("pathlib").Path(ROOT / "kickoff/static/rail-icons.js").read_text().split("f1: {")[1].split("\n")[0])
check("the icon is shown (made visible) once it has a drawing", all(g["on"] for g in got))
tops = [float(g["top"].split(",")[1].replace("px", "")) for g in got]
check("the icon rides the head of the fill: lower on the rail as you scroll, from the top to the bottom of the 700px rail", tops == sorted(tops) and tops[0] == 0 and abs(tops[-1] - 700) <= 1, tops)
spin = {g["y"]: g["turn"] for g in got}
check("balls turn with the scroll (the football at 2100 and 3100 are at different angles) and do not all sit at 0", spin[2100] != spin[3100] and spin[2100] not in (None, "rotate(0deg)"), spin)
check("the trophy, the F1 flag and the NFL goalposts only sway a little (within 7 degrees); the NFL no longer spins like a ball", all(abs(int(spin[y].replace("rotate(", "").replace("deg)", ""))) <= 7 for y in (0, 5100, 7100)), spin)
check("the fill still grows as before (scaleY from 0 to 1)", got[0]["fill"] == "scaleY(0)" and got[-1]["fill"] == "scaleY(1)", [got[0]["fill"], got[-1]["fill"]])
_h = run(SECS, [[5000, 800], [5000, 600], [5000, 800]])
_t = [float(g["top"].split(",")[1].replace("px", "")) for g in _h]
check("the icon follows the rail when its height changes (iPhone Safari's address bar): at the same scroll the offset shrinks with a shorter window and returns", _t[1] < _t[0] and abs(_t[1] / _t[0] - 500 / 700) < 0.03 and abs(_t[2] - _t[0]) < 1, _t)
nofill = run(SECS, [0, 5000, 12000], with_icon=False)
check("with no icon element the bar works exactly as before and nothing breaks", isinstance(nofill, list) and nofill[0]["fill"] == "scaleY(0)" and nofill[-1]["fill"] == "scaleY(1)" and nofill[0]["top"] is None, nofill)
check("every section id the page can make has a drawing (big-stuff, on-today, arsenal, football, cricket, nba, nfl, mlb, f1, tennis, tour, young-guns, other-sports, stories, quiet)",
      all(f'"{k}"' in ICONS or f"{k}:" in ICONS for k in ("big-stuff", "on-today", "arsenal", "football", "cricket", "nba", "nfl", "mlb", "f1", "tennis", "tour", "young-guns", "other-sports", "stories", "quiet")))
from kickoff import render  # noqa: E402
pg = render.render_edition({"date": "2026-11-05", "dummy": False, "sections": [{"id": "cricket", "title": "Cricket", "html": "<p>a</p>"}]})
check("the page carries the icon element and both scripts, in one file", 'id="rail-icon"' in pg and "RAIL_ICONS" in pg and "rail-fill" in pg and pg.index("RAIL_ICONS") < pg.index("moveIcon"))
print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
