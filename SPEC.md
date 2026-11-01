# The Kickoff: build spec

Nov 1, 2026 · @D

## Overview

The Kickoff is D's personal daily sports digest: one web page every morning at 8:00am Singapore time, linked from a Telegram ping. It covers the sports, clubs and players D follows, with summaries, tables, standouts and what's on today.

- **Reader:** one person in Singapore (SGT, UTC+8), reading mostly on an iPhone in dark mode. A long read is welcome.
- **Owner:** a beginner coder building with Claude Code on a Mac Mini. Every setup step must spell out each click, such as where to find Terminal.
- **Build approach:** one complete build, wired and tested one sport at a time. The daily schedule is switched on only after full test runs pass.
- **Voice:** plain, warm and specific. Summaries are written in our own words, short, with a link to the original. No copied article text.
- **Images:** no club crests or logos. Use team names or three-letter codes.

## Architecture and hosting

The Kickoff runs entirely on GitHub: a scheduled job builds the page, publishes it and pings Telegram, with no computer needing to be switched on.

&#91;embedded content: daily run · 5 steps, secrets and state\]

Every step reads its keys from the secrets vault, and the build reads and updates the state files so it knows what changed since yesterday.

- **Repo:** a public GitHub repo holding the code, the page template and the state files. Keys never go in the code.
- **Secrets:** ANTHROPIC\_API\_KEY, TELEGRAM\_BOT\_TOKEN, TELEGRAM\_CHAT\_ID and the data-source keys live in GitHub's encrypted secrets. For testing on the Mac Mini, a local .env file that git ignores.
- **Pages:** each edition at its own dated address, plus an archive page. A noindex tag and robots.txt keep it out of search engines.
- **State files:** small JSON files for the last published tables, the Young Guns watchlist, the key-player list, the FIFA top-30 list and stories featured in the last week.
- **Fallbacks:** if a source fails, its section shows a short "No data this morning" line. If the whole run fails, the bot sends D an alert instead of the edition.
- **Cost control (built before the schedule goes live):** every Claude call logs its model, tokens and cost to a state file, by section and by day, and the run's total is shown in its log so D can see what each section really costs. A monthly budget setting guards spending: at 80% of the budget the Opus jobs switch to Sonnet, and at 100% Claude is skipped and the plain code-built fallbacks are used. The Anthropic workspace's own spend limit stays as the hard stop. D has agreed to a one-month trial of the current model choices (Opus for overviews, Sonnet for notes) to learn real costs and quality. After the month the per-section cost log and every rejected-note record are reviewed, and the choices are changed from real data. A cheap verification pass (Haiku checking Sonnet's writing against the facts) is the planned experiment for cutting the cost of overviews.
- **Claude:** writes the summaries, standout lines, what's-at-stake lines and Young Guns notes, and picks the stories. Use a current Claude model; check its exact name in Anthropic's docs during the build. The model is a setting per task. The optional written storyline (off by default; see Round-up box) would use Claude Opus 5.5 (`claude-opus-5-5`): on a real matchday it found the sharper insight and was more precise than Sonnet, at about twice the cost, so it is the model to use if the storyline is switched on. Match notes use Claude Sonnet 5.5 (`claude-sonnet-5-5`): on 12 real notes it matched Claude Opus 5.5 on accuracy and rule-following at about half the cost, while Claude Haiku 5.5 broke the length rule. Judgment-heavy tasks, such as picking stories and the what's-at-stake lines, may use Opus 5.5 and will be compared the same way. Claude only ever sees a facts sheet and is told to use nothing else. Code then checks every note: any number or name that isn't in the facts, a table-move claim ("climbed", "stay", "now") without a previous position, hype words, raw minute symbols and any note over its word limit are rejected, retried once, and then replaced by a plain scoreline written by code.

## Schedule and delivery

The edition lands at 8:00am SGT every day, seven days a week. The job starts around 7:15am SGT (23:15 UTC the previous day), because GitHub's scheduled runs can start late when GitHub is busy.

- **Telegram ping:** a plain message from a dedicated The Kickoff bot, separate from D's other bots. It holds the date, the top three headlines and the link to that day's page.
- **Page:** each edition gets its own address by date, plus an archive page listing past editions.
- **What makes it in time:** European football, the Champions League, F1 races in the Americas and West Indies Test days all finish before 8am SGT.
- **What lands a day later:** NFL late-afternoon games, Sunday Night Football and Monday Night Football finish later in the Singapore morning. Most NBA games do too, so their results appear in the next day's edition.

## Edition structure and weekly rhythm

Every edition follows the same order, and a section appears only when it has something in it. Sunday, Monday and Tuesday are the heavy editions; a quiet midweek day may be half the length.

1. **The big stuff:** key overnight scores, the biggest news, major injuries and one Performance of the Day across all sports.
2. **On today:** today's events in Singapore time, each tagged "While you're up" (sun icon) or "Overnight" (moon icon). Mondays add Games to Watch for the week.
3. **Arsenal:** the men's team in full, plus Arsenal Women.
4. **Football:** Premier League notes, other-league one-liners, sackings, Champions League, international football during breaks, tables and the FPL corner.
5. **Cricket, NBA, NFL and baseball:** each its own section with its own standouts, shown only when there is play.
6. **Young Guns:** rookie and young star watch across all sports.
7. **Around the sporting world:** the general section. F1 and Grand Slam tennis come first, then the other sports.
8. **Interesting stories:** three to five picks from across everything covered.

| Day | What's extra |
| --- | --- |
| Every day | Tables appear only when changed: top 6 plus D's clubs outside it, or "No change since Tuesday" |
| Monday | Weekend wrap, Games to Watch for the week, NFL early-game scores |
| Tuesday | Table day: full tables for the six leagues and the WSL, NBA conference standings, NFL late-game and Sunday Night Football scores |
| Wednesday | NFL wrap: every game by division, standouts, Player of the Week, division tables |
| Saturday | Thursday Night Football score |

**Standouts rule (all sports):** picked by clear stat thresholds, not just each game's leader. Show three to five per sport per edition, ranked, one line each with context. Defensive performances count too: goalkeepers, defenders, bowlers, NFL defence, and NBA blocks and steals.

**Games to Watch picks:** D's clubs' big games, top-of-the-table clashes and derbies, deciding Tests in a series, title-deciding races, and tracked NBA stars facing each other. All times in SGT.

**Lead sport (which full sport section comes first):** The Big Stuff and On Today always stay on top. Below them, the sport sections keep the order above, except that one lead sport moves to the front. Plain rules in code decide it, not Claude, so the order is predictable.

1. **Your teams first.** If one of D's teams or players had a match or notable performance since the last edition, their sport leads: Arsenal (men and women), Sunrisers Hyderabad, the India men's cricket team, the tracked NBA stars, the Jaguars (Trevor Lawrence), the Steelers (Aaron Rodgers), and the Dodgers only when an Ohtani or Yamamoto trigger from the Baseball section happens.
2. **If several of those happened, the most important match leads.** Importance scale, highest first: finals and title deciders, knockouts, derbies and clashes at the top of a table, then ordinary league or group games. Exact scoring to be tuned during the build.
3. **If none did, a big competition moment leads:** a Champions League matchday, the NBA playoffs or the IPL.
4. **Otherwise** the normal order stays.

**Major events (F1 and Grand Slam tennis), built from the start:** when an actual F1 race has happened, or a Grand Slam has reached the quarter-finals or later, two things always happen. (1) It gets a headline line under "Major Events" in The Big Stuff. (2) Its block leaves Around the Sporting World and becomes its own section, placed right after the lead sport group (Arsenal and Football together, unless another sport leads), with F1 before Tennis. On other days F1 and Tennis stay at the top of Around the Sporting World, ahead of the other sports. The ordering rules live in `kickoff/order.py` and are tested by `scripts/test_order.py`.

## Football

Football is the core of every edition: six leagues and 17 "listed clubs": Arsenal in full, the other five big-six clubs with full Premier League notes, and 11 clubs in other leagues with one-liners.

- **Leagues:** Premier League, La Liga, Ligue 1, Serie A, Bundesliga and Turkish Süper Lig. The Women's Super League has its own block at the bottom of the leagues, built like the men's leagues.
- **Every league block has the same shape, in this order:** (1) the round-up box; (2) the scoreboard: every game played since the last edition, one aligned line each (home team, gold score, away team) with its scorers underneath, each under their own team, a repeat scorer listed once with all minutes, penalties tagged (pen) and own goals (OG), and the names of D's listed clubs in bold; (3) Claude's notes, which appear only when Claude wrote them and they passed the checks (all Premier League games except Arsenal's, the listed clubs' games in the other leagues, and a derby between two listed clubs in fuller form), never a plain repeat of the scoreboard; (4) the table with the leaders lines. The Champions League follows the same pattern, and the Women's Super League block (box, scoreboard, table) sits after the six men's leagues. The WSL table follows the same full, changed or unchanged rules as the others.
- **Arsenal, in full:** result, scorers, next fixture, and form. Injuries, news and transfer rumours are not daily items: each appears only when something credible has actually been reported by ESPN, the Premier League's official site, Arsenal's official site, the BBC or The Guardian, and is left out on quiet days rather than padded. A rumour is clearly labelled as a rumour, and only when a reliable source reports it. Arsenal Women get their own short block. How it is built: code collects the result in every competition (Premier League, Champions League, cups; friendlies excluded from form), scorers with assists, red cards, table position, the last five results and the current unbeaten run. Claude writes only the result note (four to six sentences for Arsenal, two for the Women), checked like every other note. Code writes the "Next up" line with the next two fixtures, with kick-off times converted to Singapore time, so a time is never left to a model. ESPN carries no injury data for Arsenal, so injuries and news come from API-Football and the news feeds in later steps.
- **Premier League, full coverage:** the round-up box on top (see Round-up box), then a proper note on every game played, starting with the big six (Arsenal in its own section, then Manchester City, Manchester United, Liverpool, Chelsea and Tottenham), then all the other games, then the table.
- **Other leagues, listed clubs only:** a one-line note for each of Bayern Munich, Borussia Dortmund, PSG, Juventus, Napoli, Inter, AC Milan, Como, Barcelona, Real Madrid and Atlético Madrid when they played, plus the table. No notes on other clubs' games. **Exception:** a match between two of these clubs, which is usually a derby, gets a fuller note. The Süper Lig has no listed club, so it gets the table only.
- **Cups and Europe:** the big six and the listed clubs get a line in every competition, including the Europa League, Conference League and domestic cups. Transfers: confirmed deals only.
- **Sackings and appointments:** manager changes at clubs in the six leagues, head coach and coordinator changes in the NFL, and head coach changes in the NBA are reported in that sport's own section under "Sackings and Appointments". If it involves the big six, a listed club or an NFL head coach, it also gets a line in The Big Stuff.
- **News (transfers, sackings, rumours, injuries outside the Premier League):** only from BBC Sport, The Guardian and ESPN (the Premier League's and Arsenal's own sites have no feed, so they are not scraped), and only the headline and short blurb, never full articles. Code first narrows roughly 180 items to a handful: published in the last 36 hours, not shown before, naming a covered club, and matching transfer, sacking or injury language. Claude then classifies each (confirmed transfer, rumour, sacked, appointed, injury, or none, with doubt meaning none, so a manager "under pressure" is never a sacking) and writes one sentence of at most 30 words in its own words; each summary is checked like every other note, including the ban on copying six or more words of the source. A summary that fails twice is replaced by the source and headline as a link, and if Claude is unavailable nothing is shown. Code then applies the rules: Arsenal gets confirmed transfers, labelled rumours, managerial news and injuries; the other listed clubs get confirmed transfers only; a sacking or appointment at any covered club is kept; injuries are kept only for listed clubs outside the Premier League (FPL covers the Premier League); a rumour about any other club is dropped. Every item carries its source as a link. On a quiet day nothing is shown.
- **Tables:** full tables every Tuesday. Other days, only when a table has changed: top 6, plus one line showing where D's clubs outside the top 6 sit. If unchanged: "No change since Tuesday." Change is detected by comparing against the last published table, saved in the state files. League tables have coloured zone bars and no legend.
- **Under each league table (six leagues, not the WSL):** three lines, shown whenever the table is shown: Top Scorer, Top Assists and Top CS (clean sheets). Each reads label, then the number in gold (always two digits, such as 09, so the columns line up), then the names, in three fixed columns. One leader: full name and club code, for example "09 Erling Haaland (MCI)". A tie: every tied player as surname and club code, for example "04 Gross (BHA), Evanilson (BOU), Rice (ARS)". Clubs always show as codes, so each row stays on one line where possible. Scorers and assists come from ESPN's season leaders (official counts). Clean sheets are counted by us: each shutout goes to the team's starting goalkeeper, built from a season scan and topped up each run, and checked against FPL's public data for the Premier League.
- **Champions League:** results after each matchday, then the full league-phase table. Built as: the round-up box first (see Round-up box); then every match as one aligned scoreline (home team, gold score, away team) with its scorers underneath, each under their own team, a repeat scorer listed once with all minutes, penalties tagged (pen) and own goals (OG), Arsenal's name in bold; then the whole 36-team table: blue bars for 1st to 8th (round of 16), lilac for 9th to 24th (play-off), rose for 25th to 36th, a heavier line after 8th and after 24th, and the listed clubs' names in bold. No legend. The table appears only on league-phase matchdays and its caption carries the matchday number. There are no per-match notes in this section: the scoreboard carries the facts and the overview carries the insight, and Arsenal's full note stays in the Arsenal section.
- **Injuries:** Premier League only, from the league's official FPL player status (injured, doubtful, suspended, with a news note and any return date). A key player averages 70+ minutes per team game, or has started at least three quarters of his team's games (so a regular who missed time still counts), and plays for a top-6 side or a big-six club. Shown: an injury with no return date or 14+ days out, a suspension, a doubt at 50% or less, and a key player returning after being reported. Each news item is shown once, when it is new, and tracked in a state file, so nothing repeats daily; on the very first run only news from the last week is shown. Arsenal's items go in the Arsenal section, the rest under "Injuries And Returns" in Football, with the source named. Games played come from FPL's finished fixtures because its team 'played' field is always 0. Other leagues have no official free injury feed: their injuries come only from credible news reports in the news step. API-Football's free plan was tested and cannot see the current season (it allows 2022 to 2024), so it is not used.
- **Standouts:** hat-tricks, three or more goal contributions in one game, standout goalkeeping such as penalty saves, and milestones or records.
- **FPL corner:** built entirely by code from FPL's public data, with no Claude and no cost. D's classic team (1476452, "merino parade fc"), Draft team (186059, "Gabi III") and Draft league (35975, "Hong Hu Express SuperLiga", total-points scoring). Pieces, each shown only when it has something to say: (1) a deadline reminder within 72 hours of the deadline, in Singapore time; (2) one line for the classic team every day: gameweek points against the average ("so far" while the gameweek runs), overall rank and its move since last gameweek, captain's points with the captain multiplier, bench points, any transfer cost or chip; (3) squad alerts: D's own players who are injured, doubtful, suspended or have left, shown near the deadline and otherwise only when the news is under 36 hours old; (4) the Draft league table with D's team in bold and a movement column (up, down or level against last gameweek's rank), only when the standings changed, showing team names only and never the other managers' names because the site is public; (5) the gameweek's top five scorers, once, when the gameweek finishes; (6) FPL Watch: injury or suspension news on players owned by 15% or more of managers, once per item; (7) transfer hints, shown only within 72 hours of the deadline and at most three, from the last three finished gameweeks, as a nudge and never advice: a starter who scored under 2 points in each of the three (in practice, not playing), or who played at least twice and averaged 2 points an appearance or less ("Move out?"), and a bench outfield player who beat the worst starter in his position by 4 or more points. Players already flagged injured, suspended or unavailable are left to the squad alerts. FPL's timestamps carry fractions of a second, and its teams list has a 'played' field that is always 0.

