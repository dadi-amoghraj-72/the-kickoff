"""Build the site into docs/.

  python3 scripts/build.py --dummy    write today's dummy edition (Singapore date), then rebuild all pages
  python3 scripts/build.py            rebuild all pages from data/editions/*.json
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff import render  # noqa: E402
from kickoff.dummy import make_dummy  # noqa: E402

if "--dummy" in sys.argv:
    today = datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()
    render.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (render.DATA_DIR / f"{today}.json").write_text(json.dumps(make_dummy(today), indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote dummy edition data for {today}")

dates = render.build_site()
print(f"Built {len(dates)} edition(s) and the archive into docs/: {', '.join(dates)}")
