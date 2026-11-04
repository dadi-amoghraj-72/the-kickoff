"""The monthly Claude budget guard. The football run records what every Claude call cost in state["costs"][month]; this reads it before the next run.

  under 80% of the budget: normal.   80% and over: "cheaper" (the Opus jobs use the Sonnet model).   100% and over: "plain" (no Claude at all;
  every note and overview is the plain version written by code).

The decision is made once, at the start of a run, from what was spent so far this month, so one run can overshoot a little but the next one stops."""
from contextlib import contextmanager

from kickoff import settings


def status(costs, day, budget=None):
    """{"mode": "normal" | "cheaper" | "plain", "spent", "budget", "pct"} for the month of `day` (a date). costs: the state["costs"] dict."""
    budget = settings.MONTHLY_BUDGET_USD if budget is None else budget
    spent = float(((costs or {}).get(day.strftime("%Y-%m")) or {}).get("spent", 0.0))
    pct = spent / budget if budget > 0 else 1.0
    mode = "plain" if pct >= 1.0 else "cheaper" if pct >= settings.BUDGET_CHEAPER_AT else "normal"
    return {"mode": mode, "spent": round(spent, 4), "budget": budget, "pct": round(pct, 3)}


@contextmanager
def models(mode):
    """Inside the block, 'cheaper' makes the overview model the note model (Sonnet); everything is put back afterwards."""
    old = settings.OVERVIEW_MODEL
    if mode == "cheaper":
        settings.OVERVIEW_MODEL = settings.CLAUDE_MODEL
    try:
        yield
    finally:
        settings.OVERVIEW_MODEL = old
