# C02 reading brief (given verbatim to each reader)

You are reading one packet of blocks from a company's proxy statement (or, for
a few companies, the Part III of an annual report) for metric C02, "Board
composition". Judge the blocks as asked below. Use only the text in the
packet: no outside knowledge of the company, its directors or its later
filings.

**What C02 is.** The owner's decision: C02 takes **composition facts** - the
board's size, the number of independent directors, the committees the board
has, their members, their chairs, and the related independence and
qualification determinations. It does not extend to governance processes in
general or to descriptions of what a committee does.

So a block states a composition fact when, read with the blocks next to it, it
says any of these about the registrant's own board:

- how many directors there are, or will be after the meeting, or how that
  number changes;
- which directors are independent, or how many are, or that all nominees
  but one are;
- which committees the board has, including a committee set up or dissolved
  (with its date);
- who serves on a committee, and who chairs it (a committee page's title,
  its "Chair:" line and the names under it together state this; so does a
  director card's "Committees:" field, and a report's signature "Submitted by
  the Audit Committee: Name (Chair), Name, Name");
- who chairs the board, who is lead or presiding independent director, and
  whether the roles are combined;
- who joins, leaves or does not stand again, and when;
- the board's determinations about a director's qualification or status on a
  committee (independence under the listing standards for a committee,
  "audit committee financial expert", financially literate).

It is not a composition fact: what a committee is responsible for, meeting
counts and attendance, how to communicate with the board, compensation of
directors or officers, voting instructions, a director's biography apart from
the facts above, stock ownership, the text of a policy or charter, and a law
quoted as such ("established in accordance with Section 3(a)(58)(A)"). Two
classes decided on the latest year's readings, stated here so every reader
answers them the same way:

- a card's tenure field - "Director since: 2017", "Joined the Board: 2025" -
  says how long someone has served, not the board's composition: **NOT**
  (a sentence saying someone joined or left, with its date, is a change and
  is a fact);
- a director's name on a card whose committee or independence field is a
  fact is itself part of that fact ("NCG (Chair)" says nothing without whose
  card it is): judge the name **FACT** when you judge the card's field a fact.

**The packet.** Blocks in document order, each with its index `i`, its
`kind` and its text:

- `SELECTED` - a block in the published value;
- `POOL` - a block not in the value that mentions directors, the board,
  committees, independence, chairs, members or nominations, or sits within a
  few blocks of one. Most pool blocks state no composition fact.

**What to answer.**

1. Every `SELECTED` block, one verdict each:
   - `FACT` - it states a composition fact (alone or as part of a structure
     with the blocks next to it: a committee page, a card, a signature, a
     table row);
   - `MIXED` - it states a composition fact among other content;
   - `NOT` - it states none.
2. Every `POOL` block that states a composition fact, and only those, with
   `FACT` or `MIXED`, and in `redundant_with` the index of every other block
   in the packet - selected or pool - that states the same fact (the same
   person on the same committee, the same count, the same chair). An empty
   `redundant_with` says no other block in the packet states it. Leave out
   every pool block that states no composition fact: a pool block you do not
   list is read as "states none".

Write JSON to the path you are given:

```
{"position": "<company>:<report_end>",
 "reader_note": "<two or three sentences: what the value covers and anything notable>",
 "selected": [{"i": 38, "verdict": "FACT", "why": "..."}, ...],
 "facts": [{"i": 276, "verdict": "FACT", "why": "...", "redundant_with": [522]}, ...]}
```

Every `why` names the fact in a few words (who, which committee, what count).
