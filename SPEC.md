# The Kickoff: how it works

*The current rules, as of 24 November 2026. Only rules live here. The history of how each one came about, and the old wording, is in SPEC-history.md. The numbers live in code (mostly `kickoff/importance.py`); the file named beside a rule is where to change it.*

## 1. What it is

A personal daily sports digest for D, one reader in Singapore, reading on an iPhone in dark mode. One web page every morning, linked from a Telegram ping, covering the sports, teams and players D follows.

- **Voice:** plain, warm and specific; our own words, short, with a link to the source. No copied article text, no hype, no emojis.
- **Official names** for events, rounds and levels, even when D says them differently.
- **Singapore time (SGT) everywhere.** No preseason, spring training or exhibition games.
- **No crests or logos.** Never other managers' or league-mates' names on the public site.
- **Simple and robust over clever:** a new rule is one plain rule or one small table, with a test. Fragility is the biggest risk.

## 2. House Style: every new table or block must pass this before D sees it

Older tables (the NBA leaders, for one) are brought in line when they are next touched, not all at once.

**Check it myself first.** Screenshot the page at 360px and at 390px in dark mode and look at it (section 13). Nothing touches an edge, nothing overlaps, nothing wraps by accident.

**Columns and alignment**
1. Each piece of information has its own column, and each column lines up straight down. Something small (a colour mark, a code) never shares a column with a name, which would push the name around.
2. Centre the columns of short items (ranks, codes, numbers, scores, dates). Names may be centred too; never leave a big empty gap between a name and the next column.
3. The first column keeps at least 8px of space on the left (12px in the fixed-width tables). Nothing sits flush against an edge, left or right.
4. Widths are set on the table (`colgroup`) so tables line up. Give the important column (the people, the winners) the larger share; shorten labels instead of widening a label column.

**Sizes and colours**
5. One font size for the main content of a row (names, dates, scores); never shrink a whole table to fit. Secondary details (ranks, colour marks, small notes) may be about two sizes smaller and grey.
6. **Gold** marks the key thing: the score, a leader, a winner, a new position, a stat figure. Leaders' rows in leader tables are gold.
7. **Grey** is for secondary information: brackets, notes, legends, DNP lines.
8. **Faded** (grey at half opacity) is for what has not happened yet (unplayed games). Only what has happened and the next thing up are bright.
9. Never single out D's own teams with colour or bold, except the gold rows in official league tables (Arsenal, Sunrisers Hyderabad, D's Draft team) or where D asked.
10. A section's class names are its own (`cm-` for chess, `mb` for the match board...). Never reuse a short class like `.r`, `.y`, `.g`, `.w` or `.pl` from another section: Sindarov once came out red that way.

