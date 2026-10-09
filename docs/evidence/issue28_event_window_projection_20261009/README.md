# Approved registered event window through ordinary save and CSV

This is a public renderer correction, not a new event matching policy or a
financial cross-entity combination. Product code: `ordinary_projection.py`.
The base is main `ae8a13c8`; the source interface from PR89 is received locally
for the actual combined source/consumer/save test. Its previously reviewed
source/test bytes remain unchanged. This increment is intended to accompany
that usable source interface, rather than form a permanent parallel renderer.

## Actual error and narrow correction

The fixed historical consumer and supplied sources produced Paramount FY2025
C01=12 count for the existing catalog's 2024-01-01..2025-12-31 registered event
window, while retaining the original annual container 2025-01-01..2025-12-31.
The real writer rejected it at `ORDINARY_PROJECTION_PREPARED_PERIOD_CHANGED`.
Source of original failure: #47 commit `1b69d77d`,
`docs/evidence/issue47_events_receiving_20261009/paramount2025-save.json/.log`.
That initial reference was read, not called a parent execution.

The new path is only for C01/E02/E03/E04/E05 with explicit registered scope.
It derives the window again from the installed projection catalog and the
registered successor policy. It checks selected primary CIK, company/registry,
catalog hash, measurement/result/reporting-year relationships, both per-CIK
source windows, actual inventory references and their source-set windows.
Different financial periods and unreceived E01 are not admitted. The original
annual input is not edited; ordinary/instant and income-statement checks keep
their existing paths. Missing registered scope does not create an exception.
Source completeness/item matching/calculation remain producer duties. This
renderer does not itself discover SEC files or certify non-disclosure.

## Executed validation

`small-before.log` records the absent scope-check helper in the original code;
it is not the real save failure. `small-after.log` contains five small scope
checks. `related-tests.log`: 49 tests passed in 3.244s, zero skips, including
existing real B01 save/read and period/subject/spec/failure guards and update
and per-metric controller tests. No expected values or status strings weakened.

`verify_saved_wide_window.py` reads only the fixed Git version of the historical
producer, uses this owned public runtime and the saved source-only root, and
denies all sockets. It does not modify the historical worktree or source root.
The producer commit/file hash and actual code/data/state roots are recorded in
`saved-wide-window.json`. This is an explicit developer combination, not a
claim that the unmerged historical producer exists in main.

The first driver successfully prepared and saved its full case JSON in an
owned temporary state, then failed because it patched the wrong module name;
see `saved-wide-window-driver-first.log`. The corrected driver reused that
exact case, did not re-extract the financial filing, and changed only the
renderer for the original-code negative comparison. The real writer, source
proof validation, record/spec checks, saving, CSV and independent reader ran
on both sides. Neither a selector nor a calculator was mocked to succeed.

Actual terminal in `saved-wide-window.json/.log`:

- same unchanged case fails with fixed original renderer;
- fixed writer preserves original Result ID/value 12 count and actual window;
- independent read equals the original calculated Result;
- original annual container remains 2025-01-01..2025-12-31;
- 35 event filings / 75 source proofs, direct reading of saved headers verifies
  12 distinct Item 5.02 accessions listed in the JSON;
- save 2.998248s, independent read 0.007770s. Preparation time is null for the
  reused object; no cross-machine speedup or duplicate execution claimed;
- metrics_matrix.csv and metric_evidence.csv exist; source request log unchanged.

This is source/consumer/persistence integration credit only. It does not grant
#28 business acceptance using #47's budget/evaluations, full history or 390
acceptance, E01 content acceptance, new source acquisition or production use.
No new SEC/provider/paid calls; original #28 ledger remains unchanged.
The dedicated company consumer's actual CSV/reentry remains #47 responsibility.
Old Runs/Results and their saved programs are not rewritten.
