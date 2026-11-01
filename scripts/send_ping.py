"""Send the Telegram ping for an edition.

  python3 scripts/send_ping.py --dry-run     show the message, send nothing
  python3 scripts/send_ping.py               send the latest edition's ping
  python3 scripts/send_ping.py 2026-11-02    send a specific date
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff.envfile import load_env  # noqa: E402
from kickoff.render import DATA_DIR  # noqa: E402
from kickoff.telegram import build_message, send_message  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
files = sorted(DATA_DIR.glob("*.json"))
path = DATA_DIR / f"{args[0]}.json" if args else (files[-1] if files else None)
if not path or not path.exists():
    sys.exit("No edition found. Run scripts/build.py first.")

message = build_message(json.loads(path.read_text()))
if "--dry-run" in sys.argv:
    print("DRY RUN, nothing sent. The message would be:\n")
    print(message)
else:
    load_env()
    send_message(message)
    print("Sent. Check Telegram.")
