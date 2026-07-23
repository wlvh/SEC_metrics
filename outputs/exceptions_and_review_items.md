# Exceptions and Review Items

Generated UTC: 2026-07-22T19:00:52.503480+00:00

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
| Marriott International | B06 Debt-to-equity | NOT_MEANINGFUL | Equity is negative; debt/equity ratio is not economically meaningful. Total debt candidate=16204000000. Tier 1 direct total debt selected; no adders applied. Next step: improve the relevant industry extractor or source registry. |
| Marriott International | C03 Executive compensation signals | NOT_EXTRACTED | No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; C03 degraded from previous ecd_fact_count. Next step: improve industry extractor, header mapping, or concept resolver. |
| Marriott International | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Marriott International | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
| Southwest Airlines | D01 Risk factors summary | NOT_EXTRACTED | Risk factor heading or theme evidence. Next step: improve industry extractor, header mapping, or concept resolver. |
| Southwest Airlines | D02 Litigation disclosures | NOT_AVAILABLE_SEC | Legal proceedings or litigation text evidence. Next step: leave blank unless SEC source later discloses it. |
| Southwest Airlines | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Southwest Airlines | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Ford Motor Company | B06 Debt-to-equity | NEEDS_REVIEW | Main debt/equity value is blank because captive finance segment/dimension was detected; consolidated candidate is retained only in evidence and sidecar with candidate_role. Next step: manual review required before treating as numeric truth. |
| Ford Motor Company | B07 Interest coverage ratio | NOT_MEANINGFUL | Operating income is non-positive. Next step: improve the relevant industry extractor or source registry. |
| Ford Motor Company | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Ford Motor Company | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | C01 CEO / CFO changes | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 5.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E03 Leadership departures | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 5.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Pfizer | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | A09 Non-performing loans / NPL ratio | NOT_EXTRACTED | Requires credit risk table or reviewed dimensions. Next step: improve industry extractor, header mapping, or concept resolver. |
| JPMorgan Chase | A13 Geographic exposure | NOT_EXTRACTED | Requires geographic dimensions or segment table. Next step: improve industry extractor, header mapping, or concept resolver. |
| JPMorgan Chase | B08 Current ratio | N_A_STRUCTURAL | Bank current ratio is structurally not applicable. Next step: improve the relevant industry extractor or source registry. |
| JPMorgan Chase | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| JPMorgan Chase | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
| Salesforce | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Salesforce | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Lumen Technologies | B06 Debt-to-equity | NOT_MEANINGFUL | Equity is negative; debt/equity ratio is not economically meaningful. Total debt candidate=17441000000. Tier 1 direct total debt selected; no adders applied. Next step: improve the relevant industry extractor or source registry. |
| Lumen Technologies | B07 Interest coverage ratio | NOT_MEANINGFUL | Operating income is non-positive. Next step: improve the relevant industry extractor or source registry. |
| Lumen Technologies | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Lumen Technologies | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Macy's | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Macy's | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | B01 Revenue | NOT_MEANINGFUL | successor stub period 2025-08-08 to 2025-12-31; annual metric not comparable. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | B02 Revenue YoY growth | NOT_MEANINGFUL | successor stub period 2025-08-08 to 2025-12-31; annual metric not comparable. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | B03 EBITDA margin | NOT_MEANINGFUL | successor stub period 2025-08-08 to 2025-12-31; annual metric not comparable. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | B04 Net income | NOT_MEANINGFUL | successor stub period 2025-08-08 to 2025-12-31; annual metric not comparable. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | B05 Free cash flow | NOT_MEANINGFUL | successor stub period 2025-08-08 to 2025-12-31; annual metric not comparable. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | B07 Interest coverage ratio | NOT_MEANINGFUL | successor stub period 2025-08-08 to 2025-12-31; annual metric not comparable. Next step: improve the relevant industry extractor or source registry. |
| Paramount Skydance / Paramount Global | C03 Executive compensation signals | NOT_EXTRACTED | No numeric ecd:PeoTotalCompAmt fact matched target fiscal year; C03 degraded from previous ecd_fact_count. Next step: improve industry extractor, header mapping, or concept resolver. |
| Paramount Skydance / Paramount Global | C04 Auditor changes | NEEDS_REVIEW | 需复核: current auditor read from dei:AuditorName, but prior 10-K has missing or blank AuditorName (prior_10k inventory row). Next step: manual review required before treating as numeric truth. |
| Paramount Skydance / Paramount Global | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Paramount Skydance / Paramount Global | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E01 M&A announcements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no M&A item rule matched. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E02 Bankruptcy filings | NOT_AVAILABLE_SEC | No Item 1.03 in FY-window 8-K; zero is normal. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E04 Financial restatements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 4.02 found. Next step: leave blank unless SEC source later discloses it. |
| Enphase Energy | E05 Material agreements | NOT_AVAILABLE_SEC | FY-window 8-K scanned; no item 1.01 found. Next step: leave blank unless SEC source later discloses it. |
