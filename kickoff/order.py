"""Decides which sections an edition has and in what order. Plain rules, no AI.

Order: The Big Stuff, On Today, then the lead sport group, then any promoted major event
(F1 race, Grand Slam quarter-final or later), then the other sport groups, Young Guns,
Around The Sporting World and Interesting Stories. A section with nothing in it is left out.
"""

TOP = ["big-stuff", "on-today"]
# Sport groups in their normal order. Arsenal and Football always travel together.
GROUPS = [["arsenal", "football"], ["cricket"], ["nba"], ["nfl"], ["baseball"]]
PROMOTABLE = ["f1", "tennis"]
AROUND_PARTS = ["f1", "tennis", "other-sports"]  # F1 and tennis first, then the rest


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

    # Around The Sporting World: F1 and tennis first (unless promoted), then the others
    parts = [p for p in AROUND_PARTS if p in content and p not in promoted]
    if parts:
        html = "".join(f"<h3>{content[p]['title']}</h3>{content[p]['html']}" for p in parts)
        sections.append({"id": "around", "title": "Around The Sporting World", "html": html})
    if "stories" in content:
        sections.append({"id": "stories", "title": content["stories"]["title"], "html": content["stories"]["html"]})
    return sections
