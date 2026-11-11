"""Offline tests for the daily run: the budget guard, the edition builder with fake sports, state saving, the workflow file. No network, no keys.
Run: .venv/bin/python scripts/test_daily.py"""
import copy
import json
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import budget, daily, order, render, settings, telegram  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"  -> {detail}"))


DAY = date(2026, 11, 5)
NOW = datetime(2026, 11, 4, 23, 15, tzinfo=timezone.utc)

# ---- Budget guard ----------------------------------------------------------------------------------------
c = lambda spent: {"2026-11": {"spent": spent, "calls": 1, "days": {}}}  # noqa: E731
check("budget: well under 80% is normal; the percentage is spent over the budget", budget.status(c(2.0), DAY, 10.0)["mode"] == "normal" and budget.status(c(2.0), DAY, 10.0)["pct"] == 0.2)
check("budget: 79.9% is still normal, exactly 80% is 'cheaper', 99.9% is still 'cheaper'", [budget.status(c(x), DAY, 10.0)["mode"] for x in (7.99, 8.0, 9.99)] == ["normal", "cheaper", "cheaper"])
check("budget: 100% and over is 'plain' (no Claude at all)", [budget.status(c(x), DAY, 10.0)["mode"] for x in (10.0, 25.0)] == ["plain", "plain"])
check("budget: a new month starts at zero, and no costs yet is normal", budget.status(c(9.9), date(2026, 12, 1), 10.0)["mode"] == "normal" and budget.status({}, DAY, 10.0)["spent"] == 0.0 and budget.status(None, DAY, 10.0)["mode"] == "normal")
check("budget: the default budget is the setting", budget.status({}, DAY)["budget"] == settings.MONTHLY_BUDGET_USD)
before_model = settings.OVERVIEW_MODEL
with budget.models("cheaper"):
    inside = settings.OVERVIEW_MODEL
check("budget: 'cheaper' makes the Opus overview model the Sonnet note model inside the block and puts it back afterwards", inside == settings.CLAUDE_MODEL != before_model and settings.OVERVIEW_MODEL == before_model)
try:
    with budget.models("cheaper"):
        raise RuntimeError("boom")
except RuntimeError:
    pass
check("budget: the model is put back even when the run inside raises", settings.OVERVIEW_MODEL == before_model)
with budget.models("normal"):
    check("budget: 'normal' changes nothing", settings.OVERVIEW_MODEL == before_model)
b100, b50 = budget.status(c(10.0), DAY, 10.0), budget.status(c(1.0), DAY, 10.0)
check("client: none when Claude is not asked for, when the key is missing, or when the budget is used up", daily.make_client(b50, {"ANTHROPIC_API_KEY": "x"}, False) is None
      and daily.make_client(b50, {}, True) is None and daily.make_client(b100, {"ANTHROPIC_API_KEY": "x"}, True) is None)


# ---- The edition with fake sports -------------------------------------------------------------------------
def ok_sport(sid, title, html, state_id=None, headlines=(), extra_sections=()):
    def go(now, day, st):
        return {"sections": [{"id": sid, "title": title, "html": html}, *extra_sections] if html else [], "state": {state_id: {"seen": [sid, day.isoformat()]}} if state_id else {},
                "headlines": list(headlines), "problems": [], "stats": {"n": 1}}
    return (sid, title, go)


def boom(sid, title):
    def go(now, day, st):
        raise ValueError("source is down")
    return (sid, title, go)


