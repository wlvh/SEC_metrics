# Older-year C02 values read in both directions (in progress)

The 27 older-year C02 values of the frame (21 in the 41-period batch, closure
`ed360ebc`; 6 in the third targeted round, closure `8530710b`) had never been
read. The selection rules (`scripts/vnext/historical_board_composition.py`) were
written on the latest year's ten proxies and checked on the same ten
(`../c02-composition-facts/`), so these are the first material the rules were
not written on.

## How they are read

`tools/read_c02_composition.py --packet` builds each position's packet from the
saved governance document through the route's own selection: every selected
block, and a pool of every block using the owner's words for composition facts
with every short block within sixteen blocks of one. The pool rule was chosen
on the latest-year readings because, with the selection, it holds every fact
block their readers found (`pool_rule.py`, `pool-rule.json`). One fresh-context
reader per position (a subagent of the same model family, not a person) gets
`reader-brief.md` verbatim and the packet, judges every selected block and lists
every pool block that states a composition fact with the blocks that state the
same fact (`reader-prompts.md`). `--merge` turns an answer into a reading in
`judgements/` and refuses one that leaves a selected block unjudged, judges one
twice, or lists a block outside the pool.

## Where it stands

All 27 are read (`judgements/`). Compared with the selection the current code
makes from the saved filings (`comparison.json`, 2026-10-01, by
`tools/read_c02_composition.py --readings-dir c02-older-years/judgements` on the
final acquisition's restored root), **26 disagree and one agrees**: 49 blocks
taken that state no composition fact and 256 fact blocks no taken block states;
Pfizer FY2024's reading agrees with its selection. An earlier version of this
paragraph said every position disagrees - it was written from the readers'
answers before the comparison was run, and the comparison does not bear it out
for Pfizer FY2024. The 26 coordinates are withdrawn in
`../known_result_defects.json` (`C02_*_OLDER_YEAR_READING_DISAGREES`); Pfizer
FY2024 is not accepted either, since a reading's agreement is not yet an
acceptance against the Run's result. The classes seen:

- taken but not composition facts: a classified board's slate count and the
  election agenda items carrying it (Enphase), class headings of the summary
  table, director-compensation policy lead-ins, other companies' boards on a
  director card or in a biography, management committees, a lead-director
  selection criterion;
- facts not taken: card committee fields printed without a "Committees:" label
  or with "(Chair)", chair markers in table footnotes, committee pages whose
  member list follows a long duties list or is printed as a matrix (Ford
  FY2022), lead independent director and chairman sentences, dated joins and
  departures in biographies and compensation footnotes, committees renamed or
  set up, per-director independence labels.

Readers also split on some classes - the slate count above (the latest Enphase
reader judged it a fact), bare rosters of nominees, "<role> since:" fields,
a card's "Committees: N/A" - which are to be decided by rule and applied to
every reading of the class, the latest years' included (as
`../c02-composition-facts/adjudicate.py` does for two classes).

Three readers were stopped by the API session limit and resumed from where they
stopped (Pfizer FY2023, FY2024, Salesforce FY2025). Two of them each wrote a helper
script under the same scratch name at about the same time, so for a while one
reader's script printed the other's packet; both noticed and printed inline from
then on. `answer_crosscheck.py` checks every answer against that: the distinctive
words of each `why` are looked up in the block (with two neighbours) of the
answer's own packet and, at the same index, of every other packet
(`answer-crosscheck.txt`). Of Salesforce FY2025's 107 entries 80 match their own
block and two match another packet better, both on a bare number ("12", "2025");
Pfizer FY2024 has 110 of 159 and two numbers or common names. Neither answer reads
like another packet's blocks. The check is a heuristic: a `why` that names
nothing distinctive is not tested by it.

No older-year C02 value is accepted, and none was before. The class decisions
and the general selector repairs follow; a repair written on these 27 readings
has no held-out material left and is labelled so.
