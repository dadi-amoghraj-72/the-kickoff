"""Preview Around The Sporting World and Interesting Stories on today's real pages (2026-11-05).

  .venv/bin/python scripts/preview_around.py            code only (no Claude): free; writes docs/demo/around.html and opens it
  .venv/bin/python scripts/preview_around.py --claude   with Claude sorting and summarising the headlines and picking stories (about a cent; needs the key in .env, which only D runs)
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/around.html, --no-open to skip opening it.

Besides the section itself the page lists the headlines code kept as candidates and the covered-sport headlines it left out, so the rules can be judged. Nothing is saved."""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import around, render  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.sources import other_sports  # noqa: E402

load_env()
now = datetime.now(timezone.utc)
client = None
if "--claude" in sys.argv:
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("No ANTHROPIC_API_KEY found: run this from your own terminal, where .env is read.")
    import anthropic
    client = anthropic.Anthropic()
src = other_sports.Source()
out = around.run(now, {}, src, client)
items = src.news()
cands = around.candidates(items, now)
kept = {c["link"] for c in cands}
esc = render.esc
cand_rows = "".join(f"<li>{esc(c['sport'])}{' (spotlight)' if c['spotlight'] else ''} · {esc(c['source'])} · {esc(c['title'])}</li>" for c in cands) or "<li>None in the last 36 hours.</li>"
left = [i for i in items if i["link"] not in kept and around.sport_of(i)[0]][:12]
left_rows = "".join(f"<li>{esc(around.sport_of(i)[0])} · {esc(i['source'])} · {esc(i['title'])} (no result or news words)</li>" for i in left) or "<li>None.</li>"
sections = [{"id": s["id"], "title": s["title"], "html": s["html"]} for s in out["sections"]] or [{"id": "other-sports", "title": "Other Sports", "html": "<p>Nothing from these sports today.</p>"}]
u = out["stats"]["claude_usage"]
note = "Claude is off: only headlines that read like a result are shown (as the source wrote them), and there are no stories." if client is None else f"Claude used {u['input']} input and {u['output']} output tokens."
sections.append({"id": "why", "title": "What the rules saw", "html": f"<p class='muted'>{esc(note)} Pages read: {len(other_sports.FEEDS)} feeds and the ESPN rugby, golf and UFC boards; {len(items)} headlines in all.</p>"
                 f"<h4>Candidates sent for sorting</h4><ul class='standouts'>{cand_rows}</ul><h4>Covered-sport headlines left out</h4><ul class='standouts'>{left_rows}</ul>"})
edition = {"date": now.date().isoformat(), "dummy": False, "banner": "REVIEW of Around The Sporting World on today's real pages.", "home": "../index.html", "headlines": [], "sections": sections}
path = ROOT / "docs" / "demo" / "around.html"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(render.render_edition(edition))
print("Built", path.relative_to(ROOT), "|", out["stats"])
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(path)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/around.html")
    done = git("commit", "-m", "Add Around The Sporting World review page")
    if done.returncode != 0:
        print("Nothing new to publish." if "nothing to commit" in (done.stdout + done.stderr) else "Could not commit: " + (done.stderr or done.stdout)[:300])
    else:
        git("pull", "--rebase")
        print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/around.html" if git("push", "origin", "main").returncode == 0 else "Push failed.")
