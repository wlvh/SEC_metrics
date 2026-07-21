# SEC_metrics 用户可观察行为

## 1. 文档关系与读者

`capability_contract.json` 是能力、限制、责任与行为承诺的机器可读真相源；本文档把这些契约翻译成业务人员、运行负责人和 reviewer 可以直接验收的 CLI 与文件行为。`docs/business_user_guide.md` 只负责首次使用教学，不得扩展本文档未声明的能力。

当前项目没有 UI、API 或聊天入口。这里的“用户可观察”是指终端退出状态、仓库内文件、CSV 字段、证据链和最终报告中能够直接核对的结果。

## 2. 当前定位

SEC_metrics 是配置驱动、SEC-only、单财年批处理研究流程。它能为 `config/company_registry.csv` 中配置的逻辑公司生成最新年度申报的指标、治理、风险与事件结果，并保留可审计证据。
<!-- capability-anchor: CAPABILITY.sec_latest_fiscal_batch -->
<!-- capability-anchor: CAPABILITY.sec_governance_risk_event_signals -->

它不是自然语言问答系统，不会在运行时追问公司、日期或指标；也不是实时行情、生产 API、daily scheduler、报价模型或已切换的 vNext 产品。
<!-- capability-anchor: BOUNDARY.configured_batch_not_interactive -->
<!-- capability-anchor: BOUNDARY.sec_only_point_in_time -->
<!-- capability-anchor: BOUNDARY.not_production_service -->

## 3. 入口与完整完成态

刷新一个完整批次时，运行负责人从干净工作区按照 `README_RUN.md` 依序执行阶段 `00` 至 `11`，随后单独运行 `scripts/12_validate_repair.py`。每个 wrapper 只执行一个固定阶段，仓库没有替代这一顺序的统一 orchestrator。
<!-- capability-anchor: BEHAVIOR.final_state_requires_full_sequence -->

业务验收对象是完成上述顺序且通过最终 gate 后的矩阵、证据、coverage、审计和报告。阶段 `08` 等中间产物可能仍包含待后续 repair 的值；`scripts/11_build_report.py` 即使内部 P0 检查失败也可能生成报告，因此“报告存在”不等于“批次通过”。

## 4. 核心用户旅程

### 4.1 查看一个财务指标

用户先在 `REPORT_十公司财务指标.md` 或 `outputs/metrics_matrix.csv` 定位公司与 `metric_id`，查看 value、unit、status、期间、公式、来源类别、confidence 与 notes。需要采信非空数值时，再以相同 `(company, metric_id)` 在 `outputs/metric_evidence.csv` 核对 SEC URL、accession、concept/section、context/dimension 与原始值。
<!-- capability-anchor: CAPABILITY.audit_ready_outputs -->
<!-- capability-anchor: BEHAVIOR.numeric_results_require_evidence -->

验收断言：可采信的非空数值状态必须存在 matching evidence；缺少证据时，该结果不能被当作已验证数值。

### 4.2 理解缺失、降级与不适用

用户通过 `outputs/coverage_matrix.csv` 与 `outputs/exceptions_and_review_items.md` 区分 SEC 未披露、本轮未可靠抽取、解析失败、结构不适用、经济意义不足和需要人工复核。系统不能为了填满矩阵而猜数。
<!-- capability-anchor: BEHAVIOR.explicit_status_no_guess -->
<!-- capability-anchor: BOUNDARY.complex_extraction_can_degrade -->

验收断言：每个适用指标格必须有 value 或明确 status；`OK_APPROX`、`TEXT_QUAL`、`NOT_EXTRACTED`、`NOT_MEANINGFUL`、`N_A_STRUCTURAL` 与 `NEEDS_REVIEW` 不得被折叠成普通 `OK`。

### 4.3 查看治理、风险与 8-K 事件

用户在 `outputs/governance_signals.csv`、`outputs/risk_legal_signals.csv` 与 `outputs/events.csv` 查看 DEF 14A、10-K 文本和财年窗口 8-K 的来源、accession、片段与状态。

若完整财年窗口扫描未命中某类 8-K 事件，系统可以输出 `value=0` 与 `status=NOT_AVAILABLE_SEC`，同时保留扫描证据。这个零表示“已扫描但未命中”，不是 `OK` 数值，也不能推广为事件绝对不存在。
<!-- capability-anchor: BEHAVIOR.event_absence_is_evidenced_zero -->

### 4.4 判断批次能否继续使用

用户最后核对 `outputs/golden_results.csv`、`outputs/repair_validation_results.csv` 与 `outputs/stratified_audit.csv`，再阅读报告中的 GO、GO WITH CAVEATS 或 NO-GO。
<!-- capability-anchor: CAPABILITY.validation_verdict -->

验收断言：Golden、P0 repair validation、workspace 完整性或 stratified audit 的失败必须阻止正常通过；流水线自判不能替代外部审计接受。
<!-- capability-anchor: BEHAVIOR.gate_failure_propagates_to_verdict -->
<!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 5. 失败与受限验证行为

非法配置、未知阶段、关键 SEC 请求失败、未声明的不完整 workspace 或最终 gate 失败时，相关 CLI 必须明确报错并非零退出；不得用旧产物或空集合伪装成功。
<!-- capability-anchor: BEHAVIOR.fail_fast_on_invalid_or_incomplete -->

light review 只有在缺少 full materials 且存在显式 marker 时才成立。其结果必须保留 `SKIPPED_LIGHT_PACKAGE` 和受限通过状态；没有 marker 的不完整工作区是 `WORKSPACE_INCOMPLETE`。
<!-- capability-anchor: BOUNDARY.light_package_not_full_validation -->
<!-- capability-anchor: BEHAVIOR.light_validation_is_explicitly_limited -->

验收断言：任何 light 结果都不得被描述为 full validation，也不得因为某项在缺 evidence 时静默无 failure 就声称该证据路径已验证。

## 6. 责任边界

- 运行负责人提供有效 SEC organization/contact email，维护 registry，并控制从干净工作区顺序运行；当前示例邮箱不能作为生产合规证明。
  <!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
- 业务与方法负责人复核近似、定性、缺失、解析失败和 `NEEDS_REVIEW`，并承担最终决策。
  <!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->
- 流水线提供证据与自判，不签发投资、信用、报价、监管或外部审计结论。
  <!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 7. 可见性与可移植性

用户应以 SEC URL、accession、hash、period、concept/section 和仓库内相对证据定位来源。历史 CSV 的 `local_path` 可能包含生成机器的绝对路径，它只是一条本地线索，不是跨机器权威地址。

当前仓库未登记 UI、API、CI、部署状态、专用支持渠道或紧急联系人。文档和 PR 不得把规划中的能力写成已经可观察的事实。
