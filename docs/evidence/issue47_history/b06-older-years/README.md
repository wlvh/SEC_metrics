# Where the historical B06 cascade stops in the older years

`probe.py` asks the historical B06 cascade (`historical_debt_results.resolve_historical_debt_metric`)
for every frame period of the 41-period batch (`../native-run-batch-2026-09-30/plan.tsv`) on
the export-restored root of the final acquisition, with the US GAAP release widening applied,
and records the stage that answered and the stage's own reason (`probe.json`, zero calls).
It answers what the frame batch could not: the batch ran before the extension acquired the
older reports' XBRL instances, so 23 older B06 positions stopped at the source walk
(`HISTORICAL_B06_SOURCE_ROUTE_UNRESOLVED`), and once the instances were present every FY2021
position stopped at the dated US GAAP namespace (`../us-gaap-release/`).

## Result

41 positions, no error. Ten positions answer: six values (Enphase FY2025, Macy's FY2025,
Paramount FY2025, Salesforce FY2025 and FY2026, Southwest FY2024) and four ratios the guard
calls meaningless because equity is not positive (Marriott FY2023-FY2025, Lumen FY2025). The
other 31 are named withholds, each at a stage written for the latest filing's layout:

| Stage reached | Positions | The stage's reason |
|---|---|---|
| Note-carrying grammar | Enphase FY2021-FY2024 | a dimensioned financing fact the grammar does not classify (FY2021 combined discount and issuance costs, FY2022 gross issuance costs, FY2023 a note's current portion, FY2024 the effective interest rate, a `number`-unit fact) |
| Bond grammar | Macy's FY2021-FY2024 | balance-sheet roles the grammar looks for under other labels (FY2021-FY2023), a bond member reported twice (FY2024) |
| Fallback resolver, disclosure note | Lumen FY2021-FY2024, Marriott FY2021-FY2022, Paramount FY2021-FY2023, Pfizer FY2022-FY2024 | `DISCLOSURE_NOTE_MISSING_OR_AMBIGUOUS` for the text block the resolver requires (lease policy, debt disclosure, schedule of debt instruments); Pfizer's latest year stops the same way, a gap shared with #28 |
| Fallback resolver, completeness | Southwest FY2021-FY2023 | a membership sum conflict (FY2021), a matured note's zero row (FY2022), the pension obligation read as a financing item (FY2023) |
| Fallback resolver, industrial scope | Ford FY2021-FY2024 | `B06_INDUSTRIAL_SCOPE_REQUIRES_SEPARATE_PROOF`: the special-scope stage that answers the latest year does not recognise the older layout; the latest year is withheld too, as a special-scope limitation |
| Current input | Paramount FY2024 (predecessor) | the 10-K/A's effect on the debt and equity inputs is not proven |

Every one of these is the program not handling a layout the filing does have, not a filing
that lacks the disclosure: the grammars and the fallback resolver were written on the latest
reports (#28's ordinary route reads only those) and are frozen there.

## The next blocker behind the first

`sibling_concepts.py` asks the fallback resolver again for the five positions
whose first stop is a missing text block that the filing tags under a sibling
concept of the same taxonomy (Marriott FY2021-FY2022 tag their debt note
`LongTermDebtTextBlock`, Paramount's predecessor FY2021-FY2023 their debt
schedule `ScheduleOfDebtTableTextBlock`), accepting the sibling in that one
process (a monkeypatch; the repository is not changed). None reaches a value:
Marriott stops next at `COMPLETE_BALANCE_SHEET_MISSING_OR_AMBIGUOUS` and
Paramount at `DEBT_FACT_MISSING` (`sibling-concepts.txt`). Each layout
difference removed shows the next one, so a repair is a successor fitted to
the older layouts stage by stage, not one alias.

## What this does not decide

- Some of these cannot become values by recognising the layout alone. The note-carrying
  grammar needs the filing's own statement that the company has no finance leases; Enphase's
  FY2024 report carries it, its FY2021-FY2023 reports do not, so those years stay withheld
  until something else in the filing proves the absence. A missing statement is not zero.
- Ford's B06 is withheld in every year by the approved industrial scope (the filing does not
  report the industrial parent's equity); recognising the older layout would change the
  reason, not the answer.
- Repairs are successors to frozen #28 grammars, measured on every saved report before they
  are kept, and are not made here.
