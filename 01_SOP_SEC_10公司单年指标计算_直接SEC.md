# 01｜SOP：基于 SEC 官方数据的十公司单年财务指标计算

版本：v1.1  
用途：指导一次可审计的 SEC 语义层计算任务。  
任务目标：对 10 家不同行业公司，计算最近一个已申报财年的财务、治理、风险和事件指标，输出带证据链的指标矩阵。  
任务边界：这是一次指标计算 spike，不是报价模型、生产调度系统或前端产品。

> **文档定位：当前业务方法规范 / 概念流程。**
>
> 本文的 M0–M7 表达业务方法阶段，不与 `scripts/00_*` 至 `scripts/12_*` 一一映射。当前物理执行顺序、终态验收和失败定位以 `SOP.md`、`README_RUN.md`、`TESTING.md` 为准；当前运行状态以 `outputs/validation_run_manifest.json`、`python3 tools/check_validation_snapshot.py` 和报告共同判断。

---

## 1. 成功标准

本任务不以“所有指标都有数值”为成功标准。成功标准是：

```text
每家公司 × 每个指标 = value / status / formula / source / evidence / confidence
```

允许出现以下合法结论：

```text
OK                         标准 XBRL / companyfacts 可直接计算
OK_APPROX                  有可解释近似口径
DIM_XBRL_OK                来自 accession XBRL/iXBRL instance 的维度事实
MDA_OK                     来自 MD&A / EX-99 表格或文本
DEF14A_OK                  来自 DEF 14A / ecd XBRL / 委托书文本
8K_ITEM_OK                 来自 8-K item
TEXT_QUAL                  定性文本结论
NOT_AVAILABLE_SEC          SEC filing 中未披露
NOT_EXTRACTED              可能披露在文本/表格中，但本轮未能可靠抽取
NOT_MEANINGFUL             结构上无意义，例如亏损年利息覆盖率
N_A_STRUCTURAL             行业结构不适用，例如银行 current ratio
PARSE_FAILED               本应可解析但解析失败
NEEDS_REVIEW               需要人工复核
```

禁止为了填满矩阵而猜数。任何数字都必须可追溯到 SEC 原始响应、accession、XBRL concept 或文本片段。

---

## 2. 数据入口选择

### 2.1 本任务使用 companyfacts 和 submissions 作为主入口

本任务是固定 10 家公司的单年计算，不是全市场每日增量更新。因此不需要以 daily index 作为主入口。推荐入口是：

```text
公司 seed list
-> SEC submissions endpoint 定位最新 10-K / 10-K/A / DEF 14A / 财年窗口内 8-K
-> SEC companyfacts endpoint 计算标准 XBRL 指标
-> 必要时进入 accession materials，解析 XBRL/iXBRL instance、FilingSummary.xml、.hdr.sgml、primary document、MD&A、DEF 14A、8-K
```

原因：daily index 的价值是“全市场某一天谁提交了什么”，适合 daily update 产品；本任务的输入是固定公司清单，直接从每个公司的 submissions history 和 companyfacts 更省工程量。

### 2.2 不能只依赖 companyfacts

companyfacts 适合计算公司级、标准 taxonomy、entire-entity 层面的事实，例如 revenue、net income、assets、cash、liabilities。它不能覆盖所有指标：

- 维度事实需要解析 10-K / 10-Q 的 XBRL/iXBRL instance，例如 JPM 资本比率、Ford 工业/金融债务、Salesforce cRPO。
- 行业 KPI 往往在 MD&A 或 EX-99 中，例如 Marriott RevPAR / occupancy、JPM LCR / AUM / VaR。
- 治理和薪酬需要 DEF 14A。
- 事件信号需要 8-K item。
- 风险因素、诉讼、监管调查、going concern 需要文本章节。

因此本任务是“companyfacts-first, accession-aware”的架构。

---

## 3. SEC 访问规则

Codex 直接访问 SEC 官方 endpoint。所有请求必须：

```text
User-Agent: <organization> <contact email>
每个 SecHttpClient 实例在进程内默认节流至 <= 5 req/s；不同 client 或进程不协调限速
遇到 403 / 429 / 5xx 指数退避
禁止隐式跟随 HTTP redirect；下一跳必须重新显式校验
所有请求记录到 evidence/requests_log.csv
requests_log_manifest.json 绑定 CSV schema、row count 与整表 SHA-256
所有原始响应保存 immutable body/header attempt，或记录 hash / status / size / URL
```

不得使用第三方数据源、新闻网站、搜索结果、金融数据商或模型记忆补数。

---

## 4. 目标公司与报告期

