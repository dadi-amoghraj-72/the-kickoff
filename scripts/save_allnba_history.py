"""Save ESPN's All-NBA lists for every season it has (real data, no key): {season: {award id: [athlete ids]}} into tests/fixtures/espn_allnba_history.json, and the names of the
athletes who appear in the most seasons. Run: .venv/bin/python scripts/save_allnba_history.py  (about 240 requests, run in parallel)."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.sources import espn_awards  # noqa: E402

s = espn_awards.Source("basketball", "nba", pause=0)
IDS = ("44", "45", "46")


def one(args):
    y, a = args
    for _ in range(3):
        try:
            return y, a, s.winners(y, a)
        except Exception:
            continue
    return y, a, None


with ThreadPoolExecutor(8) as ex:
    res = list(ex.map(one, [(y, a) for y in range(2026, 1946, -1) for a in IDS]))
hist = {}
for y, a, w in res:
    hist.setdefault(str(y), {})[a] = w
(ROOT / "tests" / "fixtures" / "espn_allnba_history.json").write_text(json.dumps(hist))
bad = [(y, a) for y, a, w in res if w is None]
print("failed:", bad)
print("seasons with a list:", sorted(int(y) for y, d in hist.items() if any(d.values()))[:3], "...", sorted(int(y) for y, d in hist.items() if any(d.values()))[-3:], len([1 for d in hist.values() if any(d.values())]))
counts = {}
for d in hist.values():
    for ids in d.values():
        for i in set(ids or []):
            counts[i] = counts.get(i, 0) + 1
for i, n in sorted(counts.items(), key=lambda x: -x[1])[:8]:
    print(i, n, s.athlete(2026, i)["name"] if n else "")
