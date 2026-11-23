"""NHL, once a week (D, 2026-11-23: stats only): the season's leaders in one table built like the NBA League Leaders table.
Skaters: goals, assists, points. Goalies: wins, save percentage, shutouts. Top five each, from ESPN's qualified players; each stat's leader in gold.
Saturday's edition (the quietest day: Sunday and Monday are heavy, Friday has the NBA leaders, Thursday the MLB round-up, Wednesday the NFL tables)."""
from kickoff import render as r
from kickoff.nba import short_name

WEEKDAY = 5
LEADER_STATS = [("Goals", "skaters", "offensive.goals", "int"), ("Assists", "skaters", "offensive.assists", "int"), ("Points", "skaters", "offensive.points", "int"),
                ("Goalie wins", "goalies", "general.wins", "int"), ("Save percentage", "goalies", "defensive.savePct", "pct"), ("Shutouts", "goalies", "defensive.shutouts", "int")]


def fmt(value, kind):
    """A save percentage the way the NHL prints it, '.934'; a count as a whole number."""
    if kind == "pct":
        v = value / 100 if value > 1 else value
        return f"{v:.3f}".lstrip("0")
    return str(int(round(value)))


def leaders_html(by_stat):
    """by_stat: {label: [{"name", "team", "value"}]}. One table: a gold sub-row per stat, then # · player · team · value; '' when ESPN gave nothing."""
    rows = ""
    for label, _, _, kind in LEADER_STATS:
        top = by_stat.get(label) or []
        if not top:
            continue
        rows += f'<tr class="grp"><td colspan="4">{r.esc(label)}</td></tr>'
        gold = ' class="p1"'
        rows += "".join(f'<tr{gold if i == 1 else ""}><td class="n">{i}</td><td>{r.esc(short_name(x["name"]))}</td><td>{r.esc(x["team"])}</td><td class="n">{fmt(x["value"], kind)}</td></tr>'
                        for i, x in enumerate(top, 1))
    if not rows:
        return ""
    return (f'<div class="pts f1 nba lead"><div class="table-wrap"><table><colgroup><col style="width:12%"><col style="width:52%"><col style="width:16%"><col style="width:20%"></colgroup>'
            f'<thead><tr><th class="tt" colspan="4">NHL Leaders</th></tr></thead><tbody>{rows}</tbody></table></div></div>')


def run(now, day, st, source, force=False):
    """{"html", "state", "stats"}: the table on Saturdays, nothing on other days. A stat that fails is left out; no stat at all counts as a failure."""
    if (day.weekday() != WEEKDAY or not (day.month >= 10 or day.month <= 6)) and not force:        # the season runs October to June
        return {"html": "", "state": st or {}, "stats": {}}
    by_stat, failed = {}, 0
    for label, category, sort, _ in LEADER_STATS:
        try:
            by_stat[label] = source.leaders(category, sort)
        except Exception:
            failed += 1
    if failed == len(LEADER_STATS):
        raise RuntimeError("no NHL leaders")
    return {"html": leaders_html(by_stat), "state": st or {}, "stats": {"failed": failed, "calls": getattr(source, "calls", 0)}}
