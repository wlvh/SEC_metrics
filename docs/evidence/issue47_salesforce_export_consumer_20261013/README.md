# Salesforce: saved-source export through the same historical company entry

Progress on #47, receiving public [PR208](https://github.com/wlvh/SEC_metrics/pull/208). Actual execution uses its head `5ea1735ff86ef453f8c74b6b258d1c1a89457610`, including main `31e4a00d` and the fixed public dependency-check test base. This record changes no production code, public controller or test runner. It supplements the already verified Marriott export with an existing noncalendar issuer; it does not repeat that fifteen-position reception.

The offline public `export --company salesforce --metric B01 --history-years 5` completed in **26.597904s**, producing an ordinary `COMPANY_SAVED_SOURCE_PACKAGE_V1` with **55 files** and issuer fiscal labels **FY2022–FY2026**. Each copied file equals the saved original byte for byte. The complete mixed request log, its manifest and company registry retain their bytes; the package does not carry a new allowance or a saved result. Source readiness is separate from metric acceptance and online source discovery/completion.

From a new empty state, the same company CLI calculated **one** B01 position, FY2026, in **5.653591s**: **41,525,000,000 USD**, actual annual interval **2025-02-01 through 2026-01-31**, accession `0001108524-26-000060`. This agrees with the already checked five-year pilot reference. Result identity remains `sha256:8cecba16403adcd8197747cecd1bbb27cb8cb851b4eb236eed2ad74f895ff60d`. The issuer FY2026 label and original DEI label are retained by the existing selection rules; neither the source date nor the source label is rewritten.

The unchanged-input repeat took **0.268098s** with the historical preparation functions and both Calculator functions forbidden. It created no new candidate or result directory and preserved all **7 result files**. A separate-process `results` took **0.181175s**, preserving all **18 state files**, and exported the same value, fiscal label, actual dates, original source references and result identity to CSV. Normal check-observation logging on repeat is allowed; result preservation and zero computation are the assertions.

`export.json.gz` is the lossless saved export receipt (ordinary gzip, not another input format). `first.json`, `repeat-forbidden.json`, `read.json`, `summary.json`, and both CSVs are the actual outputs. The local state is `/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence/salesforce-history-export-consumer-20261013/state`; originals are the existing read-only `SEC_metrics-issue47-company-verified-source-20261006/source-inputs`. `record.json` identifies the executed script; `verify.py` replaces only its local source/output assignments with arguments. The adaptation is syntax/help checked, without a second financial execution. The initial saved process completed normally; loss of its terminal session handle did not trigger a rerun.

## Reproduce on available code and inputs

Use the fixed PR208 code or a main version actually containing it. Keep the existing original source root read only; outputs must be new external directories. If originals have not been restored, use the retained PR52 branch `task/sec-history-five-year` at `bcc0c0bc` and its existing `python tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out <new-directory>`; consume the returned `data_root` (the actual `source-inputs`), not the restore parent. Restoration is offline. No new acquisition is needed for this sample.

From the code root with its normal Python dependencies:

```bash
PYTHONPATH=scripts:tools:. python3 -B \
  docs/evidence/issue47_salesforce_export_consumer_20261013/verify.py \
  --source-root /absolute/existing/source-inputs \
  --output-root /absolute/new/salesforce-export-review
```

The equivalent user commands remain the public company entry:

```bash
python3 tools/vnext_company.py export --company salesforce --metric B01 \
  --history-years 5 --source-root /absolute/existing/source-inputs \
  --output-root /absolute/new/salesforce-package
python3 tools/vnext_company.py run --company salesforce --metric B01 \
  --period fiscal-years --fiscal-year-start 2026 --fiscal-year-end 2026 \
  --source-root /absolute/new/salesforce-package \
  --work-dir /absolute/new/salesforce-state --output-dir /absolute/new/salesforce-first
python3 tools/vnext_company.py results --company salesforce \
  --state-root /absolute/new/salesforce-state --output-root /absolute/new/salesforce-read
```

No other financial year or metric was recalculated. Calls **SEC/provider/paid 0/0/0**; existing sources, responses, ledgers and old results are preserved. PR208 remains a candidate until reception/merge; this evidence does not claim main already exports this package, online discovery is complete, all five-year metrics pass, or Issue47 is closed. The existing main guide remains the entry for capabilities actually merged.
