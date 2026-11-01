"""A dummy edition: placeholder content in the real section order, to test the design."""
from kickoff import render as r
from kickoff.order import assemble

LONG = ("This is placeholder text so the page is long enough to scroll and the progress rail has "
        "something to measure. Real editions will have short summaries in our own words, each with "
        "a link to the original story.")

ZONES = [("blue", "Quarter-final places"), ("lilac", "Play-off place"), ("rose", "Relegated")]


def make_dummy(iso_date, lead=None, promoted=("f1",)):
    content = {
        "big-stuff": {"title": "The Big Stuff", "html":
            r.potd("Player One, Home FC", "Placeholder for the one standout performance across all sports. " + LONG)
            + "<h3>Key Overnight Scores</h3><p><strong>Home FC 2–1 Away FC.</strong> A placeholder result. "
            + LONG + "</p><h3>Biggest News</h3><p>Placeholder news item. " + r.link("https://example.com", "Read the original")
            + "</p><h3>Major Injuries</h3><p>Placeholder injury note for a key player. Back in about three weeks.</p>"},
        "on-today": {"title": "On Today", "html":
            r.on_today([("up", "5:30pm", "Placeholder: a Premier League early kick-off."),
                        ("up", "8:00pm", "Placeholder: a Champions League match."),
                        ("overnight", "2:00am", "Placeholder: an NBA game, results in tomorrow's edition.")])
            + "<h3>Games To Watch This Week</h3><p>Mondays carry the week's big games, with every time in Singapore time. "
            + "This is a placeholder for the picks.</p>"},
        "arsenal": {"title": "Arsenal", "html":
            "<p><strong>Placeholder result.</strong> Scorers, injuries, next fixture and news go here. " + LONG + "</p>"
            "<p><strong>Transfer rumour (unconfirmed):</strong> placeholder, clearly labelled as a rumour.</p>"
            "<h3>Arsenal Women</h3><p>A short placeholder block for the women's team.</p>"},
        "football": {"title": "Football", "html":
            "<h3>Premier League</h3><p>A proper note on every game: the big six first, then all the others. "
            "Placeholder. " + LONG + "</p>"
            + r.table("Placeholder league table", [("Team", False), ("P", True), ("GD", True), ("Pts", True)],
                      [["AAA", 10, "+14", 25], ["BBB", 10, "+9", 22], ["CCC", 10, "+7", 20],
                       ["DDD", 10, "+3", 17], ["EEE", 10, "-2", 12], ["FFF", 10, "-8", 6]],
                      zones=["blue", "blue", "lilac", None, None, "rose"], legend=ZONES)
            + "<h3>Other Leagues</h3><p>One line for each of your clubs, plus the table. A derby between two of your "
            "clubs gets a fuller note. Placeholder.</p>"
            "<h3>Sackings And Appointments</h3><p>Manager changes at major clubs go here. Placeholder.</p>"
            "<h3>FPL Corner</h3><p>Team news, deadline reminder and the gameweek's top scorers will go here.</p>"},
        "cricket": {"title": "Cricket", "html":
            "<p>International and franchise cricket, men's and women's. " + LONG + "</p>"
            + "<h3>Standouts</h3>" + r.standouts(["<strong>Player Two</strong>, 112 off 98 balls. Placeholder context.",
                                                  "<strong>Player Three</strong>, 5 for 31. Placeholder context."])},
        "nba": {"title": "NBA", "html":
            "<h3>Tracked Players</h3><p>Stat lines for the tracked stars come first, with a one-line story each. Placeholder.</p>"
            "<h3>Other Games</h3><p>Compact one-line scores for every other game. Placeholder.</p>"},
        "nfl": {"title": "NFL", "html":
            "<p>Mondays carry the early-game scores, grouped by division. " + LONG + "</p>"
            "<h3>Standouts</h3>" + r.standouts(["<strong>Player Six</strong>, 4 touchdown passes. Placeholder context."])
            + "<h3>Sackings And Appointments</h3><p>Head coach and coordinator changes go here. Placeholder.</p>"},
        "baseball": {"title": "Baseball", "html":
            "<p><strong>Dodgers 5–3.</strong> Placeholder for an Ohtani or Yamamoto entry: the score, the stat line "
            "and a one-line story.</p>"},
        "young-guns": {"title": "Young Guns", "html":
            "<p><strong>Player Four</strong> (football, age 19): placeholder note, such as \"his third big game this month.\"</p>"
            "<p><strong>Player Five</strong> (NBA rookie): placeholder note.</p>"},
        "f1": {"title": "F1", "headline": "Placeholder race result and the championship picture.", "html":
            "<p>Race, sprint and qualifying results plus standings go here. " + LONG + "</p>"},
        "tennis": {"title": "Tennis", "headline": "Placeholder Grand Slam quarter-final result.",
                   "html": r.no_data("Tennis")},
        "other-sports": {"title": "Other Sports", "html":
            "<p>Rugby, golf, UFC, badminton, athletics and more appear here only when something major happened. "
            "Placeholder.</p>"},
        "stories": {"title": "Interesting Stories", "html":
            "<p><strong>Placeholder story one.</strong> Two or three sentences in our own words. "
            + r.link("https://example.com", "Original") + "</p>"
            "<p><strong>Placeholder story two.</strong> Another short summary. "
            + r.link("https://example.com", "Original") + "</p>"},
    }
    return {"date": iso_date, "dummy": True,
            "order": {"lead": lead, "promoted": list(promoted)},
            "headlines": ["Dummy headline one: placeholder for the biggest story",
                          "Dummy headline two: placeholder for the second story",
                          "Dummy headline three: placeholder for the third story"],
            "sections": assemble(content, lead=lead, promoted=promoted)}
