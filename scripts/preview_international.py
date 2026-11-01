"""Preview the international block for a date, as a page. Opens it in your browser; --publish puts it on the website.

  .venv/bin/python scripts/preview_international.py 2026-10-05            the morning after matchday 4 (plain stake lines, free)
  .venv/bin/python scripts/preview_international.py 2026-11-12            the morning of matchday 5, before any result
  .venv/bin/python scripts/preview_international.py 2026-10-05 --claude   Claude phrases the stake lines (a few cents)
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/international-<date>.html
  add --no-open to build without opening the browser

The standings are always as of now (after matchday 4), so these two dates are consistent with them.
"""
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import international, notes, render, settings  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
day = date.fromisoformat(args[0]) if args else datetime.now(timezone.utc).date()
now = datetime(day.year, day.month, day.day, 0, 30, tzinfo=timezone.utc)  # 08:30 in Singapore: the morning edition
client = None
if "--claude" in sys.argv:
    import anthropic
    load_env()
    client = anthropic.Anthropic()

out = international.run(day, now, client)
if not out["html"]:
    sys.exit(f"No international football for {day}: not near a break. Try 2026-10-05 or 2026-11-12.")
banner = (f"Preview of the international block for {render.nice_date(day.isoformat())}. "
          + ("Stake lines written by Claude, checked by code. " if client else "Stake lines are the plain code-written ones, no AI. ")
          + "The ranking used for League B and C groups is a stand-in for FIFA's: " + (out["top30"] or {"source": "see the table notes"})["source"] + ".")
edition = {"date": day.isoformat(), "dummy": False, "banner": banner, "home": "../index.html", "headlines": [],
           "sections": [{"id": "international", "title": "International Football", "html": out["html"]}]}
(ROOT / "docs" / "demo").mkdir(parents=True, exist_ok=True)
page = ROOT / "docs" / "demo" / f"international-{day.isoformat()}.html"
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} | {out['html'].count('<table')} tables | problems: {out['problems'] or 'none'}")
if client:
    print(f"Claude: {out['usage']['input']} in, {out['usage']['output']} out, ~${notes.cost(out['usage'], settings.NEWS_MODEL):.4f}")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", str(page.relative_to(ROOT)))
    done = git("commit", "-m", f"Add international demo page ({day})")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        pushed = git("push", "origin", "main")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/" + page.name if pushed.returncode == 0 else "Push failed: " + pushed.stderr[:300])
