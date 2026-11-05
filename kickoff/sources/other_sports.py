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
GNEWS = "https://news.google.com/rss/search?q={q}&hl=en-SG&gl=SG&ceid=SG:en"
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
    # Added 2026-11-05 (D asked for livelier sources than Wikipedia): Yahoo Sports, the Indian and Singapore papers' sport pages (the spotlight rule), and Google News searches per sport,
    # which pick up fresh headlines from many outlets within the hour.
    ("Yahoo Sports", "rss", "https://sports.yahoo.com/rss/"), ("Yahoo Sports", "rss", "https://sports.yahoo.com/golf/rss/"),
    ("The Hindu", "rss", "https://www.thehindu.com/sport/feeder/default.rss"), ("The Straits Times", "rss", "https://www.straitstimes.com/news/sport/rss.xml"),
    ("Times of India", "rss", "https://timesofindia.indiatimes.com/rssfeeds/4719148.cms"),
] + [("Google News", "gnews", GNEWS.format(q=q)) for q in (
    "badminton+BWF", "%22field+hockey%22+FIH", "handball+EHF", "PDC+darts", "chess+FIDE", "%22Diamond+League%22+OR+%22World+Athletics%22", "%22Asian+Games%22+OR+%22SEA+Games%22+OR+%22Commonwealth+Games%22",
    "%22Women%27s+Euro%22+OR+%22Women%27s+World+Cup%22+football", "%22Ryder+Cup%22+OR+%22Solheim+Cup%22")]


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

    def ufc_listing(self):
        """The addresses on UFC.com's events list ('ufc-332', 'cryptocom-ufc-331', 'ufc-fight-night-november-07-2026'): used to find a numbered event's address when it has a sponsor in front."""
        self.calls += 1
        import re
        page = http.get_bytes("https://www.ufc.com/events", retries=1, timeout=30).decode("utf-8", "replace")
        return sorted(set(re.findall(r'href="/event/([^"#?]+)"', page)))

    def ufc_rankings_page(self):
        """UFC.com's rankings page as html (updated by UFC every Tuesday)."""
        self.calls += 1
        return http.get_bytes("https://www.ufc.com/rankings", retries=1, timeout=30).decode("utf-8", "replace")

    def ufc_page(self, slug):
        """UFC.com's event page ('ufc-309') as html: the official source of the fights' details (ranks, title bout, method, round, time)."""
        self.calls += 1
        return http.get_bytes(f"https://www.ufc.com/event/{slug}", retries=1, timeout=30).decode("utf-8", "replace")

    def wikitext(self, title):
        """A Wikipedia page's wikitext ('' when missing): the majors of the sports without a feed (kickoff.majors). Two seconds between pages keeps Wikipedia's rate limit happy."""
        if not hasattr(self, "_wiki"):
            from kickoff.sources import wikipedia
            self._wiki = wikipedia.Source(pause=2.0)
        self.calls += 1
        return self._wiki.wikitext(title)

    def top(self):
        """Lichess's broadcast list: the active and the recently finished events with their latest round."""
        return self._json("https://lichess.org/api/broadcast/top")

    def tour(self, tour_id):
        return self._json(f"https://lichess.org/api/broadcast/{tour_id}")

    def round_pgn(self, round_id):
        self.calls += 1
        return http.get_bytes(f"https://lichess.org/api/broadcast/round/{round_id}.pgn").decode("utf-8", "replace")

    def news(self):
        """Every item of every feed that answers, newest first (headline, blurb, link, source, time)."""
        self.calls += len(FEEDS)
        return self._fetch(FEEDS)