## Round-up box

Above the table in every league block and the Champions League block there is the same four-line box, built entirely by code from the results and pre-match odds. It is exact, free and always the same shape, so every league reads alike. A league with no results has no box.

- **Game week** (the Champions League says **Matchday**) comes first: the current round over the season's rounds, for example 9/38 (a double round-robin has 2 x (teams - 1): 38 for a 20-team league, 34 for an 18-team league, 8 for the Champions League's league phase). The round is worked out from the table: the most games any team has played, and the games finished in it so far are the teams on that number divided by two.
- **Games played:** results since the last edition over the round size (teams divided by two: 10 for a 20-team league, 9 for an 18-team league, 18 for the Champions League's 36 teams), for example 3/10, followed by how far through the round we are in square brackets, so a Monday edition reads "3/10 [9/10 so far this game week]" and one game is visibly still to come.
- **Favourites won:** the clear favourites (50% or more to win before kick-off) who won, over all clear favourites, for example 2/4. If no match had a clear favourite it says so, and if odds are unavailable it says "No odds available".
- **Biggest upset:** the match, and the favourite's pre-match chance, picked from the clear favourites who lost, the biggest chance first; or "None".
- **Game of the day** (the Champions League says "night"): picked by code from goals, lead changes, a close finish, a late goal, a comeback, red cards and an upset, shown with its goals and "comeback" where true.
- **Expectation comes from pre-match betting odds** (the DraftKings lines ESPN carries in each match summary) with the bookmaker's margin removed. ClubElo is the planned backup if odds are missing, to be tested when the service is reachable (it returned an error when tried).
- **A written storyline is optional and off by default.** The earlier Claude-written overview (Opus) is kept in the code and tested, with its checks: goal timeline, winning goal, league records, no history claims, no copied report text, no unsupported upset language. It would become at most one sentence for notable cases only (an upset, a very high-scoring game or a red card), if D asks for it after seeing real days. Not using it saves the most expensive Claude calls.
- **Not available, and not used:** an official FIFA club ranking does not exist (FIFA ranks national teams only), and there is no reliable free source of public sentiment.

## International football

International football appears only during international breaks and major tournaments, and only for competitive games.

- **Which games:** qualifiers, the UEFA Nations League and final tournaments. Friendlies are excluded.
- **Which teams:** men's sides in the FIFA top 30, refreshed before each international break, plus Singapore and India always.
- **Women's football:** the Women's World Cup and Women's Euro finals only, as headline events in Around the sporting world.
- **Nations League tables:** all four League A groups, plus any League B or C group containing a top-30 side. Each row carries a zone colour with a legend: quarter-finals (blue), play-off (lilac), relegated (rose).
- **What's at stake:** two or three lines per group before and after each matchday. Code works out every possible finish from the remaining fixtures; Claude only phrases what that calculation supports. Where a finish depends on goal difference or head-to-head, say so rather than guess.
- **Where each place leads (League A):** 1st and 2nd go to two-legged quarter-finals in March 2027, then the Finals in June 2027. 3rd plays a two-legged play-off against a League B runner-up. 4th is relegated to League B.
- **League B:** 1st is promoted, 2nd plays the promotion play-off, 3rd plays a relegation play-off against a League C runner-up, and 4th is relegated.
- **How it is built (checkpoint 4):** the block is headed International Football and appears only when the Nations League has results in the edition's window or a match kicks off within 30 hours, or a competitive qualifier or final involving a top-30 side, Singapore or India was played. Between breaks it is absent and no Nations League data is even requested. Friendlies are never looked at.
- **Zones are read from ESPN's own notes** on the League A rows, which spell out the rules for every league (for example "A: Qualifies for QFs; B-D: Promotion playoffs"). Blue bars are quarter-finals or promotion, lilac is a play-off, rose is relegation, with a legend per league.
- **Groups shown:** all four League A groups, and any League B or C group that contains a top-30 side. The top 30 comes from `kickoff/rankings.py`: FIFA publishes no stable open feed, so by default it is World Football Elo (eloratings.net), labelled on the page as a stand-in for the FIFA ranking and refreshed when older than 21 days. To use the real FIFA list, D edits `data/top30_manual.json` before each break (`{"source": "FIFA ranking, <date>", "updated": "<YYYY-MM-DD>", "teams": [30 names]}`); that file always wins. Without any ranking only League A is shown.
- **What's at stake is proven by code:** for each group the remaining matches are found through each team's own ESPN schedule, every win, draw and loss is tried (3 to the power of the matches left), and each team's best and worst possible finish is recorded. Teams level on points can take any place between them, so a zone that could depend on goal difference or head-to-head is flagged and the lines say so. The calculation was cross-checked against an independent brute force on all 14 real groups. **If the number of remaining matches found does not equal the number the games-played counts require, the group is marked unconfirmed, no positions are given, Claude is not asked, and the page says the fixtures could not be confirmed. A group is called finished only when every team has played all its games.** Claude only phrases the proven lines (one to three per group, each at most 30 words), and its lines are rejected if they say a team has "secured" or is "through" when it is not settled, omit a needed tie-break warning, invent a name or number, or run over length; after one retry the plain code-written lines are used.
- **Scoreboard:** the window's results in the shown groups, with scorers, in the same design as every league. Qualifiers and finals involving a top-30 side, Singapore or India appear under their competition name with the same scoreboard.
- **Not yet verified on live data:** Singapore and India's competitive fixtures (none fall in the current window), and the other qualifier competitions' ESPN codes.
- **Euro 2028 link:** the best-ranked group winners who don't qualify through the main route are expected to get a play-off place. This is pending UEFA's formal approval.

Source: [2026–27 UEFA Nations League format](https://en.wikipedia.org/wiki/2026%E2%80%9327_UEFA_Nations_League).

## Cricket, F1 and tennis

Each of these appears only when there's play, and each gets its own standouts.

**Cricket**

- **How it is built (checkpoint 5):** from CricketData.org's free tier, which allows 100 calls a day. A match list costs 1 call per 25 matches (the list covers about the last four days) and **a scorecard costs 10 calls**, so only about eight scorecards fit in a day after the lists and a reserve of 10 calls. The block buys scorecards for the most important matches first (men's Tests, then women's Tests, men's internationals, women's internationals, then leagues) and shows every other result from the list alone; the page says how many matches had their standouts checked. A match whose scorecard fails keeps its result. No Claude is used: results and standouts are built by code from exact data.
- **What counts:** matches where at least one of the 12 Test-playing nations plays (men's or women's) and the name says T20I, ODI, Test or a tri-series; plus the IPL, BBL, The Hundred and the women's WPL, WBBL and women's Hundred. Left out: Hong Kong Sixes, unofficial Tests and A-team matches, and domestic competitions such as the Sheffield Shield and the Ford Trophy. Innings labels in the data are messy ("ireland Inning 1", "Namibia,Ireland Inning 1"), so they are matched against the match's real team names.
- **What is shown:** results grouped under International, Women's international and each league, each with both innings, the result line and the series; India in bold. A match whose scorecard was bought also shows a compact scorecard: for each innings the top three batters (initial and surname, runs and balls, * for not out) and the wicket-takers from the other side (wickets-runs, best first). A match outside the call budget shows its result only. **A scorecard is paid for once:** the compact scorecard and the standouts for each match are cached in the state file (the most recent 60), so re-running the same day, or running the demo again, never spends calls twice on the same match. Finished matches appear once (tracked in a state file). A live Test appears on each day its status changes.
- **Standouts, ranked, at most five:** a century (100 or more), a five-wicket haul, a fifty off 25 balls or fewer, and in a T20 a four-wicket haul, in that order. From a final scorecard a fifty can be called fast only when the whole innings was 50 or more off 25 balls or fewer, so that rule is conservative. **T20 hat-tricks and career milestones are not in a scorecard, so they are not claimed.**
- **Sources tried:** ESPN has no cricket data and Cricinfo blocks bots (not used); Cricsheet is free and detailed (ball-by-ball) but was a week behind when tested, so it is not a daily source; Big Balls Data (the spec's backup) has not been tested.

- **International:** the 12 Test-playing nations (Australia, England, India, New Zealand, Pakistan, South Africa, Sri Lanka, West Indies, Bangladesh, Zimbabwe, Afghanistan and Ireland), men's and women's, all formats.
- **Leagues:** IPL, BBL and The Hundred, plus the women's competitions: WPL, WBBL and the women's Hundred.
- **Standouts:** centuries, five-wicket hauls, T20 hat-tricks and four-wicket hauls, fifties off 25 balls or fewer, and milestones.

**F1**

- Results tables appear only after Qualifying and after the Race, each race weekend, with driver and constructor standings after each race. Free practice is not covered. Sprint results stay as in the original plan.
- **Standouts:** big recoveries through the field, first podiums or wins, and standout qualifying laps. Rookies feed Young Guns.

**Tennis**

- Grand Slams only: Australian Open, Roland-Garros, Wimbledon and US Open. Men's and women's singles.
- **Rounds 1 to 3:** only matches involving seeded players. **From the last 16:** every match.
- Top-10 players withdrawing before a Slam.
- **Standouts:** top-10 seeds knocked out, comebacks from two sets down, and milestones.

## NFL and NBA

The NFL gets a full Wednesday wrap; the NBA shows every game, with marquee players' games first.

**NFL**

- Games grouped by division, each with the score and a one-line story.
- Quick scores on Monday and Tuesday as games finish. Wednesday has the full wrap: every game by division, standouts, Player of the Week and the division tables. Saturday carries the Thursday Night Football score.
- Three to five standouts per week, ranked, each with one line of context.

| Position | Standout threshold |
| --- | --- |
| Quarterback | 350+ passing yards, 4+ touchdown passes, 300+ yards with 3+ touchdowns and no interceptions, or 100+ rushing yards |
| Running back | 150+ rushing yards, or 3+ total touchdowns |
| Receiver or tight end | 150+ receiving yards, or 3 receiving touchdowns |
| Defence | 3+ sacks, 2+ interceptions, or any defensive touchdown |
| Special teams | Return touchdowns, field goals of 55+ yards, game-winning kicks |
| Any player | Franchise records, career milestones, rookie breakout games |

**NBA**

- Every game gets a score, in two tiers. Games with a tracked player come first: score, the star's stat line and a one-line story. All other games follow as compact one-line scores.
- **Extra focus:** LeBron James and James Harden always get their stat line and a milestone watch, win or lose.
- **Standouts from any game:** 40+ points, triple-doubles, 20-point and 20-rebound games, game-winning shots and milestones.
- **Defence counts too:** 5+ blocks, 5+ steals, or shutting down an opposing star earns a standout line or a short comment.
- **Players join automatically:** anyone off the list with three standout games in 30 days is added. Auto-added players drop off after eight weeks without a standout; D's picks stay on permanently.
- Conference standings every Tuesday.
- Players are tracked by player ID, so a traded player is followed automatically.

| Player | Team (2026-27) |
| --- | --- |
| Victor Wembanyama | San Antonio Spurs |
| Shai Gilgeous-Alexander | Oklahoma City Thunder |
| Nikola Jokić | Denver Nuggets |
| Luka Dončić | Los Angeles Lakers |
| Jalen Brunson, Karl-Anthony Towns | New York Knicks |
| Giannis Antetokounmpo | Miami Heat |
| LeBron James, Joel Embiid, Jaylen Brown | Philadelphia 76ers |
| Donovan Mitchell, James Harden | Cleveland Cavaliers |
| Stephen Curry | Golden State Warriors |
| Kevin Durant | Houston Rockets |
| Anthony Edwards | Minnesota Timberwolves |
| Jayson Tatum | Boston Celtics |
| Ja Morant, Damian Lillard | Portland Trail Blazers |
| Trae Young, Anthony Davis | Washington Wizards |
| Tyrese Haliburton | Indiana Pacers |
| Zion Williamson | New Orleans Pelicans |
| Cooper Flagg | Dallas Mavericks |
| Cade Cunningham | Detroit Pistons |

Source: [NBA.com 2026-27 season previews](https://www.nba.com/2026-27-season-preview/features).

## Baseball

Baseball is a short, focused block on the Los Angeles Dodgers' two Japanese stars, not full MLB coverage. It appears only when one of the triggers below happens.

- **Shohei Ohtani, batting:** a home run, a stolen base or a game-winning hit.
- **Shohei Ohtani, pitching:** every start. All pitching performances count as noteworthy whenever he is the starting pitcher.
- **Yoshinobu Yamamoto:** every start.
- **What each entry holds:** the Dodgers' score, the player's stat line and a one-line story. Postseason games count the same as regular-season ones.
- **Timing:** US night games finish late in the Singapore morning, so many land in the next day's edition, like the NBA.
- **Lead sport:** a trigger above makes baseball eligible to lead, under the lead-sport rule.

## Young Guns

Young Guns is one dedicated section for rookies and young stars across every sport, with a running watchlist so each player's rise reads like a story.

| Sport | Who counts |
| --- | --- |
| Football | Under-21s in the six leagues and the Champions League, with extra attention on D's clubs |
| NFL | Rookies |
| NBA | Rookies and second-year players |
| F1 | Rookies |
| Cricket | Under-23s or players in their first year of international cricket, plus uncapped players at the IPL |
| Tennis | 21 and under |

- **Watchlist:** saved in the state files. Each entry records the player, sport, team and a dated log of standout games, so lines can say things like "his third big game this month."
- **Who makes the cut:** a young player who hits that sport's standout threshold joins the watchlist. Players drop off after about eight weeks without a standout.
- **Spotlight:** young Southeast Asian and Indian athletes get extra attention, matching the rule in Around the sporting world.

## Around the sporting world and interesting stories

The general section covers major events only and is built from news feeds, since these sports lack good free data. Women's events are included throughout.

| Sport | What's covered |
| --- | --- |
| Rugby | Men's and women's internationals and World Cups |
| Golf | The four men's majors, the five women's majors, the Ryder Cup and the Solheim Cup |
| UFC | Numbered events only, main and co-main events only, ranked fighters only |
| Badminton | BWF Super 1000s, World Championships and World Tour Finals |
| Athletics | Diamond League and World Championships |
| Handball | World Championships, Euros and the EHF Champions League Final Four, men's and women's |
| Field hockey | FIH Pro League, World Cup and Asia Cup, men's and women's |
| Chess | World Championship match, Candidates, Chess Olympiad, Women's World Championship, and elite invitationals such as Tata Steel and Norway Chess |
| Darts | PDC World Championship, World Matchplay, Grand Slam of Darts and Premier League finals night |
| Multi-sport games | Olympics, Asian Games, SEA Games and Commonwealth Games |
| Women's football | Women's World Cup and Women's Euro finals |

- **Spotlight rule:** any Southeast Asian or Indian athlete reaching a semi-final, final or podium at a notable event gets a line, even if the event is below the usual bar. A Super 750 badminton semi-final counts, for example.
- **Not covered:** MotoGP (for now), cycling, snooker and ONE Championship.
- **Interesting stories:** three to five stories from across everything covered, each summarised in two or three sentences in our own words, with a link to the original. Avoid repeating a story already featured in the last week.

## Data sources

No single repo does this job, so The Kickoff combines several free sources, with backups where one might break. Free-tier limits change, so check each provider's current terms during the build.

| Source | Used for | Caveat |
| --- | --- | --- |
| [ESPN unofficial API](https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b) | Backbone: football scores and news (including the Turkish league, Champions League and Nations League), NFL, NBA, tennis, F1 news, NFL and NBA injuries | Undocumented, no guarantee, can break at any time; needs fallbacks |
| football-data.org, free tier | Backup tables for the top five leagues and the Champions League | 12 free competitions, no Turkish league, 10 requests a minute |
| FPL official data | Premier League injuries, suspensions and key-player minutes | Unofficial but the league's own feed; team 'played' is 0, so games are counted from fixtures |
| API-Football, free tier | Tested and dropped: the free plan only covers seasons 2022 to 2024, so no current data | A paid plan would be needed; not used |
| [Jolpica F1 API](https://github.com/jolpica/jolpica-f1) | F1 results, qualifying and standings | Community-run successor to the old Ergast API; respect its rate limits |
| [CricketData.org](https://cricketdata.org/), main cricket source | Cricket results and scorecards, international and franchise | Running since 2015 as CricAPI; permanent free tier of 100 calls a day, ample for one run; women's coverage may be thinner |
| [Big Balls Data](https://bigballsdata.com/cricket-api), backup cricket source | Women's competitions and cross-checks | 250 free calls a day, 500 with a linked GitHub account; covers WBBL and the women's Hundred, but its live data looked weeks old when checked, so test freshness first |
| MLB Stats API or ESPN | Dodgers games, Ohtani and Yamamoto stat lines | Source to confirm and test during the baseball checkpoint |
| FPL public data | D's classic team and Draft league | Unofficial; needs D's team and league IDs |
| RSS feeds: BBC Sport, The Guardian, governing bodies, the Premier League's official site and club sites | News, injuries, transfer reports, the general section, interesting stories | Summaries only, always linked to the original. Whether the Premier League and club sites offer usable feeds is tested in the news step |
| ESPN match odds | Pre-match win chances for overviews (favourites, upsets) | DraftKings lines carried by ESPN; undocumented like the rest of ESPN; ClubElo is the untested backup |
| FIFA ranking | The top-30 list before each international break | Exact source to confirm during the build |
| Anthropic API | Summaries, standout lines, what's-at-stake lines, Young Guns notes, picking stories | Dedicated key in its own workspace with a monthly spend limit |

Ruled out for cricket: [Roanuz](https://www.cricketapi.com/docs/guides/Free-APIs/), whose free tier is only sample matches from 2013 and 2014, and the [Cricbuzz scraper on GitHub](https://github.com/mskian/live-cricket-score-api), which is unofficial and returns just one match's live score.

## Design system

The look is a floodlit pitch: deep green, chalk text and trophy gold, built dark-mode first, with two fonts in clear roles.

- **Masthead:** "The Kickoff" in Newsreader, styled as an old-school newspaper nameplate.
- **Everything else:** Josefin Sans for headlines, body text and tables. Body text at 18px with 1.7 line spacing, never below regular weight; headlines in semibold. If long paragraphs feel tiring after a week, switch only the body text to Jost.
- **Team names in match notes** are in bold, so each note is easy to scan.
- **Headings:** section and sub-section headings (such as The Big Stuff and Key Overnight Scores) are in trophy gold, bold (700) and have every word capitalised, so they stand apart from the chalk body text.
- **Numbers:** right-aligned table cells so columns line up.

| Colour | Hex | Use |
| --- | --- | --- |
| Pitch | #13251E | Page background |
| Surface | #1A2F27 | Tables and chips |
| Hairline | #2A4238 | Dividers and the rail track |
| Chalk | #E8E3D6 | Main text |
| Muted | #A3B0A6 | Secondary text |
| Trophy gold | #CFB06E | Accent: rail fill, Performance of the Day, masthead rule |
| Zone blue | #8DB4CC | Qualifying and quarter-final places |
| Zone lilac | #B3A6CC | Play-off places |
| Zone rose | #C99590 | Relegation places |

- **Light mode:** switches automatically with the phone's setting. Pale grey-green background, deep green text, and the same accents darkened to meet 4.5:1 contrast. Values: background #E9EFEA, surface #DCE6DF, hairline #B7C6BB, text #13251E, muted #44574B, gold #7A5C14, blue #2F6280, lilac #5E4F8A, rose #9A4A43. Lowest contrast checked: 4.78:1.
- **Rules:** no pure black or pure white, no strong red, no crests or logos.
- **Layout:** one column, left-aligned, about 62 characters per line on wide screens and full width with comfortable margins on phones. Generous space between sections. League tables carry coloured zone bars and no legend. Nations League tables keep a legend, as their zones are less obvious.
- **On today tags:** "While you're up" with a sun icon, "Overnight" with a moon icon.

**Progress rail**

- A thin vertical rail on the right edge with one tick per section; tapping a tick jumps to that section.
- The rail fills gold as you read.
- A chip in the top bar's right corner shows the percentage read (such as 43%) and minutes left, estimated from the word count at about 230 words a minute. It sits in a thin bar so it never covers text.
- It must never cover text, and it respects the phone's reduced-motion setting.

## Build checkpoints

The whole build happens in one project, in this order. Each checkpoint is tested on the Mac Mini before it's committed, and a failing source must never break the rest of the edition.

1. **Accounts and setup:** GitHub account (the username appears in the web address), a new public repo, and GitHub Pages switched on. In the Anthropic Console, a new workspace called The Kickoff with a monthly spend limit, then a new API key inside it. A new Telegram bot via BotFather, plus D's chat ID.
2. **Skeleton:** page template, design system and progress rail. Publish a dummy edition and send the Telegram ping.
3. **Football:** leagues, results, tables and change detection, clubs, Arsenal and Arsenal Women, Champions League, injuries and the key-player list, transfers, FPL corner.
4. **International football:** Nations League tables, zones and what's at stake.
5. **Cricket.**
6. **F1.**
7. **Tennis.**
8. **NFL,** including the weekly rhythm.
9. **NBA,** including tracked players.
10. **Baseball:** Ohtani and Yamamoto triggers, Dodgers scores.
11. **Young Guns** and the watchlist.
12. **Around the sporting world.**
13. **Cross-sport sections:** The big stuff, On today, Games to Watch, interesting stories and the lead-sport ordering.
14. **Test runs:** three mornings run by hand, then switch on the daily 7:15am SGT schedule.

## Open items

Small things to settle, none of which blocks starting the build.

- [ ] WPL coverage: confirm CricketData.org or Big Balls Data carries it before the next season starts.
- [ ] FIFA ranking: World Football Elo is the labelled stand-in; D can supply the real FIFA top 30 in data/top30_manual.json before each break.
- [ ] FPL classic team ID and Draft league ID: collect during the build.
- [ ] Baseball data source: choose between the MLB Stats API and ESPN during the baseball checkpoint, after testing both.
- [ ] Baseball scope: the spec assumes only Ohtani and Yamamoto trigger an entry. Widen it if D wants other Dodgers or MLB news.
