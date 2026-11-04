"""The best individual performers of a Champions League night or a Premier League day: the top three, picked by code from ESPN's player counts.

ESPN gives counts only (goals, assists, shots on target, saves, cards), no ratings and no man-of-the-match, so the pick is a plain weighted score:
goals and assists dominate, a goalkeeper counts on his saves and a clean sheet, a red card or an own goal costs. A player appears only when he made a real
contribution (a goal, or a goalkeeper's big night), so a quiet night lists fewer than three. Free: one match summary per match, no Claude."""
import re

from kickoff import clubs, overview
from kickoff import render as r
from kickoff.sources import espn

GOAL, ASSIST, SHOT_ON = 5.0, 3.0, 0.4
SAVE, CLEAN_SHEET, KEEPER_MIN_SAVES = 0.5, 2.0, 4
RED, OWN_GOAL = 4.0, 3.0
MIN_SCORE = 5.0
LISTED_BONUS = 0.5      # a small nudge for one of D's 17 clubs, so on equal numbers his club's player is the one shown
LIMIT = 3


def keeper(p):
    return p["pos"] == "G" and p["starter"]


def score(p):
    s = GOAL * p["goals"] + ASSIST * p["assists"] + SHOT_ON * p["shots_on"] - RED * p["red"] - OWN_GOAL * p["own_goals"]
    if keeper(p) and p["saves"] >= KEEPER_MIN_SAVES:
        s += SAVE * p["saves"] + (CLEAN_SHEET if p["conceded"] == 0 else 0)
    return s


def line(p):
    """'F. Ruiz (PSG): 2 goals, 1 assist' or 'D. Vásquez (ROM): 6 saves, clean sheet'. Code: ours for the 17 listed clubs, else ESPN's."""
    bits = []
    if p["goals"]:
        bits.append(f"{p['goals']} goal{'s' if p['goals'] != 1 else ''}")
    if p["assists"]:
        bits.append(f"{p['assists']} assist{'s' if p['assists'] != 1 else ''}")
    if keeper(p) and p["saves"] >= KEEPER_MIN_SAVES:
        bits.append(f"{p['saves']} saves")
        if p["conceded"] == 0:
            bits.append("clean sheet")
    code = overview.team_code({"id": p["team_id"], "abbr": p["team_abbr"], "name": p["team"]})
    return f"{p['short']} ({code}): " + ", ".join(bits)


def best(league, matches, fetch=None, limit=LIMIT):
    """The top `limit` performers over the finished matches: [{"id", "text", "score"}], best first. A match whose summary fails is skipped."""
    fetch = fetch or espn.get_player_stats
    found = []
    for m in matches:
        if not m.get("completed", True):
            continue
        try:
            players = fetch(league, m["id"])
        except Exception:
            continue
        found += [(score(p) + (LISTED_BONUS if clubs.is_listed(p['team_id']) else 0), p) for p in players]
    found = [(s, p) for s, p in found if s >= MIN_SCORE and (p["goals"] or p["assists"] or keeper(p))]
    found.sort(key=lambda sp: (-sp[0], -sp[1]["goals"], sp[1]["name"]))
    seen, out = set(), []
    for s, p in found:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append({"id": p["id"], "text": line(p), "score": round(s, 2)})
        if len(out) == limit:
            break
    return out


def html(perf):
    """The list under a 'Best performers' heading with the figures in gold, as in the NBA standouts; '' when nobody qualified."""
    if not perf:
        return ""
    gold = lambda text: re.sub(r"(?<![\w-])(\d+)(?=\s)", r'<span class="n">\1</span>', r.esc(text))  # noqa: E731
    rows = "".join(f'<div class="pl"><span class="t">{gold(x["text"])}</span></div>' for x in perf)
    return f'<h4>Best performers</h4><div class="dlist">{rows}</div>'
