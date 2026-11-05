"""Which news items are worth a closer look: recent, new to us, about a club we cover, and about a transfer,
a manager change or an injury. This is the cheap code filter that runs before Claude sees anything."""
import re
from datetime import timedelta

from kickoff.clubs import CLUBS

CATEGORIES = {
    "managerial": re.compile(r"\b(sack\w*|dismiss\w*|parts? company|part ways|resign\w*|quit\w*|appoint\w*|"
                             r"(?:new|interim|caretaker) (?:manager|head coach|boss|coach)|takes? charge|steps? down|under pressure)\b", re.I),
    "transfer_done": re.compile(r"\b(signs?|signed|signing|completes?|completed|unveil\w*|officially|"
                                r"(?:new|extends?) contract|contract extension|announces?)\b", re.I),
    "transfer_talk": re.compile(r"\b(bid|offer|target\w*|linked|interest\w*|talks|negotiat\w*|swoop|set to join|close to|"
                                r"agree\w* (?:a )?(?:fee|deal|terms)|medical|loan|free agent|transfer)\b", re.I),
    "injury": re.compile(r"\b(injur\w*|ruled out|out for|doubt\w*|sidelined|fitness|hamstring|knee|ankle|thigh|calf|surgery|"
                         r"setback|return\w* from)\b", re.I),
}
PRIORITY = ["managerial", "transfer_done", "injury", "transfer_talk"]
# Without Claude (D, 2026-11-05: a Kuyt match reaction, a Gyokeres match report and a Football Daily column were shown as manager news): the headline itself must say a manager has been
# sacked, has left or has been appointed, and must not be a reaction, a live blog, a column or a talking-points piece.
MANAGER_CHANGE = re.compile(r"\b(sack(?:ed|s|ing)?|dismiss(?:ed|es|al)?|appoint(?:ed|s|ment)?|named (?:\w+ ){0,3}(?:as )?(?:the )?(?:new )?(?:manager|head coach|boss)|new (?:manager|head coach|boss)|"
                            r"(?:interim|caretaker) (?:manager|head coach|boss)|takes? charge|hired|resign(?:ed|s)?|steps? down|parts? ways?|part company|leaves? (?:his |the )?(?:role|post|club)|replaces?)\b", re.I)
MANAGER_WORD = re.compile(r"\b(manager|head coach|boss|coach)\b", re.I)
NOT_NEWS = re.compile(r"\b(live|hails?|reacts?|reaction|player ratings|talking points|football daily|analysis|opinion|verdict|what we learned|observations)\b|\bv\b", re.I)
RECENT = timedelta(hours=36)


def club_aliases(table_rows_by_league=None):
    """Every name a covered club might appear under, from our list of 17 plus the six leagues' tables."""
    names = {"Gunners", "Spurs", "Man City", "Man Utd", "Man United"}
    names.update(n for n, _, _ in CLUBS.values())
    for rows in (table_rows_by_league or {}).values():
        for r in rows or []:
            names.update({r["team"], r.get("short") or r["team"]})
    return {n for n in names if len(n) >= 4}


def mentioned(item, names):
    """The covered clubs named in an item's headline or blurb."""
    text = f"{item['title']} {item['text']}"
    return sorted(n for n in names if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text))


def category(item):
    """The first matching kind of news, or None. A hint only: Claude makes the real call."""
    text = f"{item['title']} {item['text']}"
    return next((c for c in PRIORITY if CATEGORIES[c].search(text)), None)


def candidates(items, names, now, seen_links=()):
    """Items worth a closer look: published in the last 36 hours, not shown before, naming a covered club, and
    matching a kind of news we report. Each gets a 'hint' and the 'clubs' it names."""
    out = []
    for i in items:
        if now - i["published"] > RECENT or i["published"] > now + timedelta(hours=1) or i["link"] in seen_links:
            continue
        clubs, hint = mentioned(i, names), category(i)
        if clubs and hint:
            out.append({**i, "hint": hint, "clubs": clubs})
    return out


