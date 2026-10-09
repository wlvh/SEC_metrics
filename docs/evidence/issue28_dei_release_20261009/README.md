# Explicit DEI release successor for the public financial parser

Actual base main6e51f416; code root and exact uncommitted tested file hashes are
in tested-tree.json. The patch adds optional dei_release="YEAR_ONLY" to
normal_annual_input.annual_period and financial_structured.inspect_inline_financial_claims.
Default signatures retain old behavior/return structures; explicit
"YEAR_QUARTER_OR_DATE" accepts SEC DEI year, q1–q4 or date-shaped release suffixes.
Arbitrary regex selections/foreign extension URIs are rejected. This does not
change metric meaning, selection/SourceSet/entity/annual context checks or
ordinary default binding. It does not copy #47 historical view/financial core.

Fixed peer94fdaf25 source parameter bundle is retained with its original fields;
it contains references/period/DEI diagnosis, not a saved AI answer or Result.
verify_saved_source.py reads its original target and inventory through the
existing saved_source verifier, checks raw SHA and blocks all socket connections.
The source root is read-only, no acquisition, ledger, attempt, Run or Result is
written. First probe before this patch expected nonexistent source_reference in
the saved_source result; actual keys are raw/proof/saved_at_utc. Only the
harness lookup was corrected; no source/verification contract changed.

## Actual source and unchanged default

JPMorgan FY2021 primary16,005,889B/SHA7c58f18f and history inventory347,650B/
SHA77f7ffeb match original fixed references. Old default annual boundary fails
DEI_MISSING_OR_AMBIGUOUS:DocumentType in1.599s. New explicit full component
succeeds in4.032s: native fact7406, Total international28,971 million USD,
annual2021-01-01 through12-31, original entity19617. These timings measure
*different* work and are not a speed comparison. Complete output and original
source proof locators are in actual-source-result.json. direct-original-read.json
independently reads table614 (2021/2020/2019) and the Revenue(c) note: net
interest income plus noninterest revenue. It is not solely a peer expectation
or cached output comparison.

Small checks45/0.233s/zero skips cover explicit/default release, foreign/invalid
selection, entity, form, focus, fiscal label, conflicting facts, short annual
context, existing namespace policy/parse reuse and update retention. Existing
current JPM/Citi original default A13 test also passes1/11.097s/zero skips;
its values remain42.758bn/42.295bn. No full financial/history suite rerun.
The new6-case selector is appended to the fast list and explicitly exercised
by current-company CI; no runner body or old test assertion is edited.

## Consumer receiving boundary

Use the actual public parser with existing SourceSet arguments:

    inspect_inline_financial_claims(..., dei_release="YEAR_QUARTER_OR_DATE")

Or read only the original annual identity:

    annual_period(..., dei_release="YEAR_QUARTER_OR_DATE")

The historical owner remains responsible for its selection/financial result
adapter and company CSV/reader receiving test. This component success does not
upgrade its old Result or count a new accepted A13 company outcome. The existing
normal update configuration already includes normal_annual_input and
financial_structured for affected financial routes; optional behavior requires
explicit caller/config selection, not monkeypatching a shared global.
No new protocol/Requirement generation, real SEC/provider/paid, production
adoption, Ready or merge. [shared-with-#47]. New calls0/0/0.
