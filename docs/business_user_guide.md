# SEC_metrics：业务人员首次使用指南

> Status: active
>
> Audience: 读取结果的业务、财务方法与审核人员
>
> Scope: 当前 SEC-only 单财年批处理 spike
>
> Capability boundary source: `capability_contract.json`
> User-visible behavior source: `interact.md`

本指南只解释已经由能力契约和用户可观察行为确认的内容，不独立承诺新能力。当前交付形态是仓库内 CSV、证据文件和 Markdown 报告，不是可对话应用。
<!-- capability-anchor: DOC.business_user_guide -->

## 1. 它能带来什么价值

SEC_metrics 为当前 registry 中配置的公司生成最近年度 SEC 申报快照，覆盖适用的财务指标以及治理、风险和财年窗口事件信号。它的核心价值是把 value、status、口径、来源和证据放在同一条可追溯链路中，并在证据不足时诚实降级，而不是保证每个格子都有数字。
<!-- capability-anchor: CAPABILITY.sec_latest_fiscal_batch -->
<!-- capability-anchor: CAPABILITY.audit_ready_outputs -->

## 2. 最适合处理的业务任务

- 查看某家已配置公司的一个指标值、单位、期间、口径与来源。
- 识别哪些指标已验证、近似、只具定性证据、未披露、未抽取或需要人工复核。
- 查看 DEF 14A、10-K 文本和财年窗口 8-K 中的治理、风险、法律与事件信号。
- 判断当前批次的流水线自判是 GO、GO WITH CAVEATS 还是 NO-GO，并定位 caveat 或失败项。

这些能力只适用于当前配置驱动的年度批次。
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

## 4. 第一次阅读的最短路径

1. 先读 `REPORT_十公司财务指标.md`，了解本批次摘要、coverage、例外和 verdict。
2. 在 `outputs/metrics_matrix.csv` 按 company 与 `metric_id` 找到具体结果。
3. 用 `outputs/coverage_matrix.csv` 和 `outputs/exceptions_and_review_items.md` 判断缺口类型。
4. 需要采信非空数值时，在 `outputs/metric_evidence.csv` 核对同一 company/metric 的来源与口径。
5. 最后核对 `outputs/golden_results.csv`、`outputs/repair_validation_results.csv` 和 `outputs/stratified_audit.csv`。

只有阶段 `00` 至 `11` 已完整运行，并且独立阶段 `12` 通过后的产物，才能作为完整批次验收对象。仅看到报告文件存在并不足够。
<!-- capability-anchor: BEHAVIOR.final_state_requires_full_sequence -->

## 5. 指标行怎么看

优先关注这些字段：

| 字段 | 业务含义 |
|---|---|
| `company` / `cik` | 逻辑公司与本行使用的 SEC 实体 |
| `metric_id` / `metric_name` | 指标标识与名称 |
| `value` / `unit` | 数值和单位；空值必须结合 status 阅读 |
| `status` | 精确、近似、文本、缺失、不适用或待复核语义 |
| `period_start` / `period_end` | 结果覆盖期间 |
| `accession` / `form` | 申报材料身份 |
| `source_class` / `concept_or_section` | 来源类别与具体 concept 或章节 |
| `confidence` / `notes` | 置信度、假设与限制 |

可采信的非空数值状态应能在 evidence 矩阵找到 matching row。
<!-- capability-anchor: BEHAVIOR.numeric_results_require_evidence -->

历史 CSV 中的 `local_path` 可能保留生成机器的绝对路径。跨机器复核时，以 SEC URL、accession、hash、期间、concept/section 与仓库内相对文件为准，不要把绝对路径当成权威地址。

## 6. 状态词典

### 6.1 有结果，但强度不同

- `OK`：标准或直接可采信结果。
- `OK_APPROX`：有明确近似口径；必须阅读 formula 与 notes。
- `DIM_XBRL_OK`：来自 accession instance 的维度事实。
- `MDA_OK`：来自 MD&A 或表格文本抽取。
- `DEF14A_OK`：来自 DEF 14A 或 ecd 事实。
- `8K_ITEM_OK`：来自 8-K item。
- `TEXT_QUAL`：只有定性证据，不能当精确数值。

