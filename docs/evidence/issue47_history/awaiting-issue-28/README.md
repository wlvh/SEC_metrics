# Positions left to Issue #28's adopted result

## What changed

The owner decided that the newest-year D04 positions wait for Issue #28's D04
result to be accepted and adopted, that #47 then references #28's published
result, and that #47 sends no call for them
(`../owner-decisions-2026-09-29/call-application-decisions.json`,
`ITEM_3_LATEST_YEAR_D04`, transcribed by the executor). Until now the coverage
frame reported those ten positions like any other D04 position with no Run:
`ROUTE_IMPLEMENTED_NOT_RUN`, or `ROUTE_IMPLEMENTED_ATTEMPT_FAILED` where a batch
recorded `HISTORICAL_SEMANTIC_ASSESSMENT_NOT_REGISTERED:LIVE`. Both read as
work #47 still has to spend a call on.

`../awaiting_issue_28.json` lists the ten positions, each with the target
filing the decision is about - the filing #28 reviewed with the same request
contract - and the filings its review covers (the 10-K/A beside Paramount's and
Southwest's 10-K). `scripts/vnext/historical_coverage.py` reads it:

- a position with no Run result whose target filing is the listed one is
  `AWAITING_ISSUE_28_ADOPTION`, and the delivery layer's reason says the same;
- a position whose target filing is another one keeps its own status - the
  decision is about a filing, not a metric or a year;
- an attempt a batch recorded stays attached in the detail; it is history;
- a Run result at the position, if one ever stands there, is reported as the
  result it is;
- the frame lists every register entry of the selected companies, matched or
  not, so the register cannot be read as covering positions the frame reports
  otherwise. JPMorgan's is listed and does not match today: its period is not
  established from the saved catalog.

The register must cite a decision the committed decision record holds, may not
list a position twice, and each target filing must be among the filings its
entry lists. It is a statement of what #47 is waiting for, not a claim that
#28 has accepted or adopted anything (it has not; #28 records an
independent-review blocker on its D04 module) or about what any filing
discloses.

## What it moves

Measured on Marriott's three saved years: the 2025 D04 position is
`AWAITING_ISSUE_28_ADOPTION`; 2024 and 2023 stay `ROUTE_IMPLEMENTED_NOT_RUN`,
the earlier years whose calls are #47's own (16 requests measured,
`../model-egress/`). No value, Run or delivery layer changes anywhere.

## Verification

- `tests/vnext/test_historical_coverage.py`,
  `PositionsLeftToIssue28AreCountedApartTest`: 7 cases.
- `injections.py`: five injections, each undoing one part (any target filing
  matches, every metric of the period is covered, the recorded attempt is
  dropped, no recorded decision is needed, a duplicate entry overwrites), each
  caught by the case written for it (`injections.json`).

Zero SEC or provider calls.
