# Accession route: reports whose FASB namespaces carry the release date (2026-10-02)

## What stopped

Three positions of the 50-period frame (`frame4`, closure `500ddf5f`) were withheld by the accession route with the generic `HISTORICAL_ACCESSION_ROUTE_UNRESOLVED`: JPMorgan FY2021 A01 and A02 (the bank's capital ratios) and Salesforce FY2022 B12 (remaining performance obligations). The route keeps the frozen reader's reason in the component, not in the Run; reading it (`probe.py`):

| Position | Frozen reader's reason |
|---|---|
| JPMorgan FY2021 A01, A02 | `NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED` |
| Salesforce FY2022 B12 | `NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED` |

The frozen accession policy (`config/normal_accession_metrics_v1.json`) spells the US GAAP, SRT and DEI namespaces as the year alone (`fasb.org/us-gaap/[0-9]{4}`). The FASB named its releases through 2021 with the release date after the year: JPMorgan's FY2021 report declares `http://fasb.org/srt/2021-01-31`, and A01/A02's required scope names an SRT axis (`srt:ConsolidatedEntitiesAxis`); Salesforce's report for the year to January 2022 declares `us-gaap/2021-01-31` for the RPO concept. Every other accession position of the frame either has year-only namespaces or is structurally not applicable. This is the program not reading a release name, not a disclosure missing - the same class as the DEI, ECD and US GAAP releases the release-aware view (`historical_dei`) already answers.

Two things kept the existing view from answering it: the patterns come from a policy file, so no frozen function holds them as constants and the view never rebinds `re` for the accession reader; and the view's table had no SRT entry (no frozen code holds an SRT pattern).

## What changed

* `historical_dei`: an SRT entry (`srt/<year>` or `srt/<year>-<month>-<day>`, nothing else) and `release_aware_pattern`, which gives the release-aware form of a frozen namespace pattern a policy file spells and refuses any other pattern by name.
* `historical_accession_results.inspect_with_dated_releases`: the frozen inspection runs first. Only when it refuses for one of the two release reasons is the same inspection run again with the three namespace patterns replaced by their release-aware forms; the inspection then records `dated_release_successor` (the frozen refusal and the patterns used), and the observation records the hash of the policy actually used. Any other refusal is the frozen one.

## Measured (zero calls, the final export-restored root)

`probe.py` → `measured.json`, the historical route resolved with the change:

| Position | Before (frame4) | After |
|---|---|---|
| JPMorgan FY2021 A01 | withheld | `0.15`, after `NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED` |
| JPMorgan FY2021 A02 | withheld | `0.131`, same |
| Salesforce FY2022 B12 | withheld | `43700000000`, after `NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED` |
| JPMorgan FY2022 A01, A02 (year-only control) | `0.149`, `0.132` | same values, **same result ids** as frame4 (`f0d51267…`, `84d67d35…`); no successor |
| Salesforce FY2023 B12 (year-only control) | `48600000000` | same value, **same result id** (`d982b006…`); no successor |

These are route values, not accepted values: the three new values still need an independent reading of the filings.

## Verification

* `tests/vnext/test_historical_accession_releases.py` (8 cases, on the saved reports from the export): the frozen inspection refuses JPMorgan FY2021 and Salesforce FY2022 for the release reason and the successor reads them; on JPMorgan FY2025 and Salesforce FY2026 (year-only) the successor returns the frozen inspection itself and the frozen policy object; a namespace that is not a FASB release (`srt/2021-1-31`) is still refused; another refusal is the frozen one; `release_aware_pattern` refuses a pattern that is not frozen.
* Injections: see `injections.json`.
