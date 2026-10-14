# Current publication follow-up: exact defects and existing D04 material

Response to receiver6165605691; progress on #28. Base actually read main `ccd9d7c2721e2f8c2116d0ca784178b96571e21f`. This is a read of saved publication/source/response metadata and existing export receipts, not another company calculation or new acquisition. No provider/paid/SEC business calls, publication mutation, adoption or deployment.

## Missing values are now checked

The receiver-selected publication `publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59` still contains:

| Company / metric | Saved published value | Read against |
|---|---|---|
| Southwest FY2025 E01 |2| Exact registered old result476829da, saved390 index and its source coordinate |
| Ford FY2025 E01 |2| Old resultad429204 and the same saved index |
| Lumen FY2025 E01 |7| Old result21824ee7 and the same saved index |
| Macy's FY2025 E01 |2| Old resultba457ef8 and the same saved index |
| Pfizer FY2025 E01 |0| Old result27708650 and the same saved index |
| Salesforce FY2026 B03 |0.2295243829018663455749548465| Actual old source/resultf07e137e; operating income8331m plus partial D&A1200m divided by41525m revenue |

Each value matches the value of the registered old error. The publication CSV does **not** carry native Result IDs, so matching value/source coordinate is not claimed as identity equality. Exact rows, input files/hash and existing defect IDs are in `source-and-publication-read.json`.

The four already reported Lumen B01/B02/B03 and Macy B02 remain subject to their existing exact defect records. The frozen publication file was not changed. New ordinary company readers continue to withhold registered exact errors; this does not retroactively fix the published CSV. A replacement/corrected published view requires the user's separate production permission. Recommendation: retain the original package, explicitly disclose these errors in the receiver's current snapshot, and prepare a bounded replacement from separately validated current results/statuses; do not write new values into the old package or borrow unaccepted model credit.

## Two additional exact Macy's current Results withdrawn

The parent directly read both original primary income statements, using the existing metric-neutral table parser and checking original file hashes:

- FY2025 accession0001628280-26-021721, primary47e1df1c, consolidated income table36: net sales21764m + other revenue857m = total revenue22621m.
- FY2024 accession0001628280-25-014315, primary29bc388b, consolidated income table38: net sales22293m + other revenue713m = total revenue23006m.

Each year's current original column was read; a later comparative column was not substituted for a prior original. The corresponding current-year Company Facts observations agree, but tag presence alone is not the scope proof. FY2022/prior policy is not changed from later comparatives.

This PR registers only the exact #28 FY2025 B01 `cdd9caf6…` and B03 `bcdc08b4…` old results, with their original periods and identities, because they consume net sales as total revenue or margin denominator. B02 `66d0234b…` was already registered. The separately identified22621m B01 `923318df…` is not withdrawn. Direct checks of the actual registry matcher confirm the two exact matches and no withdrawal of a different Result identity. Current 44 company-record tests pass in8.365s with zero failures/errors/skips.

#47 owns historical FY2024 result registration/consumer validation; the direct original-source findings are supplied for that work. Root does not invent historical Result IDs or write the historical branch. This is not a new scope decision: an explicitly reported net-sales component cannot serve as the approved total-revenue operand.

## D04 material exists, but the historical package reader is not yet compatible

All ten #28 current D04 sources have the exact requested `D04_NATIVE_COMPLETE_SEMANTIC_SOURCE` type, with93 original successful groups in total. The record lists actual ledger call directories, source identities and actual fiscal dates: Ford70/72–81; Pfizer83–93; Marriott115–118; Southwest119–124; JPM125–151; Salesforce152–156; Lumen157–164; Macy165–169; Enphase173–178; Paramount179–188. Failed69/71 and other failed variants are not group members or erased.

The original root is `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`. Its read-only D04 backup is `/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d04-original-material-backup-20261013`; `backup.json` fixes its inventory. This check rereads original source-type/coordinate/terminal metadata and reuses prior complete-partition/response validations. It does not newly validate all93 model answers or their omissions.

There is **no established directly compatible `--saved-call-package` archive for the #47 reader**. Current `saved_d04_replay.read_saved_d04_assessment` accepts only binding `ISSUE_47_HISTORICAL_MODEL_ALLOWANCE` and its matching intent/terminal types. #28 originals are `CONTINUOUS_CALL_ALLOWANCE` / `CONTINUOUS_CALL_INTENT` / `CONTINUOUS_CALL_TERMINAL`. Source type equality alone cannot overcome that actual code restriction. Do not relabel #28 binding/answers as #47 calls. Its existing current-company reader already consumes the original ledger without new requests; an explicit compatible read-only archive adapter, if needed, must preserve those original identities.

Six existing independent current D04 CSV/summary/state references are supplied in the receipt: Enphase, Ford, Lumen, Pfizer, Salesforce and JPMorgan. These files were read without rerunning the producers. Their recorded commit or named dirty-code delta is retained, separately from the current moving code-root path. They are defined-scope `WITHHELD/null` with `TEXT_QUAL`, not health assurances, new model outputs or formal adoption. This finite reply does not claim ten current company exports; other existing evidence stays at its original boundary. Paramount's visible/native current-period conflict is not resolved by its old successful source.

## Period questions

The published Salesforce/Macy B10/B11 rows are structural N/A rows with a generic2025 calendar coordinate and no filing accession; this is not their actual fiscal year window. Keep the original published metadata, but do not count that calendar field as verified fiscal comparability. The current company route must select the actual company's period when preparing a new result/view.

Published Paramount D01–D04 explicitly point to CIK813828/FY2024 filing0001193125-25-096776. Those are retained predecessor-period source rows, not FY2025 results, and must not satisfy the latest-period390 coordinates. Current FY2025 source/entity/period limitations are separate and cannot be fixed by changing the old row's year. This report establishes the observed metadata, not the historical developer's intent. No production row was rewritten.
