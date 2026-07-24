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

1. 先读 `outputs/validation_run_manifest.json`，确认 mode、result，以及本次真正刷新的 tracked validation/audit artifact；`FAILED` 或 `IN_PROGRESS` 时停止验收。
2. 运行 `python3 tools/check_validation_snapshot.py`。缺少 provenance、source-input tree dirty/不一致、显式 source 文件缺失，或关键 artifact SHA-256/size 失配时停止验收。
3. checker 通过后再读 `REPORT_十公司财务指标.md`，了解本批次摘要、coverage、例外和 verdict。
4. 在 `outputs/metrics_matrix.csv` 按 company 与 `metric_id` 找到具体结果。
5. 用 `outputs/coverage_matrix.csv` 和 `outputs/exceptions_and_review_items.md` 判断缺口类型。
6. 需要采信非空数值时，在 `outputs/metric_evidence.csv` 核对同一 company/metric 的来源与口径。
7. 最后只核对 manifest `refreshed_artifacts` 中的 `repair_validation_results.csv`、`stratified_audit.csv` 等证据；旧文件存在不代表本次运行已评估。
<!-- capability-anchor: BEHAVIOR.validation_manifest_controls_freshness -->
<!-- capability-anchor: BEHAVIOR.validation_snapshot_binds_source_and_artifacts -->

`manifest.source_commit` 与当前 HEAD 相同是最直接的匹配；artifact commit 或 merge commit 改变 SHA 时，只有 checker 证明完整 source-input tree digest 和文件数仍一致、当前 source closure clean，才允许以 warning 继续。`+dirty` 只说明整个工作树含改动，不能单独判断源代码是否参与运行。

只有阶段 `00` 至 `11` 已完整运行、独立阶段 `12` 通过，并且 snapshot checker 通过后的产物，才能作为完整批次验收对象。仅看到报告文件或成功 manifest 存在并不足够。
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

新 artifact 使用 `source_url`、`repo_relative_path`、`content_sha256`、`accession` 与 `document_name` 定位。历史 CSV 中的 `local_path` / `source_path` 只作为 relocation hint；读取优先当前 clone 的 repo-relative path，不存在时再按 accession/document/hash 重定位。旧绝对路径出现多个仓库目录 anchor 时必须唯一匹配当前 clone；同一 request 的 body/header 还必须来自同一个旧仓库根。无匹配、有歧义或跨根拼接时失败，绝不把原作者机器路径当作权威地址。新请求的 request-log locator 指向每次 attempt 的 content-addressed immutable body/header；已审核 ledger 是有序前缀，只能尾部追加，不能靠重排把旧响应重新定义为最新。历史 row 的 hash 若已找不到对应 bytes，只能标为 `NOT_EVALUATED_MISSING_EVIDENCE`。
<!-- capability-anchor: BEHAVIOR.artifact_locator_is_clone_portable -->

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

若事件指标为正数，`outputs/metric_evidence.csv` 应为每个被计数的 event component 各保留一行 SEC filing identity；同一 accession 出现多个匹配 item 时也不能只看第一行。value、accession 列表与这些 component 必须完全一致。

若事件指标显示 `value=0` 且 `status=NOT_AVAILABLE_SEC`，应先确认 repair validation 的 8-K chain/output gate 通过：系统从 manifest 验证后的有序 request log 取得 request-bound 原始 bytes；submissions 必须匹配最新成功 200，filing-bound raw 文档的多个成功 observation 必须内容一致。系统再由 submissions 推导财年 filing inventory，从 raw hdr/primary 重放 item，并与 events 做完整集合比对；随后核对零值 scan evidence。这个零只表示已验证扫描范围内未命中对应规则，不代表事件在所有来源和所有时间都不存在。
<!-- capability-anchor: BEHAVIOR.event_chain_is_exact -->
<!-- capability-anchor: BEHAVIOR.event_absence_is_evidenced_zero -->

### 7.4 复核 C04 审计师变更