# ---- Claude classifies and summarises ---------------------------------------------------------

import json  # noqa: E402

from kickoff import notes, settings  # noqa: E402

KINDS = ["transfer_confirmed", "transfer_rumour", "manager_sacked", "manager_appointed", "injury", "none"]
SYSTEM = """You sort and summarise football news items for The Kickoff, a personal daily digest. Each item is only a headline and
a short blurb from BBC Sport, The Guardian or ESPN. You see nothing else, so know nothing else.

For every item choose one "kind":
- transfer_confirmed: the text says a signing, loan or contract is DONE (signed, completed, announced, unveiled, new contract).
- transfer_rumour: the text reports talks, interest, a bid, a target or a deal that is close but not done.
- manager_sacked: a manager or head coach has actually been sacked, has resigned or has left.
- manager_appointed: a manager or head coach has actually been appointed, including interim.
- injury: the text states that a named player is injured, ruled out or doubtful.
- none: anything else. Match reports, opinion, a manager "under pressure", a manager who "could be sacked", transfers
  that are only speculation about the future, and anything you are unsure about are all "none". When in doubt, "none".

For every kind except none also give "club" (exactly one of the clubs listed for that item) and a "summary":
ONE sentence of at most 30 words in your own words. Use only the headline and blurb. Add nothing from memory. Never copy
a run of more than five words. No hype, no emojis. Say "reportedly" or "is linked with" for a rumour; never state a rumour as fact.
Return one entry per item, using the item's link as its id."""
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"link": {"type": "string"}, "kind": {"type": "string", "enum": KINDS},
                                     "club": {"type": "string"}, "summary": {"type": "string"}},
    "required": ["link", "kind", "club", "summary"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}


def check_summary(summary, item):
    """Problems with a summary: invented names or numbers, history claims, hype, copying, or too long."""
    facts = {"headline": item["title"], "blurb": item["text"], "clubs": item["clubs"], "source": item["source"],
             "length": notes.TIERS["news"][0]}
    problems = notes.check_note(summary, facts)
    if notes.copied_run(summary, [item["title"], item["text"]]):
        problems.append("copies a run of six or more words from the source")
    return problems


def classify(client, cands):
    """{link: {"kind", "club", "summary", "problems"}} for the candidates Claude kept, plus usage. A summary that fails
    its checks after one retry is replaced by None (the page then shows the source and headline as a link)."""
    if not cands:
        return {}, {"input": 0, "output": 0}
    by_link = {c["link"]: c for c in cands}
    payload = [{"link": c["link"], "source": c["source"], "headline": c["title"], "blurb": c["text"], "clubs": c["clubs"]} for c in cands]
    out, total, pending = {}, {"input": 0, "output": 0}, payload
    for attempt in (1, 2):
        extra = "" if attempt == 1 else ("Your earlier summaries for these items broke a rule (see problems). Rewrite them, or "
                                         "choose kind none if the text cannot support them.\n")
        obj, usage = notes.call_json(client, SYSTEM, SCHEMA, extra + "Items:\n" + json.dumps(pending, ensure_ascii=False, indent=1),
                                     model=settings.NEWS_MODEL)
        total = {k: total[k] + usage[k] for k in total}
        redo = []
        for r in (obj or {}).get("items", []) if isinstance(obj, dict) else []:
            item = by_link.get(r.get("link"))
            if not item or r.get("kind") not in KINDS or r["kind"] == "none":
                if item:
                    out[item["link"]] = {"kind": "none", "club": "", "summary": None, "problems": []}
                continue
            problems = check_summary(r.get("summary", ""), item)
            if r.get("club") not in item["clubs"]:
                problems.append("club is not one of the item's clubs")
            if problems:
                out[item["link"]] = {"kind": r["kind"], "club": r.get("club", ""), "summary": None, "problems": problems}
                redo.append({**next(p for p in payload if p["link"] == item["link"]), "problems": problems})
            else:
                out[item["link"]] = {"kind": r["kind"], "club": r["club"], "summary": r["summary"].strip(), "problems": []}
        pending = redo
        if not pending:
            break
    return out, total


