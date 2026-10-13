# Additive feature tests no longer share one append point

Receiver6133724712 requested reducing repeated conflicts in `run_fast_tests_v2.py`. This bounded public increment moves only recent additive feature registrations into individual JSON files under `tests/feature_selectors`, consumed by a small loader in the existing runner. No new test platform, controller, scheduling/notification system or recursive scan is introduced. Earlier/frozen runner bytes, timeouts, retirement rules and business tests remain.

Initial base was actual main385. `before-selectors.json` records193 fast selectors/100 source-material selectors and both material shards. `selector-comparison.json` proves exact ordered list/shard equality after moving six features. Files are sorted by name, lists retain order; new features use a later date/number prefix. Duplicate fields/selectors, invalid suite/type, unreadable/missing directory fail visibly. Two independent feature files are actually loaded together by the unit control; their tests do not require editing the same central line.

`before-controls.log` preserves the absent loader reproduction. `final-with-skip-controls.log`:12 registration/current-runner controls0.004s/zero skips. A separate exact regression (`skip-only-before.log`) proves the required in-process runner incorrectly returned0 when every test was skipped. Its return now requires successful execution, a nonempty suite and no skips; diagnostics/reasons remain. The source file contains three existing identical definitions of that function; all three identical return expressions were adapted rather than accidentally changing only the inactive first copy. They were not otherwise refactored. Assertion errors, missing selectors, return124 and source-layer failures retain their previous behavior.

`actual-fast.json/.stderr`: actual current `run_foundation_ci --suite fast --jobs 4`, business keys unset, **272 tests /zero failure,error,skip**. Suite72.282s, whole command74.122s. These are the current foundation entry's75 selectors, not all193 v2 additive selectors or the100 complete-material selectors. Different runner lists are explicitly distinguished. `migrated-feature-controls.log`:63 migrated feature controls2.885s/zero skips. Full originals/financial outputs were not rerun for this registration change. No timing from another branch/machine is combined into a speedup claim.

## Received main integration

During this batch receiver merged the already supplied PR215 combination to actual main `3fec376b5ea737afe3d558c8b5061baa69358819`, tree3706fdf8. Normal merge retains its production changes and adds its income-caption, bond-maturity and standby-note selectors as three separate feature declarations. Only the shared append block conflicted; no ours/theirs resolution discards required content.

`received-main-selector-comparison.json` compares the actual main3fec module with this candidate: **196 fast/100 source**, exact ordered lists and both shards. `received-main-controls.log`:40 registration/runner/newly received producer controls0.082s/zero skips. Original272 in-process fast evidence remains its measured main385 scope; newly received code is covered by the affected40 controls and the receiver's already verified combination. No new main fast execution is retroactively asserted.

The required workflow now explicitly executes `tests.test_selector_registry` beside the existing foundation coverage checks. The test preserves old selectors as an ordered subsequence, allowing real new feature additions without editing a frozen expected list. It still catches deleted/moved existing tests and changed material-shard placement. Actual business assertions and old fixture bytes are not rewritten to produce green status.

## Reproduce and use

```sh
PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py tests.test_selector_registry tests.test_foundation_ci tests.vnext.test_income_section_captions tests.vnext.test_bond_maturity_sections tests.vnext.test_standby_note_relation
PYTHONPATH=scripts:tools:. python3 tools/run_foundation_ci.py --suite fast --jobs 4
```

New additive records are described in `tests/feature_selectors/README.md`. This same convention is available to #47; it does not create a second runner. Pending PR218's E01 registration can be adapted after reception without rerunning its unchanged material. No other candidate is forced to wait for this mechanism.

`tested-worktree.json` records baseline/merge, code root and tested producer/test blobs; final commit/tree/CI are distinct. New provider/paid/SEC0/0/0; no raw source, model answer, ledger or prior Result touched. No author Ready/merge/production operation. This solves the reported finite registration conflict and required-skip error, not390/business/model completion or all future test interactions.
