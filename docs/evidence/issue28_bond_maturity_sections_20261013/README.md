# Bond maturity-section source relation on the public company path

This increment consumes the existing historical implementation at bcc0c0bc and the actual receiving failure at [06289308](https://github.com/wlvh/SEC_metrics/blob/062893081694c1b3b9fa7644216081443380f6c5/docs/evidence/issue47_b06_bond_section_receiving_20261013/README.md). It extracts the section/native relationship into the existing shared b06_bond_leases module; no dynamic wrappers, installer, historical engine or new debt definition is imported. The public owner implements once and history consumes it.

## Behavior and scope

An instrument label remains unique within each maturity section. When a label occurs in both sections, native matching also binds current/noncurrent concept, actual row, complete decoded schedule geometry, current column, unit, original entity/context/dimensions and amount. Both zero and nonzero occurrences are retained; cross-file precision and row-set checks remain. Globally unique labels follow the same output representation: a complete synthetic proof hash captured from actual main31 before the patch is unchanged afterward. No company/CIK/year-specific production branch was added.

The old implementation fails the reused ten section regression cases at the global duplicate check (before.log); the new implementation passes all ten, including positive/zero classes, same-section duplicates, equal amounts in the wrong class, mismatched XML, unrelated tables, changed context and changed cell span. The 48 related public/history/source-form tests pass in0.073s, zero skips (related-controls.log). The fast selector is appended once and the required public B06 CI step explicitly runs it. Workflow parses normally; functions/timeouts and other selectors are not changed.

## Actual full saved sources and company entry

verify_saved_sections.py resolves the existing fiscal year, reads both complete primary/XML originals and runs the actual shared source functions with the selected namespace configuration and network prohibited. It reconciles21 native members, preserving the same bond at current6,000,000USD and noncurrent0USD. Source inspection completed in5.900s; actual-sections.json retains the schedule, all21 members and original source references. The first evidence serialization failed on a floating-point elapsed time after the source assertions; that diagnostic is retained in actual-sections.log. Only evidence timing serialization was repaired; no financial operand was changed.

company_consumer.py invokes the formal tools/vnext_company.py CLI on a new external state root using the already saved originals, Macys FY2024 (2024-02-04..2025-02-01), B06 instant2025-02-01. First processing7.774s: CANDIDATE_WITHHELD/null; input-assessment now reaches BOND_LEASE_STANDBY_CAPACITY_NATURE_UNPROVEN. The previous BOND_MEMBER_DUPLICATED rejection is gone, but financing completeness is still unproved. The Result4bdb9b retains the same withholding semantics; the new attempt's input assessment records the current failure. This is not a new accepted B06 numerical result.

Stable withheld reuse is tested with both factories and both numeric Calculator entries made to raise if invoked, without changing their module/name/source-file metadata. Repeat0.135s returns PREVIOUS_INPUT_WITHHELD, raw_input_unchanged=true, calculation_performed=false and new_candidate_created=false; all7 saved result files are preserved. Independent results subprocess0.121s emits CSV/evidence and preserves all23 state files at that boundary. The real source relationship and the company/controller seam are both exercised; none of the parsing, calculation, saving or reading is mocked as successful.

The initial repeat harness used MagicMock for the producer, which made inspect.getsourcefile reject configuration before reuse; that is not a passing no-recalculation check. Its output/log are retained with invalid-sentinel filenames. Later harness checks corrected cleanup and the expected stable-withheld status; those diagnostics are also retained. The original first processing was not repeated, old completed state and result files stayed intact. Only the final verified repeat/read count as reuse evidence.

## Reproduction and boundaries

```sh
python3 docs/evidence/issue28_bond_maturity_sections_20261013/verify_saved_sections.py --source-root /absolute/saved/source-inputs --output /absolute/new-section-proof.json
python3 docs/evidence/issue28_bond_maturity_sections_20261013/company_consumer.py --source-root /absolute/saved/source-inputs --work-root /absolute/new-company-state --evidence /absolute/new-evidence
PYTHONPATH=scripts python3 tests/required_unittests.py tests.vnext.test_bond_maturity_sections tests.vnext.test_current_b06_case tests.vnext.test_historical_b06_case tests.vnext.test_b06_note_source_forms
```

Actual tested base is main31e4a00d plus the uncommitted production/test changes recorded in tested-worktree.json, not a claimed future committed SHA. The full material and company checks were run by public #28; the original receiving failure and older18-material evidence were read from #47, not rerun or credited as new execution. Source root is read-only. No new acquisition/model call, ledger mutation, result upgrade, Ready/merge/adoption/deployment/active operation occurred. The standby/unused capacity and accrued-interest/full financing relations remain responsibilities after this bounded fix.
