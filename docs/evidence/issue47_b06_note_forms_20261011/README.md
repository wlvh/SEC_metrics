# Shared B06 note forms: current and selected-year consumer

The four already developed historical note-reading changes are moved directly into the common b06_note_carrying module on main63a340ca. #28 explicitly delegated these functions/tests to the historical executor and does not write this module concurrently. No release_aware wrapper, old historical registry/installer, permission mechanism, debt formula or company/year-specific branch is moved.

The changes classify a standard DebtInstrumentInterestRateEffectivePercentage with a pure unit as a rate, an entire principal-balance statement explicitly dated before the selected year-end as prior, all explicitly non-currency share quantities in options/warrants prose as shares, and the existing Commercial paper asset row under the same asset-table opening with an optional The. All other source, company, period, unit, composition, native inventory, complete note, lease and debt/equity checks remain. The two pure helper bodies match the retained historical implementation; the three inventory insertion sites match its finite substitutions.

29 targeted tests pass in21.359s, zero failure/error/skip: six small real-reader form controls, four complete-source mutations, eight retained source integrity/completeness rejections and eleven current-company seam controls. Source material is prepared once per module and shared by the two classes. The earlier run used the initial duplicate setup and took23.697s for12 material tests; the final version uses shared preparation. This is a modest preparation reduction, not a project-wide speed claim. USD/custom same-name rates, another pure financing fact, missing/historical/quoted/contradicted finance-lease absence, extra borrowing, unknown rows, member mismatch, wrong currency and primary/XML conflict remain rejected.

Committed productdded207e runs the actual current company CLI in a new external Enphase task: first5.054s, unchanged repeat0.736s with the case factory and both calculators forbidden, independent results0.529s. All exit0. The old supported source debt1,204,377,000/equity1,087,023,000 yields1.107959077222837051285943352ratio, original Result2983956c, measured2025-12-31/FY2025. Result/input/current/completed files are unchanged on repeat, and all state files are unchanged on read. The first driver incorrectly guessed a long decimal literal at its last assertion; complete execution logs are preserved, the corrected driver divides the independently known source operands, and saved output was checked offline without repeating first processing.

The already restored selected Enphase FY2024 primary/XML are also processed by this same shared inspector, not the old dynamic wrapper:7.923s including historical source selection. It reconstructs debt1,302,380,000 (current101,291,000 + noncurrent1,201,089,000), equity833,016,000 and explicit current finance-lease absence, matching the retained original-source reference and ratio1.563451362278755750189672227. This is a real complete-source inspector result; historical company case/save/reuse/CSV still requires the public selected-B06 seam and historical consumer. It is not represented as complete historical CLI delivery by this core PR.

This change intentionally allows those finite supported source forms in current and historical consumers of the same reader. The actual latest Enphase result is unchanged. The old historical50-position comparison and reference remain evidence at PR52 docs/evidence/issue47_history/b06-older-years/note-forms; they are not re-executed or claimed as a new50-position acceptance. Earlier years without explicit finance-lease evidence remain unresolved; Macy interest and industrial/bank scope limits remain separate. No source GET, provider call, old result/Run rewrite or formal adoption occurs.

Run the tests on this branch:

```bash
PYTHONPATH=scripts:tools:. python3 -m unittest -v \
  tests.vnext.test_b06_note_source_forms tests.vnext.test_b06_note_source_material \
  tests.vnext.test_current_b06_case
```

The current-company driver uses the committed main source root and new external state. The selected-source probe uses an already restored PR52 source-inputs root; the copyable probe uses the existing committed period/annual/source readers and requires --source-root, so no private WIP module is needed. The recorded run used the byte-identical source-selection steps from the prior local selector. Exact arguments, timings, raw source proof and original driver error are retained here. Public runner/CI integration remains with #28; no second history runner or new source archive is introduced.

CI integration: public#28 assigned both new modules to PR140's company-source worker. ci-note-forms.patch is the finite patch against fixed1408bb0c1de: two path triggers and one mandatory required_unittests step, with required always-gate unchanged. It does not replace the whole workflow or remove main63's newly received B06 step. This core candidate does not claim remote execution of its two modules before that integration. The receiving combination must keep the157 B06 step and the140 worker split.

Copyable consumer checks (outputs must be new):

```bash
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_b06_note_forms_20261011/verify_current_company.py --output-root /new/b06/current-check
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_b06_note_forms_20261011/verify_selected_original.py --source-root /saved/sec/source-inputs --receipt /new/b06/selected-original.json
```

CI followup consumes public fixedadf915bd five-worker layout and its159-only adapter53cb1593. YAML comparison proves exactadf preserved after removing only two test paths and one source-worker mandatory step;157B06/requiredgate/permissions/setup/timeouts remain. Exact required_unittests command locally runs18 new module tests21.466s, zero skips/failures/errors. This replaces the earlier patch-only pending integration statement; actual new-head remote execution still must be read. No financial run is repeated for CI placement.
