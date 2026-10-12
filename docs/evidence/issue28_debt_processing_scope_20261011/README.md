# Current deterministic tasks do not consume the B06-only debt grammar

Actual main e24a5271 keeps an old whole-batch rule-path list in each ordinary task configuration. Existing pure zero-AI producers (the installed22 metric set, not B06) do not call the current B06 note/bond/inclusive/financing grammars. Changing only `b06_note_carrying.py` nevertheless changes B01/B02/B03 configurations. `before.log` records the actual three failing configuration comparisons. This is a repeat-calculation dependency defect, not a financial amount defect.

The call chain was read: `ordinary_saved_result._ordinary_case` → `normal_run_inputs.prepare_ordinary_zero_ai_run_input` → the selected zero-AI/CompanyFacts/accession producer. Their source/formula functions do not use these debt grammars. In contrast `current_b06_case` owns the existing explicit PROCESSING_FILES and dispatches note/bond/inclusive/debt guards. The installed zero-AI MetricSpec set does not includeB06. No allrepo/import graph platform is introduced.

The patch removes one explicit B06-only family (20 existing module/config/Spec paths) from this known zero-AI producer's inherited comparison list. Shared annual selection, amendment admission, period/fiscal labels, subject/traits, sources, units, calculators and current writer/controller bytes remain. B06 still includes all20 through its existing configuration; their changes continue to require B06 processing. Historical/explicit consumers may declare actual processing_files separately; this patch does not erase those declarations, alter any business selector, modify frozen Specs or rewrite old configurations.

Two directed tests verify B01/B02/B03 remain unchanged after a note-only version change, and all20 family paths remain effective on B06 while absent from B01/B03/B07. Existing consumed annual/financial rules and explicit producer/dependency change tests remain. Final111 tests9.592s, zero errors/failures/skips, covering current update/B06/company/registry/D04-scope/selected-history state (`final-controls.log`). These are not all390business checks.

Formal company CLI on actual verified Marriott FY2025 saved originals:

```sh
python3 tools/vnext_company.py run --company marriott_international --source-root VERIFIED_SOURCE --metric B01 --work-dir EMPTY_STATE --output-dir OUTPUT
python3 tools/vnext_company.py results --company marriott_international --state-root EMPTY_STATE --output-root INDEPENDENT_OUTPUT
```

`verify_company.py` creates a genuinely new task and runs real source preparation/Calculator/save/CSV.2.701s: revenue26,186,000,000USD, full2025period, original e279b28d Result identity. A simulated SHA change only at the debt-note grammar then uses factory/writer-forbidden repeat.180s: NO_SOURCE_CONTENT_CHANGE, same Result files. Independent subprocess reading.437s leaves state unchanged. Registry/requestlog/actualmanifest hashes are unchanged; sockets prohibited,0newSEC/provider/paid. The hash substitution tests the dependency change, not a synthetic financial answer; the value is checked only after actual production. No oldCSV is supplied as input.

This patch and PR171's D04 controller changes apply without conflict in a separate detached verification checkout. Their union's update/D04/parsed/B0683 tests1.116s zero skips (`d04-union-controls.log`); PR171 source changes are not included in this candidate and its actual company chain is reused, not rerun. The union code/tree is an uncommitted test assembly, not claimed an already reviewed or main tree. No receiver branch or peer workspace is altered.

`tested-tree.json` records actual standalone working-tree production/test hashes before commit; those must match published commit. The main runtime update file changes, so saved tasks may normally reprocess once on installation; this fix stops future B06-only edits from repeatedly recalculating unrelated zero-AI metrics. No special compatibility bridge re-signs or bypasses old results. Main-based independent candidate; does not expand reviewing171, current debt policy or history core. No new call/merge/Ready/adoption/deployment/active permission.
