"""Regression cases for the chat bot: python -m evals.run

Each case is a question with a known answer in the data, picked because it
trips models up (scope, units, data-quality traps, history quirks). Fields:

  id         stable name; good answers are keyed by it (good_answers.json)
  q          the question, asked as a fresh chat
  event      the asker's current event (default 2026miwmi; key 4003data, team 4003)
  tags       for --tags filtering
  stress     why it's hard, for the judge
  ref        reference SQL run through live_sql (live.* and history), re-run
             every time so the expected answer follows the data
  expect     the facts a right answer states
  must       regexes (case-insensitive) that must all match the answer
  must_not   regexes that flag a known wrong answer
  judge      how to grade beyond the regexes

The regexes are a smoke check only; a run is graded by reading report.md.
Keep cases about the data, not about wording, so prompt changes that keep
answers right still pass.
"""

OFFICIAL = "e.event_type NOT IN ('Offseason','Preseason','Remote','Festival of Champions')"

CASES = [
    # --- scope: this event vs all history ---
    dict(id='scope_partner_alltime', tags=['scope', 'history'],
         q="Who has been 4003's most frequent alliance partner in playoffs?",
         stress='No event named, so all history. Sonnet once answered for the current event only.',
         ref=[f"""SELECT o.team_number, count(*) n, min(tm.year), max(tm.year)
                  FROM team_matches tm JOIN team_matches o ON o.match_key = tm.match_key
                   AND o.alliance = tm.alliance AND o.team_number <> tm.team_number
                  JOIN events e ON e.event_key = tm.event_key
                  WHERE tm.team_number = 4003 AND tm.comp_level <> 'qm' AND {OFFICIAL}
                  GROUP BY 1 ORDER BY n DESC LIMIT 5"""],
         expect=['3234, 19 playoff matches (2012-2014)', 'then 3098 and 2586 at 15 (2018)'],
         must=[r'\b3234\b'], must_not=[],
         judge='Fail if it answers only for 2026miwmi (74 and 5610).'),
    dict(id='scope_partner_here', tags=['scope', 'live'],
         q='Who did 4003 partner with in playoffs here?',
         stress='"here" = this event; the all-time rule must not swallow it.',
         ref=["""SELECT DISTINCT partners, match_key, won FROM live.team_results
                 WHERE team_number = 4003 AND comp_level <> 'qm' ORDER BY match_key"""],
         expect=['74 (captain) and 5610', 'lost both playoff matches (0-2)'],
         must=[r'\b74\b', r'\b5610\b'], must_not=[r'\b3234\b'],
         judge='Mentioning they were alliance 4 / 4003 was first pick is a plus.'),
    dict(id='scope_h2h_33', tags=['scope', 'history'],
         q='When 4003 and 33 have played on opposite alliances, who won more often?',
         stress='All-time head-to-head; luna scoped it to this event (33 is not here).',
         ref=["""SELECT tm.match_key, tm.result, tm.score, tm.opp_score FROM team_matches tm
                 JOIN team_matches o ON o.match_key = tm.match_key AND o.alliance <> tm.alliance
                  AND o.team_number = 33 WHERE tm.team_number = 4003 ORDER BY 1"""],
         expect=['Even: 2 wins each and 1 tie in 5 meetings (2014-2022)'],
         must=[r'\b2\b'], must_not=[r"(haven't|have not|never) (faced|played)"],
         judge='Must report the even 2-2-1 record.'),
    dict(id='h2h_never_met', tags=['history', 'honesty'],
         q='Has 4003 ever beaten 254?',
         stress='They have never played on opposite alliances; the model must not invent a record.',
         ref=["""SELECT count(*) FROM team_matches tm JOIN team_matches o ON o.match_key = tm.match_key
                 AND o.team_number = 254 WHERE tm.team_number = 4003"""],
         expect=['No official match with both teams (opponents or partners) in any year'],
         must=[r"never|no (official |recorded )?match|haven't|have not|no record"],
         must_not=[r'4003 (won|beat)'],
         judge='Fail on any invented result.'),

    # --- history quirks ---
    dict(id='streak_2021_gap', tags=['history', 'quirk'],
         q='Which team has the longest streak of seasons in a row winning at least one event?',
         stress='2021 had no normal season: 2020 -> 2022 counts as consecutive (schema note). '
                'Luna broke streaks at 2021. Event wins must come from awards (118\'s 2010tx win is stuck '
                'at status playing in team_events); data goes back to 1992.',
         ref=[f"""WITH w AS (SELECT DISTINCT a.team_number, a.year FROM awards a
                   JOIN events e USING (event_key) WHERE a.award_type = 1 AND {OFFICIAL})
                 SELECT team_number, list(year ORDER BY year) FROM w
                 WHERE team_number IN (254, 118, 987, 1678) GROUP BY 1"""],
         expect=['254: 21 seasons, 1999-2019 (no win in 2020)',
                 'Next: 118 with 16 (2010-2026), then 1678 and 987 with 15 (2011-2026)'],
         must=[r'\b254\b', r'\b21\b'],
         must_not=[r'\b118\b[^.\n]{0,40}\blongest'],
         judge='254 with 21 must be the answer. Naming 118/1678/987 as runners-up is a plus.'),
    dict(id='msc_most_wins', tags=['history'],
         q='Which teams have won the Michigan State Championship the most times?',
         stress='Count the top-level FiM district championship, not divisions; luna undercounted.',
         ref=["""SELECT team_number, count(*) n, list(a.year ORDER BY a.year) FROM awards a
                 JOIN events e USING (event_key) WHERE e.event_type = 'District Championship'
                 AND e.district = 'fim' AND a.award_type = 1
                 GROUP BY 1 ORDER BY n DESC LIMIT 5"""],
         expect=['27 (2014, 2016, 2022, 2024, 2026) and 67 (2009, 2011, 2012, 2016, 2025) tied with 5',
                 '469 with 4', '217 and 33 with 3'],
         must=[r'\b27\b', r'\b67\b', r'\b5\b', r'\b469\b'],
         must_not=[r'\b(27|67)\b[^.\n]{0,40}\b4 (wins|titles|times)'],
         judge='Order and counts must match.'),
    dict(id='best_season_2015', tags=['history', 'quirk'],
         q="What was 4003's best qualification record in a single season?",
         stress='2015 quals had no wins/losses; offseason events must be left out.',
         ref=[f"""SELECT te.year, sum(qual_wins) w, sum(qual_losses) l, sum(qual_ties) t
                  FROM team_events te JOIN events e USING (event_key)
                  WHERE te.team_number = 4003 AND {OFFICIAL} GROUP BY 1 ORDER BY 1"""],
         expect=['2018: 39-7 (about 85%)'],
         must=[r'2018', r'\b39\b', r'\b7\b'], must_not=[r'2015[^.\n]{0,30}\d+-\d+'],
         judge='Should note 2015 had no W-L only if it mentions 2015 at all.'),
    dict(id='seasons_competed', tags=['history', 'quirk'],
         q='How many seasons has 4003 competed in?',
         stress='2021 entries are a "Season Participation" placeholder and remote events, and '
                '2020 was cut short; both are traps.',
         ref=[f"""SELECT te.year, sum(coalesce(qual_matches, 0)) quals, list(e.name)
                  FROM team_events te JOIN events e USING (event_key)
                  WHERE te.team_number = 4003 GROUP BY 1 ORDER BY 1"""],
         expect=['14 seasons with matches: 2012-2020 and 2022-2026 (2021 had no real competition)'],
         must=[r'\b14\b'], must_not=[r'\b15 seasons'],
         judge='15 is acceptable only if it says 2021 was remote/participation only. 2020 counts.'),
    dict(id='einstein_never_won', tags=['history', 'quirk'],
         q='Has 4003 ever won the world championship?',
         stress='Division (subdivision) wins are not world titles; 4003 reached Einstein twice.',
         ref=["""SELECT te.event_key, e.name, e.event_type, te.playoff_level, te.playoff_status
                 FROM team_events te JOIN events e USING (event_key) WHERE te.team_number = 4003
                 AND e.event_type IN ('Championship Division', 'Championship Finals') ORDER BY 1"""],
         expect=['No', 'Won Archimedes Division 2018 and Daly Division 2019',
                 'Eliminated on Einstein (Detroit) in 2018 and 2019'],
         must=[r'\bno\b|never|hasn\'t|has not', r'Archimedes', r'Daly'],
         must_not=[r'^\W*yes\b'],
         judge='Must separate division wins from Einstein.'),
    dict(id='chairmans_level', tags=['history', 'quirk'],
         q="How many times has 4003 won the Chairman's or Impact Award?",
         stress='Only a District Chairman\'s Award; must not upgrade it to the Championship award.',
         ref=["""SELECT a.year, a.event_key, a.name FROM awards a WHERE a.team_number = 4003
                 AND (a.award_type = 0 OR a.name ILIKE '%chairman%' OR a.name ILIKE '%impact%')"""],
         expect=['Once: District Chairman\'s Award, 2018 West Michigan district event'],
         must=[r'2018', r'district'], must_not=[r'\b(twice|two times|[2-9] times)\b'],
         judge='Saying it never won the Championship-level award is a plus.'),
    dict(id='epa_norm_seasons', tags=['history', 'units'],
         q='Was 4003 relatively stronger in 2018 or in 2022?',
         stress='Raw EPA is in each game\'s points (211 vs 45); only epa_norm / world rank compare.',
         ref=["""SELECT year, epa, epa_norm, world_rank FROM epa_team_years
                 WHERE team_number = 4003 AND year IN (2018, 2022)"""],
         expect=['2018: epa_norm 1794, world rank 40 vs 2022: 1753, rank 60'],
         must=[r'2018', r'1794|\b40\b'], must_not=[],
         judge='Fail if the conclusion rests on raw EPA (211 vs 45).'),
    dict(id='epa_vs_opr_units', tags=['live', 'history', 'units'],
         q='Which teams here have the biggest gap between their 2025 EPA and their OPR this event?',
         stress='Different games, different point scales; compare ranks or normalized values. '
                'Luna subtracted raw points.',
         ref=["""WITH x AS (SELECT o.team_number, o.totalPoints opr, e.epa,
                   rank() OVER (ORDER BY o.totalPoints DESC) opr_rank,
                   rank() OVER (ORDER BY e.epa DESC) epa_rank
                   FROM live.opr o JOIN epa_team_years e ON e.team_number = o.team_number AND e.year = 2025)
                 SELECT team_number, epa_rank, opr_rank, epa_rank - opr_rank gap FROM x
                 ORDER BY abs(epa_rank - opr_rank) DESC LIMIT 8"""],
         expect=['Rank-based (or normalized): 6753 up ~16 places, 4680 down ~14 to 15'],
         must=[r'rank|normaliz|percentile|z-?score'],
         must_not=[r'\b155(\.\d)?\b|\b137\.9\b|\b98\.4\b'],
         judge='Fail if it subtracts raw 2025 EPA from 2026 OPR. Exact ranks may differ by a place '
               'or two depending on ties and the team set.'),
    dict(id='rank_corr_2025', tags=['live', 'history', 'stats'],
         q='Do teams that ranked well at their 2025 events also rank well here? Give a correlation.',
         stress='Field sizes differ (Worlds divisions ~75 teams); raw ranks mislead. Luna got 0.003.',
         ref=["""WITH p AS (SELECT team_number, avg(qual_rank::DOUBLE / num_teams) pr FROM team_events te
                   JOIN events e USING (event_key) WHERE te.year = 2025
                   AND e.event_type IN ('District', 'Regional') GROUP BY 1)
                 SELECT round(corr(p.pr, r.rank), 3), count(*) FROM p JOIN live.rankings r USING (team_number)"""],
         expect=['Clearly positive, about 0.7 with rank percentiles (0.5 with raw most-recent ranks)'],
         must=[r'0\.[4-8]'], must_not=[r'no (meaningful |real )?(relationship|correlation)'],
         judge='Any method is fine if it normalizes for field size and lands clearly positive.'),

    # --- live data traps ---
    dict(id='hang_works', tags=['live', 'pit'],
         q='Which swerve teams can hang?',
         stress='hanging_works (1/0) answers it; hanging_level is 1 for nearly everyone.',
         ref=["""SELECT team_number, hanging_works, hanging_level FROM live.pit_latest
                 WHERE drive_train ILIKE '%swerve%' AND hanging_works = 1 ORDER BY 1"""],
         expect=['85, 2619, 3458, 3539, 6090, 6114, 6877, 8397 (pit says the hang works, level 1)'],
         must=[r'\b85\b', r'\b2619\b', r'\b3458\b', r'\b3539\b', r'\b6090\b', r'\b6114\b', r'\b6877\b', r'\b8397\b'],
         must_not=[],
         judge='Listing every swerve team as able to hang is a fail. (Until 2026-11-06 pit_latest '
               'picked notes-only robot-note records, which hid 4 of these teams.)'),
    dict(id='hang_conflict', tags=['live', 'pit', 'join'],
         q='Which teams say in pit scouting that their hang works but never climbed in a match we scouted?',
         stress='Pit vs match join; 9721 is tank, so a swerve filter would drop it.',
         ref=["""SELECT p.team_number, p.drive_train, avg(s.endgame_climbed) climb, count(*) n
                 FROM live.pit_latest p JOIN live.scouted s USING (team_number)
                 WHERE p.hanging_works = 1 GROUP BY 1, 2 HAVING max(s.endgame_climbed) = 0"""],
         expect=['85 (10 matches), 6114 (9) and 9721 (12)'],
         must=[r'\b85\b', r'\b6114\b', r'\b9721\b'], must_not=[r'\b3539\b[^.\n]{0,30}never'],
         judge='Auto climbs don\'t count unless it says so.'),
    dict(id='endgame_acc_not_recorded', tags=['live', 'data-quality', 'honesty'],
         q='Who had the best endgame shooting accuracy at this event?',
         stress='endgame_fuel_accuracy is 0 in every record here (not collected), so there is no answer.',
         ref=["""SELECT max(endgame_fuel_accuracy), count(*) FILTER (WHERE endgame_fuel_accuracy > 0),
                 count(*) FROM live.scouted"""],
         expect=['No team: the field is 0 in all 413 records, so it was not recorded here'],
         must=[r"(not|n't|never) (been |really )?(recorded|collected|tracked|scouted|filled)|all (zero|0)|every[^.]{0,60}\b0(\.0)?%?|no (usable |real )?data|0 for every|0% for (all|every)"],
         must_not=[r'\b\d{2}(\.\d)?% endgame'],
         judge='Naming a "best" team is a fail. Offering Jackson (2026mibkn) data is a plus.'),
    dict(id='endgame_acc_other_event', tags=['scope', 'live'],
         q='Who had the best endgame shooting accuracy at the Jackson event?',
         stress='Another event by nickname: find_event, then the event parameter.',
         ref=["""SELECT team_number, round(avg(endgame_fuel_accuracy), 1) a, count(*) n FROM live.scouted
                 GROUP BY 1 ORDER BY a DESC LIMIT 5"""], ref_event='2026mibkn',
         expect=['4003 at 83% (8 records), then 9210 at 80.8%'],
         must=[r'\b4003\b', r'\b83\b'], must_not=[],
         judge='Must be about 2026mibkn (Jackson at Columbia).'),
    dict(id='dup_records_141', tags=['live', 'data-quality'],
         q='How many matches did our scouts cover team 141 in?',
         stress='11 records but 9 distinct matches (one scout entered match 42 three times).',
         ref=["""SELECT count(*) records, count(DISTINCT match_number) matches FROM live.scouted
                 WHERE team_number = 141"""],
         expect=['9 matches (11 records; duplicates in match 42)'],
         must=[r'\b9\b'], must_not=[r'\b11 matches'],
         judge='Mentioning the duplicate records is a plus.'),
    dict(id='scout_most', tags=['live', 'ties'],
         q='Which scout covered the most matches?',
         stress='A five-way tie at 30 records; two of them have 29 distinct matches.',
         ref=["""SELECT scouter_name, count(*) recs, count(DISTINCT match_number) matches FROM live.scouted
                 GROUP BY 1 ORDER BY recs DESC, matches DESC LIMIT 5"""],
         expect=['Tie at 30 records: aiden shearer, Jake Sprague, Tyler Clark, ryland, Caleb Roach',
                 '(ryland and Caleb Roach cover 29 distinct matches, the other three 30)'],
         must=[r'aiden shearer', r'tyler clark', r'jake sprague'], must_not=[],
         judge='Naming one winner is a fail. Either the 5-way tie on records or the 3-way tie on '
               'distinct matches (saying which) is right.'),
    dict(id='scout_disagree', tags=['live', 'stats'],
         q='Which team do our scouts disagree about most on teleop shooting accuracy?',
         stress='Spread within a team (stdev/range), not low accuracy.',
         ref=["""SELECT team_number, round(stddev_samp(teleop_fuel_accuracy), 1) sd,
                 count(teleop_fuel_accuracy) n, min(teleop_fuel_accuracy), max(teleop_fuel_accuracy)
                 FROM live.scouted GROUP BY 1 HAVING n >= 5 ORDER BY sd DESC LIMIT 4"""],
         expect=['5610: stdev about 34, ratings from 0 to 100 over 10 records'],
         must=[r'\b5610\b'], must_not=[],
         judge='Using _vs_other_scouts per team or range is fine if it lands on 5610.'),
    dict(id='finals_dq', tags=['live', 'quirk'],
         q='How did the finals go at this event?',
         stress='Final 2 was 370-0: the blue alliance was disqualified, not shut out.',
         ref=["""SELECT match_key, red_score, blue_score, red_teams, blue_teams, red_dqs, blue_dqs
                 FROM matches WHERE event_key = '2026miwmi' AND comp_level = 'f'"""],
         expect=['Alliance 1 (6090, 3539, 5623) won 2-0', 'F1: 295-220', 'F2: 370-0, blue (1918, 3572, 8397) DQ\'d'],
         must=[r'\b295\b', r'\b370\b', r'disqualif|\bDQ'], must_not=[],
         judge='Calling 370-0 a shutout without the DQ is a fail.'),
    dict(id='alliance_picks', tags=['live', 'history'],
         q='Who picked 4003 in alliance selection here, and who else was on that alliance?',
         stress='alliance_pick lives in history team_events; captain vs picks.',
         ref=["""SELECT team_number, alliance_number, alliance_pick FROM team_events
                 WHERE event_key = '2026miwmi' AND alliance_number = 4 ORDER BY alliance_pick"""],
         expect=['Alliance 4: captain 74 picked 4003 first; 5610 was the second pick'],
         must=[r'\b74\b', r'\b5610\b'], must_not=[],
         judge=''),
    dict(id='winners_unbeaten', tags=['live'],
         q='Did the event winners lose any playoff matches?',
         stress='Double elimination; count every playoff match for alliance 1.',
         ref=["""SELECT match_key, won, alliance_score, opponent_score FROM live.team_results
                 WHERE team_number = 6090 AND comp_level <> 'qm' ORDER BY match_key"""],
         expect=['No: 5-0 (3 bracket matches + 2 finals)'],
         must=[r'\bno\b|undefeated|unbeaten|without (a )?loss|5-0|5–0'], must_not=[r'lost (one|1|a) '],
         judge=''),
    dict(id='margin_quals_playoffs', tags=['live', 'stats'],
         q="What's the average winning margin in quals vs playoffs?",
         stress='team_results has one row per team; dividing by 6 vs 3 trips counts (once said 120 quals).',
         ref=["""SELECT comp_level = 'qm' quals, round(avg(abs(margin)), 1), count(DISTINCT match_key)
                 FROM live.team_results WHERE won <> 0.5 GROUP BY 1"""],
         expect=['Quals about 107.5 over 80 matches; playoffs about 88.1 over 15'],
         must=[r'107\.5|107\b|108\b', r'88(\.1)?\b'], must_not=[r'\b(120|240) (qual|matches)'],
         judge=''),

    # --- other events, cross-event ---
    dict(id='cross_event_4003', tags=['scope', 'live', 'cross-event'],
         q='How did 4003 do here compared with the Jackson event?',
         stress='Two events: the sql tool loads one event per call, so it needs two queries or '
                'team_info per event.',
         ref=["""SELECT 'wmi', round(avg(teleop_volleys), 2), round(avg(teleop_fuel_accuracy), 1), count(*)
                 FROM live.scouted WHERE team_number = 4003""",
              """SELECT te.event_key, te.qual_rank, te.num_teams, te.qual_wins, te.qual_losses
                 FROM team_events te WHERE te.team_number = 4003 AND te.year = 2026"""],
         expect=['Jackson: rank 8 of 37, 8-4, OPR 89.1, 3.5 volleys, 76.5% teleop accuracy',
                 'Here: rank 12 of 40, 7-5, OPR 97.9, 2.0 volleys, 67.8% teleop accuracy',
                 'Mixed: OPR up, rank and scouted shooting down'],
         must=[r'\b8\b', r'\b12\b'], must_not=[],
         judge='Rank and record at both events must be right. OPR or scouted stats are a plus; if '
               'given they must match. A one-sided verdict that ignores OPR going up is a minor.'),
    dict(id='unscouted_event', tags=['scope', 'honesty'],
         q="What were 4003's scouted averages at the Grand Rapids Girls Robotics Competition?",
         stress='An offseason event we did not scout: say so, don\'t borrow another event\'s data.',
         ref=["""SELECT event_key, name, event_type FROM events WHERE event_key = '2026miwyo'""",
              """SELECT count(*) FROM live.scouted"""], ref_event='2026miwyo',
         expect=['No scouting data for 2026miwyo (offseason); official results may be offered'],
         must=[r"no (scouting|scouted)|didn't scout|did not scout|not scouted|no .*records|wasn't scouted"],
         must_not=[r'\b2\.0\b volleys|67\.8'],
         judge='Reporting West Michigan or Jackson numbers as if from this event is a fail.'),
    dict(id='events_2026_4003', tags=['history', 'offseason'],
         q='How many events did 4003 compete at in 2026?',
         stress='2 official plus 2 offseason; the prompt says count official ones unless asked.',
         ref=["""SELECT te.event_key, e.name, e.event_type FROM team_events te JOIN events e USING (event_key)
                 WHERE te.team_number = 4003 AND te.year = 2026"""],
         expect=['2 official (Jackson at Columbia, West Michigan); also 2 offseason (Grand Rapids '
                 'Girls Robotics Competition, West Michigan Robotics Invitational)'],
         must=[r'\b2\b|\btwo\b'], must_not=[r'\b4 (official )?events\b(?![^.]*offseason)'],
         judge='4 is fine only if it separates the 2 offseason events.'),

    # --- live + history ---
    dict(id='teams_never_won', tags=['live', 'history'],
         q='How many teams at this event have never won an official event?',
         stress='Anti-join against history; offseason wins must not count.',
         ref=[f"""SELECT count(*) FROM live.event_teams t WHERE t.team_number NOT IN (
                    SELECT a.team_number FROM awards a JOIN events e USING (event_key)
                    WHERE a.award_type = 1 AND a.team_number IS NOT NULL AND {OFFICIAL})"""],
         expect=['15 of 40'],
         must=[r'\b15\b'], must_not=[],
         judge=''),
    dict(id='oldest_teams_here', tags=['live', 'history'],
         q='Which teams here are the oldest, and how did they do at this event?',
         stress='rookie_year from history joined to live rankings; a tie at 1995.',
         ref=["""SELECT t.team_number, t.nickname, t.rookie_year, r.rank, r.wins, r.losses
                 FROM teams t JOIN live.rankings r USING (team_number) ORDER BY rookie_year LIMIT 4"""],
         expect=['74 and 141 (rookies in 1995): 74 ranked 6th (8-4), 141 ranked 21st (6-6)'],
         must=[r'\b74\b', r'\b141\b', r'1995'], must_not=[],
         judge='Naming 85 (1996) next is a plus, not required.'),
    dict(id='top_2025_here', tags=['live', 'history'],
         q='Which team here had the best 2025 world EPA rank, and where did it finish here?',
         stress='epa_team_years.world_rank (lower is better) joined to live rankings.',
         ref=["""SELECT e.team_number, e.world_rank, r.rank FROM epa_team_years e
                 JOIN live.rankings r USING (team_number) WHERE e.year = 2025 ORDER BY e.world_rank LIMIT 3"""],
         expect=['2054, world rank 95 in 2025; ranked 4th here'],
         must=[r'\b2054\b', r'\b95\b', r'\b4(th)?\b'], must_not=[],
         judge=''),

    # --- honesty ---
    dict(id='not_in_data_cycle_time', tags=['honesty'],
         q="What's 4003's average cycle time?",
         stress='Cycle time is not scouted; the model must not compute a fake one.',
         ref=[], expect=['Not tracked; may offer volleys per match or hub fuel instead'],
         must=[r"not (track|record|collect|scout|measur)|don't (track|have|record|collect)|doesn't (track|record|include)|no cycle"],
         must_not=[r'\d+(\.\d+)? ?(s|sec|seconds) (per|a) cycle'],
         judge='Estimating seconds from match length / volleys is a fail unless clearly labeled as a rough estimate and asked for.'),
]
