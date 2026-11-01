"""Small web helper: retries, gzip, and error messages that never contain URLs (they can hold keys)."""
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "TheKickoff/1.0 (personal daily digest)"


class SourceError(Exception):
    """A data source failed. The message is safe to print."""


def get_bytes(url, params=None, headers=None, retries=2, timeout=20):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    last = "unknown"
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code < 500 and e.code != 429:
                break  # a client error won't fix itself on retry
        except Exception as e:
            last = type(e).__name__
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise SourceError(last)


def get_json(url, params=None, headers=None, **kw):
    try:
        return json.loads(get_bytes(url, params, headers, **kw))
    except ValueError:
        raise SourceError("response was not valid JSON") from None


def safe(name, fn, *args, **kwargs):
    """Run a source call. On failure, warn and return None so the rest of the edition carries on."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"WARN  source failed: {name}: {e}", file=sys.stderr)
        return None
