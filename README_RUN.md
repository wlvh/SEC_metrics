# README_RUN

<!-- validation-reading-routes:start -->
## 只读取现有结果

1. 先读 `outputs/validation_run_manifest.json`；`result` 不是 `PASSED` / `PASSED_WITH_CAVEATS` 时停止验收。
2. 运行 `python3 tools/check_validation_snapshot.py`；缺少 provenance、源输入树不一致、关键 artifact hash 失配或 source input 有未提交改动时停止验收。
3. 再读 `REPORT_十公司财务指标.md`，随后按需查看 `outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。
4. `source_commit` 与当前 HEAD 不同不自动等于失败；只有独立 checker 证明 source-input tree 等价时，merge commit 等 SHA 变化才可接受。

## 执行新批次

1. 使用干净 checkout，并配置有效 SEC organization/contact email。
2. 按顺序运行阶段 `00`–`11`；stage 11 exit 0 只表示报告构建完成。
3. 单独运行 `python3 scripts/12_validate_repair.py`。
4. 只有 stage 12 exit 0、terminal manifest 成功，且 `python3 tools/check_validation_snapshot.py` 通过，才构成完整批次成功。

## Validation snapshot provenance

- stage 11 在修改报告前删除可安全识别的旧 regular `outputs/validation_snapshot_provenance.json`；alias/非 regular 目标提前失败。
- `config/validation_source_policy.json` 分类 runtime source、acceptance source、generated artifact、发布治理和解释性文档；SOP 权威引用必须有明确角色，解释性非权威文档不能作为运行权威。
- stage 12 只在 policy-defined source closure 无未提交改动时继续；成功后绑定当前 Git commit、完整 source-input tree SHA-256，以及 manifest、报告、README、metrics/evidence/coverage/Golden、request ledger 与 refreshed validation artifact 的 SHA-256/size。
- 提交或 merge 导致 commit SHA 改变时，checker 只有在完整 source-input tree 仍等价时才给 warning 并允许继续；任一 source byte 或 artifact byte 漂移都失败。
- light package 可以生成显式 `LIGHT_PACKAGE_NO_GIT` 的受限 provenance，但不能升级为 full validation。
<!-- validation-reading-routes:end -->

## 配置

- 运行时支持 POSIX 本地文件系统上的 Python 3.9+。
- SEC HTTP 配置：`config/sec_config.json`。
- 所有时间戳使用 UTC；文本编码 UTF-8。
- 单个 `SecHttpClient` 实例执行进程内请求节流，默认 5 requests/sec；
  不同 client 或进程之间不协调限速；同一 repository 的 request log
  publication 会在 cooperating threads / POSIX processes 间串行化，不承诺网络文件系统锁语义。
- immutable response 防预存和最终文件名 symlink/hardlink 别名，但假设单次写入期间父目录 namespace 稳定；它不是 WORM 存储。
- `SecHttpClient` 不自动跟随 HTTP redirect；首跳 3xx body、headers、Location 与日志会保留，目标 URL 只能作为下一次显式、重新校验的请求。

## 从干净目录运行阶段 00-11

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

阶段 11 的 bounded repair primarily uses local artifacts, but C04 AuditorName repair only fetches the next official SEC candidate while all ordered local facts remain unavailable.
随后阶段 11 生成 coverage、exceptions、validation run manifest、repair validation、最终报告和本 README。

## 验收顺序

### 第一层：十家公司功能验收

```bash
python3 scripts/10_run_golden_assertions.py
python3 scripts/12_validate_repair.py
python3 tools/check_validation_snapshot.py
```

- `outputs/golden_results.csv` 必须与配置/generator/fixture 推导的 assertion exact set 一致、唯一且全 PASS。
- `outputs/stratified_audit.csv` 必须与当前 metrics 推导的五层 deterministic sample exact set 一致且唯一。
- 完整工作区 `outputs/repair_validation_results.csv` 必须全 PASS；轻量审核包中依赖 raw evidence / concept inventory 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`；full gate 本身也不能写成 PASS。
- validation status 只使用 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。缺材料不能写成 PASS。
- 轻量审核包必须在根目录包含 `LIGHT_REVIEW_PACKAGE.marker`；未声明的缺 evidence / concept inventory 工作区必须 `WORKSPACE_INCOMPLETE`。
- full 模式中的关键 `NOT_EVALUATED_MISSING_EVIDENCE` 阻止 GO；light 模式只能把它作为显式 caveat。
- 先读 `outputs/validation_run_manifest.json` 判断本次真正刷新的 validation artifact；旧文件存在不代表本次已评估。
- 阶段 11/12 的报告写入成功后才发布 terminal manifest；写入失败必须保持 `IN_PROGRESS`。
- stage 12 在成功返回前还必须发布并自验 `outputs/validation_snapshot_provenance.json`；缺失 sidecar、source-input dirty/tree mismatch 或关键 artifact hash mismatch 都使完整批次失败。
- manifest 的 `source_commit` 带 `+dirty` 只说明整个工作树含未提交改动；最终 source 判断以 provenance checker 的 source-input closure 为准。
- `metrics/evidence/coverage/report` 必须能互相追溯一致。

### 第二层：去公司特例验收

```bash
python3 tools/check_no_company_literals.py
python3 tools/check_capability_contract_alignment.py
```

- 生产 extractor 不得出现公司名业务分支。
- `config/`、`tests/fixtures/`、报告模板可以出现公司名。
- 自动审计使用 AST 扫描 Python literal，明细写入 `outputs/scalability_audit.csv`。
- capability checker 只验证 anchor/path/symbol 等结构事实；symbol 存在不等于 claim 已被证明，证据强度仍由 reviewer 判断为 direct / partial / structural / none。

