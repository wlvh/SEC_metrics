# Issue #28 revision 2 — bounded R4 offline implementation

## Status and authority

This five-file snapshot is a NOT_ACTIVATED proposal. It supersedes
`issue_28_v1` at
`sha256:08994b0aa3324511ce655958fbe3c48fdcd873fa2d63a9bfe4de573046d519ac`.
The parent and all R1–R3 history retain their bytes and interpretation.
`PROFILE_DRIVEN_V3` is a new retained engine; Requirement revision 2 and
engine generation 3 are separate identities. V1/V2 engines are not edited.

Policy-content authority is the Decision Register, bound to exact owner
comments 5524085182 and 5524746204 and their author/timestamp/body hashes.
Neither those comments nor this implementation activate this closure. A later
owner exact-head/closure activation is required before merging PR-B; live
provider authorization remains a separate PR-C action.

## Exact R4 scope

R4 contains only A03, A04, A09, A11, A12 and A13. B06/B13 stay pending R5.
There must be one production and one materially different alternate positive
per task. Source-specific reviewed windows are not general automatic source
discovery. Only positive fixture classes can be call-eligible; a structured
success is still zero-call. A09/A13 run accession XBRL first and may enter
table fallback only on STRUCTURED_SOURCE_AMBIGUOUS.

## Source-bound composite scope

The default same-target-table rule remains. Numeric value cells and amount
scale/header evidence remain in the original target table. Only these scope
dimensions may use exact same-source, deterministically associated narrative:

- A12: 95-percent confidence and one-day holding period.
- A03: firm entity scope and average aggregation.

Bind original source SHA, accession/document, exact byte offsets/bytes/span
SHA, named section and structure, and the actual target table. Enumerate and
disposition all competing declarations; a conflicting declaration governing
the same measure prevents automatic certification. Never borrow another
source/year, copy prose into table/caption, create a virtual cell, or use
AI/fuzzy/embedding/ranking to select scope. Table-proven dimensions may be
combined with the permitted narrative dimensions without fabricating either.

The Citi alternate A03 fixture may use its disclosed quarterly average only
with exact source-bound period evidence. It is not an annual average and
does not change any other metric's period semantics. Provider payloads remain
certified table windows only; narrative is deterministic checker-side evidence.

## A13 economic measure

A13 is INTERNATIONAL_NET_REVENUE: issuer-disclosed consolidated non-US or
international net revenue, full-fiscal-year duration, canonical USD; never net
income, assets, loans, deposits, maturity, segment-only or global totals.
Prefer a direct international total. Regional summation requires mutually
exclusive leaves, matching concept/unit/period/non-geography context, no
parent/child overlap and exact global-minus-US reconciliation. Otherwise the
candidate is AMBIGUOUS_EXCLUDED. The two-source/two-navigation/out-of-window
NO_INDEPENDENT_LEGACY_ANCHOR controls remain mandatory for A09 and A13.

## Resource and execution boundaries

Only total-cell capacity may increase after guarded three-source measurement,
never above 250000. Select the smallest sufficient value with documented
headroom; keep all other resource limits unchanged. Production and the
512 MiB/no-swap/network-none measurement harness use the identical parser and
constant, without caller or worker override. Exact cap passes; cap+1 fails.

Retain the process-local immutable session and at least 10x aggregate wall-time
gate on the same actual inputs/interpreter with at least six prior terminal
Runs. No child may replay full prior Runs or rebuild full source/DerivedAsset
or authority. Include one independent final full R4 disk replay. Component
microbenchmarks do not establish the aggregate gate.

The two previously authorized BAC/Citi acquisitions are exhausted. No further
SEC, provider or paid-model call, actual token measurement, live cycle/freeze,
Stage-A, R4 publication, rollback/restore or archived-response reuse is allowed
by this snapshot. Active R3 remains unchanged. PR-B stays Draft until full
offline validation and independent exact-head/closure review complete.
