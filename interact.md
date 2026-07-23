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

业务验收对象是完成上述顺序且通过最终 gate 后的矩阵、证据、coverage、审计和报告。阶段 `08` 等中间产物可能仍包含待后续 repair 的值；`scripts/11_build_report.py` 即使内部 P0 检查失败也可能生成 NO-GO 报告，因此“报告存在”不等于“批次通过”。阶段 `11` / `12` 会先保持 manifest=`IN_PROGRESS`，用同一 run 的 projected terminal state 原子替换非 symlink regular report，并校验报告的 run_id/result；报告（阶段 11 还包括 README）持久化成功后才发布 manifest 终态。写入失败或 alias 目标时不得留下成功 manifest 与旧/缺报告的跨 run 组合。

## 4. 核心用户旅程

### 4.1 查看一个财务指标

用户先在 `REPORT_十公司财务指标.md` 或 `outputs/metrics_matrix.csv` 定位公司与 `metric_id`，查看 value、unit、status、期间、公式、来源类别、confidence 与 notes。需要采信非空数值时，再以相同 `(company, metric_id)` 在 `outputs/metric_evidence.csv` 核对 SEC URL、accession、concept/section、context/dimension 与原始值。
<!-- capability-anchor: CAPABILITY.audit_ready_outputs -->
<!-- capability-anchor: BEHAVIOR.numeric_results_require_evidence -->

验收断言：可采信的非空数值状态必须存在 matching evidence，且 value、unit、period、accession、SEC source、concept/section 与 extraction method 完整对齐；只有 `(company, metric_id)` 的空壳证据不能被当作已验证数值。

集合验收断言：`metrics_matrix.csv` 必须恰好包含 registry、profile 与 applicability contract 推导的 unique `(company, metric_id)` 集合；`coverage_matrix.csv` 必须与 matrix 的 exact key set 完全一致。删行、重复替换或加入未知 key 都不能因剩余行合法而 PASS。

### 4.2 理解缺失、降级与不适用

用户通过 `outputs/coverage_matrix.csv` 与 `outputs/exceptions_and_review_items.md` 区分 SEC 未披露、本轮未可靠抽取、解析失败、结构不适用、经济意义不足和需要人工复核。系统不能为了填满矩阵而猜数。
<!-- capability-anchor: BEHAVIOR.explicit_status_no_guess -->
<!-- capability-anchor: BOUNDARY.complex_extraction_can_degrade -->

验收断言：每个适用指标格必须有 value 或明确 status；`OK_APPROX`、`TEXT_QUAL`、`NOT_EXTRACTED`、`NOT_MEANINGFUL`、`N_A_STRUCTURAL` 与 `NEEDS_REVIEW` 不得被折叠成普通 `OK`。coverage 缺少、重复或多出任一 matrix key 都必须失败。

### 4.3 查看治理、风险与 8-K 事件

用户在 `outputs/governance_signals.csv`、`outputs/risk_legal_signals.csv` 与 `outputs/events.csv` 查看 DEF 14A、10-K 文本和财年窗口 8-K 的来源、accession、片段与状态。

若完整财年窗口扫描未命中某类 8-K 事件，系统可以输出 `value=0` 与 `status=NOT_AVAILABLE_SEC`，同时保留扫描证据。这个零表示“已扫描但未命中”，不是 `OK` 数值，也不能推广为事件绝对不存在。
<!-- capability-anchor: BEHAVIOR.event_chain_is_exact -->
<!-- capability-anchor: BEHAVIOR.event_absence_is_evidenced_zero -->

验收断言：full validation 必须从 manifest 验证后的有序 request log 取得 request-bound 原始 bytes；submissions 当前 bytes 必须匹配同 URL/document 的最新成功 200 完整身份，filing-bound hdr/primary 的多个成功 observation 必须指向同一 body identity。系统据此推导财年 8-K inventory，并从 raw filing 重放 item，与 `events.csv` 做完整集合比对；任一 request/submission/filing/item 被删除、重复、增加、回滚或身份不匹配都不能 PASS。正向 count 的 value/accession 与每个 event component evidence 必须完全一致；零值只能在完整事件集合确实无匹配项且存在 scan evidence 时成立。

### 4.4 复核 C04 审计师变更

C04 不仅检查已生成的 metric 文字。repair 必须先检查 filed `target_10k`（含 10-K/A），仅在 AuditorName 不可用时回退同 CIK、同期间原始 10-K；期间起点只能来自同 CIK prior，没有同 CIK prior 时从当前报告年度 1 月 1 日开始，不能跨 successor/predecessor 拼接。full validation 会对当期候选 filing 和上期 10-K 分别读取 request-bound accession index，要求 filing-bound 成功 bodies 一致，重建应有的原始实例文档，再重新解析官方 DEI `AuditorName`；validator 不复用生产 row builder。两期原始事实可用时，metric 与 evidence 的完整字段、双 accession、双 locator 和引用文本必须与重算结果完全一致；事实缺失或冲突时必须按原始扫描结果降级并绑定对应 raw scan，同 accession 的其他合法文件不能替代；损坏输入必须显示 FAIL，缺失原始证据时不得 PASS。
<!-- capability-anchor: BEHAVIOR.auditor_change_replays_both_filings -->

