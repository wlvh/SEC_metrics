# SEC_metrics 用户可观察行为

## 1. 文档关系与读者

`capability_contract.json` 是能力、限制、责任与行为承诺的机器可读真相源；本文档把契约翻译成业务人员、运行负责人和 reviewer 可以直接验收的 CLI、文件与退出状态。`docs/business_user_guide.md` 只负责首次使用教学，不得扩展本文档未声明的能力。

当前项目没有 UI、API 或聊天入口。这里的“用户可观察”是指终端退出状态、仓库内文件、CSV 字段、证据链、validation manifest、snapshot provenance 和最终报告中能够直接核对的结果。

## 2. 当前定位

SEC_metrics 是配置驱动、SEC-only、单财年批处理研究流程。它能为 `config/company_registry.csv` 中配置的逻辑公司生成最新年度申报的指标、治理、风险与事件结果，并保留可审计证据。
<!-- capability-anchor: CAPABILITY.sec_latest_fiscal_batch -->
<!-- capability-anchor: CAPABILITY.sec_governance_risk_event_signals -->

它不是自然语言问答系统，不会在运行时追问公司、日期或指标；也不是实时行情、生产 API、daily scheduler、报价模型或已切换的 vNext 产品。
<!-- capability-anchor: BOUNDARY.configured_batch_not_interactive -->
<!-- capability-anchor: BOUNDARY.sec_only_point_in_time -->
<!-- capability-anchor: BOUNDARY.not_production_service -->

## 3. 入口与完整完成态

刷新完整批次时，运行负责人从 source-input closure clean 的 Git checkout 按 `README_RUN.md` 依序执行阶段 `00` 至 `11`，随后单独运行 `scripts/12_validate_repair.py`。每个 wrapper 只执行固定阶段，仓库没有替代这一顺序的统一 orchestrator。
<!-- capability-anchor: BEHAVIOR.final_state_requires_full_sequence -->

阶段 `11` 可以在内部 P0 失败时仍生成 NO-GO 报告，因此“报告存在”和“stage 11 exit 0”都不等于完整批次通过。阶段 `12` 只有在既有 Golden/repair/report terminal publication 成功，并且 source-input tree 与关键 artifact digest sidecar 已写入、重新读取且验证通过后，才返回零。

stage 11 或 stage 12 开始时会删除可安全识别的旧 regular `outputs/validation_snapshot_provenance.json`；若该路径是 alias 或非 regular 目标，则在修改新 artifact 前失败。新报告、manifest 或 validation CSV 不能继续复用上一轮 success proof。
<!-- capability-anchor: BEHAVIOR.validation_snapshot_binds_source_and_artifacts -->

## 4. 最短验收路径

用户判断一个现有 snapshot 是否仍可使用时，必须按以下顺序：

1. 读取 `outputs/validation_run_manifest.json`；`FAILED` 或 `IN_PROGRESS` 立即停止。
2. 运行 `python3 tools/check_validation_snapshot.py`。
3. checker 通过后再读取 `REPORT_十公司财务指标.md`。
4. 需要采信具体结果时，继续核对 metrics、coverage、evidence 与 request history。

`manifest.source_commit` 只是运行时观察值。当前 HEAD 与它完全相同是直接匹配；artifact commit 或 merge commit 改变 SHA 时，只有 checker 证明完整 source-input tree digest 和文件数仍相同、当前 source closure 仍 clean，才允许以 warning 继续。任一 source byte、source path set 或 artifact byte 变化都失败。

`+dirty` 只说明整个工作树有改动，不能区分生成 outputs 与源代码；用户不得只凭这个后缀做最终判断。
<!-- capability-anchor: BEHAVIOR.validation_manifest_controls_freshness -->

## 5. 核心用户旅程

### 5.1 查看一个财务指标

用户先在报告或 `outputs/metrics_matrix.csv` 定位公司与 `metric_id`，查看 value、unit、status、期间、公式、来源类别、confidence 与 notes。需要采信非空数值时，再以相同 `(company, metric_id)` 在 `outputs/metric_evidence.csv` 核对 SEC URL、accession、concept/section、context/dimension、原始值与 extraction method。
<!-- capability-anchor: CAPABILITY.audit_ready_outputs -->
<!-- capability-anchor: BEHAVIOR.numeric_results_require_evidence -->

验收断言：可采信的非空数值状态必须存在 matching evidence，且 value、unit、period、accession、SEC source、concept/section 与 extraction method 完整对齐；只有 `(company, metric_id)` 的空壳证据不能被当作已验证数值。

集合验收断言：`metrics_matrix.csv` 必须恰好包含 registry、profile 与 applicability contract 推导的 unique `(company, metric_id)` 集合；`coverage_matrix.csv` 必须与 matrix exact key set 完全一致。删行、重复替换或加入未知 key 都不能因剩余行合法而 PASS。

### 5.2 理解缺失、降级与不适用

用户通过 `outputs/coverage_matrix.csv` 与 `outputs/exceptions_and_review_items.md` 区分 SEC 未披露、本轮未可靠抽取、解析失败、结构不适用、经济意义不足和需要人工复核。系统不能为了填满矩阵而猜数。
<!-- capability-anchor: BEHAVIOR.explicit_status_no_guess -->
<!-- capability-anchor: BOUNDARY.complex_extraction_can_degrade -->