ST = {n: {} for n in daily.STATE_NAMES}
ST["nba"] = {"seen": ["old"]}
fake = [
    ("football", "Football", lambda now, day, st: {"sections": [{"id": "arsenal", "title": "Arsenal", "html": "<p>A</p>"}, {"id": "football", "title": "Football", "html": "<p>F</p>"}],
                                                    "state": {"tables": {"x": 1}}, "headlines": ["H1", "H2", "H3", "H4"], "problems": ["Ligue 1 table"], "stats": {}}),
    ok_sport("cricket", "Cricket", "<p>C</p>", "cricket"),
    ok_sport("f1", "F1", "<p>F1</p>", "f1"),
    ok_sport("tennis", "Tennis", "", "tennis"),
    ok_sport("nfl", "NFL", "<p>N</p>", "nfl"),
    boom("nba", "NBA"),
    ok_sport("mlb", "MLB", "<p>M</p>", "mlb"),
]
st0 = copy.deepcopy(ST)
out = daily.build_edition(NOW, DAY, ST, fake)
ed = out["edition"]
check("the input state is never changed by a run", ST == st0)
ids = [s["id"] for s in ed["sections"]]
check("sections come in the house order: arsenal, football, cricket, nba, nfl, mlb, then F1 as its own section (tennis had nothing)", ids == ["arsenal", "football", "cricket", "nba", "nfl", "mlb", "f1"], ids)
check("a sport that raises shows a 'No data this morning' line in its own place and is reported (not an exception)", "No data this morning" in next(s["html"] for s in ed["sections"] if s["id"] == "nba")
      and out["failed"] == ["nba"] and "nba (ValueError)" in out["problems"])
check("a failed sport keeps its old state exactly; the sports that worked get their new state", out["state"]["nba"] == {"seen": ["old"]} and out["state"]["tables"] == {"x": 1} and out["state"]["mlb"]["seen"][0] == "mlb")
check("a sport with nothing to show has no section but its state still moves on (tennis)", "tennis" not in ids and out["state"]["tennis"]["seen"][0] == "tennis")
check("problems inside a sport (a failed table) are carried along beside the failures", "Ligue 1 table" in out["problems"])
check("the headlines are football's first three, no more", ed["headlines"] == ["H1", "H2", "H3"])
check("the edition has the date, is not a dummy and says how Claude was used", ed["date"] == "2026-11-05" and ed["dummy"] is False and ed["claude"] == "normal" and ed["built"].startswith("2026-11-04T23:15"))
page = render.render_edition(ed)
check("the edition renders to a page with every section and the date", all(f'<section id="{i}">' in page for i in ids) and "Thursday 5 November 2026" in page, page[:200])
quiet = daily.build_edition(NOW, DAY, ST, [ok_sport("nfl", "NFL", "", "nfl")])["edition"]
check("when nothing at all has anything to show the edition says it is a quiet morning, rather than being an empty page", [s["id"] for s in quiet["sections"]] == ["quiet"] and quiet["headlines"] == [])
allfail = daily.build_edition(NOW, DAY, ST, [boom("a", "A"), boom("b", "B")])
check("every sport failing is visible to the caller (failed lists all of them), still no exception", allfail["failed"] == ["a", "b"] and len(allfail["problems"]) == 2)
run = daily.run_day(NOW, DAY, {**ST, "costs": c(8.5)}, lambda client: fake, use_claude=True, env={"ANTHROPIC_API_KEY": "x"})
check("run_day: at 85% of the budget the run is 'cheaper' and says so in the edition and in the budget report", run["budget"]["mode"] == "cheaper" and run["edition"]["claude"] == "cheaper" and run["client_used"] is True, (run["budget"], run["edition"]["claude"]))
seen = {}
daily.run_day(NOW, DAY, {**ST, "costs": c(12.0)}, lambda client: seen.setdefault("client", client) or fake, use_claude=True, env={"ANTHROPIC_API_KEY": "x"})
check("run_day: over budget, the adapters are built with no Claude client", seen["client"] is None)
plain = daily.run_day(NOW, DAY, ST, lambda client: fake, use_claude=False)
check("run_day: without --claude the edition says 'off'", plain["edition"]["claude"] == "off" and plain["client_used"] is False)

# ---- State on disk -----------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    new = copy.deepcopy(ST)
    new["nfl"] = {"reported": ["g1"]}
    new["costs"] = {"2026-11": {"spent": 0.5, "calls": 2, "days": {}}}
    changed = daily.save_state(new, ST, d)
    check("save_state writes only the files that changed", sorted(changed) == ["costs", "nfl"] and sorted(p.stem for p in d.glob("*.json")) == ["costs", "nfl"], changed)
    back = daily.load_state(d)
    check("load_state reads them back and gives {} for the rest, for every sport", back["nfl"] == {"reported": ["g1"]} and back["mlb"] == {} and set(back) == set(daily.STATE_NAMES))
    check("saving again with nothing changed writes nothing", daily.save_state(back, back, d) == [])
    edd = d / "editions"
    edd.mkdir()
    check("edition_exists is false before the edition is written and true after", not daily.edition_exists(DAY, edd) and (edd / "2026-11-05.json").write_text(json.dumps(ed)) and daily.edition_exists(DAY, edd))
    docs = d / "docs"
    dates = render.build_site(edd, docs)
    check("build_site can write into another folder (the dry run), leaving the real docs alone", dates == ["2026-11-05"] and (docs / "editions" / "2026-11-05" / "index.html").exists() and (docs / "index.html").exists())