### 4.5 判断批次能否继续使用

用户最后先读 `outputs/validation_run_manifest.json`，只把 `refreshed_artifacts` 中的 tracked validation/audit 文件视为本次运行已刷新；`outputs/golden_results.csv`、矩阵和 evidence 仍需各自的重跑来源。随后核对 `outputs/repair_validation_results.csv` 与本次已刷新的 `outputs/stratified_audit.csv`，最后阅读报告中的 GO、GO WITH CAVEATS 或 NO-GO。
<!-- capability-anchor: CAPABILITY.validation_verdict -->
<!-- capability-anchor: BEHAVIOR.validation_manifest_controls_freshness -->

验收断言：Golden 必须是配置/generator/fixture 推导的 exact assertion set 且唯一；stratified audit 必须与当前 metrics 推导的五层样本 exact set 一致且唯一；request log 必须与整表 row-count/hash manifest、Git HEAD/base 已审核有序前缀、下游 locator 和已存 response sidecar 一致。base/HEAD 中每条 current/legacy row 都必须与声明 schema 精确同宽，历史 observation 只能追加合法 tail row，不能删改、重排或用多余/缺失单元格绕过比较。任一缺行、重复/多余集合、P0 repair validation、workspace 完整性或 full 关键检查 `NOT_EVALUATED_MISSING_EVIDENCE` 必须阻止正常通过；流水线自判不能替代外部审计接受。
<!-- capability-anchor: BEHAVIOR.gate_failure_propagates_to_verdict -->
<!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 5. 失败与受限验证行为

非法配置、未知阶段、关键 SEC 请求失败、未声明的不完整 workspace 或最终 gate 失败时，相关 CLI 必须明确报错并非零退出；不得用旧产物或空集合伪装成功。
<!-- capability-anchor: BEHAVIOR.fail_fast_on_invalid_or_incomplete -->

repair validation 的 status 只允许 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。缺少验证材料时不能返回 PASS；full 的关键 NOT_EVALUATED 阻止 GO，light 的 skipped / NOT_EVALUATED 只能进入 manifest caveat。light review 只有在缺少 full materials 且存在显式 marker 时才成立；没有 marker 的不完整工作区是 `WORKSPACE_INCOMPLETE`。
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

用户应以 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`、period 和 concept/section 定位来源。filing raw material 的 URL、accession、document、resolved path 与 hash 必须联合指向同一份 SEC 文档，不得用其他 accession 的同名同 hash 文件回填。新 artifact 不写生成机器绝对路径；历史 CSV 的 `local_path` / `source_path` 只是一条 relocation hint。旧绝对路径若含多个仓库目录 anchor，系统必须用当前 clone 的联合身份选出唯一后缀；同一 request 的 body 与 headers 还必须丢弃同一个旧仓库根前缀，不能把两个 clone 候选各自命中的文件拼成一条 observation。无匹配、有歧义或跨根拼接时失败，不猜测仓库根。新 SEC 请求的每次已发 attempt 必须落一条 observation，有响应体时 request-log locator 指向 content-addressed immutable body/header；最终文件名被 symlink/hardlink 抢占时必须失败且不得覆盖 victim。初始 URL 必须是精确官方 HTTPS origin，HTTP redirect 只记录首跳 3xx 与 Location，不会隐式请求下一跳。`evidence/requests_log_manifest.json` 以严格 JSON key/type 和 CSV 行 schema 绑定整表 bytes；working ledger 必须保留 HEAD 有序前缀；PR checker 先要求 base/HEAD 的每条 current/legacy row 与声明 schema 精确同宽，再对 legacy base 独立规范化 portable 完整字段、对 current base 逐字段保留有序前缀，之后只允许合法尾部追加，下游/sidecar 再反向覆盖完整集合。同一 repository 的 request-log publication 会在 cooperating threads / POSIX processes 间串行化；这不提供跨 client 全局限速，不承诺网络文件系统锁语义，也不构成对恶意同 UID 进程的 WORM。无 Git history baseline 或历史 row 的原 bytes 时必须显示 `NOT_EVALUATED_MISSING_EVIDENCE`，不能仅凭自签 manifest、URL 或文件存在宣称完整、可复现。
<!-- capability-anchor: BEHAVIOR.artifact_locator_is_clone_portable -->

当前仓库未登记 UI、API、CI、部署状态、专用支持渠道或紧急联系人。文档和 PR 不得把规划中的能力写成已经可观察的事实。
