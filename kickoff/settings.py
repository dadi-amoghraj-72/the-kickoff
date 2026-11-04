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

# Claude spending guard. The Anthropic workspace's own spend limit is the hard stop; this is the softer one the run checks first: at 80% of the month's
# budget the Opus jobs switch to Sonnet, at 100% Claude is skipped and the plain, code-written versions are used. D confirmed $10 a month as the project maximum on 2026-11-04 (aiming to spend less; his Anthropic account has auto-reload on).
MONTHLY_BUDGET_USD = 10.00
BUDGET_CHEAPER_AT = 0.80

# A second source for the IPL's end-of-season awards: Yahoo Sports carries Cricket News' 'IPL <year> awards list'. The article's address cannot be guessed from the year, so each
# season's link is added here once it is published (the Wikipedia page is the automatic source and does not need it).
IPL_AWARDS_URLS = {2026: "https://sports.yahoo.com/articles/ipl-2026-awards-list-full-184814541.html"}
