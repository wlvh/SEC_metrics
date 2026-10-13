# Marriott FY2021: distinguish proved contract deduction from unresolved full D&A

This diagnostic uses actual main `16e82aae` and the already saved original `0001628280-22-002666/mar-20211231.htm`, SHA256 `54effe78b84966cd0793dcb23b8db4ad30b0614ea3d42074f3ece89adebe8bf5`. It reuses the [three saved candidate-year readings](../issue28_b03_source_candidates_20261008/README.md) and FY2021 primary/XML candidate references. It does not reread all three years, choose another sample, install a company or compute EBITDA.

The current shared `_visible_revenue_deductions` already recognizes FY2021's contract-investment amortization: consolidated fee revenue `2694 − 75 = 2619` million USD, US/Canada `1580 − 55 = 1525`, international `568 − 20 = 548`, operating-segments total `2148 − 75 = 2073`. The last total overlaps its two segments; it is not an additional amount. The existing core does not need a new contract-deduction recognizer for this original. `actual.json` records native ordinals, dimensions, actual dates, original table/grid identity and all four shared proofs. The actual diagnostic takes0.343s; the saved original hash is unchanged afterward.

The other D&A issue is distinct. Primary/XML candidate ordinal925 reports165m intangible amortization with `FiniteLivedIntangibleAssetsByMajorClassAxis=ContractBasedIntangibleAssetsMember`; its reimbursed62m is explicitly **included**, as49m is included in gross depreciation138m. The existing original-composition check admits undimensioned amounts only. Removing that restriction would not establish full D&A coverage: the original also separately describes amortization of contract-fulfillment costs in “Owned, leased, and other - direct expenses,” without proving their amount or inclusion in165m. `original-fragments.json` retains that complete source paragraph and exact byte spans. These are source facts and an unresolved inclusion relation, not permission to sum candidates or change the definition.

The earlier gross-depreciation paragraph continues across a page break. Its reference to impairment on leased hotels is explicitly **2020 and2019**. It cannot be used to infer FY2021 impairment from the truncated first page. Prior candidate records and null results remain unchanged. No financial claim, Run, Result, state pointer, source blob, request ledger or original answer is written. Full FY2021 B03 remains unproved; no new business credit is claimed.

Run after restoring the existing PR52 source export and finding its actual source-input root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_marriott_da_scope_followup_20261013/probe.py \
  --source-root /your/restored/source-inputs > /your/new/probe.json
```

Output goes to a new review file; sources stay read-only. The probe verifies the complete original hash and entity/period/USD/official namespace before calling the same existing shared source function. This is a source diagnostic, not a company first-run, repeat or independent-result-read acceptance. Public D&A core changes remain owned by #28; historical selection and subsequent consumer validation remain #47's responsibility. New SEC/provider/model calls are0.
