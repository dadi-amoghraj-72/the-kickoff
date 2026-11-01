"""Run every offline test suite. Exits with an error if any suite fails.

  .venv/bin/python scripts/run_all_tests.py
"""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
failed = []
for path in sorted(here.glob("test_*.py")):
    run = subprocess.run([sys.executable, str(path)], capture_output=True, text=True)
    last = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
    print(f"{'ok  ' if run.returncode == 0 else 'FAIL'}  {path.stem:14} {last}")
    if run.returncode != 0:
        failed.append(path.stem)
print("\nALL SUITES PASS" if not failed else f"\nFAILING: {', '.join(failed)}")
sys.exit(1 if failed else 0)
