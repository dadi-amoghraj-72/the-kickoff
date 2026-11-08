"""The FA Cup block: the ties finished since the last edition, from ESPN (the `eng.fa` league), with the round named in the heading.

Only the ties that matter (D, 2026-11-08): a Premier League club played; a Championship club lost to a lower-league club; or the winner sits 20 or more places
below the loser in the English pyramid (the five tiers ESPN has tables for counted as one ladder: Premier League 1-20, Championship 21-44, League One 45-68,
League Two 69-92, National League 93-116; a club below them counts as 117). Everything else (the early rounds' dozens of ties) is left out. No table, no Claude."""
from kickoff import render as r
from kickoff.scoreboard import scores_html

LIMIT = 12
TIERS = ["eng.1", "eng.2", "eng.3", "eng.4", "eng.5"]
BELOW = 117                 # a club below the National League
GIANT_KILLING = 20          # the winner at least this many places below the loser


def pyramid(get_table):
    """{team id: place in the English pyramid} from the five tables (get_table(league) -> rows best first); a tier whose table fails is skipped."""
    out, offset = {}, 0
    for lg in TIERS:
        try:
            rows = get_table(lg) or []
        except Exception:
            rows = []
        for i, x in enumerate(rows, 1):
            out[str(x["id"])] = offset + i
        offset += len(rows) or {"eng.1": 20}.get(lg, 24)
    return out


def matters(m, pyr):
    """True for a tie worth a line: a Premier League club played, a Championship club lost to a lower club, or a giant-killing of 20 places or more."""
    h, a = pyr.get(str(m["home"]["id"]), BELOW), pyr.get(str(m["away"]["id"]), BELOW)
    if min(h, a) <= 20:
        return True
    side = m.get("winner") or ("home" if m.get("home_score", 0) > m.get("away_score", 0) else "away" if m.get("away_score", 0) > m.get("home_score", 0) else None)
    if not side:
        return False
    win, lose = (h, a) if side == "home" else (a, h)
    return (21 <= lose <= 44 and win > 44) or win - lose >= GIANT_KILLING


def round_name(slug):
    """'third-round' -> 'Third Round', 'quarterfinals' -> 'Quarterfinals', '' -> ''."""
    return " ".join(w.capitalize() for w in (slug or "").replace("-", " ").split())


def pick(matches, top_ids, limit=LIMIT):
    """(the matches to show, in kick-off order, how many were left out). top_ids: the ESPN ids of the Premier League and Championship clubs."""
    if len(matches) <= limit:
        return list(matches), 0
    rank = lambda m: (-(m["home"]["id"] in top_ids or m["away"]["id"] in top_ids), -(m["home_score"] + m["away_score"]), m["kickoff"])  # noqa: E731
    chosen = sorted(matches, key=rank)[:limit]
    return sorted(chosen, key=lambda m: m["kickoff"]), len(matches) - limit


def html(matches, top_ids, limit=LIMIT):
    """The block, '' when there were no finished ties."""
    done = [m for m in matches if m["completed"]]
    if not done:
        return ""
    shown, rest = pick(done, set(top_ids), limit)
    name = round_name(done[0]["stage"])
    head = "FA Cup" + (f" · {name}" if name else "")
    note = f'<p class="muted">{rest} other tie{"s" if rest != 1 else ""} played.</p>' if rest else ""
    return f"<h3>{r.esc(head)}</h3>" + scores_html(shown) + note
