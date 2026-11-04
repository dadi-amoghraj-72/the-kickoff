"""The daily run. Builds today's edition from every sport, saves the state and rebuilds the site. Does not send or publish anything.

  .venv/bin/python scripts/daily.py --dry-run            a rehearsal on real data: writes only into preview/daily-dry-run/ (a private copy), changes nothing real
  .venv/bin/python scripts/daily.py --dry-run --claude   the same, with Claude's notes (costs a little; the budget guard applies)
  .venv/bin/python scripts/daily.py                      the real run: writes data/editions, data/state and docs/ (the workflow then commits them)
  --date 2026-11-05    a Singapore date other than today      --force    rebuild a date that already has an edition

Exit code 1 means every sport failed (the workflow then sends the alert). One or two failed sports are not an error: their section says "No data this morning"."""
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import daily, render, telegram  # noqa: E402
from kickoff import state as state_files  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402

args = [a for a in sys.argv[1:] if not a.startswith("--")]
dry, force, use_claude = "--dry-run" in sys.argv, "--force" in sys.argv, "--claude" in sys.argv
day = date.fromisoformat(args[0]) if args else datetime.now(ZoneInfo("Asia/Singapore")).date()
if "--date" in sys.argv:
    day = date.fromisoformat(sys.argv[sys.argv.index("--date") + 1])
load_env()

if dry:
    base = ROOT / "preview" / "daily-dry-run"
    shutil.rmtree(base, ignore_errors=True)
    data_dir, state_dir, docs_dir = base / "editions", base / "state", base / "docs"
    for src, dst in ((ROOT / "data" / "editions", data_dir), (ROOT / "data" / "state", state_dir)):
        if src.exists():
            shutil.copytree(src, dst)
else:
    data_dir, state_dir, docs_dir = render.DATA_DIR, state_files.STATE_DIR, render.DOCS_DIR
data_dir.mkdir(parents=True, exist_ok=True)

if daily.edition_exists(day, data_dir) and not force:
    print(f"The edition for {day} already exists. Nothing to do (use --force to rebuild it).")
    sys.exit(0)

now = datetime.now(timezone.utc)
before = daily.load_state(state_dir)
out = daily.run_day(now, day, before, daily.real_adapters, use_claude=use_claude)
ed = out["edition"]
if len(out["failed"]) == len(daily.real_adapters(None)):
    print("Every sport failed:", ", ".join(out["problems"]), file=sys.stderr)
    sys.exit(1)

(data_dir / f"{day.isoformat()}.json").write_text(json.dumps(ed, indent=2, ensure_ascii=False) + "\n")
changed = daily.save_state(out["state"], before, state_dir)
state_files.save("run_log", {"date": day.isoformat(), "built": ed["built"], "failed": out["failed"], "problems": out["problems"], "claude": ed["claude"],
                             "budget": out["budget"]}, state_dir)
dates = render.build_site(data_dir, docs_dir)

b = out["budget"]
print(f"Edition {day}{' (dry run, nothing real changed)' if dry else ''} | Claude: {ed['claude']} | sections: {', '.join(s['id'] for s in ed['sections'])}")
print(f"Budget: ${b['spent']:.2f} of ${b['budget']:.2f} this month ({b['pct'] * 100:.0f}%), mode {b['mode']}")
print("Headlines:", ed["headlines"])
print("State files changed:", ", ".join(changed) or "none")
if out["problems"]:
    print("Parts that failed or were skipped (the rest was built):", ", ".join(out["problems"]))
print("\nThe Telegram message would be:\n" + telegram.build_message(ed))
page = docs_dir / "editions" / day.isoformat() / "index.html"
print(f"\nWrote {page.relative_to(ROOT)} ({len(dates)} editions in the archive)")
if dry and "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
    print("Opened it in your browser.")