### 6.2 缺失、失败或需要处理

- `NOT_AVAILABLE_SEC`：在已定义的 SEC 检索范围内未找到披露；不等于现实世界绝对不存在。
- `NOT_EXTRACTED`：可能披露，但本轮没有可靠抽取。
- `PARSE_FAILED`：预期可解析但解析失败。
- `NEEDS_REVIEW`：存在候选、口径冲突或复杂维度，需要人工复核。

### 6.3 不应计算

- `NOT_MEANINGFUL`：数字可以存在，但在当前经济或连续性语境下没有可靠意义。
- `N_A_STRUCTURAL`：该指标对当前行业或主体结构不适用。

系统不得把这些状态静默改成 `OK`，也不得为了矩阵完整而猜数。
<!-- capability-anchor: BEHAVIOR.explicit_status_no_guess -->

## 7. 真实使用场景

### 7.1 复核一个标准或派生财务指标

在 metrics matrix 找到公司和指标，先确认 status、period、unit 与 formula，再到 metric evidence 核对 accession、concept、原始值和来源 URL。若是 `OK_APPROX`，需要财务方法负责人确认近似口径是否适合本次用途。

完成标准：结论、口径和来源能够闭合；不能只从报告摘要复制一个数字。

### 7.2 处理 `NEEDS_REVIEW` 或 `NOT_EXTRACTED`

先查看 coverage reason 与异常清单，再检查 evidence 中是否保留候选事实、dimension、原文片段或缺失原因。`NEEDS_REVIEW` 不代表结果错误，但在人工复核完成前不能升级为正常可用值。

完成标准：明确是补证据、改 parser、确认口径，还是接受 SEC 未披露；不把未知部分写成事实。

### 7.3 理解 8-K 未命中的零值

若事件指标显示 `value=0` 且 `status=NOT_AVAILABLE_SEC`，应核对 events 与 evidence 是否证明财年窗口已完整扫描。这个零只表示扫描范围内未命中对应规则，不代表事件在所有来源和所有时间都不存在。
<!-- capability-anchor: BEHAVIOR.event_absence_is_evidenced_zero -->

### 7.4 理解 GO WITH CAVEATS

GO WITH CAVEATS 表示流水线没有触发 NO-GO，但仍有必须阅读的限制或人工复核项。它不是外部审计接受、投资建议或生产发布许可。
<!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 8. full 与 light review

full validation 需要本地 raw evidence、请求日志和 concept inventory 的完整工作区形状，并且仍要以 Golden 与 repair gate 的实际结果为准。light review 只验证随包范围，跳过项必须显示为 `SKIPPED_LIGHT_PACKAGE`；不能将其宣传为 full validation。
<!-- capability-anchor: BOUNDARY.light_package_not_full_validation -->
<!-- capability-anchor: BEHAVIOR.light_validation_is_explicitly_limited -->

## 9. 什么时候必须找人

出现以下情况时，停止把输出当作自动完成的结论：

- status 为 `NEEDS_REVIEW`、`PARSE_FAILED` 或关键 `NOT_EXTRACTED`。
- `OK_APPROX`、`TEXT_QUAL` 或复杂表格结果将影响高风险决定。
- 需要改变 company registry、报告期、指标定义或 successor/predecessor 口径。
- live 刷新前 `config/sec_config.json` 尚未配置有效的 SEC organization 与 contact email。
- Golden、P0 validation、workspace 完整性或分层审计出现失败。
- 需要外部审计接受、生产发布或正式业务批准。

运行配置与完整阶段由仓库运行负责人负责；指标口径与 caveat 由财务方法复核人负责；最终业务与外部接受由相应负责人承担。
<!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
<!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->

仓库目前没有登记具体联系人、即时通信频道或紧急升级路径。需要升级时应由仓库负责人明确分派，不能在文档中虚构渠道。

## 10. 最短建议

先看 status，再看 evidence，最后看 gate。看到空值不要猜，看到零值先确认语义，看到 GO WITH CAVEATS 要继续读 caveat。
