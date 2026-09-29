# Fiscal-year labels: two definition forms older annual reports use

## The finding

Every metric of a pinned period starts from the annual input, and the input's
fiscal-year label comes from the issuer's own definition in the filing
(`ordinary_fiscal_year_labels_v1`). Macy's FY2022 and FY2021 annual reports,
which the acquisition saved, stopped there:
`ORDINARY_FISCAL_LABEL_UNRESOLVED:EXPLICIT_DEFINITION_UNRESOLVED`, so every
metric of both periods failed before its route ran (the D01 and B03
measurements of 2026-09-29 each recorded the two failures).

The frozen scan (`fiscal_year_labels._definitions`, bound by Issue #28's
generations) reads three sentence forms. When a sentence that looks like a
definition mentions the period's end year but is none of them, the period
stops - the right answer for a definition it cannot read. The two filings use
two forms it does not read:

- FY2022 (`m-20230128.htm`), in the notes: "Fiscal years 2022, 2021 and 2020
  ended on January 28, 2023, January 29, 2022 and January 30, 2021,
  respectively, and included 52 weeks." The frozen ordered form requires the
  sentence to end at "respectively.". The filing's other definition, the
  reference sentence at the front, parses and gives 2022.
- FY2021 (`m-10k_20220129.htm`): the same notes sentence, and a reference
  sentence that defines "Macy's" or the "Company" while the DEI registrant
  name is "Macy's, Inc.". The frozen alias proof requires the registrant's
  name as DEI states it.

Nothing either sentence says is outside what the frozen forms say: the first
maps the same labels to the same end dates and adds how many weeks the years
had; the second names the same registrant without its legal form. DEI and
Company Facts agree with both (2022 and 2021). This is a reader that cannot
read the filing, not a filing that does not say.

## The repair

`scripts/vnext/historical_fiscal_labels.py` reads again only a period the
frozen inspection leaves unresolved, with the frozen scan's own code object
and two of its recognizers widened:

- the ordered form may end "respectively, and included 52 weeks." or "... 53
  weeks." as well as "respectively.";
- the reference form's alias may be a registrant name with trailing
  legal-form words removed (Inc., Corporation, Co., Ltd., LLC, plc, ...), as
  well as the name itself.

The frozen definitions must come back unchanged and the frozen unparsed leads
must shrink, or the period is refused by name; the label is then decided by
the frozen rule. Every period the frozen scan resolved keeps the frozen
inspection itself, so its input identity does not move. A sentence neither
form covers still stops the period, as does a widened reading that yields a
second label or leaves another current-year lead unread.

## Verification

- `tests/vnext/test_historical_fiscal_labels.py`: the two saved Macy's
  reports, read from the export's own archives (checked against the index's
  digests), resolve to 2022 and 2021 with the added definitions' spans
  returning to the original bytes; the frozen rule is reproduced before
  widening; bytes other than the inspected ones are refused; constructed
  documents run through the frozen scan show a resolved period is never read
  again, another trailing clause or an alias naming another entity still
  stops the period, a second label stops it, and a widened scan that changes a
  frozen definition or leaves a new lead is refused.
- `measure_fiscal_labels.py` over the root restored from the export at 288
  captures, every saved annual report frozen and widened (`measured.json`, 2.5
  hours, zero calls): 45 periods measured - nine companies, five each; JPMorgan's
  five originals are not saved there. Exactly two move, Macy's FY2022 and
  FY2021, from `EXPLICIT_DEFINITION_UNRESOLVED` to `SOURCE_LABELS_CONSISTENT`
  with labels 2022 and 2021 (FY2022 through the ordered form alone; FY2021
  through both forms), each leaving no unread lead. The other 43 come back as
  the frozen inspection itself, inspection ID and all: 35
  `METADATA_LABEL_ONLY`, 7 `SOURCE_LABELS_CONSISTENT`, 1
  `SOURCE_LABEL_CONFLICT` (Salesforce FY2026, as before).
- `injections.py`: 10 injections, each part of the repair undone, each caught
  by the case written for it (`injections.json`, run in a clone of the branch
  holding the same files).

Zero SEC or provider calls.
