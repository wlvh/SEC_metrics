# Current B06 receiving gap: a bond appears in two maturity sections

This is a bounded reconnection of an already implemented historical component,
not a new bond experiment or a second debt reader. Actual company execution is
on the existing receiving combination `385472f9`. The three relevant production
modules are byte-identical to actual main31e4; their hashes are recorded.
This evidence-only branch starts at main31e4 and carries no production patch.

## Current authoritative failure

One new public company task requests Macy's B06 **FY2024** from the read-only
saved source root. First processing **6.146196s**, exit2, records
`CANDIDATE_WITHHELD`, value null, Result
`sha256:4bdb9b24989e48efd58b5a51da4359c6ed7a3e4334c712d7f6646641755ae9cb`.
The generic Result reason is `B06_SOURCE_RELATIONSHIP_UNRESOLVED`; the saved
input assessment identifies the actual first failing cause:
**`BOND_LEASE_BOND_MEMBER_DUPLICATED`**.

The original debt schedule reports **7.60% Senior debentures due 2025** twice:
current **6,000,000 USD** at row4, noncurrent **0 USD** at row7. It is the same
bond in two maturity sections, not a duplicate within one section. Actual year
container is FY2024, annual dates **2024-02-04–2025-02-01**; B06 measurement is
**2025-02-01**, an instant. Selected original accession is
**0001628280-25-014315**. The full actual rows, both native source references,
section totals and schedule adjustments are in `bond-section-refusal.json`.

`_bond_schedule` currently requires label uniqueness across both sections;
`_native_bond_members` subsequently also indexes by label alone. Repairing only
the first assertion would lose maturity identity or overwrite zero. The public
owner must consume the existing section-aware implementation and preserve
native context/concept/dimensions, unit, location and amount reconciliation.
Current/noncurrent is part of the member identity; no source row is deleted.

## Existing implementation to reuse

Retained PR52 commit **bcc0c0bc0293ba6b6ffc58b1f4e9034dbb52a786** already contains
`scripts/vnext/historical_bond_sections.py` and
`docs/evidence/issue47_history/b06-older-years/bond-sections/README.md`.
That implementation separately keys sections and validates all **21 native
members**. Original borrowing **2,779,000,000 USD** plus separately reported
finance lease **15,000,000 USD** is only a **2,794,000,000 USD component**.
The old reader uses release-aware/dynamic wrappers; current integration should
extract the minimal source relationship, not import the old freeze/installer
or whole historical branch. Public debt code remains a single-owner module.

This earlier source-level repair progressed to standby-capacity/borrowing
relationships, and full financing completeness remained unproved. Current
code has controlled word-zero paths, but this new execution stops before them.
Do not describe this current failure as the old `C03_ZERO_TRANSFORM_TEXT_CONFLICT`
or already the accrued-interest refusal. The **48,000,000 USD current accrued
interest relation** and other full-scope dependencies remain unresolved after
this structural issue; no inclusion/exclusion is invented here.

## Save/reuse/read and reproduction

Repeat with historical/shared B06 factories and both Calculator entries
forbidden: **0.367146s**, zero calculation/no new candidate. Independent results
and CSV: **0.175251s**, all **17 state files** unchanged. The original refusal
and source are retained; the readable null does not complete this business work.

Use the already restored PR52 `source-inputs` root and new external directories:

```bash
python3 tools/vnext_company.py run --company macys --metric B06 \
  --period fiscal-years --fiscal-year-start 2024 --fiscal-year-end 2024 \
  --source-root /absolute/saved/source-inputs \
  --work-dir /absolute/new-b06-state --output-dir /absolute/new-b06-output
python3 tools/vnext_company.py results --company macys \
  --state-root /absolute/new-b06-state --output-root /absolute/new-b06-read
```

`probe_schedule.py` reproduces only the actual shared schedule refusal, with
network forbidden, using explicit `--source-root /absolute/saved/source-inputs`
and `--output /absolute/new-refusal.json` arguments. It saves real rows before asserting the known
failure; it never supplies manual expected debt operands. The initial diagnostic
selected the narrative debt note instead of the actual schedule note and failed
its assertion; that harness failure is retained separately and corrected to the
actual `notes['schedule']`. The company processing was not repeated.

New SEC/provider/paid calls **0/0/0**. No new capture, model trial, old-result
rewrite, Run credit, author Ready/merge/adoption/active. This precise receiving
gap is handed to #28 for the shared implementation; history consumes its fix.
