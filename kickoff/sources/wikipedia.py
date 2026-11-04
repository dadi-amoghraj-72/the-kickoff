"""Wikipedia's free API, for the few honours ESPN does not carry (the AP All-Pro teams, the Pro Bowl and NBA All-Star selections, the NBA Coach of the Year):
the wikitext of a page. Volunteers edit these pages, so the parsers (kickoff.honours) accept only the layout they were tested on and return nothing otherwise;
a missing honour is better than a wrong one. A short pause and an identifying User-Agent keep it polite, as Wikipedia asks."""
import time
from urllib.parse import quote

from kickoff import http

API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "the-kickoff/1.0 (personal sports digest; https://github.com/dadi-amoghraj-72/the-kickoff)"}


class Source:
    def __init__(self, get_json=http.get_json, pause=0.3):
        self._get, self.pause, self.calls = get_json, pause, 0

    def wikitext(self, page):
        """The page's wikitext, following redirects; '' when the page does not exist."""
        if self.calls:
            time.sleep(self.pause)
        self.calls += 1
        j = self._get(f"{API}?action=parse&format=json&redirects=1&prop=wikitext&page={quote(page)}", headers=HEADERS)
        return (j.get("parse") or {}).get("wikitext", {}).get("*", "")
