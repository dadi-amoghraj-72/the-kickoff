"""Grand Slam tennis from ESPN's unofficial scoreboard (the same family of API as the football data) and its rankings.

For a Slam week the scoreboard returns the whole tournament in one event, both singles draws, every match with its round, set scores and a
"notes" line that carries the seeds ("(1) A. Zverev (GER) bt (8) B. Shelton (USA) 6-3 7-6 (7-2) 5-7 6-2"). That is one call per date.
Undocumented and free: any failure is a SourceError and the caller carries on without tennis."""
import re
from datetime import timedelta

from kickoff import http

BASE = "https://site.api.espn.com/apis/site/v2/sports/tennis/"
SLAMS = ("Australian Open", "Roland Garros", "French Open", "Wimbledon", "US Open")
SINGLES = ("mens-singles", "womens-singles")


def is_slam(event):
    return bool(event.get("major")) and event.get("name") in SLAMS


def is_finals(event):
    """The season-ending tour finals: the ATP Finals (men) and the WTA Finals (women), whatever the sponsor puts in front ('Nitto ATP Finals', 'FAGE WTA Finals Indian Wells')."""
    return bool(re.search(r"\b(ATP|WTA) Finals\b", event.get("name") or ""))


def _merge(events, found):
    """Add Slam events to the dict by id; a later copy of the same event adds any draw the first one lacked."""
    for e in found:
        if not is_slam(e):
            continue
        have = events.setdefault(e["id"], e)
        if have is not e:
            known = {g["grouping"]["slug"] for g in have["groupings"]}
            have["groupings"] += [g for g in e["groupings"] if g["grouping"]["slug"] not in known]


class Source:
    """One object per run; `calls` counts requests. get_json is injectable for tests."""

    def __init__(self, get_json=http.get_json):
        self._get, self.calls = get_json, 0

    def _scoreboard(self, tour, day):
        self.calls += 1
        return self._get(f"{BASE}{tour}/scoreboard?dates={day:%Y%m%d}").get("events", [])

    def slam_events(self, now):
        """Slam events running today or yesterday (UTC), each with both singles draws. Yesterday matters: the morning edition after a
        final comes after the tournament has left today's scoreboard. The men's endpoint carries both draws during a Slam; if a draw
        is missing, the women's endpoint is asked as well."""
        events = {}
        for back in (1, 0):
            day = now - timedelta(days=back)
            _merge(events, self._scoreboard("atp", day))
            if any(not set(SINGLES) <= {g["grouping"]["slug"] for g in e["groupings"]} for e in events.values()):
                _merge(events, self._scoreboard("wta", day))
        return list(events.values())

    def finals_events(self, now):
        """The ATP Finals and WTA Finals events running today or yesterday (UTC), from their own tours' scoreboards: round-robin groups, semi-finals and the final all come in one event
        with the singles draw. {event id: event}."""
        events = {}
        for tour in ("atp", "wta"):
            for back in (1, 0):
                for e in self._scoreboard(tour, now - timedelta(days=back)):
                    if is_finals(e) and any(g["grouping"]["slug"] in SINGLES for g in e.get("groupings", [])):
                        have = events.setdefault(e["id"], e)
                        if have is not e:
                            known = {g["grouping"]["slug"] for g in have["groupings"]}
                            have["groupings"] += [g for g in e["groupings"] if g["grouping"]["slug"] not in known]
        return list(events.values())

    def top10(self, tour):
        """The ten highest-ranked players' names for 'atp' or 'wta'."""
        self.calls += 1
        ranks = self._get(f"{BASE}{tour}/rankings")["rankings"][0]["ranks"]
        return [x["athlete"]["displayName"] for x in ranks[:10]]
