"""Settings that are not secret. Keys and tokens live in .env (and GitHub secrets), never here."""
FPL_CLASSIC_TEAM_ID = 1476452
FPL_DRAFT_ENTRY_ID = 186059  # D's Draft team
FPL_DRAFT_LEAGUE_ID = 35975  # the league that team plays in

# Claude: which model writes the notes, and how hard it thinks. Check Anthropic's docs for current names.
CLAUDE_MODEL = "claude-sonnet-5-5"  # match notes. Compared on 12 real notes: Sonnet matched Opus on accuracy and rules.
NEWS_MODEL = "claude-sonnet-5-5"  # classifying and summarising news items; checked by code like everything else.
OVERVIEW_MODEL = "claude-opus-5-5"  # matchday overviews need judgment: Opus found the sharper insight and was more precise.
CLAUDE_EFFORT = "low"  # low | medium | high. Note-writing is rephrasing facts, so low is enough.
# Dollars per million tokens (input, output), for the cost estimate only.
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}
