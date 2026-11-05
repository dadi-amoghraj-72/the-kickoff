# The Kickoff: consistency audit (2026-11-05)

D asked for one last pass over every decision, to flag where something that should work the same way across sports works differently. Evidence below comes from the code, the CSS, the saved demos and
the real data; all of it has since been applied (D's answers, 2026-11-05; see SPEC.md round 20). Each item has a recommendation: **FIX** (I would just do it), **YOUR CALL** (changes something D has already approved or is a judgement), **LEAVE** (a
deliberate difference, written down so it stops looking like an accident).

## 1. Results: who is first, which verb, which dash

1. **Who comes first in a result differs by sport.** Football: home first, whoever won ("Lille 2–4 Galatasaray"). NBA, NFL and MLB tables: away first ("Toronto Raptors 125–131 Los Angeles Lakers", the
   loser first). Cricket: batting order. Tennis, badminton, UFC: winner first ("def."). The Big Stuff mixes them in one list ("Lille 2–4 Galatasaray" above "Jacksonville Jaguars 42–7 Indianapolis Colts").
   **FIX the Big Stuff and the Telegram headlines only: winner first for every sport** (they are summary lines). **LEAVE the tables** in each sport's own convention (home/away), which is how fans read them
   and what D approved. **Where it applies:** `kickoff/events.py`.
2. **The verb.** "def." in UFC and badminton; "beat" in NFL highlights and football notes; "beaten by" in tennis notes ("(6) A. de Minaur beaten by (1) C. Alcaraz", the loser first); "won by" in cricket.
   **YOUR CALL:** put the tennis "Top Seed Out" notes in the same winner-first "def." form as badminton? They were approved earlier.
3. **The dash in a score.** En dash in the newer work (badminton, UFC, golf, rugby, the Big Stuff, NBA/MLB table cells) but a hyphen in the tennis notes ("7-5 6-2 6-1"), NBA and NFL "Best game" boxes
   ("BKN 98-90 IND"), NFL highlights ("31-24"), the football season notes ("3-0 after extra time") and old demo headlines. **FIX: one en dash everywhere a score is displayed.**
4. **Winner emphasis.** Gold row for the leader of a ranked table (F1, golf, UFC rankings, IPL, league tables of D's clubs); bold white for the winner of a head-to-head (tennis, badminton, UFC box); cricket
   gives the winner's score gold (D's request). **LEAVE: write the rule down: ranked table, gold leader; head-to-head, bold winner; cricket's gold score is D's own exception.**
5. **Seeds and ranks.** Tennis "(6) A. de Minaur"; badminton "Shi Yuqi (CHN) [1]"; UFC "[#3]" and "[C]"; FPL figures in square brackets; golf "T3". **YOUR CALL:** one rule, square brackets for every
   seed or rank, which would change the tennis notes.

## 2. Names

6. **Initial and surname versus full names.** Initials: F1, tennis tables and notes, NFL, NBA notes, football best performers, **Young Guns** ("M. Liberali (COMO, 19)"). Full names: golf, UFC, badminton,
   the UFC rankings, cricket scorecards. D's reason for full names was "I do not know golfers' names". The same reason applies most to Young Guns, whose players are by definition unknown to him.
   **FIX: full names in Young Guns.** LEAVE the rest (F1 and tennis are names D knows).
7. **Women's labels.** Cricket "IND-W" and "Sydney Sixers W" (D's rule); football "Arsenal Women"; golf, UFC, badminton "Women's ..." (the official name). **LEAVE: official names win; written down.**

## 3. Titles, headings, dates

