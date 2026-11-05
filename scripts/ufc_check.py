"""Can UFC.com's event page, rankings page and events list be read from here? Used by the manual 'UFC check' workflow to find out whether GitHub's servers are let in (ESPN's cricket pages are not). Exit 1 when the fights cannot be read.

  .venv/bin/python scripts/ufc_check.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kickoff import ufc, ufcrank  # noqa: E402
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
ok = len(picks) == 3
try:
    rk = ufcrank.listing(ufcrank.parse(get_bytes("https://www.ufc.com/rankings", retries=1, timeout=30).decode("utf-8", "replace")))
    print(f"rankings: {len(rk)} lists, first: {list(rk)[0]} -> {rk[list(rk)[0]][0]}")
    ok = ok and len(rk) == 13
except Exception as e:
    print("the rankings page could not be read:", e)
    ok = False
try:
    import re
    ev = sorted(set(re.findall(r'href="/event/([^"#?]+)"', get_bytes("https://www.ufc.com/events", retries=1, timeout=30).decode("utf-8", "replace"))))
    print(f"events list: {len(ev)} addresses, e.g. {ev[:3]}")
    ok = ok and len(ev) > 0
except Exception as e:
    print("the events list could not be read:", e)
    ok = False
sys.exit(0 if ok else 1)
