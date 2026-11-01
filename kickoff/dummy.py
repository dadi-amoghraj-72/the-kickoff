"""A dummy edition: placeholder content in the real section order, to test the design."""
from kickoff import render as r

LONG = ("This is placeholder text so the page is long enough to scroll and the progress rail has "
        "something to measure. Real editions will have short summaries in our own words, each with "
        "a link to the original story.")

ZONES = [("blue", "Quarter-final places"), ("lilac", "Play-off place"), ("rose", "Relegated")]


def make_dummy(iso_date):
    sections = [
        {"id": "big-stuff", "title": "The Big Stuff", "html":
            r.potd("Player One, Home FC", "Placeholder for the one standout performance across all sports. " + LONG)
            + "<h3>Key Overnight Scores</h3><p><strong>Home FC 2–1 Away FC.</strong> A placeholder result. "
            + LONG + "</p><h3>Biggest News</h3><p>Placeholder news item. " + r.link("https://example.com", "Read the original")
            + "</p><h3>Major Injuries</h3><p>Placeholder injury note for a key player. Back in about three weeks.</p>"},
        {"id": "on-today", "title": "On Today", "html":
            r.on_today([("up", "5:30pm", "Placeholder: a Premier League early kick-off."),
                        ("up", "8:00pm", "Placeholder: a Champions League match."),
                        ("overnight", "2:00am", "Placeholder: an NBA game, results in tomorrow's edition.")])
            + "<h3>Games To Watch This Week</h3><p>Mondays carry the week's big games, with every time in Singapore time. "
            + "This is a placeholder for the picks.</p>"},
        {"id": "arsenal", "title": "Arsenal", "html":
            "<p><strong>Placeholder result.</strong> Scorers, injuries, next fixture and news go here. " + LONG + "</p>"
            "<p><strong>Transfer rumour (unconfirmed):</strong> placeholder, clearly labelled as a rumour.</p>"
            "<h3>Arsenal Women</h3><p>A short placeholder block for the women's team.</p>"},
        {"id": "football", "title": "Football", "html":
            "<h3>Results</h3><p>League results and club one-liners go here. " + LONG + "</p>"
            + r.table("Placeholder league table", [("Team", False), ("P", True), ("GD", True), ("Pts", True)],
                      [["AAA", 10, "+14", 25], ["BBB", 10, "+9", 22], ["CCC", 10, "+7", 20],
                       ["DDD", 10, "+3", 17], ["EEE", 10, "-2", 12], ["FFF", 10, "-8", 6]],
                      zones=["blue", "blue", "lilac", None, None, "rose"], legend=ZONES)
            + "<h3>FPL Corner</h3><p>Team news, deadline reminder and the gameweek's top scorers will go here.</p>"},
        {"id": "other-sports", "title": "Cricket, F1, Tennis, NFL And NBA", "html":
            "<h3>Cricket</h3>" + r.standouts(["<strong>Player Two</strong>, 112 off 98 balls. Placeholder context.",
                                              "<strong>Player Three</strong>, 5 for 31. Placeholder context."])
            + "<h3>F1</h3><p>Race, sprint and qualifying results plus standings go here. " + LONG + "</p>"
            + "<h3>Tennis</h3>" + r.no_data("Tennis")
            + "<h3>NFL</h3><p>Mondays carry the early-game scores. " + LONG + "</p>"
            + "<h3>NBA</h3><p>Tracked players first, then the compact scores. Placeholder.</p>"},
        {"id": "young-guns", "title": "Young Guns", "html":
            "<p><strong>Player Four</strong> (football, age 19): placeholder note, such as \"his third big game this month.\"</p>"
            "<p><strong>Player Five</strong> (NBA rookie): placeholder note.</p>"},
        {"id": "around", "title": "Around The Sporting World", "html":
            "<p>Rugby, golf, UFC, badminton, athletics and more appear here only when something major happened. "
            "Placeholder.</p><p>" + LONG + "</p>"},
        {"id": "stories", "title": "Interesting Stories", "html":
            "<p><strong>Placeholder story one.</strong> Two or three sentences in our own words. "
            + r.link("https://example.com", "Original") + "</p>"
            "<p><strong>Placeholder story two.</strong> Another short summary. "
            + r.link("https://example.com", "Original") + "</p>"},
    ]
    return {"date": iso_date, "dummy": True,
            "headlines": ["Dummy headline one: placeholder for the biggest story",
                          "Dummy headline two: placeholder for the second story",
                          "Dummy headline three: placeholder for the third story"],
            "sections": sections}