当 C04 有两期审计师事实时，先核对 evidence 是否同时列出当期候选 filing 和上期 10-K 的 accession、文档和 locator。系统先检查 filed target（含 10-K/A），只有其中 AuditorName 不可用时才回退同 CIK、同期间原始 10-K；没有同 CIK prior 时，C04 期间从当前报告年度 1 月 1 日开始，不与 predecessor CIK 硬拼。full validation 会分别从 request-bound accession index 重建两期原始实例集，要求 filing-bound 成功 bodies 一致，重新解析官方 DEI `AuditorName`，并在不复用生产 row builder 的前提下重算完整 metric/evidence。只有单期事实或出现冲突名称时，结果必须降级且 evidence 仍要绑定对应 raw scan；同 accession 的其他合法文件不能替代。缺 raw bytes 时不得通过 full gate，也不应把降级结果当作已完成的变更判断。
<!-- capability-anchor: BEHAVIOR.auditor_change_replays_both_filings -->

### 7.5 理解 GO WITH CAVEATS

GO WITH CAVEATS 表示流水线没有触发 NO-GO，但仍有必须阅读的限制或人工复核项。它不是外部审计接受、投资建议或生产发布许可。
<!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 8. validation 与 full/light review

repair validation 的 status 只有以下五种：

- `PASS`：所需材料存在，检查实际执行且通过。
- `FAIL`：检查实际执行并发现失败。
- `SKIPPED_LIGHT_PACKAGE`：light 包按声明省略了 full-only 检查。
- `NOT_EVALUATED_MISSING_EVIDENCE`：缺少该检查所需证据，不能判断通过或失败。
- `WORKSPACE_INCOMPLETE`：工作区缺少结构性材料，且不满足声明的 light package 边界。

full validation 需要本地 raw evidence、请求日志和 concept inventory 的完整工作区形状，并且仍要以 Golden、repair gate、manifest、provenance 与 snapshot checker 的实际结果为准。full 关键检查出现 `NOT_EVALUATED_MISSING_EVIDENCE` 时必须 NO-GO。light review 只验证随包范围，`SKIPPED_LIGHT_PACKAGE` 或 `NOT_EVALUATED_MISSING_EVIDENCE` 必须成为显式 caveat；不能将其宣传为 full validation，也不能把“没有发现失败”改写成 PASS。
<!-- capability-anchor: BOUNDARY.light_package_not_full_validation -->
<!-- capability-anchor: BEHAVIOR.light_validation_is_explicitly_limited -->

`LIGHT_PACKAGE_NO_GIT` provenance 只证明随包 source/artifact bytes 与 sidecar 一致，不补足 Git history 或 raw evidence。无 Git light package 缺少能力契约、指标定义、AGENTS/SOP/TESTING/architecture/interact 或其他显式 source singleton 时，checker 必须失败，不能通过删文件缩小 source closure。

## 9. 什么时候必须找人

出现以下情况时，停止把输出当作自动完成的结论：

- status 为 `NEEDS_REVIEW`、`PARSE_FAILED` 或关键 `NOT_EXTRACTED`。
- `OK_APPROX`、`TEXT_QUAL` 或复杂表格结果将影响高风险决定。
- 需要改变 company registry、报告期、指标定义或 successor/predecessor 口径。
- live 刷新前 `config/sec_config.json` 尚未配置有效的 SEC organization 与 contact email。
- Golden、P0 validation、workspace 完整性、分层审计或 snapshot checker 出现失败，或 full 关键检查为 `NOT_EVALUATED_MISSING_EVIDENCE`。
- 需要外部审计接受、生产发布或正式业务批准。

运行配置与完整阶段由仓库运行负责人负责；指标口径与 caveat 由财务方法复核人负责；最终业务与外部接受由相应负责人承担。
<!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
<!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->

仓库目前没有登记具体联系人、即时通信频道或紧急升级路径。需要升级时应由仓库负责人明确分派，不能在文档中虚构渠道。

## 10. 最短建议

先看 manifest，再跑 snapshot checker，然后看 status 与 evidence，最后看 gate。看到空值不要猜，看到零值先确认语义，看到 GO WITH CAVEATS 要继续读 caveat。