| # | 公司 | CIK seed | SIC | 财年底 | 报告期口径 |
|---:|---|---:|---:|---|---|
| 1 | Marriott International | 1048286 | 7011 | 1231 | FY2025 |
| 2 | Southwest Airlines | 92380 | 4512 | 1231 | FY2025 |
| 3 | Ford Motor Company | 37996 | 3711 | 1231 | FY2025 |
| 4 | Pfizer | 78003 | 2834 | 1231 | FY2025 |
| 5 | JPMorgan Chase | 19617 | 6021 | 1231 | FY2025 |
| 6 | Salesforce | 1108524 | 7372 | 0131 | FY2026，period end 约 2026-01-31 |
| 7 | Lumen Technologies | 18926 | 4813 | 1231 | FY2025 |
| 8 | Macy's | 794367 | 5311 | 0201 | 使用最新 10-K reportDate |
| 9 | Paramount Skydance / Paramount Global | 2041610 + 813828 | 4833 | 1231 | FY2025；事件扫描跨 successor/predecessor CIK；YoY 可能不可比 |
| 10 | Enphase Energy | 1463101 | 3674 | 1231 | FY2025 |

CIK seed 必须通过 submissions endpoint 验证。若 SEC 返回公司身份、名称、财年底、entityType 与预期不一致，必须在 `company_resolution.csv` 和报告中说明。

---

## 5. 标准目录结构

Codex 应创建一个自包含项目：

```text
scripts/
  sec_http.py
  sec_urls.py
  git_workspace.py
  validation_provenance.py
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
  raw/
  accession_materials/
  companyfacts/
  submissions/
  xbrl_instances/
  def14a/
  mda_text/
  request_attempts/
  requests_log.csv
  requests_log_manifest.json

outputs/
  company_resolution.csv
  latest_filings_inventory.csv
  companyfacts_inventory/
  metrics_matrix.csv
  metric_evidence.csv
  coverage_matrix.csv
  companyfacts_crosscheck.csv
  events.csv
  governance_signals.csv
  risk_legal_signals.csv
  golden_results.csv
  golden_candidates.csv
  exceptions_and_review_items.md
  repair_validation_results.csv
  validation_run_manifest.json
  validation_snapshot_provenance.json
  stratified_audit.csv

tools/
  check_no_company_literals.py
  check_capability_contract_alignment.py
  check_validation_snapshot.py

REPORT_十公司财务指标.md
README_RUN.md
```

---

## 6. 阶段流程

> **阶段映射说明：** M0–M7 是业务概念阶段。物理脚本是 00–12；尤其 M7 中的 report build 与 terminal validation 在当前实现中分别由 stage 11 和 stage 12 承担，不能把 M7、stage 11、stage 12 当成同一状态。

### M0：SEC 连接与公司身份解析

目标：确认能访问 SEC，解析 10 家公司身份。

Codex 要做：

1. 请求 `company_tickers_exchange.json`。
2. 对 10 家公司请求 submissions JSON。
3. 记录 entityType、sic、fiscalYearEnd、tickers、exchanges、name、formerNames。
4. 输出 `company_resolution.csv`。
5. 若 CIK、财年底、公司名称或 successor/predecessor 关系有异常，写入 `exceptions_and_review_items.md`。

### M1：定位最新申报材料

目标：确认每家公司用于计算的 filings。

Codex 要做：

1. 从 submissions 中定位最新 10-K / 10-K/A。
2. 定位上一财年 10-K，用于 YoY 和平均余额。
3. 定位最新 DEF 14A。
4. 定位报告期窗口内全部 8-K。
5. 对 Paramount 类 successor/predecessor 情形，事件扫描必须覆盖两个 CIK 的相关期间。
6. 输出 `latest_filings_inventory.csv`。

### M2：companyfacts 标准指标

目标：先用 companyfacts 计算标准、公司级指标。

Codex 要做：

1. 对每家公司请求 companyfacts JSON。
2. 原始 JSON 保存到 evidence。
3. 生成 concept inventory：taxonomy、concept、unit、form、period、accn、filed、fp、fy。
4. 按《02 指标定义》的候选链计算标准指标。
5. 所有命中的 tag 必须写入 `metric_evidence.csv`。

### M3：accession instance 维度与自定义事实

目标：补足 companyfacts 无法覆盖的维度、自定义、DEI/ecd facts。

Codex 要做：

1. 下载最新 10-K accession directory index、FilingSummary.xml、XBRL/iXBRL instance。
2. 大实例必须流式解析。
3. 保留每条事实的 context、period、unit、dimensions。
4. 用于 JPM 资本比率、Ford 债务维度、Salesforce RPO/cRPO、AuditorName、本地 custom facts 等。

### M4：8-K 事件信号

目标：抽取财年窗口内事件信号。

Codex 要做：

