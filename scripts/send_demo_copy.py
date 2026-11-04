"""One-off: build the live demo page of everything built so far, publish it, and send its link to Telegram.

  .venv/bin/python scripts/send_demo_copy.py --dry-run   build the page here and show the message; publish nothing, send nothing
  .venv/bin/python scripts/send_demo_copy.py --now       build, publish and send straight away
  .venv/bin/python scripts/send_demo_copy.py --now --claude   the same, with Claude's notes and overviews (a few cents up to about 30 cents; uses your key)
  .venv/bin/python scripts/send_demo_copy.py --scheduled run by the one-off Mac job (only on 4 November 2026 Singapore time; removes the job afterwards)
To switch the one-off job on (7:15am Singapore time on 4 November 2026, once):
  launchctl bootstrap gui/$(id -u) scripts/com.thekickoff.democopy.plist
To cancel it:  launchctl bootout gui/$(id -u)/com.thekickoff.democopy

Plain text, no Claude, no cost, unless you add --claude. It uses your .env (Telegram token and chat id) by itself; nothing secret is printed or logged.
Everything is logged to preview/demo-copy.log. This is not the daily schedule, which stays off."""
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import render  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.telegram import send_message  # noqa: E402

URL = "https://dadi-amoghraj-72.github.io/the-kickoff/demo/"
LABEL = "com.thekickoff.democopy"
PLIST = ROOT / "scripts" / f"{LABEL}.plist"   # kept in the project; you switch it on with one launchctl command (see below)
LOG = ROOT / "preview" / "demo-copy.log"
TARGET = date(2026, 11, 4)


def log(text):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{datetime.now(ZoneInfo('Asia/Singapore')):%Y-%m-%d %H:%M:%S} {text}\n")
    print(text)


def uninstall():
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    PLIST.unlink(missing_ok=True)
    log("the one-off job is removed")


def main():
    dry, scheduled = "--dry-run" in sys.argv, "--scheduled" in sys.argv
    today = datetime.now(ZoneInfo("Asia/Singapore")).date()
    if scheduled and today != TARGET:
        log(f"not the day ({today}): doing nothing")
        return 0
    cmd = [str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "scripts" / "build_demo.py"), "--no-open"] + (["--claude"] if "--claude" in sys.argv else []) + ([] if dry else ["--publish"])
    log("building the demo page" + (" (dry run: not published)" if dry else ""))
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = "\n".join((run.stdout or "").strip().splitlines()[-8:])
    log(tail)
    day = today.isoformat()
    found = re.search(r"sections: (.*)", run.stdout or "")
    names = {"football": "football", "cricket": "cricket", "f1": "F1", "tennis": "tennis", "nfl": "NFL", "nba": "NBA", "mlb": "MLB"}
    have = ", ".join(names.get(x.strip(), x.strip()) for x in found.group(1).split(",")) if found else "everything built so far"
    message = (f"The Kickoff · {today:%a} {today.day} {today:%b} (demo copy)\n\n"
               f"A live copy of everything built so far, from live data. Today's page has: {have}. "
               "The daily schedule is still off.\n\n" + URL)
    if "--claude" in sys.argv:
        message = message.replace("(demo copy)", "(demo copy, with Claude)", 1)
    if run.returncode != 0:
        message = f"The Kickoff demo copy did not build (exit {run.returncode}). Nothing was published. Details are in preview/demo-copy.log."
        log("BUILD FAILED: " + ((run.stderr or "").strip().splitlines() or ["no message"])[-1][:200])
    elif dry:
        log("DRY RUN: the message would be:\n" + message)
        return 0
    else:
        marker = render.nice_date(day)
        for _ in range(20):   # GitHub Pages takes a minute or two after a push
            try:
                if marker in urllib.request.urlopen(URL + f"?t={int(time.time())}", timeout=20).read().decode("utf-8", "replace"):
                    break
            except Exception:
                pass
            time.sleep(15)
        else:
            log("the page is not showing the new date yet; sending the link anyway")
    if dry:
        return 0
    load_env()
    try:
        send_message(message)
        log("sent to Telegram")
    except Exception as e:  # the token never appears in these messages
        log(f"Telegram failed: {e}")
        return 1
    finally:
        if scheduled:
            uninstall()
    return 0


if __name__ == "__main__":
    sys.exit(main())
