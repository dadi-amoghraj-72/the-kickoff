"""Send the Telegram ping for an edition.

  python3 scripts/send_ping.py --dry-run     show the message, send nothing
  python3 scripts/send_ping.py               send the latest edition's ping
  python3 scripts/send_ping.py 2026-11-02    send a specific date
  python3 scripts/send_ping.py --wait 900    (the daily workflow) wait up to 900 seconds for the page to be live before pinging; if it is not, send the digest as text
                                              and the whole edition as an HTML file instead (the backup for a slow or broken GitHub Pages). Only today's edition
                                              (Singapore date) is sent in this mode, never an older one.
  python3 scripts/send_ping.py --fallback    send the text-and-file version straight away (to rehearse the backup)
"""
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff import backup  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.render import DATA_DIR  # noqa: E402
from kickoff.telegram import DEFAULT_BASE_URL, build_message, send_document, send_message  # noqa: E402

argv = sys.argv[1:]
wait = int(argv[argv.index("--wait") + 1]) if "--wait" in argv else None
args = [a for i, a in enumerate(argv) if not a.startswith("--") and not (i and argv[i - 1] == "--wait")]
files = sorted(DATA_DIR.glob("*.json"))
path = DATA_DIR / f"{args[0]}.json" if args else (files[-1] if files else None)
if not path or not path.exists():
    sys.exit("No edition found. Run scripts/build.py first.")
edition = json.loads(path.read_text())
today = datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()
if wait is not None and not args and edition["date"] != today:
    sys.exit(f"The newest edition is {edition['date']}, not today ({today}): nothing sent.")

message = build_message(edition)
if "--dry-run" in argv:
    print("DRY RUN, nothing sent. The message would be:\n")
    print(message)
    print("\nThe backup (if the page is not live) would be:\n")
    print(backup.digest(edition, "The page is not live yet, so here is the edition itself (open the attached file)."))
    sys.exit(0)

load_env()
if "--fallback" in argv or (wait is not None and not backup.wait_for_page(message.splitlines()[-1], wait)):
    out = Path(tempfile.mkdtemp())
    sent = backup.fallback(edition, send_message, send_document, lambda name, html: (out / name).write_text(html) or out / name)
    print("Page not live in time, so sent the backup:", ", ".join(sent))
else:
    send_message(message)
    print("Sent. Check Telegram.")