1. 对每个 8-K 下载 `.hdr.sgml`。
2. 解析 `<ITEMS>`。
3. 若 `<ITEMS>` 缺失，fallback 到 complete text header 或 primary document headings。
4. 一份 8-K 可对应多个 item。
5. 输出 `events.csv`。

用于：CEO/CFO changes、M&A、bankruptcy、leadership departures、restatements、material agreements。8-K Item 4.01 可以作为事件上下文，但当前 C04 审计师变更指标的权威重放路径是 current/prior 10-K 官方 DEI `AuditorName` 比较，不由 8-K item 单独决定。

### M5：DEF 14A 治理与薪酬

目标：处理董事会构成和高管薪酬信号。

Codex 要做：

1. 定位最新 DEF 14A。
2. 若存在 ecd XBRL instance，dump ecd namespace facts。
3. 尝试抽取 CEO 年度总薪酬。
4. 董事会构成本轮允许 TEXT_QUAL 或 NEEDS_REVIEW。

### M6：MD&A / EX-99 / 风险法律文本

目标：抽取行业 KPI 和文本类风险。

Codex 要做：

- Marriott：从 10-K Lodging Statistics 或 EX-99 表格抽取 occupancy / RevPAR，优先使用 Comparable Systemwide Properties / Worldwide 绝对值，不能把 RevPAR growth 当作 USD。
- Salesforce：ARR/churn，若未披露则用 RPO/cRPO 替代并明确不是 ARR。
- JPM：LCR、AUM、VaR、平均生息资产。
- 10-K Item 1A：风险因素。
- Item 3 / contingencies：诉讼。
- 监管调查关键词。
- going concern 概念和审计意见关键词。

所有文本/表格抽取必须保存原文片段。

### M7：组装矩阵、断言和报告

目标：输出完整交付物；本概念阶段在物理实现中跨越 stage 10、11、12。

Codex 要做：

1. 合并 `metrics_matrix.csv`。
2. 生成 `coverage_matrix.csv`。
3. 运行 golden assertions。
4. 运行 repair validation。
5. 生成分层抽样 `stratified_audit.csv`。
6. 生成 `REPORT_十公司财务指标.md`。
7. 给出 `GO / GO WITH CAVEATS / NO-GO`。
8. stage 11 exit 0 只表示报告构建完成；完整终态必须由 stage 12 exit 0、terminal manifest 和 snapshot checker 共同证明。

---

## 7. 证据链要求

每个数值必须具备：

```text
company
cik
metric_id
metric_name
value
unit
period_start
period_end
fiscal_year
fiscal_period
source_class
source_url
repo_relative_path
content_sha256
document_name
accession
form
filed_date
concept_or_section
context_or_dimension
formula
confidence
status
notes
```

文本/表格抽取必须额外具备：

```text
document_url
section_name
evidence_quote
extraction_method
```

无证据链的数值视为失败。历史 `local_path` / `source_path` 只能作为 relocation hint，不能作为跨 clone 的权威地址。

---

## 8. 质量控制

### 8.1 Golden assertions

Golden assertions 是防止“代码跑通但数字错”的核心机制。期望集合和锁定值必须独立于本次实际输出，失败时不得自动改写 expected。当前 stage logic 仍集中在 `sec_pipeline.py`，full Golden 也可能访问官方 SEC companyconcept；因此“物理模块完全独立”是目标架构，不是当前已实现事实。当前应依赖锁定 fixture、exact-set 校验、独立重算和对抗测试证明断言不是循环自证。

规则：

```text
断言失败 = 停机报告实际值
不得自动修改期望值
不得硬编码输出矩阵绕过计算
不得用持久化 PASS 字符串替代重新计算
```

### 8.2 Coverage matrix

Coverage matrix 必须回答：

```text
哪些指标可由 companyfacts 计算
哪些指标必须解析 instance
哪些指标必须读 MD&A / DEF14A / 8-K
哪些指标 SEC 未披露
哪些指标行业不适用
哪些指标需要人工复核
```

---

## 9. 完成定义

任务完成必须同时满足：

1. 10 家公司身份解析完成。
2. 最新 10-K / prior 10-K / DEF 14A / 8-K inventory 完成。
3. 每家公司每个指标都有 value 或明确 status。
4. 每个数值有证据链。
5. Golden assertions 输出并通过，或失败后停机报告实际值。
6. coverage matrix 完整。
7. exceptions_and_review_items.md 清楚列出所有未解决问题。
8. 最终报告区分“直接计算值”“近似值”“文本抽取值”“不可得值”。
9. stage 12 独立 gate 退出 0，terminal manifest 为允许的成功状态。
10. `python3 tools/check_validation_snapshot.py` 证明 source-input tree 与关键 artifact bytes 未漂移；否则当前 snapshot 不可验收。
