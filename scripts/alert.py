"""Send D a short Telegram alert that the daily run failed (the workflow runs this only when a step failed). Standard library only."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kickoff.envfile import load_env  # noqa: E402
from kickoff.telegram import send_message  # noqa: E402

load_env()
run = ""
if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY"):
    run = f"\n{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
send_message("The Kickoff: this morning's run failed, so there is no new edition. Yesterday's page is still up." + run)
print("Alert sent.")
