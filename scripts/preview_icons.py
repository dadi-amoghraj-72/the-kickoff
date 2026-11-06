"""One page with every rail icon, big and at the size the rail shows it, and what each one leads (D, 2026-11-05).

  .venv/bin/python scripts/preview_icons.py            writes docs/demo/icons.html and opens it
  add --publish to put it at https://dadi-amoghraj-72.github.io/the-kickoff/demo/icons.html, --no-open to skip opening it."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import render  # noqa: E402

js = (ROOT / "kickoff/static/rail-icons.js").read_text()
icons = {n: (spin == "true", svg) for n, spin, svg in re.findall(r"^  (\w+): \{ spin: (true|false), svg: '(.*)' \},?$", js, re.M)}
sec = json.loads(re.search(r"RAIL_SECTION_ICON = (\{.*?\});", js, re.S).group(1).replace("-", "_").replace("_", "-") if False else "{}") if False else {}
SECTION = {"big-stuff": "The Big Stuff", "on-today": "On Today", "arsenal": "Arsenal", "football": "Football", "cricket": "Cricket", "nba": "NBA", "nfl": "NFL", "mlb": "MLB", "f1": "F1",
           "tennis": "Tennis", "tour": "Tour Finals", "young-guns": "Young Guns", "other-sports": "Other Sports", "stories": "Interesting Stories", "quiet": "A quiet morning"}
by_sec = {}
for key, name in re.findall(r'"?([\w-]+)"?: "(\w+)"', re.search(r"RAIL_SECTION_ICON = \{(.*?)\};", js, re.S).group(1)):
    by_sec.setdefault(name, []).append(SECTION.get(key, key))
by_sport = {"rugby": "Other Sports: Rugby", "golf": "Other Sports: Golf", "ufc": "Other Sports: UFC", "badminton": "Other Sports: Badminton", "darts": "Other Sports: Darts", "chess": "Other Sports: Chess"}
for k, v in by_sport.items():
    by_sec.setdefault(k, []).append(v)
by_sec.setdefault("flag", []).append("The End (the finish of the page)")
cells = "".join(
    f'<div class="ic"><div class="bg"><svg viewBox="0 0 24 24">{svg}</svg></div><div class="disc"><span><svg viewBox="0 0 24 24">{svg}</svg></span></div>'
    f'<p class="nm">{render.esc(n)}</p><p class="us">{render.esc(", ".join(by_sec.get(n, ["(not used yet)"])))}</p><p class="mv">{"turns as you scroll" if spin else "sways a little"}</p></div>'
    for n, (spin, svg) in icons.items())
css = ".icgrid{display:grid;grid-template-columns:1fr 1fr;gap:18px 10px}.ic{text-align:center}.bg{width:84px;height:84px;margin:0 auto;color:var(--gold)}.bg svg,.disc svg{width:100%;height:100%}" \
      ".disc{width:30px;height:30px;margin:8px auto;border-radius:50%;background:var(--pitch);border:1.5px solid var(--gold);color:var(--gold);display:flex;align-items:center;justify-content:center}" \
      ".disc span{width:18px;height:18px;display:block}.nm{margin:2px 0;font-weight:700}.us{margin:0;font-size:14px}.mv{margin:0;font-size:13px;color:var(--muted)}"
body = f"<style>{css}</style><p>{len(icons)} icons. The big one, then the size on the rail (the disc), what it leads, and how it moves.</p><div class=\"icgrid\">{cells}</div>"
edition = {"date": "2026-11-05", "dummy": False, "home": "../index.html", "banner": "Demo: every icon of the progress bar.", "headlines": [], "sections": [{"id": "icons", "title": "The Rail Icons", "html": body}]}
page = ROOT / "docs" / "demo" / "icons.html"
page.write_text(render.render_edition(edition))
print(f"Built {page.relative_to(ROOT)} with {len(icons)} icons: {', '.join(icons)}")
missing = [n for n in icons if n not in by_sec]
print("Not used by any section:", missing or "none")
if "--no-open" not in sys.argv and sys.platform == "darwin":
    subprocess.run(["open", str(page)])
if "--publish" in sys.argv:
    def git(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    git("add", "docs/demo/icons.html")
    done = git("commit", "-m", "Add the rail icons sheet")
    print("Published: https://dadi-amoghraj-72.github.io/the-kickoff/demo/icons.html" if done.returncode == 0 and git("push", "origin", "main").returncode == 0 else "Nothing published.")
