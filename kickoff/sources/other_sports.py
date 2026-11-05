"""Sources for Around The Sporting World (checkpoint 12), all free and all read with The Kickoff's honest identity (see scripts/probe_other_sports.py for what answered on 2026-11-05).

Structured data from ESPN's free JSON (the same family as the other sports): rugby scoreboards by league, the PGA and LPGA Tour scoreboards, the UFC scoreboard and rankings.
Everything else comes from news feeds (BBC Sport, The Guardian, ChessBase, Chess.com): headline and short blurb only, never the full article.
Sports with no usable feed on that day (badminton and field hockey have almost no BBC/Guardian coverage; handball's EHF site has no feed; FIH and PDC pages did not answer) are
covered only when the general BBC and Guardian sport feeds mention them. Any failing page is skipped; one never costs the rest."""
from kickoff import http
from kickoff.sources import feeds

SITE = "https://site.api.espn.com/apis/site/v2/sports/"
RUGBY_LEAGUES = {"268565": "British & Irish Lions Tour", "164205": "Rugby World Cup", "180659": "Six Nations", "244293": "The Rugby Championship", "17567": "Nations Championship",
                 "289234": "International Test Match", "289237": "Women's Rugby World Cup"}
BBC = "https://feeds.bbci.co.uk/sport/{}/rss.xml"
GUARDIAN = "https://www.theguardian.com/{}/rss"
FEEDS = [
    ("BBC Sport", "rss", BBC.format("rugby-union")), ("The Guardian", "rss", GUARDIAN.format("sport/rugby-union")),
    ("BBC Sport", "rss", BBC.format("golf")), ("The Guardian", "rss", GUARDIAN.format("sport/golf")),
    ("BBC Sport", "rss", BBC.format("athletics")), ("The Guardian", "rss", GUARDIAN.format("sport/athletics")),
    ("BBC Sport", "rss", BBC.format("hockey")), ("BBC Sport", "rss", BBC.format("badminton")), ("The Guardian", "rss", GUARDIAN.format("sport/badminton")),
    ("The Guardian", "rss", GUARDIAN.format("sport/chess")), ("ChessBase", "rss", "https://en.chessbase.com/feed"), ("Chess.com", "rss", "https://www.chess.com/rss/news"),
    ("BBC Sport", "rss", BBC.format("darts")), ("The Guardian", "rss", GUARDIAN.format("sport/darts")),
    ("BBC Sport", "rss", BBC.format("olympics")), ("The Guardian", "rss", GUARDIAN.format("sport/olympic-games")), ("BBC Sport", "rss", BBC.format("commonwealth-games")),
    ("BBC Sport", "rss", BBC.format("football/womens")), ("The Guardian", "rss", GUARDIAN.format("football/womensfootball")),
    ("The Guardian", "rss", GUARDIAN.format("sport/ufc")),
    ("BBC Sport", "rss", "https://feeds.bbci.co.uk/sport/rss.xml"), ("The Guardian", "rss", GUARDIAN.format("sport")),
]


class Source:
    """One object per run. get_json and fetch are injectable for tests."""

    def __init__(self, get_json=http.get_json, fetch=feeds.fetch_all):
        self._get, self._fetch, self.calls = get_json, fetch, 0

    def _json(self, url):
        self.calls += 1
        return self._get(url)

    def rugby(self, league):
        """The scoreboard of one ESPN rugby league (the current round or window)."""
        return self._json(SITE + f"rugby/{league}/scoreboard")

    def golf(self, tour):
        """'pga' or 'lpga': the tour's current or latest event."""
        return self._json(SITE + f"golf/{tour}/scoreboard")

    def ufc(self):
        return self._json(SITE + "mma/ufc/scoreboard")

    def ufc_rankings(self):
        return self._json(SITE + "mma/ufc/rankings")

    def news(self):
        """Every item of every feed that answers, newest first (headline, blurb, link, source, time)."""
        self.calls += len(FEEDS)
        return self._fetch(FEEDS)
