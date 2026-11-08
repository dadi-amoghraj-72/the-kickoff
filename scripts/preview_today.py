"""A rehearsal of the real edition on today's real data, with Claude, saved as a demo page. Changes nothing real: no state is written, no ping is sent, no edition is saved.

  .venv/bin/python scripts/preview_today.py --claude            builds docs/demo/today-real.html and opens it (a few cents; needs the key in .env, so D runs it)
  .venv/bin/python scripts/preview_today.py                     the same without Claude (free)
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/today-real.html, --no-open to skip opening it
  add --ping to send the Telegram message for this rehearsal (the headlines and the demo page's link; needs the Telegram key in .env, so D runs it)
  --state-from <commit>   the saved state to start from (default 1974d1f: the state before the first test morning, so games already reported on 5 Nov show again)
  --date 2026-11-05       the Singapore edition date (default: today)
  --label 002-b           the footer reads 'Edition #002-b' (a re-run of a day's edition with newer code)

Why not the real run? The real run remembers what it has reported, so a second run on the same day shows only what is new (and `--force` would replace the first edition of the day).
This rehearsal starts from an older state, so the page is as full as a morning edition, and On Today shows what is still to come from the minute you run it."""
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import daily, render  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.telegram import build_message, send_message  # noqa: E402

arg = lambda name, default: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default  # noqa: E731
commit = arg("--state-from", "1974d1f")
day = date.fromisoformat(arg("--date", datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()))
use_claude = "--claude" in sys.argv
load_env()

tmp = Path(tempfile.mkdtemp())
try:
    tar = subprocess.run(["git", "archive", commit, "data/state"], cwd=ROOT, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(tmp)], input=tar, check=True)
    before = daily.load_state(tmp / "data" / "state")
finally:
    pass
now = datetime.now(timezone.utc)
out = daily.run_day(now, day, before, daily.real_adapters, use_claude=use_claude, today=daily.real_today)
shutil.rmtree(tmp, ignore_errors=True)
ed = out["edition"]
spent_by = daily.extra_costs(out["stats"])
ed["banner"] = (f"Rehearsal of {render.nice_date(day.isoformat())} on real data, built at {now.astimezone(ZoneInfo('Asia/Singapore')):%-I:%M%p} Singapore time"
                + (" with Claude" if out["client_used"] else " without Claude") + ". Nothing was saved or sent; it starts from an older state, so games already reported this morning show again.")
ed["home"] = "../index.html"
if "--label" in sys.argv:
    ed["edition_label"] = arg("--label", "")
page = ROOT / "docs" / "demo" / "today-real.html"
page.write_text(render.render_edition(ed))
print(f"Sections: {', '.join(s['id'] for s in ed['sections'])}")
print(f"Problems: {out['problems'] or 'none'} | failed: {out['failed'] or 'none'}")
print(f"Claude used: {out['client_used']} | extra Claude cost outside football: ${spent_by[0]:.4f} ({spent_by[1]} calls)")
print(f"Wrote {page.relative_to(ROOT)}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/today-real.html")
    done = git("commit", "-m", "Add the today rehearsal demo page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout).strip()[:300])
    else:
        pushed = git("push", "origin", "main")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/today-real.html" if pushed.returncode == 0 else "Committed, but the push failed: " + pushed.stderr.strip()[:300])
if "--ping" in sys.argv:
    lines = build_message(ed).splitlines()
    lines[-1] = "https://dadi-amoghraj-72.github.io/the-kickoff/demo/today-real.html"          # the rehearsal page, not the real edition's address
    lines[0] += f" (Edition #{ed['edition_label']})" if ed.get("edition_label") else " (rehearsal)"
    message = "\n".join(lines)
    print("Telegram message:\n" + message)
    try:
        send_message(message)
        print("Sent.")
    except RuntimeError as e:
        print(f"Not sent: {e}")
