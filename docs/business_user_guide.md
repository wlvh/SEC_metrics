# SEC_metrics：业务人员首次使用指南

> Status: active
> Audience: 读取结果的业务、财务方法与审核人员
> Scope: 当前 SEC-only 单财年批处理 spike
> Capability boundary source: `capability_contract.json`
> User-visible behavior source: `interact.md`

本指南只解释已经由能力契约和用户可观察行为确认的内容，不独立承诺新能力。当前交付形态是仓库内 CSV、证据文件和 Markdown 报告，不是可对话应用。
<!-- capability-anchor: DOC.business_user_guide -->

## 1. 先建立正确判断顺序

不要先打开报告找数字。一个文件“存在”，只说明它在磁盘上，不说明它来自当前代码，也不说明它通过了最终验证。

第一次读取只走四步：

```text
1. outputs/validation_run_manifest.json
2. python3 tools/check_validation_snapshot.py
3. REPORT_十公司财务指标.md
4. metrics / coverage / evidence
```

### 第一步：看 manifest

- `FAILED` 或 `IN_PROGRESS`：停止验收。
- `PASSED_WITH_CAVEATS`：只表示受限通过，必须阅读 caveat。
- `refreshed_artifacts`：说明本轮实际刷新的 validation/audit 文件；旧 CSV 存在不能代替本轮刷新。

### 第二步：运行 snapshot checker

checker 验证当前 source-input tree 与关键 artifact bytes 是否仍和该 run 绑定：

```bash
python3 tools/check_validation_snapshot.py
```

- `PASS`：继续读报告；
- `WARNING`：commit SHA 改变，但完整 source-input tree 等价，常见于 artifact commit 或 merge commit；
- `FAIL`：缺少 provenance、源代码/配置/测试有未提交改动、source tree 不同，或 manifest/report/metrics/evidence/request/validation artifact 的 hash/size 变化。此时停止使用 snapshot。

`manifest.source_commit` 带 `+dirty` 只表示整个工作树有修改，不足以判断源代码是否变了；最终以 checker 的 source-input closure 为准。
<!-- capability-anchor: BEHAVIOR.validation_manifest_controls_freshness -->
<!-- capability-anchor: BEHAVIOR.validation_snapshot_binds_source_and_artifacts -->

### 第三步：看报告

报告用于快速理解本批次的 coverage、例外与 verdict。只有阶段 `00` 至 `11` 已完整运行、独立阶段 `12` exit 0，且 snapshot checker 通过后的产物，才能作为完整批次验收对象。
<!-- capability-anchor: BEHAVIOR.final_state_requires_full_sequence -->

### 第四步：回到原始结果行

需要采信某个结果时，必须回到 `outputs/metrics_matrix.csv`、`outputs/coverage_matrix.csv` 和 `outputs/metric_evidence.csv`，不能只复制报告摘要。

## 2. 它能带来什么价值

SEC_metrics 为当前 registry 中配置的公司生成最近年度 SEC 申报快照，覆盖适用的财务指标以及治理、风险和财年窗口事件信号。核心价值是把 value、status、口径、来源和证据放在同一条链路中，并在证据不足时诚实降级，而不是保证每个格子都有数字。
<!-- capability-anchor: CAPABILITY.sec_latest_fiscal_batch -->
<!-- capability-anchor: CAPABILITY.audit_ready_outputs -->

最适合的任务：

- 查看某家已配置公司的一个指标值、单位、期间、口径与来源；
- 识别精确、近似、定性、未披露、未抽取、不适用或待复核结果；
- 查看 DEF 14A、10-K 文本和财年窗口 8-K 中的治理、风险、法律与事件信号；
- 判断当前批次是 GO、GO WITH CAVEATS 还是 NO-GO，并定位失败或 caveat。
<!-- capability-anchor: CAPABILITY.sec_governance_risk_event_signals -->
<!-- capability-anchor: CAPABILITY.validation_verdict -->

## 3. 当前不支持什么

- 不支持自然语言问答、自动追问或运行时自由选择任意公司、日期和指标。
  <!-- capability-anchor: BOUNDARY.configured_batch_not_interactive -->
- 不提供实时行情、新闻或第三方数据补数；结果是执行时可见的 SEC 年度申报快照。
  <!-- capability-anchor: BOUNDARY.sec_only_point_in_time -->
- 不保证复杂表格、维度债务、治理与风险指标都能自动得到数值；它们可能明确降级。
  <!-- capability-anchor: BOUNDARY.complex_extraction_can_degrade -->
- 当前没有前端、API、daily scheduler、生产数据库服务或已完成切换的 vNext 发布系统。
  <!-- capability-anchor: BOUNDARY.not_production_service -->
- 不替人做投资、信用、报价、监管或外部审计决定。
  <!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->

## 4. 指标行怎么看

优先关注：

