# The Kickoff: how it works

*The current rules, by section, as of 8 November 2026. The full history of how each rule came about, round by round, is in SPEC-history.md. Where the two differ, this file wins. The numbers quoted here live in code (mostly `kickoff/importance.py`); the file named next to each rule is where to change it.*

## 1. What it is

A personal daily sports digest for D, one reader in Singapore, reading on an iPhone in dark mode. One web page every morning, linked from a Telegram ping, covering the sports, teams and players D follows.

- **Voice:** plain, warm and specific; our own words, short, with a link to the source. No copied article text, no hype, no emojis.
- **Official names** for events, rounds and levels (BWF levels, round names), even when D says them differently.
- **Singapore time (SGT) everywhere.** No preseason, spring training or exhibition games, ever.
- **No crests or logos;** team names or three-letter codes. Never other managers' or league-mates' names on the public site.
- **Simple and robust over clever (D, 2026-11-08):** a new rule should be one plain rule or one small table with a test. Fragility is the biggest risk.

## 2. How it runs

- **Every day at 7:15am SGT** GitHub Actions (`.github/workflows/daily.yml`, cron `15 23 * * *`, pinned to Ubuntu 24.04) builds the edition (`scripts/daily.py`), commits the page, edition and state, and pings Telegram. GitHub can start a scheduled run 5 to 30 minutes late. A manual run (`gh workflow run daily.yml -f claude=true -f ping=true`) does the same; `-f force=true` rebuilds a day that already has an edition.
- **Pages:** each edition at `/editions/<date>/` plus an archive (GitHub Pages, noindex). A footer counter, "Edition #001" for 7 November 2026, adds one a day.
- **State:** small JSON files in `data/state/` remember what has been reported, so each edition shows what is new since the last one and a missed day catches up.
- **Keys** live in GitHub's secrets and in a local `.env` that git ignores; never printed or committed. Runs that use them (Telegram sends, Claude rehearsals, starting workflows) are usually started by D; Claude Code may run one when it really matters (D, 2026-11-08).
- **Python 3.9** today (Apple's built-in version). It is past its end of life; moving to 3.12 is an open item (section 12).

**Reliability: nothing fails silently**

- **A failing source** never breaks the edition: that part is left out and counted; a sport that fails shows "No data this morning" and keeps its old state.
- **Health check** (`kickoff/health.py`): up to four ⚠ lines in the ping when something should have come through and did not: a sport that could not be built, a skipped part, a cricket match with a score but no scorecard, Claude off or in cheaper mode, the Mac's cricket backup not run for over a day, nothing from any sport. A good morning adds nothing.
- **Ping fallback:** the ping waits up to 15 minutes for the page; if it is not live, it sends the digest as text plus the whole page as an HTML file.
- **Failure alert:** if the run fails, D gets a Telegram alert.
- **Mac jobs** (launchd; python3.9 has Full Disk Access): the **cricket backup** at 6:50am fetches ESPN's cricket pages into `data/cricket_cache.json` and pushes it (a backup only since 8 Nov); the **watchdog** at 8:30am builds and sends the edition from the Mac if the page is not live, after waiting (up to 45 minutes) for a GitHub run still in progress, so it never sends a second edition beside a late one.
- **Probe** (`.github/workflows/probe.yml`, started by hand): tries every outside source and today's cricket from GitHub's own servers.

**Cost:** every Claude call is logged by section and day; the monthly budget is **$10** (`settings.MONTHLY_BUDGET_USD`): at 80% the expensive model steps down, at 100% Claude is skipped and code writes plain lines. Models: Sonnet 5.5 for notes and news, Opus 5.5 for matchday overviews (`kickoff/settings.py`). Claude only ever sees a facts sheet; code checks every name, number and claim it writes, retries once, then falls back to plain lines.

## 3. The edition, top to bottom

A section appears only when it has something in it.

1. **The Big Stuff** (section 4)
2. **On Today** (section 5)
3. **The sport sections:** Arsenal and Football (together), Cricket, NBA, NFL, MLB, in that order, except that one **lead sport** moves to the front: D's team or player played (Arsenal men and women, India men, Sunrisers Hyderabad, Royal Challengers Bengaluru, the tracked NBA stars, the Jaguars and Steelers, the Dodgers in the postseason); among several, the bigger kind of match; otherwise a playoff or knockout moment; otherwise the normal order. Baseball never leads in the regular season. (`kickoff/order.py`, `bigstuff.py`)
4. **F1 and Tennis:** an F1 race or a Grand Slam from the quarter-finals is a **major event**: a line under "Major Events" in The Big Stuff, and its section moves right after the lead group. On other days F1 and Tennis are still their own sections, after the sports.
5. **Young Guns** (section 9)
6. **Around The Sporting World:** Other Sports (section 10)
7. **Interesting Stories:** three to five picks across everything, two or three sentences each with a link, never repeated within a week (Claude only)
8. **The End:** a gold line, so the finish is clear.

## 4. The Big Stuff and the Telegram ping

**Key Overnight Scores** (`kickoff/bigstuff.py`, `events.py`, numbers in `importance.py`)
- Every finished game is scored: the kind of game (final 10, knockout or playoff 7, a big night or top-of-the-table 5, ordinary 2), +6 for D's team, +2 for a listed football club, a little for goals and margin, then, **only when a big club or D's team played** (D, 2026-11-09): +4 for a dramatic finish (a last-seconds winner or **equaliser**, overtime by 3 or less, a one-point game), +5 for something crazy (a five-goal margin that was not an expected thrashing, a comeback in a high-scoring game), and in football **+4 for an upset: one of the 17 big clubs beaten by a club outside them, +6 when the odds also made it the clear favourite**; +3 when two big clubs meet. On Sunday and Monday a plain regular-season NBA, MLB or cricket game counts 0.4 of its score (0.7 other days); India, Sunrisers and Royal Challengers are never cut. Under 4 points is dropped.
- Up to 8 lines on Sunday and Monday, 6 on Tuesday and Saturday, 5 otherwise; Arsenal's result first, Arsenal Women's right after; at most 4 from one sport (D's teams and finals excepted).
- **Grouped by sport** under a grey header; **Football** is one header with each competition as a small italic label under it. **Scores in gold** ("3–1", "504 (134.3)"); team names stay white. Winner first.
- A finished Test between Test nations is always a line, draw included: "Bangladesh v West Indies · 2nd Test, Match drawn".
- A Test in progress is a team-score line on mornings its score moved: "Afghanistan v Zimbabwe · Stumps, Day 3: Zimbabwe 504 (134.3), Afghanistan 402/7 (125)".
- **F1 pole:** "**On pole** · Lando Norris · Brazilian Grand Prix · 1:27.470" ("On pole" in gold), below a race win.

**Biggest News** (at most 2, with source links; confirmed news only: no rumours or gossip columns, no contract renewals; the same story from two outlets once) and **Major Injuries** (at most 2: listed clubs' key players out or suspended, Arsenal first).

**Stars Of The Night**
- Individual performances on one 0-100 scale, at least 70 (an NBA 40-point game or triple-double always reaches it): up to three, at most two from one sport; milestones (a century, a five-for, ten wickets in a Test, a T20 fast fifty, a world record) always make it, up to five in all.
- **At most two from one match:** its best, then the best of the other discipline if there is one (a six-for beside a double hundred), else its next best.
- **Bowling hauls by format** (`events.HAUL_RUNS`): the runs a haul is worth, then scored like a century: five wickets = 100 everywhere; six = 150 in a T20, 125 in an ODI, 115 in a Test; seven = 200, 150, 130; eight or more = 250, 200, 150.

**The Telegram ping:** the date, three headlines (an F1 race win or a Slam final always first, then the key scores, then the Stars, then the best game even below the bar, so it is never empty), a "Today:" block of up to three items on a quiet morning (fewer than three key scores), any ⚠ health lines (up to four, then "and N more"), and the link.

## 5. On Today and In The Week Ahead

(`kickoff/ontoday.py`, `fixtures.py`)

- **On Today:** from now until the next edition, in SGT. **While You're Up** (sun, 7am to 11pm), then **Overnight** (moon, 11pm to 7am). At most 12 lines, the highest scores kept, shown in time order; a game already under way says "Under way".
- **What is in:** D's teams; every final, knockout and playoff game; a listed club's league game; Champions League nights with a listed club; a plain NBA game only for D's five teams; the NFL's night games and D's two teams; the MLB postseason; every international of the Test-playing nations and the IPL; every F1 session; a Slam's late rounds; UFC main events; badminton finals days and golf starts ("All day"). FA Cup ties only with a Premier League club.
- **A Test under way** shows its day and start time ("11:30am · Bangladesh v West Indies · 2nd Test · Day 4"), "Under way" only during the day's play, and counts as a **running story**: it outranks a listed club's routine league game, not D's teams or the big games.
- **★ Don't Miss** opens On Today: up to three of D's teams' games, finals, semi-finals and playoffs, derbies, top-of-the-table clashes (both clubs in their league's top 4) and **meetings of two of the 17 big clubs** (Atlético v Barcelona), and every F1 qualifying, sprint and race. Not a plain NBA or MLB regular-season game. Ranked by score, then by the clubs' combined table places. The same games are marked **rust** in the time list.
- **In The Week Ahead (Mondays):** the six days after today, grouped by day, at most 12 lines (a sport at most 4; D's football, cricket and NFL teams and finals excepted, the NBA always capped): D's teams (not plain NBA games), knockouts and finals, derbies, top-of-the-table clashes, tracked NBA stars' teams meeting, **the NFL's prime-time games (Thursday, Sunday and Monday nights)**, F1 races, a Slam's late rounds, UFC cards, golf and badminton starts. Cricket matches ahead are found by date (ESPN's live feed lists a match only about a day before).

## 6. House style (every sport)

- **Tables:** the title is the table's own top row ("Table (top 6 only)", "Qualifying Results", "Six Nations"), centred; the first column keeps at least 8px of space on the left (12px in fixed-width tables); numbers right-aligned; fixed widths where tables must line up; checked at 360px before showing D.
- **Names:** full team names on game lines; three-letter codes elsewhere (fix maps where ESPN's are not three letters: GSW, NOP, NYK, SAS, UTA; KCR, SDP, SFG, TBR); "initial + surname" for people in tables; full names in notes, Young Guns and golf.
- **Markers:** gold diamond bullets on every list; gold for the key figure; ▲n / ▼n / – for movement; a white asterisk on an underdog winner (football, NBA, NFL, MLB) with a key; seeds and ranks in square brackets ("[1]"); one en dash in scores ("3–1").
- **Gold rows** only in official league tables: Arsenal (Premier League, WSL, Champions League), Sunrisers Hyderabad (IPL), D's Draft team (FPL).
- **No repetition:** an item appears once; standouts do not repeat the score above them.
- **Headings:** Title Case, short, trophy gold.
- **In progress:** a game being played at edition time shows its score with "In progress" and is reported as a final the next morning.

## 7. Arsenal and Football

(`kickoff/football.py` and its helpers)

- **Arsenal:** the result in every competition (a Claude note of four to six sentences, two for Arsenal Women, checked), scorers and assists, form, then **Next up**: three bullets, "Sat 7 Nov, 11pm · Hull City (home) · EPL" (EPL, FA Cup, CL, LC). Injuries and news only when credible and new.
- **Leagues:** the Premier League, La Liga, Serie A, Bundesliga, Ligue 1 and Süper Lig, then the WSL. Each block: the round-up box (Game week, Games played, Underdogs won, Biggest upset, Best game; by code from results and pre-match odds), the scoreboard (scorers under each side; an asterisk on an underdog winner), Claude's notes (every Premier League game; the listed clubs' games elsewhere), the table and the leaders lines (Top Scorer, Top Assists, Top CS).
- **The 17 listed clubs** (`kickoff/clubs.py`): Arsenal, Man City, Man Utd, Liverpool, Chelsea, Spurs; Bayern, Dortmund, PSG, Juventus, Napoli, Inter, AC Milan, Como, Barcelona, Real Madrid, Atlético.
- **Tables:** in full on Tuesdays and the first time; otherwise only when changed, as "Table (top 6 only)"; **Arsenal outside the top 6 get their own gold row under it, set apart**; other listed clubs outside it in one line, "Other major clubs: TOT 9th (12 pts), MUN 17th (7 pts)". Unchanged: one muted line at the end, "No new games: ...". Movement arrows against the last table shown.
- **Champions League:** the box, the scoreboard, the 36-team table on league-phase matchdays; knockout ties as two-legged series tables.
- **FA Cup:** only the ties that matter: a Premier League club played; a Championship club lost to a lower-league club; or a giant-killing of 20 places or more in the English pyramid (the top five tiers as one ladder, 1 to 116). (`kickoff/facup.py`)
- **International football:** only in breaks and tournaments, competitive games only; Nations League tables (League A, plus B or C groups with a top-30 side) and "what's at stake" proven by code; Singapore and India always.
- **Injuries:** Premier League key players from FPL's status, each item once. **News:** BBC, Guardian and ESPN only; Claude classifies and writes one checked sentence.
- **FPL corner:** the morning within 24 hours of a deadline, and once after a gameweek is checked: D's summary box, the Draft league table (team names only), Injuries, Bench Swaps, Underperforming Players, Potential Pick Ups, FPL Watch (not D's own players). No Claude.

## 8. Cricket, F1, Tennis, NFL, NBA, MLB

**Cricket** (`kickoff/cricket.py`, `sources/espn_cricket.py`)
- **Scope:** every international of the 12 Test-playing nations (men's and women's, all formats); the IPL, BBL, The Hundred, WPL, WBBL and the women's Hundred. **An India match always opens the section.**
- **Sources, one fixed order:** ESPN's JSON feeds (matches, scores, the full scorecard, state, Player of the Match, points tables; read for yesterday and today by date, because finished matches drop off the live feed), then the Mac's cache, then ESPN's pages. A match with a score and no scorecard is a ⚠ line in the ping.
- **Layout:** "New Zealand v India · 2nd ODI", the result as the big line, the scores (winner's gold), Player of the match ("not available at time of print" when ESPN has not posted it), the full scorecard for big-six, Test and IPL matches, the series table for Tests and ODIs.
- **A Test in progress:** the "Test · in progress" pill, the heading "1st Test", and ESPN's own state: "**Stumps, Day 3** · Afghanistan trail by 102 runs" ("Live, Day 4", "Lunch, Day 4"). Only innings that moved since the last edition are shown in full; on the last day the match summary (each innings with its total right-aligned in gold, "386" for all out, "398/6d" for a declaration, top batter and bowler, then "Match result: Drawn" or "IND won by an innings and 12 runs") and the series table.
- **Standouts** (grouped under their competition, figures gold): a hundred; in a T20 any fifty (a fast fifty is 50 off 25 balls or fewer); five wickets; in a T20 four; in a T20 or ODI three or four at under five an over; ten in a Test match. **Milestones** (a hundred, then 150, 200, 250, 300; a five-for; ten wickets; a T20 fast fifty) are said once each, live matches included.
- **Virat Kohli:** his score always appears, small and muted, under his match ("Virat Kohli: 7 (7)"). He is a standout, a Key Overnight Scores suffix, a headline or a Star only on the normal rules (50 or more).

**F1** (`kickoff/f1.py`, `f1grid.py`, `sources/jolpica.py`, `sources/openf1.py`)
- Each session that finished since the last edition, newest first: Race, Sprint, Qualifying, under "Race 20/23 · Brazilian Grand Prix, São Paulo"; driver and constructor standings after a race (checked before they are shown); a title note when a championship is decided.
- **Times:** Jolpica first; **OpenF1** fills any time Jolpica left blank, by car number. With no times at all, the qualifying shows the order and a short note.
- **Grid penalties** (from the weekend's BBC, Guardian and ESPN reports, one small checked Claude call): a * on each penalised driver in the qualifying table, one line per penalty with its cause, and a **provisional grid (our calculation)**: a place drop moves the driver down, back-of-grid drivers go to the end in qualifying order, a penalty of unreported size is listed but not moved.
- **Standouts:** Biggest Mover, Big Moment, first wins and podiums, a dominant or first pole.

**Tennis:** the four Grand Slams (seeded players' matches in rounds 1 to 3, every match from the last 16), the ATP Finals and the WTA Finals; top-10 withdrawals; Top Seed Out, comebacks from two sets down, and provable milestones.

**NFL:** the week's scoreboard (home icon, underdog asterisk, OT), weekly leaders (D's quarterbacks Lawrence and Rodgers always listed), highlights, and on Wednesdays Top Performances, division tables and, from week 14, the playoff picture.

**NBA:** every game finished since the last edition (Lakers, 76ers, Cavaliers, Spurs and Celtics first). Under each game, **the tracked players and the key players together, by points, most first** (the winning team's top scorer from 20, anyone from 25, at most three key players), then the absent tracked players as small grey DNP lines. Best game, standouts, standings with movement, Cup tables on Cup days, playoff series tables.

**MLB:** a Thursday round-up of the Dodgers, Ohtani and Yamamoto through the regular season; daily from the Dodgers' 155th game; series tables in the postseason; a closing note.

**Season rhythm:** an Awards table on mornings something new is announced (NBA, NFL, MLB, Premier League, IPL caps and awards); a closing note when a competition is decided; a "season is coming" note a week before the NBA, NFL and Premier League start.

## 9. Young Guns

(`kickoff/youngguns.py`, `young_sports.py`)

- Rookies (NBA, NFL, MLB) and anyone **under 21** on the day, in every sport with a feed, shown only when they did something notable: NBA 20 points, 12 rebounds, 10 assists, 4 steals or 4 blocks; NFL 250 passing yards or 2 passing TDs, 100 rushing or receiving yards or 2 TDs, 2 sacks or an interception; football a goal or an assist (every league covered and the Champions League; D, 2026-11-08: young budding stars wherever they play); F1 a podium, points, pole or fastest lap; tennis a last-16 win or a win over a seed.
- Up to five lines, grouped by sport, the stat phrase in gold, full names. A player notable on three different days joins the watchlist and then needs only 70% of the thresholds.

## 10. Around The Sporting World: Other Sports

(`kickoff/around.py` and its helpers)

Each sport under its own gold heading; a sport with nothing is left out. Structured sources by code first; news-feed lines only from BBC, The Guardian, ESPN, The Straits Times, The Hindu and ChessBase, only for sports with no structured source, only as a Claude sentence checked against the source, at most two a sport.

- **Rugby:** internationals and World Cups from ESPN; **tables** under the results on a morning their games were played: the Six Nations, The Rugby Championship and the Nations Championship (Northern and Southern pools).
- **Golf:** the four men's majors, THE PLAYERS, the five women's majors, Ryder and Solheim Cups: a start note, then the first 25 after each round, D's players below in position order, full names.
- **UFC:** every UFC event: the main event, co-main and the top Prelims bout from UFC.com; the rankings table.
- **Badminton:** the Super 1000s, World Championships, World Tour Finals, Singapore Open and India Open from Wikipedia's draws: a start note, early-round lines for India's and Southeast Asia's players and the top three seeds (Singapore first, then India), every match from the semi-finals in tables.
- **Athletics** (`kickoff/athletics.py`): world records anywhere; at the top meets only (Diamond League, World and World Indoor, European and European Indoor Championships, Olympics, Commonwealth and Asian Games) a world lead or meeting record by the winner, and a **close finish** in a running final: 1st to 2nd within 0.03s up to 400m, 0.5s for 800m to 1500m, 1.5s longer. **World U20 records** too.
- **Swimming:** world records (long and short course, individual and relay) and **world junior records**.
- Five lines a morning at most for athletics and for swimming (records first); a world record is also a Star Of The Night.
- **Field hockey, handball, darts, chess, women's football:** champions of the listed events from Wikipedia; chess rounds from Lichess.
- **India and Singapore:** a semi-final, final or medal in any covered sport gets a line, even below the usual event bar (hockey's Asian Champions Trophy, for example).
- **Multi-sport Games** (Olympics, Youth Olympics, Paralympics, Asian, Commonwealth Games; the calendar is `around.GAMES`): while one is on and there is an India or Singapore line, Other Sports opens with it: "Youth Olympic Games · Dakar · Day 9 of 14 · until Fri 13 Nov", each line starting with its sport. Nothing to say, no Games header.

## 11. Design

- **Colours:** pitch #13251E (background), surface #1A2F27, hairline #2A4238, chalk #E8E3D6 (text), muted #A3B0A6, trophy gold #CFB06E, zone blue #8DB4CC, lilac #B3A6CC, rose #C99590, **rust #DB6A45 (Don't Miss)**. Light mode follows the phone, with darker accents for contrast.
- **Fonts:** Newsreader for the masthead; Josefin Sans for everything else, body 18px.
- **Progress rail:** a gold rail on the right fills as you read, with a chip showing the percentage and minutes left. A gold icon rides the head of the bar, one per section and per Other Sports heading: **20 designs, frozen** (football, cannon for Arsenal, cricket ball, basketball, NFL goalposts, baseball, tennis, golf flag, rugby, F1 helmet, chequered flag at The End, UFC glove, badminton, darts, chess king, trophy, clock, star, swimmer, runner). Balls turn as you scroll; the others sway.

## 12. Open items

1. **Python 3.12 upgrade** (Mac and GitHub): 3.9 is past its end of life. D is doing it on 8 November.
2. **The Mac cricket job stays for a month** (review around 8 December 2026): if ESPN's feed on GitHub has carried every scorecard, it is removed.
3. **Thresholds to review after a month of real editions** (early December): NBA standouts, Stars Of The Night (bar 70), the Key Overnight Scores caps, the bowling haul table.
4. **Not built yet:** season-closing notes for the Champions League, FA Cup, F1 and tennis; tournament mode for the Rugby World Cup 2027 and similar events (results, then group tables, then knockouts; built a month before each); the WPL's source; the IPL's live caps outside Wikipedia.
