"""Send a message through the Telegram bot. Standard library only."""
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

DEFAULT_BASE_URL = "https://dadi-amoghraj-72.github.io/the-kickoff"


def build_message(edition, base_url=None):
    """Plain message: date, top three headlines and the link to that day's page."""
    base = (base_url or os.environ.get("PAGES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    d = date.fromisoformat(edition["date"])
    head = f"The Kickoff · {d:%a} {d.day} {d:%b}" + (" (test edition)" if edition.get("dummy") else "")
    lines = [f"{i}. {h}" for i, h in enumerate(edition["headlines"][:3], 1)]
    return "\n".join([head, "", *lines, "", f"{base}/editions/{edition['date']}/"])


def send_message(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as e:
        # Report only the status code, so the token never ends up in an error message.
        raise RuntimeError(f"Telegram send failed: HTTP {e.code}") from None
    except Exception as e:
        raise RuntimeError(f"Telegram send failed: {type(e).__name__}") from None
