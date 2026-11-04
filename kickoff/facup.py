"""The FA Cup block: the ties finished since the last edition, from ESPN (the `eng.fa` league), with the round named in the heading.

A round can have dozens of ties (33 on a first-round Saturday), mostly between clubs nobody follows, so a big day shows the 12 that matter most: ties with a
Premier League or Championship club first, then the highest-scoring of the rest, and one line says how many other ties were played. A small day shows every tie.
No table, no Claude."""
from kickoff import render as r
from kickoff.scoreboard import scores_html

LIMIT = 12


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