# ---- The real adapter list ----------------------------------------------------------------------------------
real = daily.real_adapters(None, env={})
check("the real adapters: football, cricket, F1, tennis, NFL, NBA, MLB, the other sports and the NFL/NBA news, in that order", [a[0] for a in real] == ["football", "cricket", "f1", "tennis", "nfl", "nba", "mlb", "around", "usnews"])
from kickoff.sources import cricket as _cricket_source  # noqa: E402
check("cricket no longer needs CricketData's key: without it the backup list is just empty (ESPN's feed is the main source), with it the real list is used", daily.backup_matches({})() == ([], 0) and daily.backup_matches({"CRICKET_DATA_API_KEY": "x"}) is _cricket_source.get_matches)
check("the state names cover every sport and no file is named twice", len(set(daily.STATE_NAMES)) == len(daily.STATE_NAMES) and {"cricket", "f1", "tennis", "nfl", "nba", "mlb", "tables", "costs"} <= set(daily.STATE_NAMES))
check("the order module knows the MLB section by its real id 'mlb'", ["mlb"] in order.GROUPS and ["baseball"] not in order.GROUPS)

# ---- The workflow file (live since D's go on 8 November 2026) -------------------------------------------------------
wf = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
live = "\n".join(line for line in wf.splitlines() if not line.lstrip().startswith("#"))
import glob as _glob  # noqa: E402
_wfs = {Path(f).name: re.sub(r"#.*", "", Path(f).read_text()) for f in _glob.glob(str(ROOT / ".github" / "workflows" / "*.yml"))}
check("every workflow is pinned to Ubuntu 24.04 (8 Nov 2026: ubuntu-latest became Ubuntu 26.04, which has no Python 3.9, and the first scheduled run failed)",
      all("runs-on: ubuntu-24.04" in t and "ubuntu-latest" not in t for t in _wfs.values()), [n for n, t in _wfs.items() if "ubuntu-latest" in t])
