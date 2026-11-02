"""A short story of the race for Sunday's Grand Prix only: what the results say, plus what BBC Sport, The Guardian and ESPN reported.

Code picks the reports and gathers the facts; Claude only phrases (one call per race, a fraction of a cent); code checks every
number and name in the blurb against the facts and reports, and drops the blurb if it fails twice. No blurb is not an error: the
factual summary line and tables always stand on their own. Only headlines and short blurbs are read, never full articles."""
import json
import re
from datetime import timedelta

from kickoff import notes, settings
from kickoff import render as r
from kickoff.sources import feeds

FEEDS = [
    ("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/formula1/rss.xml"),
    ("The Guardian", "rss", "https://www.theguardian.com/sport/formulaone/rss"),
    ("ESPN", "espn", "https://site.api.espn.com/apis/site/v2/sports/racing/f1/news"),
]
WINDOW = timedelta(hours=48)  # reports from the race's start to two days later: after that they are about the next race
MAX_REPORTS = 8
MAX_WORDS = 65
# Claims that must come from the material: a lowercase word like "collision" or "champion" is not caught by the name and number checks.
CLAIMS = re.compile(r"\b(champion\w*|title|clinch\w*|crown\w*|crash\w*|collid\w*|collision\w*|contact|penalt\w*|safety|red-flag\w*|disqualif\w*|"
                    r"steward\w*|rain\w*|wet|puncture\w*|engine|mechanical|spun|spin|strateg\w*|undercut\w*|pit-?stop\w*|overtak\w*|dominan\w*|"
                    r"dominat\w*|youngest|oldest|maiden|incident\w*|damage\w*|brake\w*|tyre\w*|accident\w*)\b", re.I)
GENERIC = {"grand", "prix", "city", "formula", "united", "states"}

SYSTEM = """You write the race story for The Kickoff, a personal daily sports digest read by one F1 fan in Singapore.

Voice: plain, warm and specific, in your own words. British spelling. No emojis, no exclamation marks, no clichés.

Hard rules:
- Use ONLY the "facts" and the "reports" supplied. Each report is only a headline and a short blurb. Add nothing from memory: no form,
  history, records, opinions or predictions of your own.
- A big claim (a championship clinched, a record, who caused a collision) may be written only if a report states it, and then
  as that report states it. Never name a cause for a retirement unless a report does.
- Use names exactly as they appear in the facts or reports. Every number you write must come from them.
- Two or three sentences, at most 60 words. Lead with the most important thing that happened, not with the winner by habit.
- Do not describe movement in the standings (stays, remains, still, climbs, moves up) unless a report says it in those words.
- If the material is thin, write one short sentence. A short accurate story beats a long invented one."""
SCHEMA = {"type": "object", "properties": {"blurb": {"type": "string"}}, "required": ["blurb"], "additionalProperties": False}


def _surnames(rows):
    return [x["Driver"]["familyName"] for x in rows[:3]]


def keywords(race, rows):
    """Words that tie a report to this race: the place and country, and the podium's surnames."""
    loc = (race.get("Circuit") or {}).get("Location") or {}
    words = {w for text in (race.get("raceName", ""), loc.get("locality", ""), loc.get("country", "")) for w in re.findall(r"[\w'’-]+", text)}
    words = {w for w in words if len(w) > 3 and w.lower() not in GENERIC}
    return words | set(_surnames(rows))


def pick_reports(items, race, rows, start):
    """Reports published after lights-out and within 48 hours, naming the place or a podium driver; the most relevant first."""
    words = {w.lower() for w in keywords(race, rows)}
    out = []
    for i in items:
        if not (start <= i["published"] <= start + WINDOW):
            continue
        text = f"{i['title']} {i['text']}".lower()
        hits = sum(1 for w in words if re.search(rf"(?<!\w){re.escape(w)}", text))
        if hits:
            out.append((hits, i["published"], i))
    out.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [i for _, _, i in out[:MAX_REPORTS]]