每个适用指标格必须有 value 或明确 status；`OK_APPROX`、`TEXT_QUAL`、`NOT_EXTRACTED`、`NOT_MEANINGFUL`、`N_A_STRUCTURAL` 与 `NEEDS_REVIEW` 不得被折叠成普通 `OK`。

### 5.3 查看治理、风险与 8-K 事件

用户在 `outputs/governance_signals.csv`、`outputs/risk_legal_signals.csv` 与 `outputs/events.csv` 查看 DEF 14A、10-K 文本和财年窗口 8-K 的来源、accession、片段与状态。

若完整财年窗口扫描未命中某类 8-K 事件，系统可以输出 `value=0` 与 `status=NOT_AVAILABLE_SEC`，同时保留扫描证据。这个零表示“已验证扫描但未命中”，不是 `OK` 数值，也不能推广为事件绝对不存在。
<!-- capability-anchor: BEHAVIOR.event_chain_is_exact -->
<!-- capability-anchor: BEHAVIOR.event_absence_is_evidenced_zero -->

full validation 必须从 manifest 验证后的有序 request log 取得 request-bound 原始 bytes；submissions 当前 bytes 必须匹配同 URL/document 的最新成功 200 完整身份，filing-bound hdr/primary 的多个成功 observation 必须指向同一 body identity。系统据此推导财年 8-K inventory、重放 raw item，并与 `events.csv` 做完整集合比对。

### 5.4 复核 C04 审计师变更

C04 repair 先检查 filed `target_10k`（含 10-K/A），仅在 AuditorName 不可用时回退同 CIK、同期间原始 10-K；比较期间只能来自同 CIK prior。full validation 分别从 request-bound accession index 重建当期候选 filing 与上期 10-K 的原始实例集，重新解析官方 DEI `AuditorName`，且 validator 不复用生产 row builder。
<!-- capability-anchor: BEHAVIOR.auditor_change_replays_both_filings -->

两期事实可用时，metric/evidence 的完整字段、双 accession、双 locator 与引用文本必须与重算结果一致；事实缺失或冲突时必须按 raw scan 降级，不能用同 accession 的其他合法文件替代。

### 5.5 判断批次能否继续使用

manifest 只说明 run、mode、result 与 refreshed/not-refreshed 集合；`outputs/validation_snapshot_provenance.json` 进一步绑定：

- source commit 与完整 source-input tree SHA-256；
- source file count 与 dirty-path policy；
- manifest、报告、README、metrics/evidence/coverage/Golden、events、request ledger 与本轮 refreshed validation artifacts 的 SHA-256/size。

checker 的 artifact key set 必须与 manifest 推导集合完全一致；缺失、多余、size 或 hash 变化都失败。报告 verdict 不能覆盖 checker failure。
<!-- capability-anchor: CAPABILITY.validation_verdict -->
<!-- capability-anchor: BEHAVIOR.gate_failure_propagates_to_verdict -->

## 6. 失败与受限验证行为

非法配置、未知阶段、关键 SEC 请求失败、未声明的不完整 workspace、失败 gate、dirty source closure 或 provenance publication failure 时，相关 CLI 必须明确报错并非零退出；不得用旧产物、旧 sidecar 或空集合伪装成功。
<!-- capability-anchor: BEHAVIOR.fail_fast_on_invalid_or_incomplete -->

repair validation status 只允许 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。full 的关键 NOT_EVALUATED 阻止 GO；light 的 skipped/NOT_EVALUATED 只能进入显式 caveat。
<!-- capability-anchor: BOUNDARY.light_package_not_full_validation -->
<!-- capability-anchor: BEHAVIOR.light_validation_is_explicitly_limited -->

light package 可以生成 `LIGHT_PACKAGE_NO_GIT` provenance，证明随包 source/artifact bytes 未漂移；它没有 Git history baseline 和 full raw evidence，因此仍不能描述为 full validation。

若 stage 12 的原有 gate 已产生 PASSED/GO，但 provenance postflight 写入或自验失败，wrapper 必须删除可安全识别的 sidecar；unsafe alias 保留为不可验收状态且 checker 明确拒绝。同时 manifest 改为 `FAILED`、报告改为 `NO-GO` 并非零退出。

## 7. 可见性与可移植性

用户应以 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`、period 和 concept/section 定位来源。filing raw material 的 URL、accession、document、resolved path 与 hash 必须联合指向同一份 SEC 文档。历史 `local_path` / `source_path` 只是一条 relocation hint。
<!-- capability-anchor: BEHAVIOR.artifact_locator_is_clone_portable -->

`evidence/requests_log_manifest.json` 以严格 JSON key/type 和 CSV row schema 绑定整表 bytes；working ledger 必须保留 HEAD 有序前缀，只能尾部追加。无 Git history baseline或历史 hash 对应原 bytes 时必须显示 `NOT_EVALUATED_MISSING_EVIDENCE`。

## 8. 责任边界

- 运行负责人提供有效 SEC organization/contact email，维护 registry，并控制 clean source closure 与规定阶段顺序。
  <!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
- 业务与方法负责人复核近似、定性、缺失、解析失败和 `NEEDS_REVIEW`，并承担最终决策。
  <!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->
- 流水线提供证据、provenance 与自判，不签发投资、信用、报价、监管或外部审计结论。
  <!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

当前仓库未登记 UI、API、CI、部署状态、专用支持渠道或紧急联系人。
