"""Save real Wikipedia pages for the major-events tests (run once, no keys): the 2025 All England Open, China Open and World Tour Finals (badminton), the 2025 Grand Slam of Darts and PDC World
Championship, the 2025 Women's EuroHockey Championship and the 2025 World Men's Handball Championship.

  .venv/bin/python scripts/save_majors_fixtures.py"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff.sources import wikipedia  # noqa: E402

FX = ROOT / "tests" / "fixtures"
PAGES = {"majors_all_england_2025": "2025 All England Open", "majors_china_open_2025": "2025 China Open (badminton)", "majors_wtf_2025": "2025 BWF World Tour Finals",
         "majors_gsod_2025": "2025 Grand Slam of Darts", "majors_pdc_wc_2025": "2025 PDC World Darts Championship", "majors_euro_hockey_w_2025": "2025 Women's EuroHockey Championship",
         "majors_handball_m_2025": "2025 World Men's Handball Championship"}
wiki = wikipedia.Source(pause=2.0)
for name, title in PAGES.items():
    for attempt in range(4):
        try:
            text = wiki.wikitext(title)
            (FX / f"{name}.txt").write_text(text)
            print("saved", name, len(text))
            break
        except Exception as e:
            print("retry", name, e)
            time.sleep(10 * (attempt + 1))
