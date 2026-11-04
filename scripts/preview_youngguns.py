"""Preview Young Guns on today's real games, plain lines (written by code) beside Claude's phrasing of the same facts, so D can see the difference (2026-11-05).

  .venv/bin/python scripts/preview_youngguns.py            plain lines only: free, writes docs/demo/youngguns.html and opens it
  .venv/bin/python scripts/preview_youngguns.py --claude   the same, with Claude phrasing the lines too (one small call, about a cent; needs the key in .env, which only D runs)
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/youngguns.html, --no-open to skip opening it.

Nothing is saved: the real state is only read. Today's candidates come from the real Premier League/Champions League matches, NBA, NFL, F1 and Grand Slam tennis finished in the window."""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import daily, render  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402

load_env()
now = datetime.now(timezone.utc)
day = now.astimezone(ZoneInfo("Asia/Singapore")).date()
client = None
if "--claude" in sys.argv:
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("No ANTHROPIC_API_KEY found: run this from your own terminal, where .env is read.")
    import anthropic
    client = anthropic.Anthropic()
out = daily.build_edition(now, day, daily.load_state(), daily.real_adapters(None), "plain", None, client)
y = out["stats"].get("youngguns", {})
plain, lines = y.get("plain", []), y.get("lines", [])
usage = y.get("claude_usage", {})
li = lambda items: "".join(f"<li>{render.esc(t)}</li>" for t in items) or "<li>Nobody notable in this window.</li>"  # noqa: E731
rows = "".join(f"<tr><td>{render.esc(a)}</td><td>{render.esc(b)}</td></tr>" for a, b in zip(plain, lines))
note = ("Claude is off for this build: both columns would be the same." if client is None else
        f"Claude used {usage.get('input', 0)} input and {usage.get('output', 0)} output tokens (a line that fails the check falls back to the plain one).")
body = (f'<p class="muted">{render.esc(note)}</p><table><thead><tr><th>Plain (code)</th><th>Claude</th></tr></thead><tbody>{rows}</tbody></table>'
        if rows else "<p>Nobody notable in this window.</p>")
why = "<h3>Why these players</h3><ul class=\"standouts\">" + li(y.get("why", [])) + "</ul>"
banner = f"REVIEW of Young Guns on real games finished in the last day ({y.get('candidates', 0)} candidates before the cap of 5). Rookies in the NBA/NFL/MLB, under 21 everywhere."
edition = {"date": day.isoformat(), "dummy": False, "banner": banner, "home": "../index.html", "headlines": [],
           "sections": [{"id": "young-guns", "title": "Young Guns", "html": body + why}]}
path = ROOT / "docs" / "demo" / "youngguns.html"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(render.render_edition(edition))
print("Built", path.relative_to(ROOT), "|", note)
for a, b in zip(plain, lines):
    print("  plain :", a, "\n  claude:", b)
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(path)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/youngguns.html")
    done = git("commit", "-m", "Add Young Guns review page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/youngguns.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
