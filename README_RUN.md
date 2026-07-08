# README_RUN

## 配置

- SEC HTTP 配置：`config/sec_config.json`。
- 所有时间戳使用 UTC；文本编码 UTF-8。
- 全局请求速率默认 5 requests/sec。

## 从干净目录运行 M0-M7

```bash
python3 scripts/00_smoke_test_sec_access.py
python3 scripts/01_resolve_companies.py
python3 scripts/02_inventory_filings.py
python3 scripts/03_companyfacts_inventory.py
python3 scripts/04_compute_standard_metrics.py
python3 scripts/05_fetch_accession_materials.py
python3 scripts/06_parse_xbrl_instances.py
python3 scripts/07_extract_8k_events.py
python3 scripts/08_extract_def14a.py
python3 scripts/09_extract_mda_and_risk_text.py
python3 scripts/10_run_golden_assertions.py
python3 scripts/11_build_report.py
```

M7 会先应用 bounded P0 local repair，然后生成 coverage、exceptions、repair validation、最终报告和本 README。

## 验收顺序

### 第一层：十家公司功能验收

```bash
python3 scripts/10_run_golden_assertions.py
python3 scripts/12_validate_repair.py
```

- `outputs/golden_results.csv` 必须全 PASS。
- 完整工作区 `outputs/repair_validation_results.csv` 必须全 PASS；轻量审核包中依赖 raw evidence / concept inventory 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`，总 gate 显示为 `PASS_LIGHT_REVIEW`。
- 轻量审核包必须在根目录包含 `LIGHT_REVIEW_PACKAGE.marker`；未声明的缺 evidence / concept inventory 工作区必须 `WORKSPACE_INCOMPLETE`。
- `metrics/evidence/coverage/report` 必须能互相追溯一致。

### 第二层：去公司特例验收

```bash
python3 tools/check_no_company_literals.py
```

- 生产 extractor 不得出现公司名业务分支。
- `config/`、`tests/fixtures/`、报告模板可以出现公司名。
- 自动审计使用 AST 扫描 Python literal，明细写入 `outputs/scalability_audit.csv`。

### 第三层：第 11 家公司测试

- 新增同行业公司只允许改 `config/company_registry.csv` 和 `tests/fixtures/`。
- 不允许为新增同行业公司改 `scripts/sec_pipeline.py`。
- `repair_validation_results.csv` 的 `eleventh_company_behavior_*` 必须 PASS。

失败时脚本 exit nonzero，并把逐项原因写入对应 outputs CSV。

## 本轮修复的请求边界

- Lodging B10/B11 使用表头映射抽取 RevPAR/Occupancy 绝对值；B12 RPO/cRPO 优先 instance fact；C03 PeoTotalCompAmt、FI A01/A02 ratio facts、coverage join、exceptions/report 更新。
- C04 只针对 AuditorName 对照补抓 SEC 官方 XBRL instance；所有请求仍通过 `SecHttpClient.fetch(...)` 写入 `evidence/requests_log.csv`。
- `outputs/stratified_audit.csv` 固化验收分层抽样：STD_XBRL/DERIVED、DIM_XBRL、DEF14A、MDA/TEXT、8K_ITEM。

## P0 validation 失败定位

- 先打开 `outputs/repair_validation_results.csv`，按 `check_id` 查看 FAIL 行。
- 对证据缺失类失败，按 `(company, metric_id)` join `outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。
- 对 C03 失败，检查 `outputs/concept_inventory/*_ecd.csv` 中目标 `period_end` 的 `PeoTotalCompAmt`。
- 对 FI Basel ratio 失败，检查对应 `outputs/concept_inventory/*_instance.csv` 的 ratio facts。
- 对请求边界失败，检查 `evidence/requests_log.csv` 的 URL、User-Agent 和 retry_attempt。

## 主要输出

- `outputs/metrics_matrix.csv`
- `outputs/metric_evidence.csv`
- `outputs/basel_ratio_candidates.csv`
- `outputs/governance_signals.csv`
- `outputs/coverage_matrix.csv`
- `outputs/exceptions_and_review_items.md`
- `outputs/repair_validation_results.csv`
- `outputs/stratified_audit.csv`
- `outputs/events.csv`
- `outputs/golden_results.csv`
- `REPORT_十公司财务指标.md`

## 轻量审核包

- 审核包只纳入代码、配置、fixture、关键 outputs 和报告；不纳入 `evidence/`、大体量 `outputs/concept_inventory/`、`__pycache__/` 或 `.DS_Store`。
- 轻量包中 `python3 scripts/12_validate_repair.py` 运行 `LIGHT_REVIEW_MODE`：可重跑代码级、矩阵级和随包 audit gate；缺 raw evidence 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`。
- 轻量包中 `python3 scripts/10_run_golden_assertions.py` 重算随包 `outputs/golden_results.csv` snapshot integrity，通过时输出 `PASS_LIGHT_GOLDEN_INTEGRITY`；完整数值 golden rerun 需要本地完整 `evidence/`。
- 包清单写入 `outputs/review_package_manifest.md`；压缩包写入 `outputs/review_package/`。
- 若审核官需要追溯 raw SEC source，回到本地完整工作区读取 `evidence/` 和 `outputs/concept_inventory/`。