### 第三层：第 11 家公司测试

- 新增同行业公司只允许改 `config/company_registry.csv` 和 `tests/fixtures/`。
- 不允许为新增同行业公司改 `scripts/sec_pipeline.py`。
- `repair_validation_results.csv` 的 `eleventh_company_behavior_*` 必须 PASS。

失败时脚本 exit nonzero，并把逐项原因写入对应 outputs CSV。

## 本轮修复的请求边界

- Lodging B10/B11 使用表头映射抽取 RevPAR/Occupancy 绝对值；B12 RPO/cRPO 优先 instance fact；C03 PeoTotalCompAmt、FI A01/A02 ratio facts、coverage join、exceptions/report 更新。
- C04 先检查 target 10-K/A，再在 AuditorName 不可用时回退同 CIK、同期间原始 10-K；空白/冲突事实必须降级；仍缺失时才按候选顺序最小补抓 SEC 官方 XBRL instance；期间起点只允许由同 CIK prior 10-K 推导；所有请求仍通过 `SecHttpClient.fetch(...)` 写入 `evidence/requests_log.csv` 及其 exact-set manifest。
- full validation 从 submissions 推导 FY 8-K inventory，重放 raw hdr/primary item 并与 `events.csv` exact-set 比对；正向 count 逐 event component 保留 evidence，零值只在完整扫描确无匹配项时成立。
- `metrics_matrix.csv` 必须恰好包含 registry/profile/applicability contract 推导的 unique `(company, metric_id)` set；`coverage_matrix.csv` 必须与该 matrix exact key set 完全一致。
- `outputs/stratified_audit.csv` 固化验收分层抽样：STD_XBRL/DERIVED、DIM_XBRL、DEF14A、MDA/TEXT、8K_ITEM；缺行、重复或多余样本均失败。

## P0 validation 失败定位

- 先打开 `outputs/repair_validation_results.csv`，按 `check_id` 查看 FAIL 行。
- snapshot checker 失败时，先区分 source-input dirty/tree mismatch、manifest/provenance identity mismatch 与具体 artifact SHA-256/size mismatch。
- 对证据缺失类失败，按 `(company, metric_id)` join `outputs/metrics_matrix.csv` 与 `outputs/metric_evidence.csv`。
- 对 matrix/coverage 完整性失败，先看 details 中的 missing、unexpected 与 duplicate keys；禁止用固定行数或复制现有行凑齐集合。
- 对 8-K 失败，按 submissions→FY inventory→raw filing→events→metric/component evidence 顺序核对 missing、unexpected 与 duplicate identity。
- 对 C03 失败，检查 `outputs/concept_inventory/*_ecd.csv` 中目标 `period_end` 的 `PeoTotalCompAmt`。
- 对 FI Basel ratio 失败，检查对应 `outputs/concept_inventory/*_instance.csv` 的 ratio facts。
- 对请求边界失败，先检查 `evidence/requests_log_manifest.json` 的 row count/hash、Git HEAD/base 有序前缀与下游/sidecar 反向覆盖，再检查 `evidence/requests_log.csv` 的 URL、User-Agent、retry_attempt、body/header locator 和 content_sha256。
- 对 `NOT_EVALUATED_MISSING_EVIDENCE`，不要把空 failure list 解释为通过；按 details 补齐所需材料后重跑。

## 主要输出

- `outputs/metrics_matrix.csv`
- `outputs/metric_evidence.csv`
- `outputs/basel_ratio_candidates.csv`
- `outputs/governance_signals.csv`
- `outputs/coverage_matrix.csv`
- `outputs/exceptions_and_review_items.md`
- `outputs/repair_validation_results.csv`
- `outputs/validation_run_manifest.json`
- `outputs/validation_snapshot_provenance.json`
- `outputs/stratified_audit.csv`
- `outputs/events.csv`
- `outputs/golden_results.csv`
- `outputs/implementation_map.csv`
- `evidence/requests_log_manifest.json`
- `REPORT_十公司财务指标.md`

## 轻量审核包

- 审核包只纳入代码、配置、fixture、关键 outputs 和报告；不纳入 `evidence/`、大体量 `outputs/concept_inventory/`、`__pycache__/` 或 `.DS_Store`。
- 轻量包中 `python3 scripts/12_validate_repair.py` 运行 `LIGHT_REVIEW_MODE`：可重跑代码级、矩阵级和随包 audit gate；缺 raw evidence 的检查必须显示为 `SKIPPED_LIGHT_PACKAGE`。
- 轻量包可发布 `LIGHT_PACKAGE_NO_GIT` provenance，用于证明随包 source/artifact bytes 未漂移；它仍不能替代 full Git history 或 raw evidence validation。
- 轻量包中 `python3 scripts/10_run_golden_assertions.py` 重算随包 `outputs/golden_results.csv` snapshot integrity，通过时输出 `PASS: LIGHT_REVIEW_MODE`；完整数值 golden rerun 需要本地完整 `evidence/`。
- reviewer 必须以 manifest 的 `refreshed_artifacts` / `not_refreshed_artifacts` 和 snapshot checker 共同判断新鲜度，不能只检查 CSV 是否存在。
- 新写入的证据 locator 使用 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`；历史绝对路径只作 relocation hint。
- `GO WITH CAVEATS` 是 pipeline self-verdict；`ACCEPT WITH CAVEATS` 仅保留给外部审计验收结论。
