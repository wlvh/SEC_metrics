# D02 reading brief (given verbatim to each reader)

You are reading packets of blocks from a company's annual report (Form 10-K)
for metric D02, "Litigation disclosures". Judge every block in every list of
each packet. Use only the text in the packet: no outside knowledge of the
company, its litigation or its later filings.

**What D02 is.** The approved definition: "Litigation disclosures. Source:
Item 3 / legal proceedings / contingencies notes." D02 content is text that
discloses the registrant's own legal proceedings, lawsuits, claims,
government investigations or enforcement actions, environmental proceedings,
settlements, or loss contingencies and accruals arising from them. That
includes a short label or case name that says which matter the next paragraph
is about, and Item 3 statements such as "we are not currently party to any
material legal proceedings" or a sentence that incorporates a note by
reference.

Each block has `i` (its index in the document). Each packet has four lists.

1. **taken** - the blocks in the published value, in its order, each with the
   `scope` it came from: `ITEM_3`; a scope starting with `NOTE_` (a note or a
   caption of a note that the filing's Item 3 incorporates by reference); or
   `ITEM_8` (a block elsewhere in the financial statements that a keyword
   brought in). Verdicts:
   - `DISCLOSURE` - D02 content as defined; or substantive text of `ITEM_3`;
     or substantive content of a `NOTE_` scope (the filing chose to
     incorporate that note or caption, so its content counts even where it
     concerns guarantees or commitments).
   - `NOT_DISCLOSURE` - page furniture (a company-name header, a "Notes to
     Consolidated Financial Statements" running head, a "Form 10-K | page"
     footer, a bare page number, a "Table of Contents" link); text of the
     independent auditor's report; or, for `ITEM_8`, text where the legal word
     is incidental rather than a disclosure of the registrant's legal matters
     (collection policy "including litigation", a list of risks or advisers,
     transaction costs, debt covenants, tax, pensions, generic cautionary
     boilerplate).
2. **skipped** - blocks inside Item 3 or a `NOTE_` scope that the value does
   not contain. Verdicts:
   - `CORRECTLY_SKIPPED` - page furniture, a contents link, an empty or
     decorative block, or not D02 content;
   - `COVERED_ELSEWHERE` - D02 content whose matter the value already states:
     give the taken block(s) that state it in `covered_by` (a list of `i`);
   - `WRONGLY_SKIPPED` - D02 content (a label or case name included) whose
     matter the value does not state.
3. **context** - blocks under a heading in Item 8 that names contingencies,
   legal proceedings or litigation, in a note Item 3 does not incorporate, that
   the value does not contain. Judge them as skipped blocks. Most are leases,
   purchase obligations, warranties or tables (`CORRECTLY_SKIPPED`). A
   paragraph describing a lawsuit, claim or investigation that no taken block
   describes is `WRONGLY_SKIPPED`; if a taken block (in Item 3, say)
   describes the same matter, it is `COVERED_ELSEWHERE` with `covered_by`.
4. **headings** - heading-shaped blocks anywhere in the document that name
   contingencies, legal proceedings, litigation or commitments, each with its
   `section`, and the index of and distance to the next taken block after it.
   Verdicts:
   - `REACHED` - it introduces D02 content (the Item 3 heading, a legal
     proceedings or contingencies note or subsection) and that content is
     represented in the value (look at the taken blocks and the context
     after it);
   - `NOT_D02` - outside D02's sources: risk-factor headings (Item 1A), MD&A
     or critical-accounting-estimate headings, statement captions such as
     "Commitments and contingencies (Note 14)", purchase or contractual
     commitments, tax contingencies, business-section headings, the auditor's
     critical audit matters, table-of-contents entries;
   - `MISSED` - it introduces the registrant's legal proceedings or litigation
     contingencies and no taken block represents that content.

**Answer.** For each packet write JSON to the path you are given:

```
{"position": "<company>:<report_end>",
 "reader_note": "<two or three sentences: what the value covers, anything notable>",
 "judgements": [
   {"kind": "TAKEN" | "SKIPPED" | "CONTEXT" | "HEADING", "i": <int>,
    "verdict": "<one of the verdicts for that kind>",
    "why": "<a short phrase>",
    "covered_by": [<int>, ...]}   <- only with COVERED_ELSEWHERE
 ]}
```

Judge every block of every list exactly once; do not copy block texts. A
reading that leaves a block out, judges one twice, or cites as `covered_by` a
block that is not taken is refused by the tool that checks it.