def facts(race, rows, extras=()):
    """Everything the code knows for sure about the result, as plain data for Claude and for the checker."""
    win = rows[0]
    podium = [{"position": x["position"], "driver": f"{x['Driver']['givenName']} {x['Driver']['familyName']}", "team": x["Constructor"]["name"],
               "grid": x.get("grid")} for x in rows[:3]]
    fastest = next((x for x in rows if (x.get("FastestLap") or {}).get("rank") == "1"), None)
    out = {"race": race.get("raceName"), "winner": podium[0]["driver"], "podium": podium,
           "did_not_finish": sum(1 for x in rows if x.get("status") not in ("Finished", "Lapped") and not re.match(r"\+\d+ Lap", x.get("status", ""))),
           "laps": win.get("laps")}
    if len(rows) > 1 and rows[1].get("status") == "Finished" and (rows[1].get("Time") or {}).get("time"):
        out["winning_margin_seconds"] = rows[1]["Time"]["time"].lstrip("+")
    if fastest:
        out["fastest_lap"] = {"driver": f"{fastest['Driver']['givenName']} {fastest['Driver']['familyName']}", "time": fastest["FastestLap"]["Time"]["time"]}
    if extras:
        out["notable"] = list(extras)
    return out


def check(blurb, f, reports):
    """Problems with a blurb. The football checker finds numbers and names not in the material, history claims and hype; this adds the
    word limit and copying."""
    material = {"facts": f, "reports": [{"headline": i["title"], "blurb": i["text"]} for i in reports]}
    problems = notes.check_note(blurb, material)
    vocab = notes._vocab(material)
    for sentence in re.split(r"(?<=[.!?])\s+", blurb):  # the football checker lets a lone invented name start a sentence; here it may not
        words = re.findall(r"[\w'’-]+", sentence)
        first = re.sub(r"['’]s$", "", words[0]) if words else ""
        if (first.isalpha() and len(first) > 2 and first.lower() not in vocab and first.lower() not in notes.STARTERS
                and not first.lower().endswith(notes.ORDINARY_ENDINGS) and f"name {first} is not in the facts" not in problems):
            problems.append(f"name {first} is not in the facts")
    for m in CLAIMS.finditer(blurb):
        word = m.group(0).lower()
        if not any(v.startswith(word[:5]) for v in vocab):
            problems.append(f'"{m.group(0)}" is a claim the facts and reports do not make')
    if len(blurb.split()) > MAX_WORDS:
        problems.append(f"{len(blurb.split())} words, over the limit of {MAX_WORDS}")
    if notes.copied_run(blurb, [t for i in reports for t in (i["title"], i["text"])]):
        problems.append("copies a run of six or more words from a report")
    return problems


def write(client, f, reports, model=None):
    """(blurb or None, usage). One retry with the problems named; None when it still fails, or Claude is unreachable."""
    payload = {"facts": f, "reports": [{"source": i["source"], "headline": i["title"], "blurb": i["text"]} for i in reports]}
    total, extra = {"input": 0, "output": 0}, ""
    for _ in (1, 2):
        obj, usage = notes.call_json(client, SYSTEM, SCHEMA, extra + json.dumps(payload, ensure_ascii=False, indent=1), model=model or settings.NEWS_MODEL)
        total = {k: total[k] + usage[k] for k in total}
        blurb = (obj or {}).get("blurb", "").strip() if isinstance(obj, dict) else ""
        if not blurb:
            return None, total
        problems = check(blurb, f, reports)
        if not problems:
            return blurb, total
        extra = "Your earlier story broke these rules, so rewrite it (or write less): " + "; ".join(problems) + "\n"
    return None, total


def story(client, fetch=feeds.fetch_all):
    """A function for f1.run: story(race, rows, start, extras) -> (html, usage). Never raises."""
    def make(race, rows, start, extras=()):
        none = ("", {"input": 0, "output": 0})
        try:
            reports = pick_reports(fetch(FEEDS), race, rows, start)
        except Exception:
            return none
        if not reports:
            return none
        blurb, usage = write(client, facts(race, rows, extras), reports)
        if not blurb:
            return "", usage
        sources = ", ".join(dict.fromkeys(i["source"] for i in reports))
        return f'<p class="f1story">{r.esc(blurb)}</p><p class="muted">From reports by {r.esc(sources)}.</p>', usage
    return make