| 字段 | 业务含义 |
|---|---|
| `company` / `cik` | 逻辑公司与本行使用的 SEC 实体 |
| `metric_id` / `metric_name` | 指标标识与名称 |
| `value` / `unit` | 数值和单位；空值必须结合 status 阅读 |
| `status` | 精确、近似、文本、缺失、不适用或待复核语义 |
| `period_start` / `period_end` | 结果覆盖期间 |
| `accession` / `form` | 申报材料身份 |
| `source_class` / `concept_or_section` | 来源类别与 concept 或章节 |
| `formula` / `confidence` / `notes` | 口径、置信度、假设与限制 |

可采信的非空数值状态必须在 evidence 矩阵找到 matching row，并对齐 value、unit、period、accession、source、concept/section 和 extraction method。
<!-- capability-anchor: BEHAVIOR.numeric_results_require_evidence -->

## 5. 状态词典

### 有结果，但证据强度不同

- `OK`：标准或直接可采信结果。
- `OK_APPROX`：有明确近似口径；必须读 formula 与 notes。
- `DIM_XBRL_OK`：来自 accession instance 的维度事实。
- `MDA_OK`：来自 MD&A 或表格文本抽取。
- `DEF14A_OK`：来自 DEF 14A 或 ecd 事实。
- `8K_ITEM_OK`：来自 8-K item。
- `TEXT_QUAL`：只有定性证据，不能当精确数值。

### 缺失、失败或需要处理

- `NOT_AVAILABLE_SEC`：在已定义 SEC 检索范围内未找到披露；不等于现实世界绝对不存在。
- `NOT_EXTRACTED`：可能披露，但本轮没有可靠抽取。
- `PARSE_FAILED`：预期可解析但解析失败。
- `NEEDS_REVIEW`：存在候选、口径冲突或复杂维度，需要人工复核。

### 不应计算

- `NOT_MEANINGFUL`：数字可能存在，但在当前经济或连续性语境下没有可靠意义。
- `N_A_STRUCTURAL`：该指标对当前行业或主体结构不适用。

系统不得把这些状态静默改成 `OK`，也不得为了矩阵完整而猜数。
<!-- capability-anchor: BEHAVIOR.explicit_status_no_guess -->

## 6. 三个常见复核场景

### 标准或派生财务指标

在 metrics matrix 找到公司和指标，确认 status、period、unit 与 formula，再到 metric evidence 核对 accession、concept、原始值和来源 URL。`OK_APPROX` 还需要方法负责人确认近似口径是否适合用途。

### 8-K 未命中的零值

正向指标应为每个被计数 event component 保留独立 filing identity。零值只有在系统从 request-bound submissions 推导完整财年 inventory、重放 raw hdr/primary item、与 events exact-set 对齐并保留 scan evidence 后才成立。
<!-- capability-anchor: BEHAVIOR.event_chain_is_exact -->
<!-- capability-anchor: BEHAVIOR.event_absence_is_evidenced_zero -->

这个零只表示已验证扫描范围内未命中对应规则，不代表所有来源和所有时间都不存在该事件。

### C04 审计师变更

C04 先检查 filed target（含 10-K/A），再按需回退同 CIK、同期间原始 10-K；期间不跨 CIK。full validation 会从 request-bound accession index 重建 current/prior 原始实例，重新解析官方 DEI `AuditorName`，并独立重算 metric/evidence。缺 raw bytes、名称冲突或错绑文档时不得通过。
<!-- capability-anchor: BEHAVIOR.auditor_change_replays_both_filings -->

## 7. Full、light 与 provenance

repair validation 的 status 只有：

- `PASS`
- `FAIL`
- `SKIPPED_LIGHT_PACKAGE`
- `NOT_EVALUATED_MISSING_EVIDENCE`
- `WORKSPACE_INCOMPLETE`

full validation 需要完整 raw evidence、request ledger、concept inventory、Golden、repair gate 和 Git source provenance；full 关键 NOT_EVALUATED 必须 NO-GO。

light review 只验证随包范围。它可以生成 `LIGHT_PACKAGE_NO_GIT` provenance，证明随包 bytes 未漂移，但没有 Git history baseline 和 full raw evidence，不能宣传为 full validation。
<!-- capability-anchor: BOUNDARY.light_package_not_full_validation -->
<!-- capability-anchor: BEHAVIOR.light_validation_is_explicitly_limited -->

`GO WITH CAVEATS` 是流水线自判，不是外部审计接受、投资建议或生产发布许可。
<!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 8. 高级审计说明

以下内容只在定位失败或进行技术审计时需要：

- portable locator 使用 `source_url`、`repo_relative_path`、`content_sha256`、`accession` 与 `document_name`；
- 历史绝对 `local_path` / `source_path` 只作 relocation hint；
- request body/header 必须来自同一历史 clone root，不能跨候选拼接；
- request ledger 保留 Git HEAD/base 有序前缀，只能追加合法 tail；
- mutable submissions 必须匹配最新成功 200，filing-bound archive 文档的成功 bodies 必须一致；
- provenance sidecar 对当前 source-input tree 和关键 artifact SHA-256/size 做 exact binding。
<!-- capability-anchor: BEHAVIOR.artifact_locator_is_clone_portable -->

机制细节见 `architecture.md` 与 `docs/validation_snapshot_provenance.md`。业务用户的主路径仍然是：manifest → checker → report → metrics/evidence。
