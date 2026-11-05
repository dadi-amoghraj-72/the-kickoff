"""How much a result matters, in one table. Plain numbers, no AI. D (2026-11-05): "the most subjective part of the whole thing", to be tested for a month,
so every knob is here and nowhere else: change a number, not the code.

A story's score = what kind of match it is (STAGE) + D's own team or player (MINE) + a little for a listed club (LISTED) + drama (margin, overtime, comeback),
then multiplied down for an ordinary regular-season game of a sport that D reads less closely on a heavy morning (DOWNSHIFT), unless it was crazy (WOW)."""

STAGE = {"final": 10, "knockout": 7, "playoff": 7, "top": 5, "regular": 2}   # playoffs and knockouts: every game counts (D), not only D's teams
MINE = 6               # one of D's teams or players played (Arsenal and Arsenal Women, Sunrisers, Royal Challengers Bengaluru, India men, tracked NBA stars, Jaguars, Steelers, Dodgers in the postseason)
KOHLI = 8              # Virat Kohli batted: on top of MINE, because he is D's favourite player in all of sport
LISTED = 2             # one of the 17 listed football clubs
WOW = 5                # something crazy happened (a huge margin, two overtimes, a comeback from far behind)
SPORT_BASE = {"football": 0, "cricket": 0, "nfl": 1, "nba": 0, "mlb": 0, "f1": 8, "tennis": 0, "golf": 0}   # a little extra for sports that are always big news on the morning

# Sports that take a back seat on a heavy morning when the game is a plain regular-season one and not D's (D: "a regular season basketball or a baseball or a cricket
# game, unless it's an India cricket game, could take a backseat"; on Sunday and Monday mornings 90% of the news is football, NFL and F1).
DOWNSHIFT_SPORTS = {"nba", "mlb", "cricket"}
HEAVY_DAYS = (6, 0)    # weekday() of the edition: Sunday and Monday (Tuesday is heavy too, but lighter; see CAP)
DOWNSHIFT = 0.4        # the multiplier on a heavy morning
DOWNSHIFT_LIGHT = 0.7  # and on every other morning (basketball and baseball still rank below football and the NFL)

# How many lines The Big Stuff carries by weekday of the edition (0 Monday ... 6 Sunday). Weekends have football, NFL, F1 and more all at once (D).
CAP = {0: 8, 1: 6, 2: 5, 3: 5, 4: 5, 5: 6, 6: 8}
PER_SPORT = 4          # at most this many lines of one sport, unless they are D's teams' or a final (those are never squeezed out)
MIN_SCORE = 4          # a story below this is not worth a line (a quiet morning shows fewer)

PERFORMANCE_MIN = 50   # a Performance of the Day needs at least this on the common 0-100 scale; below it there is none that day


def heavy(weekday):
    return weekday in HEAVY_DAYS


def story_score(sport, stage="regular", mine=False, listed=False, kohli=False, margin_bonus=0.0, wow=False, weekday=1):
    """The score of one finished game. weekday: of the edition's date (Monday 0)."""
    s = STAGE.get(stage, STAGE["regular"]) + SPORT_BASE.get(sport, 0) + margin_bonus
    s += MINE if mine else 0
    s += KOHLI if kohli else 0
    s += LISTED if listed else 0
    if sport in DOWNSHIFT_SPORTS and stage == "regular":
        if not mine:
            s *= DOWNSHIFT if heavy(weekday) else DOWNSHIFT_LIGHT
        elif sport == "nba" and heavy(weekday):          # D's own NBA teams too: a plain regular-season game is not a Monday-morning story (India, Sunrisers and Royal Challengers are exempt)
            s *= DOWNSHIFT_LIGHT
    if wow:
        s += WOW
    return round(s, 2)
