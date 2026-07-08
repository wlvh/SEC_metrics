## 你的角色

你在执行一次 SEC 语义层计算 spike。目标是：直接连接 SEC 官方 endpoint，对 10 家公司计算最近一个已申报财年的财务、治理、风险和事件指标，输出可审计的指标矩阵、证据文件和中文报告。

你不是在开发生产系统、报价模型、前端或 daily update 调度。你可以写临时脚本、使用 SQLite/DuckDB/CSV，但最终交付必须围绕“指标计算 + 证据链 + 验收断言”。

---

# 0. 硬约束

1. 所有 SEC 请求必须带 `User-Agent: "<Org> <email>"`，通过配置提供。
2. 全局请求速率默认 <= 5 requests/sec。
3. 遇到 403 / 429 / 5xx，指数退避重试。
4. 所有请求写入 `evidence/requests_log.csv`。
5. 所有原始响应必须落盘，或至少保存 URL、status、headers、content length、hash、sample path。
6. 所有数值必须来自本次 SEC 原始响应，不得使用模型记忆、新闻、第三方数据或搜索摘要补数。
7. 每个数值必须有证据三件套：`accession + concept_or_section + context_or_dimension`。
8. 找不到数据时输出状态，不得猜数。
9. Golden assertion 失败必须停机报告实际值，不得自动修改期望值。
10. 大 XBRL/iXBRL instance 必须流式解析，不得整树加载。
11. 指标口径、候选链、状态枚举以 `02_指标定义_SEC_10公司单年指标.md` 为准。

---

# 1. SEC endpoints

使用以下官方数据源：

```text
company tickers:
https://www.sec.gov/files/company_tickers_exchange.json

submissions:
https://data.sec.gov/submissions/CIK##########.json

companyfacts:
https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json

accession directory:
https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/index.json

hdr.sgml:
https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/{accession}.hdr.sgml

filing detail page:
https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/{accession}-index.html

FilingSummary.xml:
https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dash}/FilingSummary.xml
```

CIK 必须按 endpoint 要求补 10 位。

---

# 2. 目标公司

| # | 公司 | CIK seed | 财年底 | 报告期 |
|---:|---|---:|---|---|
| 1 | Marriott International | 1048286 | 1231 | FY2025 |
| 2 | Southwest Airlines | 92380 | 1231 | FY2025 |
| 3 | Ford Motor Company | 37996 | 1231 | FY2025 |
| 4 | Pfizer | 78003 | 1231 | FY2025 |
| 5 | JPMorgan Chase | 19617 | 1231 | FY2025 |
| 6 | Salesforce | 1108524 | 0131 | FY2026 |
| 7 | Lumen Technologies | 18926 | 1231 | FY2025 |
| 8 | Macy's | 794367 | 0201 | 最新 10-K reportDate |
| 9 | Paramount Skydance / Paramount Global | 2041610 + 813828 | 1231 | FY2025；事件跨 CIK；YoY 可能不可比 |
| 10 | Enphase Energy | 1463101 | 1231 | FY2025 |

M0 必须验证 CIK、name、sic、fiscalYearEnd、entityType、tickers、exchanges、formerNames。

---

# 3. 项目结构

创建：

```text
scripts/
  sec_http.py
  sec_urls.py
  00_smoke_test_sec_access.py
  01_resolve_companies.py
  02_inventory_filings.py
  03_companyfacts_inventory.py
  04_compute_standard_metrics.py
  05_fetch_accession_materials.py
  06_parse_xbrl_instances.py
  07_extract_8k_events.py
  08_extract_def14a.py
  09_extract_mda_and_risk_text.py
  10_run_golden_assertions.py
  11_build_report.py
  12_validate_repair.py

evidence/
  requests_log.csv
  company_tickers/
  submissions/
  companyfacts/
  accession_materials/
  xbrl_instances/
  def14a/
  mda_text/

outputs/
  company_resolution.csv
  latest_filings_inventory.csv
  metrics_matrix.csv
  metric_evidence.csv
  events.csv
  governance_signals.csv
  risk_legal_signals.csv
  companyfacts_crosscheck.csv
  coverage_matrix.csv
  golden_results.csv
  golden_candidates.csv
  repair_validation_results.csv
  stratified_audit.csv
  exceptions_and_review_items.md
  concept_inventory/

REPORT_十公司财务指标.md
README_RUN.md
```

---

# 4. 里程碑

## M0：SEC 连接和公司解析

运行：

```bash
python scripts/00_smoke_test_sec_access.py
python scripts/01_resolve_companies.py
```

要求：

1. 成功请求 company_tickers_exchange.json。
2. 成功请求 10 家 submissions JSON。
3. 输出 `outputs/company_resolution.csv`。
4. 对每家公司记录 name、cik、entityType、sic、fiscalYearEnd、tickers、exchanges、formerNames。
5. 执行结构类 golden assertions。

## M1：定位 filings

