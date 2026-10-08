# The FASB's dated US GAAP releases (FY2021 annual reports)

## What stopped

Once the extension had acquired the older annual reports' XBRL instances, the
frame's Marriott FY2021 B06 stopped at `B06_GUARD_EQUITY_NAMESPACE_CONFLICT`
instead of reading the equity it was asking about. The frozen readers decide
whether a fact's concept is a US GAAP concept with
`re.fullmatch(r"https?://fasb\.org/us-gaap/[0-9]{4}", uri)` (or `\d{4}`): the
year alone. The FASB named its releases through 2021 with the date after the
year. Every FY2021 annual report of the ten companies declares
`us-gaap/2021-01-31`, every FY2020 one `us-gaap/2020-01-31`, and from FY2022
every report declares the year alone (`declared_namespaces.py`,
`declared-namespaces.txt`, read off each saved document's own bytes).

This is the question the release-aware view (`scripts/vnext/historical_dei.py`)
already answers for DEI and ECD: frozen code that asks "is this namespace a
release of taxonomy X" with a year-only pattern, run through a view that
accepts the release forms the taxonomy actually uses. The US GAAP entry maps
both frozen spellings to `us-gaap/[0-9]{4}(?:-\d{2}-\d{2})?`: the dated form
and nothing else (no quarter form, no other FASB taxonomy, no filer's own
namespace).

## Where the question is asked

Frozen code asks it in the seven B06 modules, B03's contract-amortization
check (`b03_contract_amortization_scope`), B13's capacity source
(`capacity_semantic_source`; its applicable branch is not wired in the
historical frame, only a case calls it), D04's request reconstruction and
D02/D03's reported-fact candidates (`text_business_candidates`), and the
successor income input (`ordinary_income_input`). #47 reached four of them
without a view; each now goes through one, or the view's completeness check
names it: B03's contract check (`historical_zero_ai_results`), D04's request
reconstruction (`historical_semantic_results`), the capacity source
(`historical_semantic_source`) and the D04 defined-absence row
(`historical_projection`).

## Measured

`effect.py` asks each position of `positions.txt` - every company's FY2021
target (dated release) and its FY2022 target (year-only, as a control) - for
B06 through the historical cascade, B03 through the zero-AI route, the D02/D03
proposal and the D04 requests, twice in one process: with the view's US GAAP
entry taken out and as committed. The result is in `effect.json` (the
export-restored root of the final acquisition, zero calls). It was measured
with the D02 route of `f77e7599`, before the D02 route repairs of `dc9adacf`;
both sides of each comparison ran that same route, so the comparison is the
US GAAP entry's alone. The repairs ask no namespace question (the view's
completeness case covers every historical function that does), so they cannot
change what the entry moves; the D02 excerpt lists recorded here are the
pre-repair ones.

Only B06 moves, and only at the ten FY2021 positions: without the entry each
stops with `B06GuardError: B06_GUARD_EQUITY_NAMESPACE_CONFLICT` - an error,
not a result; with it each reads the equity, passes the guard and reaches the
debt grammars, which withhold it by name (`B06_SOURCE_RELATIONSHIP_UNRESOLVED`).
B03, the D02/D03 proposal and the D04 requests are the same at all twenty
positions, and the ten FY2022 controls move nowhere. So the change turns ten
run failures into named withholds and delivers no new value: why the older
years' debt relationship is unresolved is the next question, and a separate
one.

The first run of `effect.py` asked the view without the entry first. The view
caches, per frozen object, whether it reaches the question - computed from the
table at the first call - so every later answer came from the reduced table
and read "no change" everywhere. It was stopped and its output is not used;
the script now asks the committed answer first and restores the view's caches
after the reduced one, and says so.

## Cases and injections

`tests.vnext.test_historical_dei.AUsGaapReleaseIsRead` (four cases) and the
completeness case `EveryHistoricalReferenceGoesThroughAView`. `injections.py`
undoes each part of the change - the table entry, the pattern, one frozen
spelling, and each of the four call sites - and requires the case written for
it to fail, recording the failure's own line.

All seven are caught, each by the case written for it (`injections.json`),
run in a worktree at `dc9adacf` with this change applied: the control run of
the module passed first (69 seconds), and every edited file was put back byte
for byte and checked after each injection.