check("the workflow runs on its 7:15am schedule and by hand, never on a push or pull request", '- cron: "15 23 * * *"' in live and "workflow_dispatch:" in live and not re.search(r"^\s*(push|pull_request):", live, re.M))
check("the workflow takes every secret from GitHub's secrets and never holds a value", all(f"secrets.{k}" in wf for k in ("ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "CRICKET_DATA_API_KEY"))
      and not re.search(r"(sk-ant|[0-9]{8,}:[A-Za-z0-9_-]{30,})", wf))
check("the workflow builds, publishes (data and docs only), pings on request and alerts on failure", all(x in wf for x in ("scripts/daily.py", "git add data docs", "scripts/send_ping.py", "scripts/alert.py", "if: failure()")))
check("runs can never overlap (one concurrency group) and have a time limit", "concurrency:" in wf and "timeout-minutes" in wf)
check("the Telegram message is the date, the headlines and the link to that day's page", telegram.build_message(ed).splitlines()[0].startswith("The Kickoff · Thu 5 Nov") and telegram.build_message(ed).endswith("/editions/2026-11-05/"))

# ---- every Claude call counts towards the month's $10 (previews, Young Guns, Around)
from datetime import date as _date
from kickoff import budget as _budget
_stats = {"nfl": {"preview_cost": 0.02}, "youngguns": {"claude_usage": {"input": 1000, "output": 500}}, "around": {"claude_usage": {"input": 10000, "output": 1000}}, "f1": {}}
_spent, _calls = daily.extra_costs(_stats)
check("the extra costs add up: a preview's dollars, Young Guns at the main model, Around at the news model", _calls == 3 and abs(_spent - (0.02 + (1000 * settings.PRICES[settings.CLAUDE_MODEL][0] + 500 * settings.PRICES[settings.CLAUDE_MODEL][1]) / 1e6 + (10000 * 2.0 + 1000 * 10.0) / 1e6)) < 1e-4, (_spent, _calls))
_ns = {"costs": {"2026-11": {"spent": 1.0, "calls": 4, "days": {"2026-11-05": {"spent": 0.5, "calls": 2}}}}}
daily.record_extra_costs(_ns, _stats, _date(2026, 11, 5))
_m = _ns["costs"]["2026-11"]
check("they are added to the month and to the day, next to the football run's own", abs(_m["spent"] - (1.0 + _spent)) < 1e-4 and _m["calls"] == 7 and abs(_m["days"]["2026-11-05"]["spent"] - (0.5 + _spent)) < 1e-4, _m)
_ns2 = {}
daily.record_extra_costs(_ns2, {"f1": {}}, _date(2026, 11, 5))
check("a day with no Claude call leaves the costs alone", _ns2 == {}, _ns2)
_ns3 = {}
daily.record_extra_costs(_ns3, {"around": {"claude_usage": {"input": 8_000_000, "output": 0}}}, _date(2026, 11, 5))
check("so the budget guard sees them: a month of Around alone can reach the plain-notes mode", _budget.status(_ns3["costs"], _date(2026, 11, 6))["mode"] in ("cheaper", "plain"), _budget.status(_ns3["costs"], _date(2026, 11, 6)))

# ---- the end of the page (D, 2026-11-05)
_pg = render.render_edition({"date": "2026-11-05", "dummy": False, "sections": [{"id": "x", "title": "X", "html": "<p>a</p>"}]})
check("every edition ends with a gold line, 'The End', a gold line, above the footer, once", _pg.count("The End</b>") == 1 and _pg.index('class="theend"') < _pg.index("<footer>") and _pg.index("<p>a</p>") < _pg.index('class="theend"') and _pg.count('class="ln"') == 2)

# ---- the ping on a quiet morning also says what is on today (D, 2026-11-05)
_qe = {"date": "2026-11-06", "dummy": False, "headlines": ["NBA: Miami Heat 117\u2013116 Los Angeles Clippers (OT)"], "ping_today": ["11:30am \u00b7 Cricket: Bangladesh v West Indies \u00b7 2nd Test \u00b7 Day 2", "9:15am \u00b7 NFL: Jacksonville Jaguars at Baltimore Ravens"], "sections": []}
_msg = telegram.build_message(_qe)
check("the quiet-morning ping: the date, the headline, then a Today block of bullets, then the link", _msg.splitlines()[0].startswith("The Kickoff") and "1. NBA: Miami Heat" in _msg and "Today:" in _msg and "\u2022 11:30am \u00b7 Cricket" in _msg and _msg.rstrip().endswith("/editions/2026-11-06/"), _msg)
_be = {**_qe}
_be.pop("ping_today")
check("a busy morning's ping has no Today block", "Today:" not in telegram.build_message(_be))

# ---- the edition counter (D, 2026-11-06): #001 on 7 November 2026, one more each day, nothing before and nothing on demo pages
_pg = lambda d, **k: render.render_edition({"date": d, "dummy": False, "sections": [{"id": "x", "title": "X", "html": "<p>a</p>"}], **k})  # noqa: E731
check("the first live edition (7 Nov 2026) reads Edition #001, the next day #002, a month on #030, in the footer, once",
      'Edition #001' in _pg("2026-11-07") and 'Edition #002' in _pg("2026-11-08") and 'Edition #030' in _pg("2026-12-06") and _pg("2026-11-07").count("Edition #") == 1 and _pg("2026-11-07").index("Edition #001") > _pg("2026-11-07").index("<footer>"))
check("the test mornings (6 Nov and before), dummy editions and demo pages carry no number", all("Edition #" not in x for x in (_pg("2026-11-06"), _pg("2026-11-05"), _pg("2026-11-09", banner="Demo"), _pg("2026-11-09", dummy=True))))
check("the number is a count of days since the launch: 1 on 7 Nov, 365 a year on", render.edition_number(date(2026, 11, 7)) == 1 and render.edition_number(date(2027, 11, 6)) == 365 and render.edition_number(date(2026, 11, 6)) is None)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
