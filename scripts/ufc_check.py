"""Can UFC.com's event page be read from here? Used by the manual 'UFC check' workflow to find out whether GitHub's servers are let in (ESPN's cricket pages are not). Exit 1 when the fights cannot be read.

  .venv/bin/python scripts/ufc_check.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff import ufc  # noqa: E402
from kickoff.http import get_bytes  # noqa: E402

try:
    html = get_bytes("https://www.ufc.com/event/ufc-309", retries=1, timeout=30).decode("utf-8", "replace")
except Exception as e:
    print("UFC.com could not be read:", e)
    sys.exit(1)
parsed = ufc.parse(html)
picks = ufc.three(parsed)
print(f"read {len(html)} bytes; fights: main {len(parsed['main'])}, prelims {len(parsed['prelims'])}, early {len(parsed['early'])}; boxes: {len(picks)}")
for label, f in picks:
    print(" ", label, f["red"]["name"], "vs", f["blue"]["name"], "|", ufc.how(f))
sys.exit(0 if len(picks) == 3 else 1)
