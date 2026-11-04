"""On Today and Games to Watch: what is still to come, in Singapore time, from the fixtures kickoff/fixtures.py collects.

  On Today        the next 24 hours until the next edition at 7am: "While You're Up" (sun, 7am to 11pm SGT) then "Overnight" (moon, 11pm to 7am)
  Games To Watch  Mondays only: the rest of the week, grouped by day (D's teams, playoffs and finals, derbies, top-of-the-table clashes, tracked NBA stars facing each other,
                  every F1 race, the late rounds of a Slam)

Plain rules in code; every time is SGT. A block with nothing in it is left out."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from kickoff import fixtures, importance
from kickoff import render as r

SGT = ZoneInfo("Asia/Singapore")
SUN_FROM, SUN_TO = 7, 23          # "While you're up" is 7am to 11pm SGT, "Overnight" 11pm to 7am (D, 2026-11-05)
MAX_TODAY = 12
MAX_WATCH = 10
WATCH_PER_SPORT = 4       # one sport never fills the week (D's teams and finals excepted)


def tag(when):
    """'sun' (While you're up) or 'moon' (Overnight) for a UTC datetime."""
    return "sun" if SUN_FROM <= when.astimezone(SGT).hour < SUN_TO else "moon"


def clock(when):
    t = when.astimezone(SGT)
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}" if t.minute else f"{h}{'am' if t.hour < 12 else 'pm'}"


def day_end(day):
    """The next edition: 7am SGT on the day after `day`, as UTC."""
    return datetime.combine(day + timedelta(days=1), time(SUN_FROM), SGT).astimezone(timezone.utc)


def pick_today(found, cap=MAX_TODAY):
    """The lines for On Today: the highest scores if there are more than `cap`, then back in time order."""
    best = sorted(found, key=lambda f: (-f["score"], f["when"]))[:cap]
    return sorted(best, key=lambda f: f["when"])


def _line(f, with_day=False):
    t = f["when"].astimezone(SGT)
    return f'<li><span class="when">{(t.strftime("%a ") if with_day else "")}{clock(f["when"])}</span> {r.esc(f["text"])}</li>'


def today_html(found):
    """'While You're Up' then 'Overnight'; '' when nothing matters today."""
    chosen = pick_today(found)
    out = ""
    for which, heading in (("sun", "☀︎ While You're Up"), ("moon", "☾ Overnight")):
        rows = [f for f in chosen if tag(f["when"]) == which]
        if rows:
            first_day = chosen[0]["when"].astimezone(SGT).date()
            out += f'<h3>{heading}</h3><ul class="standouts ontoday">' + "".join(_line(f, f["when"].astimezone(SGT).date() != first_day) for f in rows) + "</ul>"
    return out


def watch_pick(found, cap=MAX_WATCH):
    """Games to Watch: D's teams, every playoff/knockout/final, derbies, top-of-the-table clashes, tracked NBA stars facing each other, every F1 race, a Slam's late rounds."""
    wanted = [f for f in found if f["mine"] or f["stage"] in ("final", "knockout", "playoff") or f["flags"] & {"derby", "clash", "stars"}]
    wanted = [f for f in wanted if not (f["sport"] == "f1" and f["text"].endswith("Qualifying")) and (f["mine"] or f["score"] >= importance.MIN_SCORE)      # F1: the race, not every session
              and not (f["sport"] in ("nba", "mlb") and f["stage"] == "regular" and "stars" not in f["flags"])]        # a plain NBA game of D's teams is On Today, not the week's big games
    best, per = [], {}
    for f in sorted(wanted, key=lambda f: (-f["score"], f["when"])):
        if len(best) < cap and (per.get(f["sport"], 0) < WATCH_PER_SPORT or f["mine"] or f["stage"] == "final"):
            per[f["sport"]] = per.get(f["sport"], 0) + 1
            best.append(f)
    return sorted(best, key=lambda f: f["when"])


def watch_html(found):
    """Grouped by day: a small heading per day, then 'time · game'."""
    chosen = watch_pick(found)
    if not chosen:
        return ""
    out, current = "", None
    for f in chosen:
        d = f["when"].astimezone(SGT).date()
        if d != current:
            out += ("</ul>" if current else "") + f'<p class="subhead">{d.strftime("%a %-d %b")}</p><ul class="standouts ontoday">'
            current = d
        out += _line(f)
    return '<h3>Games To Watch</h3>' + out + "</ul>"


def build(src, now, day, mine_nba=(), tracked_nba=()):
    """{"html", "today", "watch", "failed"}. now: UTC; day: the edition's date in Singapore. Games to Watch is added on Mondays and covers the six days after today."""
    end = day_end(day)
    today, failed = fixtures.collect(src, now, end, day.weekday(), mine_nba, tracked_nba=tracked_nba)
    html = today_html(today)
    watch = []
    if day.weekday() == 0:
        watch, failed2 = fixtures.collect(src, end, end + timedelta(days=6), day.weekday(), mine_nba, watch=True, tracked_nba=tracked_nba)
        failed = sorted(set(failed) | set(failed2))
        html += watch_html(watch)
    return {"html": html, "today": today, "watch": watch, "failed": failed}
