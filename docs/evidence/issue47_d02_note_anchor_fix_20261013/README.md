# D02: numbered subsections cannot establish a note page-header anchor

Responds to [PR240 P2 4255622268](https://github.com/wlvh/SEC_metrics/pull/240#discussion_r4255622268) and [receiver prerequisite 4255803563](https://github.com/wlvh/SEC_metrics/pull/240#discussion_r4255803563). Public #28 confirmed that its saved D02 company consumer opens `d02_page_furniture=True`, so this is a concrete prerequisite of that consumer. The old default remains closed.

The generic note-heading pattern makes `Note` optional. Previously an emphasized `4. Procedural matters` could therefore bypass the actual referenced-note titles and cause three identical substantive legal paragraphs next to consecutive page numbers to be removed. `before.log` reproduces the receiver's scenario as a failure on actual main6efe; it is not dismissed because the layout is uncommon.

The fallback now requires the end boundary of an already located referenced-note range and a heading format supported by the existing source parser; the literal `Note` prefix is optional. The original referenced title and its matching continued caption remain valid anchors. This preserves Ford's closing Note25 boundary without treating arbitrary numbered subsections or an unreferenced Note40 as page furniture. No company/year special case, legal-language classifier, arbitrary caller regex, source edit or response cropping is added.

55 existing/affected tests pass in 0.363 seconds, zero failures/errors/skips. The added method covers both the original numbered subsection and an unreferenced explicit note; all three substantive paragraphs remain. Year columns, repeated product names, page-number and note-caption positives, source/raw-span checks, default V2, D03 and the original H1 4-pass/8-reject/14-overlong-quote contracts remain.

The existing complete Ford FY2025 prepared object was reused to call only the changed helper, 0.039552 seconds: removed exactly 3963/3964/3965/3974/3975/3976/3990/3991; retained all 45 original excerpt fields and unchanged D03. `ford-helper-reuse.json` records this limited execution and the core hash. It does not claim a new full-source parse, candidate/Evidence/model execution, company result or reissued old receipt. Original source preparation/case evidence stays in PR240 and the saved-consumer record.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  tests/required_unittests.py tests.vnext.test_text_business_candidates \
  tests.vnext.test_text_results_v2 tests.vnext.test_legal_review_contract
```

The new method is in the already executed `TextResultV2SourceTest` within the source-material module. Existing script/test triggers remain; no public runner or CI policy change. Published-head remote execution and the receiver's prerequisite recheck remain separate.

Base is actual main6efe, already containing PR240/243/244/238/242. Production diff is only the existing D02 core; tests use the existing module. Public factory/CLI/controller/store/renderer remain #28's responsibility. The public consumer must take this corrected version before opening the option for its company validation. Other D02 semantic failures and the full five-year target remain; new real SEC/provider/model calls 0/0/0, no old Run/answer/failure changes or author merge/Ready/adoption/deployment/active action.

## PR247 prefix-less boundary feedback

[4257796903](https://github.com/wlvh/SEC_metrics/pull/247#discussion_r4257796903) correctly identifies an overrestriction in the first245 fix: the original source parser supports `2. Contingencies` followed by `3. Income Taxes`. The corrected fallback preserves its already located end boundary instead of requiring a literal Note prefix. The original numbered4 subsection/unreferencedNote40 negatives remain. The first fixture accidentally left an original court paragraph between the header run and its closing note; `prefixless-initial-fixture.log` retains that nonisolating setup. The corrected adjacent-boundary fixture fails on33d before the change, then56 related tests pass/.338s/zero skips. `prefixless-before.log` and `prefixless-controls.log` retain these executions. Only the changed helper runs on the same complete Ford prepared object again: unchanged eight removed blocks/45 original fields/D03, see `prefixless-ford-reuse.json`. No full source, candidate, model or company first execution is repeated. Current head changes; public247 must consume the new fixed core and receiver recheck this feedback.
