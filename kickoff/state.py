"""Small JSON state files in data/state/: what was published last, so the next run knows what changed."""
import json
import os
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "data" / "state"


def load(name, default=None, directory=None):
    path = (directory or STATE_DIR) / f"{name}.json"
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text())


def save(name, obj, directory=None):
    directory = directory or STATE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)  # swap in whole, so a crash never leaves a half-written file
