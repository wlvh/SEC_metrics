# B03: two scope withholds from #28, asked on the historical route

The first is a kept D&A total the filing says includes impairment-related
depreciation (Ford FY2025); the second, a kept composition beside a separate
contract-cost amortization (Marriott FY2025 and FY2024).

## The finding

Ford's FY2025 B03 was published at 0.0363384899635280108080975292 and accepted
(`CONTENT_B03_FORD_2025`, result `sha256:1829d73d...`). Its D&A input is
`DepreciationDepletionAndAmortization` 15,974,000,000, the total of the
segment table in the 10-K's own primary document. That table's
"Model e" column, 8,235, carries footnote (g): "Includes $8.1 billion of
depreciation related to the Model e asset impairment (see Note 13)." The
cash-flow statement tags the split exactly: depreciation and tooling
amortization 7,834 million and depreciation included in the asset impairment
8,140 million; 15,974 = 7,834 + 8,140. The approved definition does not add
impairment back, so the published value counts 8,140 million the definition
excludes.

Issue #28 found this on its ordinary route (`b03_depreciation_scope`,
`[shared-with-#47]` commit `08915a83`, and its exact split in
`b03_exact_impairment_relation`). The same result id is the historical route's:
both routes compute B03 from the same Company Facts for the same accession.

The cross-source reading that accepted the value followed the same approved
chain over the filing's own inline facts, so it read the same 15,974 and
could not see what the total covers - the same limitation that let
Salesforce's fixed-asset subtotal through (`../b03-depreciation-scope/`).

## Where else it applies

`measure_b03_impairment.py` asks #28's check of every B03 the historical
route resolves over every saved annual report, on the data root restored from
the branch's export (the acquisition's sources included): `measured.json`.
Only Ford FY2025 is `SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT`. Ford's FY2021
to FY2024 totals and every other company's are not footnoted this way.

## The repair

The historical route asks a direct D&A total it keeps, or retakes from the
filing's composition, whether the filing itself says the total includes
impairment-related depreciation (`historical_zero_ai_results.impairment_included`).
The question is #28's own, `_selected_impairment_inclusion`, bound here through
the parent generation's authority: the footnote marker must follow a numeric
component of the selected row, the visible components must sum to the selected
total, and the adjacent footnote must say the component includes depreciation
related to an impairment. A nearby mention is not enough, and a prior year's
column in the same table is its own fact. A total the filing says includes it
is withheld by name, `B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN`, with the
table, the footnote and its span recorded; B01 is still carried.

That is the standing rule - do not take a total that includes what the
definition excludes, and where the right amount is not proven, limit the
metric precisely - not a new decision. The exact exclusion (7,834 million) is
#28's successor Spec, `catalog/r6/B03_impairment_excluded_v1.md`, still a
private candidate there; it is not ported. The ordinary route is #28's.

## The second check: contract-cost amortization beside a composition

#28 found that Marriott's annual reports state, apart from the depreciation
and intangible-asset amortization the approved composition takes, a positive
amortization of capitalized contract costs - "Contract investment
amortization", deducted from revenue - that the composition neither adds nor
is shown to include (`b03_contract_amortization_scope`, `[shared-with-#47]`
commit `45bcce3d`; a bounded independent review, `969de88b`, returned
PASS_WITH_BOUNDS). Until the relation is proved or the definition decided
either way, #28 withholds a composed B03 whose filing reports it.

The historical route asks the same question with #28's own function
(`historical_zero_ai_results.contract_amortization_unreconciled`), handing it
the pinned input's source proofs, the target period and the route's B03
observations, so the facts it reads are the primary document the pinned input
admitted. A kept composition the filing answers for is withheld by name,
`B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN`, with #28's answer carried;
B01 is still carried; nothing is added or recomputed. The module is a V14
file, not the parent's, so it is bound through the successor's own authority
list, and a change #28 makes to it moves this generation's closure.

Measured on the saved annual reports: only Marriott's FY2025 and FY2024 take
the composition (`measured.json`, `NO_DIRECT_DEPRECIATION_SELECTION`), and
both report the amortization - 135,000,000 beside 145,000,000 + 313,000,000
for FY2025 and 103,000,000 beside 128,000,000 + 255,000,000 for FY2024, each
on the fee-services member with its segment breakdown. The accepted values for
both are withdrawn by coordinate
(`B03_MARRIOTT_2025_COMPOSED_DA_BESIDE_CONTRACT_COST_AMORTIZATION`,
`..._2024_...`).

## Verification

- `tests/vnext/test_historical_da_scope_route.py`,
  `AKeptTotalTheFilingSaysIncludesImpairment`: Ford FY2025 is withheld by name
  and still carries B01; the route's proof is #28's check's answer on the same
  component (same table, grid, component and footnote span); the same table's
  FY2024 and FY2023 columns are not footnoted and are not caught; the
  footnoted total asked about another period finds no fact; a total retaken
  from the filing's composition is asked too (constructed: no saved filing
  retakes). The existing cases (Enphase and Marriott unchanged, Salesforce
  withheld, the constructed shapes) still pass.
- `AComposedTotalBesideAContractCostAmortization`: Marriott FY2025 and FY2024
  are withheld by name and still carry B01; the answer carried is #28's own
  answer on the ordinary case for the same filing, field for field; with the
  check answering None the same composition is published as before; a direct
  total is not its question.
- `injections.py`: 7 injections - 4 for the impairment check, 3 for the
  contract-amortization one - each caught by the case written for it
  (`injections.json`; run in a clone of the branch holding the same files).

Zero SEC or provider calls.
