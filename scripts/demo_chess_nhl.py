"""The demo page for the chess match table and the NHL leaders (D, 2026-11-24: a demo shows ONLY the new pieces, real data forced on today).
Writes docs/demo/chess-nhl.html. Free: Lichess and ESPN only, no Claude.
Run: .venv/bin/python scripts/demo_chess_nhl.py   then   swift scripts/tools/shot.swift docs/demo/chess-nhl.html /tmp/demo.png 360"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import chess_live, nhl, render  # noqa: E402
from kickoff.sources import espn_nhl, other_sports  # noqa: E402


class Sample(other_sports.Source):
    """The real match with MADE-UP results for games 1 to 3, seen on the morning of game 4."""
    MADE_UP = {"Game 1": "1/2-1/2", "Game 2": "1-0", "Game 3": "0-1"}

    def tour(self, tid):
        t = super().tour(tid)
        self.ids = {}
        for x in t["rounds"]:
            if x["name"] in self.MADE_UP:
                x["finished"], x["finishedAt"] = True, x["startsAt"] + 5 * 3600 * 1000
                self.ids[x["id"]] = self.MADE_UP[x["name"]]
        return t

    def round_pgn(self, rid):
        text = super().round_pgn(rid)
        return text.replace('[Result "*"]', f'[Result "{self.ids[rid]}"]') if rid in self.ids else text


now = datetime.now(timezone.utc)
live = chess_live.match_blocks(other_sports.Source(), now)
sample = chess_live.match_blocks(Sample(), datetime(2026, 11, 27, 23, 30, tzinfo=timezone.utc))
nh = nhl.run(None, date.today(), {}, espn_nhl.Source(), force=True)["html"]
ed = {"date": date.today().isoformat(), "dummy": False, "headlines": [], "sections": [
    {"id": "nhl", "title": "NHL Leaders", "html": '<p class="subhead">Saturdays. Real data, shown today for the demo.</p>' + nh},
    {"id": "other-sports", "title": "Chess: Real, This Morning", "html": live[0][0] if live else "<p>No match table today.</p>"},
    {"id": "stories", "title": "Chess: Made-Up Games 1 To 3", "html": '<p class="subhead">Made up to show a draw, wins and the next game\'s time. Not real.</p>' + (sample[0][0] if sample else "")}],
    "built": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "claude": "off"}
(ROOT / "docs/demo/chess-nhl.html").write_text(render.render_edition(ed))
print("wrote docs/demo/chess-nhl.html")
