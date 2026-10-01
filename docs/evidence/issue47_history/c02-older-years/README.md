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

Read so far (24 of 27), every position disagrees with the selection - blocks taken that
state no composition fact and facts no taken block states. The classes seen:

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

No older-year C02 value is accepted, and none was before. The acceptance pass,
the defects with their causes and the general selector repairs follow the
readings; a repair written on these 27 readings has no held-out material left
and will be labelled so.
