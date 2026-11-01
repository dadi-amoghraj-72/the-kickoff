"""The 17 listed clubs, by ESPN team ID (names can change, IDs don't). Codes are our own three letters."""

# id: (name, code, group). "big6" clubs get full Premier League notes; Arsenal also has its own section.
CLUBS = {
    "359": ("Arsenal", "ARS", "big6"), "382": ("Manchester City", "MCI", "big6"),
    "360": ("Manchester United", "MUN", "big6"), "364": ("Liverpool", "LIV", "big6"),
    "363": ("Chelsea", "CHE", "big6"), "367": ("Tottenham", "TOT", "big6"),
    "132": ("Bayern Munich", "BAY", "listed"), "124": ("Borussia Dortmund", "BVB", "listed"),
    "160": ("Paris Saint-Germain", "PSG", "listed"), "111": ("Juventus", "JUV", "listed"),
    "114": ("Napoli", "NAP", "listed"), "110": ("Inter", "INT", "listed"),
    "103": ("AC Milan", "MIL", "listed"), "2572": ("Como", "COM", "listed"),
    "83": ("Barcelona", "BAR", "listed"), "86": ("Real Madrid", "RMA", "listed"),
    "1068": ("Atlético Madrid", "ATM", "listed"),
}
ARSENAL_ID = "359"


def is_listed(team_id):
    return str(team_id) in CLUBS


def is_big6(team_id):
    return CLUBS.get(str(team_id), (None, None, None))[2] == "big6"


def code(team_id, fallback=""):
    """Our three-letter code for a listed club, or ESPN's own code for anyone else."""
    return CLUBS[str(team_id)][1] if str(team_id) in CLUBS else fallback
