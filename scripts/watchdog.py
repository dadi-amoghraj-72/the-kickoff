"""The Mac's morning check (the backup for GitHub). Runs at 7:40am Singapore time (scripts/com.thekickoff.watchdog.plist) and does nothing at all when today's page is live.

  .venv/bin/python scripts/watchdog.py --dry-run     say what it would do now; build nothing, send nothing
  .venv/bin/python scripts/watchdog.py               the real check
  add --date 2026-11-06 to check another Singapore date, --no-claude to build without Claude, --force to run before go-live (to rehearse). Until the daily workflow has a schedule
(go-live) it does nothing, so switching its Mac job on early is harmless.

If the page is not live: pull from GitHub (it may have the edition), build the edition here if there is none (scripts/daily.py, Claude on, the budget guard applies), send the digest as
text and the page as an HTML file to Telegram, then try to push (commit "Edition (Mac backup)"). If an edition cannot be built or sent, you get a plain alert. It sends at most once a
day. Uses your .env by itself; nothing secret is printed. Log: preview/watchdog.log."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import backup, render  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.telegram import DEFAULT_BASE_URL, send_document, send_message  # noqa: E402

LOG = ROOT / "preview" / "watchdog.log"
MARK = ROOT / "preview" / "watchdog-sent"
dry = "--dry-run" in sys.argv
day = date.fromisoformat(sys.argv[sys.argv.index("--date") + 1]) if "--date" in sys.argv else datetime.now(ZoneInfo("Asia/Singapore")).date()


def log(text):
    LOG.parent.mkdir(exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {text}"
    print(line)
    with LOG.open("a") as f:
        f.write(line + "\n")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def edition_path(d):
    return render.DATA_DIR / f"{d.isoformat()}.json"


class Deps:
    def live(self, d):
        return backup.page_live(f"{DEFAULT_BASE_URL}/editions/{d.isoformat()}/")

    def pull(self):
        git("pull", "--rebase", "--autostash")

    def have_local(self, d):
        return edition_path(d).exists()

    def build(self, d):
        cmd = [str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "scripts" / "daily.py"), "--date", d.isoformat()] + ([] if "--no-claude" in sys.argv else ["--claude"])
        done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        log(f"build: exit {done.returncode}")
        return done.returncode == 0 and edition_path(d).exists()

    def send(self, d):
        ed = json.loads(edition_path(d).read_text())
        out = Path(tempfile.mkdtemp())
        backup.fallback(ed, send_message, send_document, lambda name, html: (out / name).write_text(html) or out / name,
                        "The page is not live yet (GitHub is slow or down), so here is the edition itself: open the attached file.")

    def already_sent(self, d):
        return MARK.exists() and MARK.read_text().strip() == d.isoformat()

    def mark_sent(self, d):
        MARK.parent.mkdir(exist_ok=True)
        MARK.write_text(d.isoformat())

    def push(self):
        git("add", "data", "docs")
        done = git("commit", "-m", f"Edition {day} (Mac backup)")
        if done.returncode != 0 and "nothing to commit" not in (done.stdout + done.stderr):
            return False
        git("pull", "--rebase", "--autostash")
        return git("push", "origin", "main").returncode == 0

    def alert(self, text):
        send_message(text)


class DryDeps(Deps):
    def pull(self):
        log("(dry) would pull")

    def build(self, d):
        log("(dry) would build the edition here with scripts/daily.py")
        return True

    def send(self, d):
        log("(dry) would send the digest as text and the page as an HTML file")

    def mark_sent(self, d):
        pass

    def push(self):
        log("(dry) would commit and push")
        return True

    def alert(self, text):
        log(f"(dry) would alert: {text}")


def schedule_is_on():
    """True once the daily workflow has an uncommented `schedule:` block, i.e. after go-live. Until then there is nothing to watch over (D's rule: the schedule stays OFF)."""
    import re
    text = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
    return bool(re.search(r"^\s*schedule:", re.sub(r"(?m)#.*$", "", text), re.M))


load_env()
if not schedule_is_on() and "--force" not in sys.argv:
    log("the daily schedule is still off, so there is nothing to watch over (use --force to rehearse)")
    sys.exit(0)
log(f"watchdog for {day}" + (" (dry run)" if dry else ""))
result = backup.run_watchdog(day, DryDeps() if dry else Deps())
log(f"result: {result}")
sys.exit(1 if result == "failed" else 0)
