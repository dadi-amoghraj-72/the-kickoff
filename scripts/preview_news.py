"""Preview the news block with live feeds. Writes preview/news.html.

  .venv/bin/python scripts/preview_news.py            code filter only: no Claude, no keys, free
  .venv/bin/python scripts/preview_news.py --claude   Claude classifies and summarises the candidates (cents)
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import news, notes, render, settings  # noqa: E402
from kickoff.envfile import load_env  # noqa: E402
from kickoff.http import safe  # noqa: E402
from kickoff.sources import espn, feeds  # noqa: E402

tables = {lg: safe(f"{lg} table", espn.get_table, lg) for lg in espn.LEAGUES}
items = feeds.fetch_all()
now = datetime.now(timezone.utc)
cands = news.candidates(items, news.club_aliases(tables), now)
print(f"{len(items)} items fetched, newest {max(i['published'] for i in items):%d %b %H:%M} UTC | {len(cands)} candidates in the last 36 hours\n")
for c in cands:
    print(f"  [{c['hint']:14}] {c['source']:12} {c['title'][:75]}  ({', '.join(c['clubs'])[:40]})")

shown = []
if "--claude" in sys.argv and cands:
    import anthropic
    load_env()
    results, usage = news.classify(anthropic.Anthropic(), cands)
    print(f"\nClaude ({settings.NEWS_MODEL}) kept {sum(1 for r in results.values() if r['kind'] != 'none')} of {len(cands)}:")
    for c in cands:
        r = results.get(c["link"])
        if r:
            print(f"  {r['kind']:19} {r['club'] or '-':18} {c['title'][:55]}")
            print(f"      summary: {r['summary']}" + (f"   (rejected: {'; '.join(r['problems'])})" if r["problems"] else ""))
    shown = news.apply_rules(cands, results)
    print(f"\nAfter D's rules, {len(shown)} item(s) would be shown. Tokens: {usage['input']} in, {usage['output']} out, ~${notes.cost(usage, settings.NEWS_MODEL):.4f}")
body = news.html(shown, "arsenal", "Team News") + news.html(shown, "football", "Transfers And Managers")
(ROOT / "preview").mkdir(exist_ok=True)
(ROOT / "preview" / "news.html").write_text(render._page("News preview", "", f"<main><section>{body or '<p class=muted>Nothing credible to report.</p>'}</section></main>"))
print("\nWrote preview/news.html")
