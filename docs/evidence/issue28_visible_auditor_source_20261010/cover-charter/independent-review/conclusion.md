# Incremental cover charter-name independent source review

Conclusion: PASS within the assigned incremental source scope; no new actionable finding established. The earlier 22a review remains unchanged and is not re-signed by this report. This conclusion does not grant C04 semantic acceptance, native-fact/Result/publication credit or production adoption.

## Exact scope

Worktree: `/Users/lyuhongwang/.codex/worktrees/issue28-visible-auditor-source/SEC_metrics`. Base `3e418c93f5b50ff09a7b76f231e7b06e2193caba` to patch/observed HEAD `95a089c0baab5d2247d2570344cf4058d6450b2f`. Only actual new delta was inspected: `_cover_charter_name`, the explicit `registrant_binding` selection and corresponding name/output fields in `scripts/vnext/visible_auditor_source.py`; four added test methods/cover fixture in `tests/vnext/test_visible_auditor_source.py`; the corresponding parameter/default/pass-through addition in `check_saved_report.py`; and cover-charter README/JSON/log. Older source behavior was used only as a regression comparison. No raw original corpus or #47 directory was accessed.

## Evidence

- The new mode requires one nonlinked SEC commission heading followed by exactly one matching 10-K/10-K/A form and one exact charter-name label/name pair, before a report/item/part boundary. Report auditee/opinion subject then match that retained cover name. Name/form/commission/label retain original-byte locators; the existing source reader still binds original bytes, filing identity/CIK, document period and form. No `/MD/` removal or incorporation-state inference is added.
- The optional mode is explicit; unknown selections reject. The previous `NATIVE_NAME_ONLY` default returns the complete former object unchanged in independently executed normal, cover-native-alias, missing-report and wrong-year controls, including each `inspection_id`.
- The exact assigned command `PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp python3 tests/required_unittests.py tests.vnext.test_visible_auditor_source tests.vnext.test_text_coverage` exited 0: 29 tests, 0 failures/errors, 0 skips. See `targeted-tests.log`.
- Additional synthetic checks independently reject a rehashed modified cover locator, wrong CIK/source subject, and wrong source period. Cover mode retains separate ICFR and financial report scopes; a financial report without its signature remains UNRESOLVED rather than borrowing the ICFR signature. All three credit flags remain false. See `incremental-checks.log`.
- The saved original/amendment JSON preserve native `MARRIOTT INTERNATIONAL INC /MD/` and explicit cover `MARRIOTT INTERNATIONAL, INC.`. The original has one financial candidate; the amendment retains `TEXT_AMENDMENT_SOURCE_SET_REQUIRED` and an UNRESOLVED overall status. ICFR and financial spans do not overlap; their signatures remain separately located. These are executor-saved original-source evidence, not a new independent raw-source rerun.
- The CLI's added selection defaults to the old mode and passes the explicit value to both inspect/rebuild via the existing arguments object. No source fetching or C04 consumer is added.

## Accounting and boundaries

Incremental tool calls: 6 nodes (3 functions.exec + 3 nested exec_command). Cumulative: 14 nodes (prior 8 + this 6). Ordinary messages this increment: 1 final report; cumulative: 3 (prior 2 + this 1). No opening commentary or question was sent in this increment.

Increment UTC start: `2026-10-10T10:03:44Z`; completion: `2026-10-10T10:05:46Z`. Prior first recorded UTC `2026-10-10T09:51:38Z`, prior completion `2026-10-10T09:53:34Z`; the prior report's initial untimestamped read remains disclosed there. Both increments are within the cumulative tool/time caps; counters were not reset.

No source/test changes, commit/push, network/SEC/provider/paid calls, spawn, archive or large-material tests. Only this cover-charter/independent-review directory was written. Final HEAD is unchanged and working-tree status contains only this untracked review directory. Assigned incremental source diff whitespace check exited 0. The old independent-review evidence was not modified.
