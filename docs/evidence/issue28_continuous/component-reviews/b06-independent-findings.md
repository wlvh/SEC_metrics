# PR43 independent incremental review before successor implementation

Reviewed head: `cbede80d6c75bae7a6022adce74416a4d281399a`.
No production code or historical evidence was edited for this review. Provider / paid / SEC = 0 / 0 / 0. The restored original package contains 1,876 files / 105,190,675 bytes, all verified against replay-index.json. Existing 13 targeted tests passed in 22.337s; six native-material tests passed in 26.171s, with socket connections forbidden.

## P1: substantive borrowing prose is omitted from completeness inventory

At `scripts/vnext/b06_disclosure.py:310-317`, related disclosure inventory visits only table rows. The full note text is retained but not evaluated for current recognized borrowing amounts, except finance-lease relationship phrases. A plain-text statement in the complete selected DebtDisclosureTextBlock can therefore establish an additional recognized obligation outside the debt table and still produce `complete=True`.

Reproduced independently on both original PR43 filings by inserting in XML and primary the same sentence: “Additional short-term borrowings of $99 million were outstanding as of [actual period end], presented in accrued expenses and other liabilities, and excluded from the components of borrowings table.” Both return `complete=True`, empty unresolved, and unchanged debt 9,111m / 6,699m. The actual downstream Calculator also returns EXACT/PUBLISHED and unchanged ratio. This is a content-validator counterexample; TEST_ONLY sources were never admitted as SEC or frozen into a Run.

Required repair: account for bounded, affirmative current-period financing assertions inside required full notes; reconcile explicit inclusion to the reported debt set, or withhold with a concrete unresolved/unsupported explanation. No broad keyword-only refusal or manual relationship entry is needed. Arbitrary natural language remains a declared limitation.

## P1: primary equity may contradict the denominator without blocking acceptance

At `scripts/vnext/b06_disclosure.py:270-271`, the primary balance-sheet scan stops at the equity heading. At `:323-325`, HTML/XML agreement is checked only for debt/lease notes. The denominator is selected from XML without agreement with the primary inline fact.

On each original PR43 filing, changing only the current primary `us-gaap:StockholdersEquity` value by +100m preserves complete acceptance and the original Calculator ratio. XML and Company Facts remain unchanged. This differs from the earlier repaired note-sign counterexample: it occurs in a numeric fact outside the three text blocks.

Required repair: normalized per-concept XML/primary comparison for every consumed numerator/denominator fact, preserving issuer/context/date/unit/scale/sign and reported precision. Contradictory visible evidence must not be labelled verified.

## P2: recognized names grant unearned reconciliation

At `scripts/vnext/b06_disclosure.py:289,297`, nondimensional current `LongTermDebt` and `DebtInstrumentCarryingAmount` are labelled INCLUDED_OR_RECONCILED even when absent from the selected calculation's precision/reconciliation set. On original Southwest FY2024, changing XML LongTermDebt from 6,697m to 99m still produces unchanged EXACT/PUBLISHED B06. Its original 6,697m is the principal maturity schedule total, not the 6,699m B06 carrying amount; this is why merely comparing every debt-named fact to B06 would be wrong.

Required repair: validate cross-source numeric consistency and retain each recognized-but-unconsumed fact's actual measurement explanation. Here the maturity principal total must tie to its own summed schedule; Salesforce DebtInstrumentCarryingAmount=8,500m must tie to the explicitly labelled principal column, while its carrying total is 8,433m. Unexplained measurements stay unsupported.

## Evidence and scope

Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 /tmp/sec_metrics_issue28_continuous/pr43-review/reproduce.py`.
`counterexamples.json` records exact original hashes, mutations, proposals, inventory and downstream Calculator results. `targeted-baseline.log` and `native-material-baseline.log` preserve baselines. No finding asserts that the two unchanged historical accepted results are numerically wrong.

After reporting these independent findings, the parent assigned this reviewer implementation of the additive v2 component. Subsequent v2 work is implementation, not independent approval; a separate reviewer must assess it.