运行：

```bash
python scripts/02_inventory_filings.py
```

要求输出 `latest_filings_inventory.csv`，至少包含：

```text
company, cik, form, accession, filingDate, reportDate, primaryDocument, isXBRL, isInlineXBRL, source_role
```

必须定位：

- 最新 10-K / 10-K/A；
- 上一财年 10-K；
- 最新 DEF 14A；
- 财年窗口内全部 8-K；
- Paramount 相关事件跨 successor/predecessor CIK。

## M2：companyfacts 标准指标

运行：

```bash
python scripts/03_companyfacts_inventory.py
python scripts/04_compute_standard_metrics.py
```

要求：

1. 每家公司请求并保存 companyfacts JSON。
2. 生成 `outputs/concept_inventory/{company}_companyfacts.csv`。
3. 计算所有可由 companyfacts 支持的标准指标。
4. 每个指标记录命中 tag、unit、period、accession、filed date。
5. Enphase / Ford 数值 golden 必须由管道复现，不得硬编码。

## M3：accession instance 维度和自定义事实

运行：

```bash
python scripts/05_fetch_accession_materials.py
python scripts/06_parse_xbrl_instances.py
```

要求：

1. 对最新 10-K 下载 accession directory index、filing detail、FilingSummary.xml、XBRL/iXBRL instance。
2. 流式解析 instance。
3. 输出 `outputs/concept_inventory/{company}_instance.csv`，包含 namespace、concept、unit、context、dimensions、period。
4. 完成 JPM A01/A02/A13、Ford B06、Salesforce B12、AuditorName 等 companyfacts 不足的项目。

## M4：8-K 事件

运行：

```bash
python scripts/07_extract_8k_events.py
```

要求：

1. 对财年窗口内所有 8-K 下载 `.hdr.sgml`。
2. 解析所有 `<ITEMS>`。
3. 若 `<ITEMS>` 缺失，fallback 到 complete text header 或 primary headings。
4. 输出 `outputs/events.csv`。
5. events.csv 支持一份 8-K 多个 item。

## M5：DEF 14A 治理和薪酬

运行：

```bash
python scripts/08_extract_def14a.py
```

要求：

1. 定位最新 DEF 14A。
2. 若存在 ecd XBRL，dump ecd facts。
3. 尝试抽取 CEO total compensation。
4. 董事会构成至少给出 TEXT_QUAL / NEEDS_REVIEW。

## M6：MD&A / EX-99 / 风险法律文本

运行：

```bash
python scripts/09_extract_mda_and_risk_text.py
```

要求：

1. Marriott occupancy / RevPAR：优先从 10-K Lodging Statistics 或 EX-99 表格抽取 Comparable Systemwide Properties / Worldwide 绝对值，不得把 RevPAR growth 当作 USD。
2. JPM LCR / AUM / VaR / average earning assets。
3. Salesforce ARR/churn 或 RPO/cRPO 替代。
4. Risk factors、litigation、regulatory investigation、going concern。
5. 每个文本/表格指标附原文片段。

## M7：组装、断言、报告

运行：

```bash
python scripts/10_run_golden_assertions.py
python scripts/12_validate_repair.py
python scripts/11_build_report.py
```

要求：

1. 输出 metrics_matrix、coverage_matrix、companyfacts_crosscheck、golden_results、repair_validation_results、stratified_audit、exceptions、报告。
2. 报告给出 `GO / GO WITH CAVEATS / NO-GO`。
3. 所有输出必须可由 evidence 复算。

---

# 5. Golden assertions

## G1：公司结构断言

- Marriott CIK == 1048286。
- Southwest CIK == 92380。
- Ford CIK == 37996。
- Pfizer CIK == 78003。
- JPMorgan CIK == 19617。
- Salesforce CIK == 1108524，fiscalYearEnd == `0131`。
- Lumen CIK == 18926。
- Macy's CIK == 794367，fiscalYearEnd == `0201`。
- Enphase CIK == 1463101。
- Paramount successor/predecessor 关系必须在 company_resolution 中说明；若 2041610 或 813828 不符合预期，停机报告。

## G2：JPM / Ford / AuditorName 结构断言

这些断言用于防止错误使用 companyfacts：

- JPM `AssetsCurrent` companyconcept 可不可用，实际结果必须记录；若 404，JPM B08 应为 `N_A_STRUCTURAL`。
- JPM CET1 / Tier 1 entity-level facts 若缺失或停更，必须走 DIM_XBRL 或 MDA。
- Ford entity-level debt concepts 若缺失，不得硬凑 B06；必须解析 instance dimensions 或标 `NEEDS_REVIEW`。
- AuditorName 必须从 accession instance 或 filing material 获取，不得假设 companyfacts 一定有。

## G3：Enphase FY2025 数值断言

目标 accession 预期：`0001463101-26-000013`。由管道独立复现：

