# Historical fiscal range: unrelated missing original propagates across years

Progress on #47. Responds to receiver6168703769/item1. This is a read-only real saved-source reproduction, not a new planner or rule change. company_fiscal_range and its planning/source dependencies match actualmain190e2f9011d264c5d6527e2bb59efd6b1b9aa3c5; tested program02454771 differs only in lodging structural consumer/test/docs, none executed by these sources commands.

Same Macy saved source root and formal sources CLI: requesting onlyFY2022 resolves in10.565s. RequestingFY2021–FY2025 returns all5tasks unresolved in9.712s; every year receives the missing original whose report_end is2020-02-01, accession0000794367-20-000040/m-0201202010xk.htm. Thus the wider selection blocksFY2022 solely becauseFY2021 is included. No fiscal year is inferred here; it compares two current production decisions for the identical requested year.

The direct mechanism is company_fiscal_range.py's per-year task loop: unread limitations are collected from all entries selected using the first requested year's metadata window, then extended into every task. Existing metadata-window discovery already knows target/nearest-prior relevance. The finite repair should reuse that existing per-target window/selection policy rather than assign a fiscal label from a calendar date or discard every unread source merely because another label is available.

Keep current negatives: unread candidates inside a relevant target/prior window still block; conflicting explicit issuer labels/duplicate source years and missing inventory shards are not silently ignored. The existing test whoseFY2025 original is missing duringFY2024 label resolution must remain. The selected B02 consumer must still read current/prior originals independently and prove scope comparability; unlocking discovery does not give MacyFY2023 a ratio from total23866 against NetSales24442.

Exact commands, terminal stdout/stderr, source requirements and failing URLs are in the two receipts. Network and both numeric Calculator entrypoints are forbidden, outputs outside source, provider/paid/SEC0/0/0, metric_executedFalse and fetch_authorizedFalse. No GET/old result/ledger modification. Restore the existing52 acquired source or reuse a read-only restored root:

```sh
python3 tools/vnext_company.py sources --company macys --source-root /your/restored/source-inputs --fiscal-year-start 2022 --fiscal-year-end 2022 --metric B01
python3 tools/vnext_company.py sources --company macys --source-root /your/restored/source-inputs --fiscal-year-start 2021 --fiscal-year-end 2025 --metric B01
```

The public planning implementation remains a single-owner interface; this handoff provides a real history consumer counterexample and expected finite behavior, without parallel modification. Further source completeness, business processing and original-source/manual checks remain separate. No adoption/merge/Ready/deploy or new-call authority.
