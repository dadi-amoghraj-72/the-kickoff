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
    today = ["", "Today:", *[f"\u2022 {x}" for x in edition["ping_today"][:3]]] if edition.get("ping_today") else []     # only on a quiet morning (D, 2026-11-05)
    return "\n".join([head, "", *lines, *today, "", f"{base}/editions/{edition['date']}/"])


def send_document(path, caption="", name=None):
    """Send a file (the edition's page as an HTML file that opens on a phone) to the chat. Standard library only; errors never contain the token."""
    import mimetypes
    import uuid
    from pathlib import Path
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")
    p = Path(path)
    boundary = uuid.uuid4().hex
    fields = {"chat_id": chat_id, **({"caption": caption[:1000]} if caption else {})}
    body = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    mime = mimetypes.guess_type(name or p.name)[0] or "application/octet-stream"
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{name or p.name}"\r\nContent-Type: {mime}\r\n\r\n').encode() + p.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{os.environ.get('TELEGRAM_API_BASE', 'https://api.telegram.org')}/bot{token}/sendDocument", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Telegram send failed: HTTP {e.code}") from None
    except Exception as e:
        raise RuntimeError(f"Telegram send failed: {type(e).__name__}") from None


def send_message(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing")
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(f"{os.environ.get('TELEGRAM_API_BASE', 'https://api.telegram.org')}/bot{token}/sendMessage", data=data)
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as e:
        # Report only the status code, so the token never ends up in an error message.
        raise RuntimeError(f"Telegram send failed: HTTP {e.code}") from None
    except Exception as e:
        raise RuntimeError(f"Telegram send failed: {type(e).__name__}") from None
