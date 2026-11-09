"""The backup for when GitHub is slow or down (D, 2026-11-05: Pages built slowly and then every push was rejected).

Three layers, none of which needs GitHub to deliver the news:
  1. The ping waits until the page really opens (`wait_for_page`). If it does not in time, the ping carries the digest as text and the whole edition as an HTML file
     (`fallback`): the file opens on a phone, in any browser, with no website at all.
  2. A watchdog on the Mac (scripts/watchdog.py, a launchd job at 7:40am) checks that today's page is live. If it is not, the Mac builds the edition itself (or uses the one the
     GitHub run left) and sends the same text and file, then tries to push (`run_watchdog`).
  3. If even that cannot build an edition, D gets a plain alert that there is no edition today.
Everything is injectable, so the tests run without a network."""
import re
import time
import urllib.request

from kickoff import render
from kickoff.http import USER_AGENT

DIGEST_SECTIONS = ("big-stuff", "on-today")
LIMIT = 3500                       # Telegram allows 4096 characters in one message


def page_url(edition, base):
    return f"{base.rstrip('/')}/editions/{edition['date']}/"


def page_live(url, fetch=None):
    """True when the page answers 200 and is The Kickoff's. A 404, a timeout or anything else is 'not live'."""
    try:
        if fetch:
            return bool(fetch(url))
        req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"t={int(time.time())}", headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200 and b"The Kickoff" in resp.read(20000)
    except Exception:
        return False


def wait_for_page(url, timeout=900, interval=20, live=page_live, sleep=time.sleep, clock=time.monotonic):
    """True as soon as the page is live; False when `timeout` seconds pass first."""
    end = clock() + timeout
    while True:
        if live(url):
            return True
        if clock() + interval > end:
            return False
        sleep(interval)


def to_text(html):
    """A section's html as plain text lines: headings as '> Title', list items and paragraphs as lines, tags gone."""
    s = re.sub(r"<h[34][^>]*>(.*?)</h[34]>", lambda m: f"\n> {m.group(1)}\n", html, flags=re.S)
    s = re.sub(r"</(li|p|tr)>", "\n", s)
    s = re.sub(r"<li[^>]*>", "• ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'").replace("&quot;", '"')
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", s)).strip()


def digest(edition, note="", limit=LIMIT):
    """The text of the fallback message: date, headlines, then The Big Stuff and On Today as plain text, cut at `limit` characters."""
    from datetime import date
    d = date.fromisoformat(edition["date"])
    head = f"The Kickoff · {d:%a} {d.day} {d:%b}" + (f"\n{note}" if note else "")
    lines = [f"{i}. {h}" for i, h in enumerate(edition.get("headlines", [])[:3], 1)]
    parts = [head, *(["", *lines] if lines else [])]
    for s in edition["sections"]:
        if s["id"] in DIGEST_SECTIONS:
            parts += ["", s["title"].upper(), to_text(s["html"])]
    text = "\n".join(parts)
    return text if len(text) <= limit else text[:limit].rsplit("\n", 1)[0] + "\n… (the rest is in the attached page)"


def standalone(edition):
    """The whole page as one self-contained HTML string (its style is already inside; only the web fonts are fetched when online)."""
    return render.render_edition({**edition, "home": "#"})


def writer(folder=None):
    """A write(name, html) -> path function for `fallback`: saves the page in a fresh temporary folder (or `folder`) and returns the file's path."""
    import tempfile
    from pathlib import Path
    base = Path(folder or tempfile.mkdtemp())

    def write(name, html):
        path = base / name
        path.write_text(html, encoding="utf-8")
        return path
    return write


def fallback(edition, send_text, send_file, write, note="The page is not live yet, so here is the edition itself (open the attached file)."):
    """Send the digest and the page. write(name, html) -> a path for the file. Returns what was sent."""
    path = write(f"the-kickoff-{edition['date']}.html", standalone(edition))
    send_text(digest(edition, note))
    send_file(path, "The Kickoff, full page")
    return ["text", "file"]


WAIT_FOR_GITHUB = 45 * 60      # seconds the watchdog waits for a GitHub run still in progress
POLL = 120


def run_watchdog(day, deps):
    """The Mac's morning check. deps: live(day) -> bool, pull(), have_local(day) -> bool, build(day) -> bool, send(day), push(), alert(text), already_sent(day) -> bool,
    mark_sent(day). Returns 'ok', 'sent', 'sent-not-pushed', 'already' or 'failed'."""
    def alert(text):
        try:
            deps.alert(text)
        except Exception:                      # the alert may fail for the same reason as the send; the result still says 'failed'
            pass

    if deps.live(day):
        return "ok"
    if deps.already_sent(day):
        return "already"
    waited = 0
    while getattr(deps, "github_running", lambda: False)() and waited < WAIT_FOR_GITHUB:    # GitHub's run is still going (it starts up to 30+ minutes late): let it finish
        deps.wait(POLL)                                                                     # rather than send a second edition beside it (D, 2026-11-09)
        waited += POLL
        if deps.live(day):
            return "ok"
    try:
        deps.pull()
    except Exception:
        pass
    if not deps.have_local(day):
        if not deps.build(day):
            alert(f"The Kickoff: no edition for {day} could be built, here or on GitHub. Yesterday's page is still up.")
            return "failed"
    try:
        deps.send(day)
    except Exception:
        alert(f"The Kickoff: the edition for {day} was built but could not be sent to Telegram.")
        return "failed"
    deps.mark_sent(day)
    try:
        return "sent" if deps.push() else "sent-not-pushed"
    except Exception:
        return "sent-not-pushed"
