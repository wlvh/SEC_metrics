# Independent review: registered native ordinary update patch

**Result: no blocking finding in this bounded difference review.** Reviewed patch SHA256 `e6dc1881b834185cd28106617fff93fda30532f39a2ac42e93c2e4a062bed499`. Exact 10 module identities are in `report.json`. The reviewer did not implement this patch, apply it to the main runtime, change a fixed ledger or source root, or send any provider/SEC request. This is a new, explicitly assigned engineering review; it does not replace the restricted 6e5 D03 review, approve the full PR, or authorize production.

## Independently executed

- Five new methods plus three existing mixed-request methods: 8/8 PASS, 9.931 seconds. The first four-method run is retained separately (7 total methods, 9.902 seconds).
- Four additional real factory/root-guard attacks PASS: arbitrary LIVE source root, wrong LIVE ledger root, recorded ledger using fixed LIVE source root, and JSON masquerading as a ledger. Authority setup is doubled; all rejected before source construction.
- Author's eight short regression methods: 8/8 PASS, 0.050 seconds; includes original36 configuration shape, native descriptor identity, current runtime routing and strict defined-absence checks.

The actual saved Enphase source packet matches the original ledger artifact hash. A provenance-only request-attempt change passes source equivalence. Eleven rehashed variants fail: omitted unit/document/proof, duplicate proof, changed source URL/body, changed source-unit content, false completeness, changed request format, output contract and annual period. This exercises real source/request reconstruction on the original complete packet; it is not a new source acquisition or real model result.

The schema2 probe uses the existing synthetic complete-source factory, genuine current native acceptance/Evidence and acceptance receipt validation. It verifies original source/request/response rows are preserved and rejects rehashed snapshot, mode, new request ID, old FAILED terminal, omitted summary, changed response, schema1 with a snapshot, and forged export. Forcing the current acceptor to reject still prevents loading; the loader cannot skip that check. Private journal location and archived-runtime response reading are isolated doubles, declared in the probe source.

The selector probe preserves the exact original successful request, leaves FAILED attempts without success credit, rejects duplicate successful versions, and rejects a changed request carrying its old ID. A separate orchestration probe supplies two equivalent complete original sets and proves no arbitrary winner is registered; only FAILED rows likewise cannot register. That orchestration probe doubles successful collection to isolate the ambiguity guard; it is not full receipt replay.

## Code-path conclusions and remaining validation

The LIVE path retains factory-owned ledger and fixed-root checks. Runtime policy/Requirement comes from the current code root during current preparation and the installed runtime during historical package replay; source JSON does not select it. Schema1 defaults remain on their existing path; schema2 records its original source packet and rechecks current full-source equivalence, original receipts and the current acceptor. Replay-only objects cannot execute. Ordinary update descriptors include registered input/mode/contract identity, and successful defined absence still passes the existing specialized projector.

The previously recorded 388.073-second six-request re-registration material was read and interpreted only within its stated isolated unbound scope; this reviewer did not rerun it. Applying/rebinding the patch and executing the complete native normal-update lifecycle (including samebody new-attempt repeat, failure preservation, recovery and history reading) remain required. New substantive input without a complete original successful set still needs new authorized execution through the existing request path; this patch does not automatically create model success or complete Issue28.
