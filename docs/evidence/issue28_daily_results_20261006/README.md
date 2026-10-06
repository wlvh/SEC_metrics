# R2 daily company read, from main8588

The current launcher now uses results --output-root for daily CSV/JSON. Its
calculation program stays pinned. Explicit export-results retains the existing
full replay/portable audit export. No Requirement, old Run/Result, request,
answer, source or project ledger is rewritten. Only the necessary csv_output
helper is received byte-for-byte from PR60/e6dd436b, not its other wrappers.

A daily read checks saved Result/Trace identity and coordinates, saved Spec
and unit, numeric/text value, measurement/fiscal labels, original CSV identity
when the old journal has it, and source reference/path/bytes. Source digests
are shared during this read. It never computes a metric or copies an attempt.
The saved rows and source links remain available by record_root/source_root;
this lightweight output is deliberately not a portable archive.

Actual old JPMorgan2025 D01 company state, original f8da5496 Result: current
CLI0.574s, one row/56titles/56evidence,144880 output bytes. All20 original metric
columns and18 evidence columns are equal to the saved native output. The earlier
full audit export log measured39.107s, but it is a different operation and is
not advertised as a matched benchmark. This read uses its old source/rule
compatibility tree and existing source trust; R3/R4 have not removed that old
installation boundary. The result is SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED.
Previous limited content evidence remains scoped to its original result/source;
this run is new reading evidence, not another content or production acceptance.

40 directed tests0.376s: tiny real Calculator records and isolated journals,
wrong value/unit/period/fiscal label, source damage, structural absence, known
unreleased defects, exact same-result prior release, latest input/import failure,
interrupted output, no overwrite and CLI failure exit. Acquisition and computation
in local orchestration tests are explicitly mocked. The actual old-company CLI
above uses real report/source recovery, record/Spec/row/source checks. Scope is
not a full run/acquisition or all metrics/history business acceptance.

Known defects default to the existing Issue28 registry path.32 own registered
entries are received from fixed7a5b328b, without its trusted-count summary or
copying peer acceptance. Other-package identity alone no longer withholds the
same previously released result in this new daily path, but its prior release
references remain and reading does not grant fresh content acceptance. Actual
unreleased defects still withhold exact matching values. Source/input/import
failure retains an old value only with PREVIOUS_RESULT and original dates;
source_freshness explicitly says this reader did not perform an online check.

Peer fixed6e968a63 B01/D01 register entries were read. The JPM2025 old running
header issue maps to our old defective9944 result; this read is the own fixedf8
graph, already covered by its limited content evidence. No new peer release
or result credit is copied. Other shared C02/D02 core remains with Issue47.

Still incomplete: ordinary_update_cycle.run_once checks old results and prepares
full cases before change detection. The two-level raw/parsed task input comparison,
Marriott D04 script-equivalence integration, shared new-attempt program/source
installation and all-company business completion remain in the existing queue.
This PR completes the daily reading part, not all of R2. No business calls,
fee/budget changes, adoption or production actions.

Issue47's actual Macy range consumer reported two missing CSV metadata fields
(JSON already had them). Daily metric/evidence output now retains
requested_in_latest_execution and period_role.41small regressions pass,
including an old FY2025 row outside a new FY2024 request. This is receiver-
reported evidence of the missing columns plus our direct CSV regression,
not a claim that we reran their historical company. Business20/18columns are
unchanged; no new reading/approval object or full metadata migration added.

The initial range-column test failed because its helper assumed a single row;
the correct view contains both oldFY2025 and failed requestedFY2024. Commit
357447f6 included that failed test and prematurely said41passed; this is
corrected here, with its failure log retained. The final41tests pass0.388s.
The pending requested row now retains its requested fiscal year and explicit
REQUESTED_WITHOUT_RESULT role; the old row is not marked requested. No old
business row/result was changed to resolve this test.

Receiver range follow-up: a range header2023--2024 differs from child year
requests, so the previous equality against only the header was insufficient.
The current pending-row flag now matches metric + exact period_request from
latest actual outcomes (falls back to the single-request header when omitted).
A three-row regression retains old2022=False and requested2023/2024=True;
42directed tests pass. It does not infer membership merely from year bounds or
metric name. Receiver's uncommitted failing test was described by them; this
is our independent small input/output reproduction, not their full range rerun.

The previous pending range test supplied an already-correct view, so it did
not prove main's upstream grouping. Peer e419a1b7 identified that dependency:
main used the range header as a pending key and lost one year. Received only
requested_period/matches_period, per-period latest request and pending keys
from that fixed source; no C02 review scan/wrapper copied. A real small-state
save_execution→build_company_view→CSV now preserves old2022 False and child
2023/2024 True, all missing values blank.43directed tests pass. This closes the
upstream gap; the earlier mocked-view check remains only a CSV branch check.
