"""Tests for the backup that delivers the news when GitHub is slow or down: waiting for the page, the text-and-file fallback, the Mac watchdog's decisions and the workflow wiring.
Run: .venv/bin/python scripts/test_backup.py"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kickoff import backup  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok and detail:
        print("   ", detail)


ED = {"date": "2026-11-09", "dummy": False, "headlines": ["Football: Arsenal 3–0 Spurs", "NFL: Jaguars win", "Cricket: India won"],
      "sections": [{"id": "big-stuff", "title": "The Big Stuff", "html": '<h3>Key Overnight Scores</h3><ul class="standouts"><li>Football: Arsenal 3–0 Spurs</li><li>NFL: Jaguars win &amp; more</li></ul>'},
                   {"id": "on-today", "title": "On Today", "html": '<h3>☀ While You\'re Up</h3><ul><li><span class="when">8pm</span> Premier League: Chelsea v Spurs</li></ul>'},
                   {"id": "football", "title": "Football", "html": "<p>Long football section that must not be in the digest.</p>"}]}

# ---- waiting for the page -----------------------------------------------------------------------
class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


c = Clock()
calls = []
check("the page is live at once: no waiting", backup.wait_for_page("u", 900, 20, lambda u: calls.append(u) or True, c.sleep, c.now) is True and c.t == 0 and len(calls) == 1)
c = Clock()
answers = iter([False, False, True])
check("the page goes live after two checks: waits 40 seconds and returns True", backup.wait_for_page("u", 900, 20, lambda u: next(answers), c.sleep, c.now) is True and c.t == 40, c.t)
c = Clock()
n = []
check("the page never goes live: gives up after the timeout and returns False, without waiting past it", backup.wait_for_page("u", 100, 20, lambda u: n.append(1) or False, c.sleep, c.now) is False and 90 <= c.t <= 100 and len(n) >= 5, (c.t, len(n)))
check("a page that does not answer (404, timeout) counts as not live", backup.page_live("https://invalid.invalid/x") is False)
check("page_live accepts an injected check", backup.page_live("u", lambda u: True) is True and backup.page_live("u", lambda u: False) is False)

# ---- the digest -------------------------------------------------------------------------------------
t = backup.digest(ED, "NOTE")
check("the digest has the date, the note, the headlines, and The Big Stuff and On Today as text", t.startswith("The Kickoff · Mon 9 Nov\nNOTE") and "1. Football: Arsenal 3–0 Spurs" in t and "THE BIG STUFF" in t
      and "• NFL: Jaguars win & more" in t and "> Key Overnight Scores" in t and "ON TODAY" in t and "8pm Premier League: Chelsea v Spurs" in t, t)
check("other sections are not in the digest, and no html tags are", "Long football section" not in t and not re.search(r"<[a-z/]", t))
big = {**ED, "sections": [{"id": "big-stuff", "title": "The Big Stuff", "html": "".join(f"<li>Line {i} " + "x" * 80 + "</li>" for i in range(100))}]}
td = backup.digest(big)
check("a long digest is cut under Telegram's limit at a line break, pointing to the attached page", len(td) < 4096 and td.endswith("(the rest is in the attached page)"), len(td))
check("the standalone page is the whole edition, self-contained (its style inline, every section there, no link back to an archive page that is not there)",
      "<style>" in backup.standalone(ED) and "Long football section" in backup.standalone(ED) and 'href="../../index.html"' not in backup.standalone(ED) and "The Kickoff" in backup.standalone(ED))

# ---- the fallback -------------------------------------------------------------------------------------
sent, written = [], {}
got = backup.fallback(ED, lambda x: sent.append(("text", x)), lambda p, cap: sent.append(("file", p, cap)), lambda name, html: written.setdefault(name, html) and f"/tmp/{name}")
check("the fallback sends the text and then the file named for the date", got == ["text", "file"] and sent[0][0] == "text" and sent[1] == ("file", "/tmp/the-kickoff-2026-11-09.html", "The Kickoff, full page") and "Long football section" in written["the-kickoff-2026-11-09.html"])

w = backup.writer()
p = w("x.html", "<html>\u00e9</html>")
check("the real file writer returns the file's path (the first live run returned a number and failed here)", isinstance(p, Path) and p.read_text(encoding="utf-8") == "<html>\u00e9</html>" and p.name == "x.html", p)
sent2 = []
backup.fallback(ED, lambda x: None, lambda path, cap: sent2.append(path), backup.writer())
check("the fallback with the real writer hands the sender a real file that holds the page", sent2 and Path(sent2[0]).exists() and "Long football section" in Path(sent2[0]).read_text(encoding="utf-8"))

# ---- the watchdog's decisions -------------------------------------------------------------------------
class Deps:
    def __init__(self, live=False, local=False, build=True, push=True, sent_before=False, send_fails=False):
        self.l, self.lo, self.b, self.p, self.sb, self.sf, self.log, self.alerts = live, local, build, push, sent_before, send_fails, [], []

    def live(self, d):
        return self.l

    def pull(self):
        self.log.append("pull")

    def have_local(self, d):
        return self.lo

    def build(self, d):
        self.log.append("build")
        return self.b

    def send(self, d):
        if self.sf:
            raise RuntimeError("telegram")
        self.log.append("send")

    def push(self):
        self.log.append("push")
        return self.p

    def alert(self, text):
        self.alerts.append(text)

    def already_sent(self, d):
        return self.sb

    def mark_sent(self, d):
        self.log.append("mark")


d = Deps(live=True)
check("the page is live: the watchdog does nothing at all", backup.run_watchdog("2026-11-09", d) == "ok" and d.log == [] and d.alerts == [])
d = Deps(local=True)
check("not live, the edition is already here (GitHub built it but could not publish): send it, no build, then try to push", backup.run_watchdog("2026-11-09", d) == "sent" and d.log == ["pull", "send", "mark", "push"], d.log)
d = Deps()
check("not live, no edition anywhere: build it here, send it, mark it sent, push", backup.run_watchdog("2026-11-09", d) == "sent" and d.log == ["pull", "build", "send", "mark", "push"], d.log)
d = Deps(push=False)
check("the news is sent even when the push fails (GitHub still down); the result says so", backup.run_watchdog("2026-11-09", d) == "sent-not-pushed" and "send" in d.log)
d = Deps(build=False)
r = backup.run_watchdog("2026-11-09", d)
check("an edition that cannot be built gives D a plain alert and sends nothing", r == "failed" and len(d.alerts) == 1 and "no edition" in d.alerts[0] and "send" not in d.log, (r, d.alerts))
d = Deps(local=True, send_fails=True)
r = backup.run_watchdog("2026-11-09", d)
check("an edition that cannot be sent to Telegram is reported (the alert may fail too, but it is tried) and is not marked as sent", r == "failed" and len(d.alerts) == 1 and "mark" not in d.log)
d = Deps(sent_before=True)
check("it never sends twice in a day", backup.run_watchdog("2026-11-09", d) == "already" and d.log == [])


class Boom(Deps):
    def pull(self):
        raise RuntimeError("git")


d = Boom(local=True)
check("a failing pull does not stop the send", backup.run_watchdog("2026-11-09", d) == "sent" and "send" in d.log)

# ---- the wiring -----------------------------------------------------------------------------------------
wf = (ROOT / ".github/workflows/daily.yml").read_text()
ping = wf[wf.index("- name: Telegram ping"):wf.index("- name: Alert D")]
check("the workflow's ping runs even if the publish step failed, waits for the page, and falls back to text and file", "always()" in ping and "--wait" in ping and "sleep 60" not in ping)
check("the alert step still runs on any failure", "if: failure()" in wf[wf.index("- name: Alert D"):])
check("the daily schedule is still OFF", "schedule:" not in re.sub(r"#.*", "", wf))
plist = (ROOT / "scripts/com.thekickoff.watchdog.plist").read_text()
check("the Mac job runs the watchdog at 7:40", "scripts/watchdog.py" in plist and "<integer>7</integer><key>Minute</key><integer>40</integer>" in plist)
sp = (ROOT / "scripts/send_ping.py").read_text()
check("in the daily mode only today's edition is ever sent (never yesterday's)", "not today" in sp and "wait is not None and not args" in sp)

wd = (ROOT / "scripts/watchdog.py").read_text()
check("the watchdog does nothing while the daily schedule is off (it only acts after go-live unless --force is given)", "schedule_is_on" in wd and "still off" in wd and "--force" in wd)

# ---- the file really goes out as a multipart upload ---------------------------------------------------
import os  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402

seen = {}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        seen["path"] = self.path
        seen["ctype"] = self.headers.get("Content-Type")
        seen["body"] = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update(TELEGRAM_API_BASE=f"http://127.0.0.1:{srv.server_port}", TELEGRAM_BOT_TOKEN="TESTTOKEN", TELEGRAM_CHAT_ID="42")
from kickoff import telegram  # noqa: E402

f = Path(tempfile.mkdtemp()) / "page.html"
f.write_text("<html>The Kickoff \u00e9</html>", encoding="utf-8")
telegram.send_document(f, "caption here")
b = seen["body"]
check("send_document posts multipart to sendDocument with the chat id, the caption and the file's bytes", seen["path"].endswith("/sendDocument") and seen["ctype"].startswith("multipart/form-data; boundary=")
      and b'name="chat_id"\r\n\r\n42' in b and b"caption here" in b and b'filename="page.html"' in b and "<html>The Kickoff \u00e9</html>".encode() in b and b.rstrip().endswith(b"--"))
os.environ["TELEGRAM_BOT_TOKEN"] = "TESTTOKEN"
srv.shutdown()
try:
    telegram.send_document(f)
    err = ""
except RuntimeError as e:
    err = str(e)
check("a failed upload reports no token or address", err.startswith("Telegram send failed") and "TESTTOKEN" not in err and "127.0.0.1" not in err, err)

print(f"\n{sum(results)} of {len(results)} passed")
sys.exit(0 if all(results) else 1)
