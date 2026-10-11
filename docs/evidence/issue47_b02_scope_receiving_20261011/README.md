# Historical B02: current causes and consumer reception

Baseline is actual main `488b43871a2a06395ec4c4b155e94da6c02a06de`. This is a bounded follow-up to the [receiver's 50-position census](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-6106222781), not another census. PR128/152 already supply the historical paired-revenue consumer and processing dependencies. Its current and prior roles call `reported_revenue_scope` with single-line admission enabled, then `selected_revenue_scope`; the old statement that history does not call these readers is no longer current.

Lumen's five positions were subsequently repaired by PR164/165, and Southwest FY2021–2024 by PR162. Those executed results are reused. Four representative positions were prepared once against today's code with network forbidden; their actual role, filing, period, null and scope status are in `current-representatives.json`. Equal values, concepts or terminal reasons are not used as scope proofs.

| Representative | Actual cause | Responsibility and next action |
| --- | --- | --- |
| Marriott FY2024 current | Consolidated statement table_000026 reports native Revenues 25,100m at ordinal92 with an empty total-row label. Net fees 5,067m + owned/leased/other 1,551m + reimbursements 18,482m reconcile. Costs are dimensional components rather than a non-dimensional CostOfRevenue in the existing filter. Note table_000054 separately reconciles segments 22,576m + corporate/other 2,524m to Consolidated revenue 25,100m. Neither label gate recognizes the statement total. | Shared original-scope reader implementation by #28; history consumes and validates it. Full statement/section, subject, units, actual period, original total and composition must be proven, rather than accepting a larger or equal amount. |
| Ford FY2024 current | Table_000077 ordinal135 reports Total revenues (Note 4), 184,992m. Same context contains cost ordinal138 and net profit ordinal168. The old label normalization does not recognize `(Note 4)`, so both readers skip this candidate. | Shared label/scope reader by #28. A numeric note reference is distinct from `(Europe)` or `(Subsidiary)` scope qualifiers. This is a separate cause from Marriott. |
| Enphase FY2024 current | Statement table_000095 Net revenues ordinal157 carries the reportable-segment dimension; the native whole-entity reader excludes it. Non-dimensional totals occur in note table_000117. | Existing Enphase qualification/single-segment investigation continues separately. A dimension name or equal note amount cannot establish whole-company scope by itself. |
| Macy's FY2022 current | Table_000039 reports Net sales 24,442m and Credit card revenues, net 863m separately, with no complete revenue total admitted by the current rule. | Real unproved-scope counterexample retained. No sum, later comparison, alternate year or old cached result is supplied as an answer. |

The full selected statement rows for Marriott FY2024 and Macy's FY2022 are saved next to this record. Marriott FY2023's table_000026 has the same revenue-section arrangement, total ordinal74 and actual first-report amount 23,713m; its native component identities and full rows are in `marriott-2023-second-layout.json`. It is an applicable second original for the proposed shared rule, not proof that the rule already works. Full source bytes and their request records remain in the committed PR52 acquisition export. Nothing in these excerpts replaces the source reader's complete checks.

## Reproduce without changing source or old tasks

Restore a **new** source directory using the retained historical acquisition branch, only when a saved root is not already available:

```sh
python3 tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out NEW_SOURCE_DIRECTORY
```

Use the command's returned actual `source-inputs` root. On main488b or this evidence branch, with the project's Python dependencies installed:

```sh
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_b02_scope_receiving_20261011/reproduce.py --source-root SOURCE_INPUTS --company marriott_international --fiscal-year 2024 --output NEW_OUTPUT/marriott2024.json
PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_b02_scope_receiving_20261011/reproduce.py --source-root SOURCE_INPUTS --company macys --fiscal-year 2022 --output NEW_OUTPUT/macys2022.json
```

The driver calls the actual historical case, forbids sockets and writes a new diagnostic file exclusively. It does not implement a selector, create a saved company result or claim fresh company-CLI success. Runtime calls remain zero. Existing originals, responses, failures and task directories are read only.

## Next consumer delivery and limits

#28 owns the shared scope/label implementation; #47 owns selected-period consumer reception. The next affected integration uses one fresh same-company B02 command for the representative and applicable second sample, then forbids the case factory/Calculator on identical input and independently reads `results`/CSV/provenance. The real Macy's unproved-scope path must remain withheld. Current/prior original filing selection, paired-measure comparability and saved old results remain unchanged.

Macy's FY2023 and Pfizer FY2021/FY2024 comparative changes retain existing values/limitations; choosing the current filing's revised comparative is not part of this work. JPM structural non-applicability and Paramount merger-year subject incomparability are separate reasons. Missing original filings, parsing defects and uncleared amendments remain distinct. Full five-year business acceptance, online discovery/completion, C04 source rules, D04 images and the other Issue47 gaps remain required.

This record is investigation and a concrete public implementation handoff, not a delivered positive B02 result, formal acceptance or a replacement for the full target. No new SEC/provider allowance, model trial, Ready, merge, adoption, deployment or active change is used.