# ---- The rules, applied by code -------------------------------------------------------------

NON_PL_LISTED = {n for n, c, g in CLUBS.values() if n not in {"Arsenal", "Manchester City", "Manchester United", "Liverpool", "Chelsea", "Tottenham"}}


def apply_rules(cands, results):
    """Keep only what D's rules allow. Returns a list of items ready to show, each with a 'section'.
    - Arsenal: confirmed transfers, rumours (labelled), managers, injuries.
    - Other listed clubs: confirmed transfers only; managers; injuries only for clubs outside the Premier League
      (the Premier League's injuries come from the official FPL status instead).
    - Managers: any covered club. A rumour about any other club is dropped."""
    shown = []
    for c in cands:
        r = results.get(c["link"])
        if not r or r["kind"] == "none":
            continue
        kind, club = r["kind"], r["club"]
        listed = club in {n for n, _, _ in CLUBS.values()}
        keep = (
            (club == "Arsenal" and kind in ("transfer_confirmed", "transfer_rumour", "manager_sacked", "manager_appointed", "injury"))
            or (listed and club != "Arsenal" and kind == "transfer_confirmed")
            or (kind in ("manager_sacked", "manager_appointed"))
            or (kind == "injury" and club in NON_PL_LISTED)
        )
        if keep:
            shown.append({"kind": kind, "club": club, "summary": r["summary"], "headline": c["title"], "source": c["source"],
                          "link": c["link"], "listed": listed, "published": c["published"],
                          "section": "arsenal" if club == "Arsenal" else "football"})
    return shown


TAG = {"transfer_confirmed": "Transfer", "transfer_rumour": "Rumour", "manager_sacked": "Sacked", "manager_appointed": "Appointed",
       "injury": "Injury", "manager_news": "Manager"}


def plain_managerial(cands, limit=4):
    """Without Claude (D, 2026-11-04: Scott Parker's appointment at West Ham was missing from a run made with Claude off): the manager stories among the candidates, shown as
    the source's own headline under a neutral 'Manager' tag (no summary: code cannot tell a sacking from an appointment, so it does not say which). One story per club, the newest;
    at most `limit`. Same item shape as apply_rules gives."""
    best = {}
    for c in cands:
        if c.get("hint") != "managerial" or not c.get("clubs"):
            continue
        # the headline must name the manager's job and, with the blurb, say he was sacked, left or appointed; and must not be a reaction, a live blog or a column
        if NOT_NEWS.search(c["title"]) or not MANAGER_WORD.search(c["title"]) or not MANAGER_CHANGE.search(f"{c['title']} {c['text']}"):
            continue
        club = c["clubs"][0]
        if club not in best or c["published"] > best[club]["published"]:
            best[club] = c
    out = [{"kind": "manager_news", "club": club, "summary": None, "headline": c["title"], "source": c["source"], "link": c["link"],
            "listed": club in {n for n, _, _ in CLUBS.values()}, "published": c["published"], "section": "arsenal" if club == "Arsenal" else "football"}
           for club, c in best.items()]
    return sorted(out, key=lambda i: i["published"], reverse=True)[:limit]


def item_html(i):
    from kickoff import render as r
    text = r.esc(i["summary"]) if i["summary"] else r.esc(i["headline"])
    return (f'<li><span class="tag">{TAG[i["kind"]]}</span> {text} '
            f'<a href="{r.esc(i["link"])}" rel="noopener">{r.esc(i["source"])}</a></li>')


def html(items, section, heading):
    mine = sorted((i for i in items if i["section"] == section), key=lambda i: i["published"], reverse=True)
    if not mine:
        return ""
    return f'<h3>{heading}</h3><ul class="news">' + "".join(item_html(i) for i in mine) + "</ul>"