**Words and markers**
11. Tables: the title is the table's own top row, centred; a small grey line under it for the context (venue and dates, season numbers).
12. Compact over long: three-letter team codes in tables (fix maps where ESPN's are not three letters), "initial + surname" for people in tables ("C. McDavid"), full names on game lines and in notes, short dates where the meaning is clear ("24N", "03D"), short labels (ROTY, MIP...).
13. A small marker beats extra text: gold diamond bullets on every list; ▲n / ▼n / – for movement; a white asterisk on an underdog winner, with a key; seeds and ranks in square brackets; one en dash in scores ("3–1"); "(W)"/"(B)" for chess colours.
14. Winner first: "Winner def. loser" in badminton, the winner's score in gold.
15. No repetition: an item appears once on the page; a standout never repeats the score above it; a legend appears once under a title, never on every row; the same story is told once in seven days.
16. Headings: Title Case, short, trophy gold.
17. Show the whole structure, not just what has happened so far (all 14 games of a match, the full bracket), with what is still to come faded.
18. No emojis anywhere on the page (they widen rows).

## 3. How it runs

- **Every day at 6:55am SGT** GitHub Actions (`.github/workflows/daily.yml`, cron `55 22 * * *`, pinned to Ubuntu 24.04) builds the edition (`scripts/daily.py`), commits the page, edition and state, and pings Telegram. GitHub starts it 30 to 45 minutes late, so it lands about 7:30 to 7:45. **The golden rule: never after 8.** A manual run: `gh workflow run daily.yml -f claude=true -f ping=true` (`-f force=true` rebuilds a day that already has an edition).
- **Pages:** each edition at `/editions/<date>/` plus an archive (GitHub Pages, noindex). The footer counter starts at "Edition #001" for 7 November 2026 and adds one a day.
- **State:** small JSON files in `data/state/` remember what has been reported, so each edition shows what is new and a missed day catches up.
- **Keys** live in GitHub's secrets and a local `.env` that git ignores; never printed or committed. Claude Code may run a key-using command (a Claude rehearsal, a ping, a workflow) when it really matters, sparingly, and says so.
- **Python 3.9** today (Apple's built-in); moving to 3.12 is an open item.
- **Cost:** every Claude call is logged by section and day. The monthly budget is **$10** (`settings.MONTHLY_BUDGET_USD`): at 80% the expensive model steps down, at 100% Claude is skipped and code writes plain lines. Sonnet 5.5 for notes and news, Opus 5.5 for matchday overviews (`kickoff/settings.py`). Claude only sees a facts sheet; code checks every name, number and claim it writes, retries once, then falls back to plain lines.

**Nothing fails silently**
- A failing source never breaks the edition: that part is left out and counted; a sport that fails shows "No data this morning" and keeps its old state.
- **Health check** (`kickoff/health.py`): up to four ⚠ lines in the ping when something should have come through and did not (a sport not built, a skipped part, a cricket score with no scorecard, Claude off or cheaper, the Mac's cricket backup not run for a day, nothing from any sport). A good morning adds nothing.
- **Ping fallback:** the ping waits up to 15 minutes for the page; if it is not live, it sends the digest as text plus the page as an HTML file. A failed run sends D a Telegram alert.
- **Mac jobs** (launchd): the **cricket backup** at 6:40am caches ESPN's cricket pages into `data/cricket_cache.json` (a backup only); the **watchdog** at 8:30am builds and sends the edition from the Mac if the page is not live, after waiting up to 45 minutes for a late GitHub run, so it never sends a second edition.
- **Probe** (`.github/workflows/probe.yml`, by hand): tries every outside source from GitHub's own servers.

## 4. The edition, top to bottom

A section appears only when it has something in it.

1. **The Big Stuff** (section 5)
2. **On Today** (section 6)
3. **The sport sections:** Arsenal and Football (together), Cricket, NBA, NFL, MLB, NHL, in that order, except that one **lead sport** moves to the front: D's team or player played (Arsenal men and women, India men, Sunrisers Hyderabad, Royal Challengers Bengaluru, the tracked NBA stars, the Jaguars and Steelers, the Dodgers in the postseason); among several, the bigger kind of match; otherwise a playoff or knockout moment. Baseball never leads in the regular season. (`kickoff/order.py`, `bigstuff.py`)
4. **F1 and Tennis:** an F1 race or a Grand Slam from the quarter-finals is a **major event**: a line under "Major Events" in The Big Stuff, and its section moves right after the lead group. Otherwise they are their own sections after the sports.
5. **Young Guns** (section 10)
6. **Around The Sporting World:** Other Sports (section 11)
7. **Story Of The Day** (a trial until about 6 December): the one story a keen fan would tell a friend about, two or three sentences with a link, never a result, never repeated within a week (Claude only; nothing on a quiet day).
8. **The End:** a gold line.

## 5. The Big Stuff and the Telegram ping

**Key Overnight Scores** (`kickoff/bigstuff.py`, `events.py`, numbers in `importance.py`)
- Every finished game gets a score: the kind of game (final 10, knockout or playoff 7, a big night or top-of-the-table 5, ordinary 2), +6 for D's team, +2 for a listed football club, a little for goals and margin. **Only when a big club or D's team played:** +4 for a dramatic finish (a last-seconds winner or equaliser, overtime by 3 or less, a one-point game), +5 for something crazy (a five-goal margin that was not expected, a comeback in a high-scoring game), +4 for a football upset (one of the 17 big clubs beaten by a club outside them; +6 when the odds made it the clear favourite), +3 when two big clubs meet. On Sunday and Monday a plain regular-season NBA, MLB or cricket game counts 0.4 of its score (0.7 other days); India, Sunrisers and Royal Challengers are never cut. Under 4 is dropped.
- Up to 8 lines on Sunday and Monday, 6 on Tuesday and Saturday, 5 otherwise; at most 4 from one sport (D's teams and finals excepted). Arsenal's result first, Arsenal Women's next, in any competition.
- Grouped by sport under a grey header; Football is one header with each competition as a small italic label. A league outside England says its country: "Ligue 1 (France)". Scores in gold, winner first.
- Always a line: a prime-time NFL game (Thursday, Sunday, Monday night); a finished Test between Test nations, draw included; a Test in progress on mornings its score moved ("Stumps, Day 3: ..."); F1 pole ("**On pole** · Lando Norris · Brazilian Grand Prix · 1:27.470") below a race win.

**Biggest News** (at most 3, with source links; confirmed news only)
- **Order:** football's best, then the other sports' best, then football's next (or the other sports' second).
- **Football: records and milestones only**, each line starting "Football:": a country's most-capped player, an all-time record for a league or competition, a 100th cap, a great retiring; already reached, never "might". A single club's own winning run or club record is not one. Team news, transfers and managers stay in the Arsenal and Football sections.
- **Other sports** (`kickoff/sportsnews.py`): ESPN's NFL, NBA and F1 news, BBC Sport and The Guardian on F1 and cricket, ESPNcricinfo; the last 72 hours. Code drops live blogs, podcasts, videos, columns, questions, "could", "sources" and anything not done yet ("set to", "poised", "likely"). Claude picks at most two big ones (a star's trade or signing, an IPL trade of a captain or star India international, a driver's seat for next season, a coach, captain or team principal change, a record, a great retiring). Cricket coach and captain news only for India, Australia, England, South Africa, New Zealand and IPL franchises.
- **Every summary** starts with the club, team or person and says plainly what happened, each person with their role; a sacking is "sacked". No rumours, no gossip, no contract renewals; the same story from two outlets once.
- **Told once in 7 days:** football: for a manager the same club and kind is the same story; for a transfer, injury or record also a shared name; a different kind is new (state `news_told`). Other sports: the same sport and two different names in common (state `sportsnews`, "told").

**Major Injuries** (at most 2, Arsenal first): listed clubs' key players out or suspended, as the name a fan knows and the status once: "Igor Thiago (BRE): suspended until 5 Dec". A player Arsenal took off injured is the first line: "David Raya (ARS): came off injured v Newcastle United".

**Stars Of The Night**
- Individual performances on one 0-100 scale, at least 70: up to three, at most two from one sport and two from one match (its best, then the best of the other discipline, else its next best). Milestones always make it, up to five in all: a century, a five-for, ten wickets in a Test, a T20 fast fifty, a world record, an NBA 40-point game or triple-double.
- A Test batter is judged by that day's runs (30 + 0.9 a run); a hundred made that day is a star night.
- A night by a player of D's five NBA teams ranks 8 higher.
- Bowling hauls by format (`events.HAUL_RUNS`), scored like a century: five wickets = 100 everywhere; six = 150 in a T20, 125 in an ODI, 115 in a Test; seven = 200, 150, 130; eight or more = 250, 200, 150.

**The Telegram ping:** the date, three headlines (an F1 race win or Slam final first, then the key scores, the Stars, then the best game, so it is never empty), a "Today:" block of up to three items on a quiet morning, any ⚠ health lines, and the link.

## 6. On Today and In The Week Ahead

(`kickoff/ontoday.py`, `fixtures.py`)

- **On Today:** from now until the next edition. **While You're Up** (7am to 11pm), then **Overnight** (11pm to 7am). At most 12 lines, the highest scores, in time order; a game under way says "Under way".
- **What is in:** D's teams; every final, knockout and playoff game; a listed club's league game; Champions League nights with a listed club; a plain NBA game only for D's five teams; the NFL's night games and D's two teams; the MLB postseason; every international of the Test-playing nations and the IPL; every F1 session; a Slam's late rounds; UFC main events; badminton finals days and golf starts ("All day"); FA Cup ties with a Premier League club; Arsenal Women's Champions League games; every League Cup tie from the quarter-finals; every game of a world top-20 national side ("Friendly: Brazil v Japan"); each World Chess Championship game.
- **A Test under way** shows its day and start time ("11:30am · Bangladesh v West Indies · 2nd Test · Day 4"), "Under way" only during play, and outranks a listed club's routine league game.
- **★ Don't Miss** opens On Today: up to three of D's teams' games, finals, semi-finals and playoffs, derbies, top-of-the-table clashes (both in their league's top 4), meetings of two of the 17 big clubs, and every F1 qualifying, sprint and race; never a plain NBA or MLB regular-season game. Ranked by score, then the clubs' table places. **A World Chess Championship game always keeps a place.** The same games are marked rust in the time list.
- **In The Week Ahead (Mondays):** the six days after today, by day, at most 12 lines (a sport at most 4; D's teams and finals excepted; the NBA always capped): D's teams (not plain NBA games), knockouts and finals, derbies, top-of-the-table clashes, tracked NBA stars' teams meeting, the NFL's prime-time games, F1 races, a Slam's late rounds, UFC cards, golf and badminton starts, and **only the next chess championship game**. Cricket ahead is found by date.

## 7. Arsenal and Football

(`kickoff/football.py` and its helpers)

- **Arsenal:** the result in every competition, a score line first ("Women's Champions League · Barcelona **1–1** Arsenal"), then a Claude note (four to six sentences; two for Arsenal Women; checked), scorers and assists, form, then **Next up**: three bullets ("Sat 7 Nov, 11pm · Hull City (home) · EPL"). Team news and injuries only when credible and new; no rumours anywhere.
- **Arsenal men's match board** (`kickoff/matchboard.py`, from ESPN's match summary, no Claude), right under the score line:
  1. A two-column stats table, home left and away right: **Goals** first (plain bold white scorer and minute, the assist on the line below, same size, grey, in brackets), then Shots, On target, Possession, Fouls, Offsides, Yellows, Reds.
  2. The **line-ups on an unfilled pitch** (home on top, goalkeeper first; away below, goalkeeper last), names only, in rows by the formation, a grey ↓ after a player taken off; team name and formation (gold) outside the pitch lines, 5px from their own touchline. **Colours only on the pitch's names:** a scorer in the champions' pearl shimmer ("(2)" for two goals), yellow card yellow, red card red, everyone else white; a carded scorer keeps the pearl with a thin underline in the card colour. No colour for assists.
  3. A **Bench** table: every substitute in plain white, each who came on with "(for Raya, 70', injury)" small and grey on its own line.
  No ratings or managers (ESPN does not give them). Arsenal Women keep the result line.
- **Note highlights** (`render.highlight`): in every football note the score and each team's new league position are gold ("from fifth to eighth": only eighth).
- **Leagues:** the Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Süper Lig, then the WSL. Each block: the round-up box (Game week, Games played, Underdogs won, Biggest upset, Best game; by code), the scoreboard (scorers under each side; an asterisk on an underdog winner; **a clear favourite has at least a 45% chance**), Claude's notes (every Premier League game; the listed clubs' games elsewhere), the table, and Top Scorer / Top Assists / Top CS.
- **The 17 listed clubs** (`kickoff/clubs.py`): Arsenal, Man City, Man Utd, Liverpool, Chelsea, Spurs; Bayern, Dortmund, PSG, Juventus, Napoli, Inter, AC Milan, Como, Barcelona, Real Madrid, Atlético.
- **Tables:** in full on Tuesdays and the first time; otherwise only when changed, as "Table (top 6 only)"; Arsenal outside the top 6 get their own gold row under it; other listed clubs outside it in one line ("Other major clubs: TOT 9th (12 pts)"). Unchanged: one muted line, "No new games: ...". Movement against the last table shown.
- **Champions League:** the box, the scoreboard, the 36-team table on league-phase matchdays; knockout ties as two-legged series tables.
- **FA Cup** (`kickoff/facup.py`): a Premier League club played; a Championship club lost to a lower-league club; or a giant-killing of 20 places or more in the top five tiers.
- **League Cup:** every tie from the quarter-finals, its own block after the FA Cup; Arsenal's earlier rounds come from the Arsenal section.
- **International football:** in breaks and tournaments; competitive games of the top 30, Singapore and India; every game of a world top-20 side, friendlies included (state `top30`), labelled with its competition.
- **Nations League:** League A, then B, then C: each league's results, then the tables of only its groups that played (League A always; B or C only with a top-30 side). Under a table one line only when something is decided, proven by code: "**Through:** Spain, England · **Relegated:** Türkiye".
- **Football news:** BBC, Guardian and ESPN only; Claude classifies and writes one checked sentence. **Transfers And Managers** and **Injury News** are separate headings (injuries never under transfers). Premier League key players' injuries from FPL's status, each once.
- **FPL corner:** the morning within 24 hours of a deadline, and once after a gameweek is checked: D's summary box, the Draft league table (team names only), Injuries, Bench Swaps, Underperforming Players, Potential Pick Ups, FPL Watch. One font size throughout; FPL's own names (web_name, "Forwards"); the legend once under each title. No Claude.

## 8. Cricket

(`kickoff/cricket.py`, `sources/espn_cricket.py`)

- **Scope:** every international of the 12 Test-playing nations (men's and women's, all formats); the IPL, BBL, The Hundred, WPL, WBBL and the women's Hundred. An India match always opens the section.
- **Sources, in order:** ESPN's JSON feeds (read for yesterday and today by date), then the Mac's cache, then ESPN's pages. A score with no scorecard is a ⚠ line in the ping.
- **Layout:** "New Zealand v India · 2nd ODI", the result as the big line, the scores (winner's gold), **Player of the match** with figures in gold, the performance that won it first (bowling first when wickets x 20 beat runs), "not available at time of print" when ESPN has not posted it; the full scorecard for big-six, Test and IPL matches; the series table for Tests and ODIs.
- **A Test in progress:** the "Test · in progress" pill and ESPN's own state ("**Stumps, Day 3** · Afghanistan trail by 102 runs"); only innings that moved are shown in full; on the last day the match summary (each innings' total right-aligned in gold, top batter and bowler, then "Match result: ...") and the series table.
- **Standouts** (under their competition, figures gold): a hundred; in a T20 any fifty; five wickets; in a T20 four; in a T20 or ODI three or four at under five an over; ten in a Test match. **A Test's standouts are the day's** (state `test_figs`): a batter with 50 that day and a quarter of the day's runs, a bowler with 3 that day and 40% of the day's wickets, or a milestone reached that day; "· 43 runs today" when the day was only part of it. Milestones (100, 150, 200..., a five-for, ten in a match, a T20 fast fifty) are said once each.
- **Virat Kohli:** his score always appears, small and muted, under his match. He is a standout or Star only on the normal rules.

## 9. F1, Tennis, NFL, NBA, MLB, NHL

**F1** (`kickoff/f1.py`, `f1grid.py`, `sources/jolpica.py`, `sources/openf1.py`)
- Each session finished since the last edition, newest first, under "Race 20/23 · Brazilian Grand Prix, São Paulo"; standings after a race (checked first); a title note when decided.
- **Times:** Jolpica first, OpenF1 fills the gaps; with no times, the order and a short note.
- **Grid penalties:** from the weekend's BBC, Guardian and ESPN reports; when a headline gives no size, code reads the reports' text and one small checked Claude call lists the sizes (a driver only named, like one inheriting pole, is not penalised). A * on each penalised driver, one line per penalty, and a **provisional grid (our calculation)**.
- **Standouts:** Biggest Mover, Big Moment, first wins and podiums, a dominant or first pole.

**Tennis:** the four Grand Slams (seeded players' matches in rounds 1 to 3, every match from the last 16), the ATP and WTA Finals; top-10 withdrawals; Top Seed Out, comebacks from two sets down, provable milestones.

**NFL:** the week's scoreboard (home icon, underdog asterisk, OT), weekly leaders (Lawrence and Rodgers always listed), highlights; on Wednesdays Top Performances, division tables and, from week 14, the playoff picture.

**NBA:** every game finished since the last edition (Lakers, 76ers, Cavaliers, Spurs and Celtics first). Under each game the tracked and key players together, by points (the winner's top scorer from 20, anyone from 25, at most three key players), then absent tracked players as small grey DNP lines. Best game, standouts, standings with movement (top 8 of each conference until a team has played 60 games, then all 15), Cup tables on Cup days, playoff series. **Fridays: League Leaders**, top five per game in points, rebounds, assists, blocks, steals; one table, a gold sub-row per stat, each leader gold.

**MLB:** a Thursday round-up of the Dodgers, Ohtani and Yamamoto in the regular season; daily from the Dodgers' 155th game; series tables in the postseason; a closing note.

**NHL** (`kickoff/nhl.py`, `sources/espn_nhl.py`): **Saturdays, October to June: NHL Leaders**, one table like the NBA's: a gold sub-row per stat, the leader gold, # · player · team · value each centred (14/44/21/21%). Skaters: Goals, Assists, Points; goalies: Goalie wins, Save percentage (.937), Shutouts; top five each, ESPN's qualified players. Its own section after MLB. A stat that fails is left out; all six failing says no data.

**Season rhythm:** an Awards table on mornings something new is announced (NBA, NFL, MLB, Premier League, IPL; All-MLB teams by position, one team from all of baseball); a closing note when a competition is decided; a "season is coming" note a week before the NBA, NFL and Premier League start.

## 10. Young Guns

(`kickoff/youngguns.py`, `young_sports.py`)

- Rookies (NBA, NFL, MLB) and anyone **under 21** on the day, in every sport with a feed, only when notable: NBA 20 points, 12 rebounds, 10 assists, 4 steals or 4 blocks; NFL 250 passing yards or 2 passing TDs, 100 rushing or receiving yards or 2 TDs, 2 sacks or an interception; football a goal or assist (every league and the Champions League); F1 a podium, points, pole or fastest lap; tennis a last-16 win or a win over a seed.
- Up to five lines, each sport under a small label, the stat in gold, full names, written by code: "Darryn Peterson (UTA, rookie, 19): **28 pts**, **7 reb** against Houston Rockets". Notable on three different days: on the watchlist, then 70% of the thresholds.

## 11. Around The Sporting World: Other Sports

(`kickoff/around.py` and its helpers)

Each sport under its own gold heading; a sport with nothing is left out. Structured sources by code first; news lines only from BBC, The Guardian, ESPN, The Straits Times, The Hindu and ChessBase, only for sports with no structured source, as a checked Claude sentence, at most two a sport. **A result is told once in 7 days** (state `around`, "told"); a new result with the same people is new.

- **Rugby:** internationals and World Cups from ESPN, under one competition header each ("Nations Championship"); tables under the results on a morning their games were played (Six Nations, The Rugby Championship, the Nations Championship pools; widths in `rugbytables.COLS`).
- **Golf:** the four men's majors, THE PLAYERS, the five women's majors, Ryder and Solheim Cups: a start note, then the first 25 after each round, D's players below in position order (T40, then MC), full names.
- **UFC:** every UFC event: main event, co-main and the top Prelims bout from UFC.com; the rankings table.
- **Badminton:** the Super 1000s, World Championships, World Tour Finals, Singapore and India Opens, from Wikipedia: a one-line start note; early-round lines for India's and Southeast Asia's players and the top three seeds, grouped by discipline (MS, WS, MD, WD, XD), "Winner def. loser"; every match from the semi-finals in tables.
- **Athletics** (`kickoff/athletics.py`): world records anywhere; at the top meets a world lead or meeting record by the winner and a close finish in a running final (0.03s up to 400m, 0.5s for 800m to 1500m, 1.5s longer); World U20 records.
- **Swimming:** world records (long and short course, relays) and world junior records. At most five lines a morning each for athletics and swimming; a world record is also a Star Of The Night.
- **Field hockey, handball, darts, women's football:** champions of the listed events from Wikipedia.
- **Chess:** decisive games and round-robin winners of the elite events from Lichess, Indian stars' wins, champions from Wikipedia. **World Chess Championship match** (`kickoff/chess_live.py`, Lichess, no Claude), in every edition from the day before game 1 to the morning after the last game:
  - Title "World Championship", a grey line "Geneva · 24 Nov – 12 Dec", a gold score row "Gukesh 2½ – ½ Sindarov".
  - All 14 games in seven centred columns: # · date · Gukesh · (W/B) · score · Sindarov · (W/B). Gukesh always left. # and (W/B) 11px grey; dates, names, scores 14px. Dates "24N", "03D" ("03 Jun" if two months share an initial).
  - Colours from Lichess's own pairing, never guessed. The score from Gukesh's side; a decisive game's winner gold.
  - Played games and the next game bright; every other unplayed game faded. Once the match has begun the next game shows its time (10pm) in gold in the score column.
  - Foot: "First to 7½ · 11 games to play", "Gukesh wins the match", "Level after 14 games: tiebreaks next" or the tiebreak score; tiebreak games are extra rows "TB". Once decided, unplayed games are dropped and the final table shows once.
  - The generic chess lines skip the match, so it is reported once.
- **World Cups:** other sports' World Cups and world championships (alpine skiing, cycling, ice hockey), each line starting with its sport. Never rugby or another sport with its own heading.
- **Never in Other Sports:** a sport covered in its own section (tennis, cricket, F1, NBA, NFL, MLB, NHL, the Premier League).
- **India and Singapore:** a semi-final, final or medal in any covered sport gets a line, even below the usual bar.
- **Multi-sport Games** (`around.GAMES`): while one is on and there is an India or Singapore line, Other Sports opens with it ("Youth Olympic Games · Dakar · Day 9 of 14 · until Fri 13 Nov").

## 12. Design

- **Colours:** pitch #13251E (background), surface #1A2F27, hairline #2A4238, chalk #E8E3D6 (text), muted #A3B0A6, trophy gold #CFB06E, zone blue #8DB4CC, lilac #B3A6CC, rose #C99590, rust #DB6A45 (Don't Miss); the champions' pearl shimmer (`.plat`). Light mode follows the phone, with darker accents.
- **Fonts:** Newsreader for the masthead; Josefin Sans for everything else, body 18px.
- **Progress rail:** a gold rail fills as you read, with a chip showing the percentage and minutes left. A gold icon rides its head, one per section and per Other Sports heading: **21 designs, frozen unless D asks** (football, cannon for Arsenal, cricket ball, basketball, NFL goalposts, baseball, tennis, golf flag, rugby, F1 helmet, chequered flag, UFC glove, badminton, darts, chess king, trophy, clock, star, swimmer, runner, hockey stick and puck). Balls turn as you scroll; the others sway.

## 13. Working rules (Claude Code)

- **Plan first:** for a batch of comments, answer point by point and wait for "go". Make the small calls myself and say what I chose; only ask what really changes the outcome.
- **Gate before every commit:** `.venv/bin/python scripts/run_all_tests.py > /tmp/gate.txt && git commit ...` (never piped), plus a scan of the staged diff for keys (sk-ant, api_key=, token=). Clear the pyc cache first: `rm -rf ~/Library/Caches/com.apple.python/Users/dadiamoghraj/Documents/the-kickoff`.
- **See it myself:** `swift scripts/tools/shot.swift <page.html> /tmp/x.png 360` screenshots a page at 360px in dark mode with Safari's engine (390 for the iPhone). The PNG is 2x: crop with `sips -c <h> <w> --cropOffset <y> 0` and look. Check against section 2 before D sees anything.
- **Demos:** a structural build (a new table or section) gets a demo page with **only the new pieces**, real data forced on today whatever the weekday (e.g. `scripts/demo_chess_nhl.py` → docs/demo/chess-nhl.html). Made-up data only where none can exist yet, and labelled.
- **Test editions:** a rehearsal of a day's edition with newer code is published as `Edition #016-a` (then -b, -c): `.venv/bin/python scripts/preview_today.py --claude --label 016-a --date <day> --state-from <the commit just before that day's real run> --publish` (a few cents; https://dadi-amoghraj-72.github.io/the-kickoff/demo/today-real.html; never the real edition).
- **After every real run:** check it myself, cricket first, and report before D asks: landing time, repeats, new features, cost.
- **Facts:** check our own data (data/, editions) before calling a fact in an edition wrong.
- **Keep this file clean:** after each batch, fold the new rules into their section, drop superseded ones, no dated batch sections, no backstories (they go to SPEC-history.md).

## 14. Open items

1. **Python 3.12 upgrade** (Mac and GitHub): 3.9 is past its end of life.
2. **The Mac cricket job:** review around 8 December; if ESPN's feed on GitHub carried every scorecard, remove it.
3. **Thresholds review** (early December): NBA standouts, Stars Of The Night (bar 70), the Key Overnight Scores caps, the bowling haul table.
4. **Story Of The Day** trial review around 6 December.
5. **First real chess table** in the 25 Nov edition; tiebreak round names on Lichess unknown until 12 December.
6. **Optional:** rename the site to `the-kickoff.github.io` (D undecided).
7. **Not built yet:** a fuller weekly NHL section (tables, playoff picture); darts tournament tables (PDC World Championship, mid-December); a CONMEBOL qualifying table; season-closing notes for the Champions League, FA Cup, F1 and tennis; tournament mode for the Rugby World Cup 2027; the WPL's source; the IPL's live caps outside Wikipedia.
