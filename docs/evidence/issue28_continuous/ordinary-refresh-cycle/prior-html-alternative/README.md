# Prior annual HTML dependency: staged implementation

This bounded patch is prepared at `/tmp/sec_metrics_issue28_continuous/optional-prior-html.patch`. Runtime files were **not applied** during real native execution. `git apply --check` passed against the current working files. `runtime-diff-identity.json` identifies the inspected base and staged bytes. The new repository test is `tests/vnext/test_prior_html_dependency.py`.

## Behavior and limits

The existing discovery row retains `saved_status=MISSING_SAVED_SOURCE` and remains in `missing_or_failed_source_urls`. Only a sole `prior_annual_primary` role can gain `alternative_dependency.status=VERIFIED_PRIOR_NATIVE_INSTANCE`. The newly explicit `unresolved_dependency_urls` and the refresh selector use that same dependency decision. Metadata refresh still requires its normal requests.

The proof reuses `_Sources.auditor_filing`, `annual_period`, and the actual C04 auditor fact reader. Every discovered native XML and its accession index must already have a verified saved source; entity, exact full prior year, adjacency to current year, and auditor facts must all pass. Source roles may differ between these existing readers, so comparison excludes only the role and its derived reference ID. Source bytes, entity, URL, accession, document, and original request attempt stay equal. Alternative references and auditor facts are preserved in the existing row. A second required HTML role, missing/failed source, failed original HTML, unproved annual identity or auditor facts leaves the dependency unresolved.

This proves neither current SEC freshness, new acquisition credit, any metric Run nor acceptance of all 39 metrics. Failed attempts remain terminal and are not retried.

## Executed checks

- Ten bounded unit tests: PASS, 0.003 s. Covers same-source role changes versus changed raw/attempt/entity/accession, other HTML roles, failed original, missing/blocked XML/index, native parsing rejection, nonadjacent prior, missing/conflicting auditor and refresh/no-retry behavior.
- Six actual full prior native source sets (Southwest, Ford, Pfizer, Lumen, Macy, Enphase): PASS, 14.337 s. Actual XML period and auditor readers; no parser doubles. Each original HTML remains missing, each alternative is proven, and no HTML is selected for fetching. Source ledger/config watched bytes unchanged; network/DNS/SEC opener blocked.
- Full Southwest saved-source discovery plus normal refresh selector: PASS, 46.231 s. `SAVED_SOURCE_DEPENDENCIES_AVAILABLE`; one original missing HTML still reported; zero unresolved dependency URLs; the two normal metadata refresh requests still pending. After marking those metadata URLs attempted, zero pending URLs. No SEC capture or metric Run executed.
- The first real probe rejected a same-source index because different reader roles generate different reference IDs. The failure log is retained. The staged implementation was corrected to compare all source fields except the role and derived ID, and all checks above ran after that correction.

All checks used new processes loading the staged two modules with ordinary existing dependencies; originals were not overwritten. Calls: provider/paid/SEC = 0/0/0. Applying and rebinding this patch, and the parent's actual refresh execution, remain separate work.
