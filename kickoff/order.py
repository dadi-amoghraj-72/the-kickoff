"""Decides which sections an edition has and in what order. Plain rules, no AI.

Order: The Big Stuff, On Today, then the lead sport group, then any promoted major event
(F1 race, Grand Slam quarter-final or later), then the other sport groups, Young Guns,
F1 and tennis (their own sections even without a major moment), Around The Sporting World and Interesting Stories. A section with nothing in it is left out.
"""

TOP = ["big-stuff", "on-today"]
# Sport groups in their normal order. Arsenal and Football always travel together.
GROUPS = [["arsenal", "football"], ["cricket"], ["nba"], ["nfl"], ["mlb"]]
PROMOTABLE = ["f1", "tennis"]
AROUND_PARTS = ["other-sports"]  # since 8 Nov 2026 F1 and tennis are always their own sections


def assemble(content, lead=None, promoted=()):
    """content: {id: {"title", "html", optional "headline"}}. A missing id means nothing to show.
    lead: id of the sport that leads (for example "cricket" or "arsenal"), or None.
    promoted: which of "f1" / "tennis" had a major moment (an F1 race, a Slam quarter-final or later).
    Returns the list of sections: [{"id", "title", "html"}]."""
    promoted = [p for p in PROMOTABLE if p in promoted and p in content]
    content = {k: dict(v) for k, v in content.items()}

    # Promoted events always get a headline in The Big Stuff
    if promoted:
        lines = "".join(f"<p><strong>{content[p]['title']}:</strong> {content[p].get('headline', '')}</p>"
                        for p in promoted)
        big = content.setdefault("big-stuff", {"title": "The Big Stuff", "html": ""})
        big["html"] = "<h3>Major Events</h3>" + lines + big["html"]

    groups = sorted(GROUPS, key=lambda g: lead not in g)  # stable: the lead's group first
    order = list(TOP)
    order += groups[0]
    order += promoted
    for g in groups[1:]:
        order += g
    order.append("young-guns")

    sections = [{"id": i, "title": content[i]["title"], "html": content[i]["html"]}
                for i in order if i in content]

    # F1 and tennis without a major moment: still their own sections (D, 2026-11-08: folded into Around The Sporting World, a qualifying-only F1 weekend had no
    # helmet on the rail, only the default), in Around's place, before the other sports
    for p in PROMOTABLE:
        if p in content and p not in promoted:
            sections.append({"id": p, "title": content[p]["title"], "html": content[p]["html"]})
    if "other-sports" in content:
        sections.append({"id": "around", "title": "Around The Sporting World", "html": f"<h3>{content['other-sports']['title']}</h3>{content['other-sports']['html']}"})
    if "stories" in content:
        sections.append({"id": "stories", "title": content["stories"]["title"], "html": content["stories"]["html"]})
    return sections