8. **Table title case.** F1, tennis, NFL: Title Case ("Qualifying Results", "Men's Singles · Third Round"). Golf, UFC, badminton: sentence case ("Main event", "Men's singles · Semi-finals", "Masters
   Tournament · After round 2"). D's rule is every word capitalised. **FIX: Title Case for the new table titles** ("Main Event", "Co-Main Event", "Prelims · Top Bout", "After Round 2"); official names such
   as "Round of 32" keep their official form.
9. **Heading depth.** League blocks use h3, NFL and NBA parts h4, the new sports a "subhead" paragraph plus the table's own title row. h4 and the subhead look identical on screen, so this is only a
   markup difference. **LEAVE.**
10. **Round names.** Tennis "First Round ... Fourth Round" (the Grand Slams' own names), badminton "Round of 32" (the BWF's), NFL and NBA their own playoff names. **LEAVE: official name per sport,
    as D said.**
11. **Date format.** "Sun 17 Nov" (UFC, MLB), "Thursday 10 April" (golf start note), "Tuesday 11 March" (badminton notice), "2 Nov" (NBA), "Sat 8:30am" (On Today). **FIX: the short weekday form
    "Thu 10 Apr" in the golf and badminton notices.**
12. **Time zone.** SGT in On Today, the UFC header, tennis dates, MLB series; US time, labelled, in the golf start note and the NBA header; **local dates, unlabelled, in the badminton notice.**
    **FIX: label the badminton notice ("local dates").** YOUR CALL whether event-start notices should be converted to SGT (a Masters Thursday is a Thursday night in Singapore).

## 4. Logic that should be the same

13. **How far back a result is still news.** Feeds 36 h, rugby 39 h, UFC 40 h, golf and the majors 3 days, badminton end + 2 days, NBA 60 h, MLB 36 h, NFL and F1 6 days, tennis 3 days. If a
    run is skipped (the watchdog covers a failed 7:15 run, not a day when one source was down) UFC, rugby and feed items older than about 40 h are lost, while NFL and F1 catch up. Every one of these also
    remembers what it has shown, so a longer window cannot repeat anything. **FIX: three days for UFC, rugby and the chess results.**
14. **"Shown once" is built eight different ways** (reported-id lists, seen links, done events, round counters, a month key). They behave alike. **LEAVE.**
15. **What happens with no Claude.** Football notes: plain note. Manager news: only a headline that says a manager was sacked, left or appointed. Overviews: plain. Previews: nothing. Young Guns: the plain
    line. The Around feed lines and the Interesting Stories: nothing. **LEAVE (the right policy differs by feature) and the table is now in this file.**
16. **Claude's cost is not all counted.** Only the football run's calls go into the monthly budget guard. The season previews, Young Guns phrasing, the Around feed sorting and the Interesting Stories
    are measured (`claude_usage`, `preview_cost`) but never added to `costs`, so the $10 guard cannot see them. **FIX before go-live: add every Claude call to the month's cost.**

## 5. What each sport gets in the top sections

17. **The Big Stuff covers sports unevenly.** Golf winners yes; F1 and Slam quarter-finals on yes; cricket yes (Kohli and India); UFC no (not even a title fight); badminton no (not even an Indian or
    Southeast Asian title); rugby no; chess no. **YOUR CALL: add a line for a UFC title fight and for a Super 1000 / India Open / Singapore Open title (and an Indian or Southeast Asian finalist).**
18. **On Today and Games to Watch.** They know football, NBA, NFL, MLB, cricket, F1, tennis Slams and the golf majors' starts. They do not know UFC cards, the badminton events or rugby internationals.
    **YOUR CALL: add UFC numbered events and Fight Night main events, and the badminton events' starts, to Games to Watch.**
19. **Spotlight.** SPEC still says "keep the spotlight rule" for the whole section and for Young Guns. What exists: badminton (Singapore, India, the others first) and the chess stars; the feed
    spotlight was removed on D's say-so. **FIX: update the spec so it says exactly that.** Also stale: the UFC row ("numbered events only, main and co-main only, ranked fighters only") and the older
    source table. **FIX (words only).**

## 6. Tables

20. **First column left padding.** The compact style gives every cell 3px. It is fixed (12px) for golf, the UFC rankings, the awards and the NFL divisions. Other compact tables (F1, NBA, MLB, IPL caps) have
    a numeric first column, right-aligned, so no number is flush against the edge on screen (checked on the F1 qualifying table). **LEAVE, with the rule: a left-aligned first column gets 12px.**
21. **D's favourites.** Golf: muted italic rows under the table; NFL: Lawrence and Rodgers always in the table, normal; NBA: tracked players in the notes; cricket: Kohli first in the standouts; leagues:
    gold row for Arsenal and Sunrisers. Each fits its table. **LEAVE.**
22. **A source quirk.** The F1 qualifying demo shows two drivers at P8 (Lindblad and Lawson) with the times out of order. That is how the source lists them; we print what it gives. **LEAVE.**

## 7. Not yet proven on live data

23. Golf mid-event behaviour and withdrawals; the women's majors (no hole detail on the LPGA board); the Lichess elite-chess paths; Wikipedia's lag after a final; the Singapore Open and India Open months;
    UFC.com changing its page layout; the UFC fallback when UFC.com is down; the Early Prelims and scorecards (not built). They are tested on real saved data, never on a live event. **LEAVE, and watch the
    first real events.**
24. Chess (D's edits pending), darts, field hockey, handball, athletics, the multi-sport games and women's football are thin by D's decision. **LEAVE.**
