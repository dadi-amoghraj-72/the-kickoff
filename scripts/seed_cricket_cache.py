"""Load a scorecard you already downloaded into the cricket cache, so it costs no calls to show.

  .venv/bin/python scripts/seed_cricket_cache.py
Uses the real saved scorecard in tests/fixtures (NZ v India, 1 Nov 2026) and its match record. Nothing is fetched."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import cricket  # noqa: E402

fx = ROOT / "tests" / "fixtures"
card = json.loads((fx / "cricket_scorecard_nz_ind.json").read_text())
match = next(m for m in json.loads((fx / "cricket_current.json").read_text()) if m["id"] == card["id"])
cricket.persist_cards({card["id"]: {"summary": cricket.summary(card, match), "standouts": cricket.standouts(card, match)}})
print("Cached the scorecard for:", match["name"])
