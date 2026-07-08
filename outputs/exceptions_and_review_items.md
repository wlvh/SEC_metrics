# Exceptions and Review Items

Generated UTC: 2026-07-07T08:02:47.609576+00:00

## 本轮修复前降级的错值

- Lodging B11: rejected percentage-change values when the metric requires absolute RevPAR.
- Subscription/contract B12: rejected small context/date noise when it is not an RPO/cRPO fact.
- C03: rejected previous `ecd_fact_count`; C03 now uses ecd:PeoTotalCompAmt or is degraded.

## Full-instance fallback notes

- Southwest Airlines 2025-12-31 original 10-K is marked `target_original_full_instance` for full-instance fallback from an amended or partial target.
- Paramount Skydance / Paramount Global 2025-12-31 original 10-K is marked `target_original_full_instance` for full-instance fallback from an amended or partial target.
- Paramount Skydance / Paramount Global 2024-12-31 original 10-K is marked `target_original_full_instance` for full-instance fallback from an amended or partial target.

## 仍需复核或未抽取项目

| Company | Metric | Status | Reason |
|---|---|---|---|
| Marriott International | B03 EBITDA margin | NOT_AVAILABLE_SEC | Required revenue, operating income, or D&A missing. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | C03 Executive compensation signals | NOT_EXTRACTED | No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; C03 degraded from previous ecd_fact_count. Next step: improve industry extractor, header mapping, or concept resolver. |
| Marriott International | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
| Southwest Airlines | D01 Risk factors summary | NOT_EXTRACTED | Risk factor heading or theme evidence. Next step: improve industry extractor, header mapping, or concept resolver. |
| Southwest Airlines | D02 Litigation disclosures | NOT_AVAILABLE_SEC | Legal proceedings or litigation text evidence. Next step: leave blank unless SEC source later discloses it. |
| Southwest Airlines | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Southwest Airlines | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Ford Motor Company | B06 Debt-to-equity | NEEDS_REVIEW | Captive finance segment/dimension detected; industrial-only debt-to-equity unavailable. Next step: manual review required before treating as numeric truth. |
| Ford Motor Company | B07 Interest coverage ratio | NOT_MEANINGFUL | Operating income is non-positive. Next step: improve the relevant industry extractor or source registry. |
| Ford Motor Company | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Ford Motor Company | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | B03 EBITDA margin | NOT_AVAILABLE_SEC | Required revenue, operating income, or D&A missing. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | B07 Interest coverage ratio | NOT_AVAILABLE_SEC | Operating income or interest expense missing. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | C01 CEO / CFO changes | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 5.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E03 Leadership departures | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 5.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | A08 Fee income vs interest income | NOT_EXTRACTED | Requires bank-specific revenue composition review. Next step: improve industry extractor, header mapping, or concept resolver. |
| JPMorgan Chase | A09 Non-performing loans / NPL ratio | NOT_EXTRACTED | Requires credit risk table or reviewed dimensions. Next step: improve industry extractor, header mapping, or concept resolver. |
| JPMorgan Chase | A10 Loan loss reserves | NOT_EXTRACTED | Requires allowance and loans denominator review. Next step: improve industry extractor, header mapping, or concept resolver. |
| JPMorgan Chase | A13 Geographic exposure | NOT_EXTRACTED | Requires geographic dimensions or segment table. Next step: improve industry extractor, header mapping, or concept resolver. |
| JPMorgan Chase | B08 Current ratio | N_A_STRUCTURAL | Bank current ratio is structurally not applicable. Next step: improve the relevant industry extractor or source registry. |
| JPMorgan Chase | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
| Salesforce | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Salesforce | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Lumen Technologies | B06 Debt-to-equity | NOT_AVAILABLE_SEC | Debt or equity missing. Next step: leave blank unless SEC source later discloses it. |
| Lumen Technologies | B07 Interest coverage ratio | NOT_MEANINGFUL | Operating income is non-positive. Next step: improve the relevant industry extractor or source registry. |
| Lumen Technologies | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Lumen Technologies | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Macy's | B06 Debt-to-equity | NOT_AVAILABLE_SEC | Debt or equity missing. Next step: leave blank unless SEC source later discloses it. |
| Macy's | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Macy's | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B01 Revenue | NOT_AVAILABLE_SEC | Revenue candidate chain from metric definition. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B02 Revenue YoY growth | NOT_MEANINGFUL | Successor/predecessor structure makes YoY not meaningful. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | B03 EBITDA margin | NOT_AVAILABLE_SEC | Required revenue, operating income, or D&A missing. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B04 Net income | NOT_AVAILABLE_SEC | Net income candidate chain from metric definition. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B05 Free cash flow | NOT_AVAILABLE_SEC | Capex chain allows PaymentsToAcquireProductiveAssets. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B06 Debt-to-equity | NOT_AVAILABLE_SEC | Debt or equity missing. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B07 Interest coverage ratio | NOT_AVAILABLE_SEC | Operating income or interest expense missing. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | C03 Executive compensation signals | NOT_EXTRACTED | No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; C03 degraded from previous ecd_fact_count. Next step: improve industry extractor, header mapping, or concept resolver. |
| Paramount Skydance / Paramount Global | C04 Auditor changes | NEEDS_REVIEW | 需复核: current auditor read from dei:AuditorName, but prior 10-K instance is missing or lacks AuditorName (prior_10k inventory row). Next step: manual review required before treating as numeric truth. |
| Paramount Skydance / Paramount Global | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