```text
Revenue = 1,472,985,000
Prior-year revenue = 1,330,383,000
Net income = 172,133,000
Operating income = 157,526,000
D&A = 80,645,000
Operating cash flow = 136,540,000
Capex = 40,639,000
Current assets = 2,606,860,000
Current liabilities = 1,262,150,000
Cash = 474,318,000
Equity = 1,087,023,000
Total assets = 3,509,792,000
Long-term debt = 1,204,377,000
EBITDA = 238,171,000
FCF = 95,901,000
Current ratio ≈ 2.07 ± 0.01
Debt-to-equity ≈ 1.11 ± 0.01
```

Revenue tag 必须记录为实际命中 tag，预期为 `RevenueFromContractWithCustomerExcludingAssessedTax`。

## G4：Ford FY2025 数值断言

目标 accession 预期：`0000037996-26-000015`。由管道独立复现：

```text
Revenue = 187,267,000,000
Prior-year revenue = 184,992,000,000
Operating income = -9,169,000,000
D&A = 15,974,000,000
Operating cash flow = 21,282,000,000
Capex = 8,815,000,000
Current assets = 123,487,000,000
Current liabilities = 114,890,000,000
Cash = 23,356,000,000
Equity = 35,952,000,000
Interest expense = 1,254,000,000
B07 interest coverage status = NOT_MEANINGFUL or equivalent because operating income < 0
```

Capex tag 预期可命中 `PaymentsToAcquireProductiveAssets`。若实际 tag 不同，停机报告。

## G5：Tier-2 golden candidates

对除 Enphase / Ford 外的其余 8 家，每家公司输出 3 个候选值：

```text
Revenue
Net income
Total assets
```

每个候选值必须带 accession、concept、period、unit、filed date，写入 `golden_candidates.csv` 供人工核值。

---

# 6. 输出 schema

## outputs/metrics_matrix.csv

```text
company,cik,metric_id,metric_name,value,unit,status,source_class,formula,period_start,period_end,fiscal_year,fiscal_period,accession,form,filed_date,concept_or_section,context_or_dimension,confidence,notes
```

## outputs/metric_evidence.csv

```text
company,cik,metric_id,source_url,local_path,accession,document_name,concept_or_section,context_or_dimension,unit,period_start,period_end,value_raw,value_normalized,evidence_quote,extraction_method,parser_version
```

## outputs/events.csv

```text
company,cik,accession,filing_date,item_code,item_source,mapping_method,confidence,brief,source_url,local_path
```

## outputs/coverage_matrix.csv

```text
company,metric_id,status,source_class,has_numeric_value,has_evidence,needs_text_extraction,needs_review,reason
```

## outputs/companyfacts_crosscheck.csv

```text
company,cik,metric_id,accession,companyfacts_value,instance_value,match_status,reason
```

## outputs/golden_results.csv

```text
assertion_id,description,expected,actual,status,evidence_path,notes
```

## outputs/repair_validation_results.csv

```text
check_id,severity,status,details
```

## outputs/stratified_audit.csv

```text
audit_id,source_bucket,company,metric_id,metric_name,value,unit,status,source_class,period_start,period_end,accession,concept_or_section,context_or_dimension,evidence_value,evidence_unit,evidence_quote,audit_verdict,audit_notes
```

---

# 7. 最终报告要求

`REPORT_十公司财务指标.md` 必须包含：

1. Executive Summary。
2. 数据来源和请求统计。
3. 公司身份解析表。
4. 指标覆盖率摘要。
5. 十公司指标矩阵摘要。
6. FI track：JPM 指标解释。
7. Non-FI track：标准财务指标、派生指标、行业 KPI。
8. Governance / Risk / Event signals 摘要。
9. Enphase 和 Ford golden assertion 结果。
10. Repair validation 结果。
11. 分层抽样 audit 结果。
12. `NOT_AVAILABLE_SEC`、`NOT_EXTRACTED`、`NEEDS_REVIEW` 清单。
13. 哪些指标可产品化，哪些不能。
14. `GO / GO WITH CAVEATS / NO-GO`。

---

# 8. 完成条件

全部满足才算完成：

1. M0–M7 均运行完成。
2. 所有 SEC 请求写入 requests_log。
3. 10 家 company_resolution 完成。
4. latest_filings_inventory 包含 10-K、prior 10-K、DEF14A、8-K inventory。
5. metrics_matrix 覆盖全部指标。
6. metrics_matrix 每格都有合法 status。
7. 所有数值都有 evidence。
8. events.csv 覆盖所有公司财年窗口内 8-K。
9. Enphase / Ford golden assertions 通过，或失败后停机报告实际值。
10. repair_validation_results 全 PASS；若有 FAIL，报告 verdict 必须 NO-GO。
11. stratified_audit 覆盖分层有值格抽查并全部 PASS。
12. golden_candidates 包含其余 8 家 × 3 候选值。
13. 报告列明所有不可得和需要复核事项。
14. 未构建生产系统。
