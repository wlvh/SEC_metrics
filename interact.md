# SEC_metrics 用户可观察行为

## 1. 文档关系与读者

`capability_contract.json` 是能力、限制、责任与行为承诺的机器可读真相源；本文档把这些契约翻译成业务人员、运行负责人和 reviewer 可以直接验收的 CLI 与文件行为。`docs/business_user_guide.md` 只负责首次使用教学，不得扩展本文档未声明的能力。

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

刷新一个完整批次时，运行负责人从 source-input closure clean 的工作区按照 `README_RUN.md` 依序执行阶段 `00` 至 `11`，随后单独运行 `scripts/12_validate_repair.py`。closure 由 `config/validation_source_policy.json` 定义；其中 runtime source directories、acceptance source files 和 policy 文件自身有未提交改动时都不算 clean。每个 wrapper 只执行一个固定阶段，仓库没有替代这一顺序的统一 orchestrator。
<!-- capability-anchor: BEHAVIOR.final_state_requires_full_sequence -->

业务验收对象是完成上述顺序且通过最终 gate 后的矩阵、证据、coverage、审计和报告。阶段 `08` 等中间产物可能仍包含待后续 repair 的值；`scripts/11_build_report.py` 即使内部 P0 检查失败也可能生成 NO-GO 报告，因此“报告存在”或“stage 11 exit 0”不等于“批次通过”。阶段 `11` / `12` 会先保持 manifest=`IN_PROGRESS`，用同一 run 的 projected terminal state 原子替换非 symlink regular report，并校验报告的 run_id/result；报告（阶段 11 还包括 README）持久化成功后才发布 manifest 终态。写入失败或 alias 目标时不得留下成功 manifest 与旧/缺报告的跨 run 组合。

stage 11/12 开始时会使旧 `outputs/validation_snapshot_provenance.json` 失效。stage 12 在主 gate 前读取 source policy，并机械检查 `SOP.md` 的权威引用是否已分类；未分类引用或把 explanatory non-authoritative 文件放在权威引用列都会失败。只有既有 Golden/repair/report terminal publication 成功，并且 source-input tree 与关键 artifact digest sidecar 已原子写入、重新读取且验证通过后，stage 12 才返回零。provenance postflight 失败必须使终态 fail closed，而不能留下可复用的旧 success proof。
<!-- capability-anchor: BEHAVIOR.validation_snapshot_binds_source_and_artifacts -->

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

用户最后先读 `outputs/validation_run_manifest.json`，只把 `refreshed_artifacts` 中的 tracked validation/audit 文件视为本次运行已刷新；随后必须运行 `python3 tools/check_validation_snapshot.py`，验证 source policy/SOP authority alignment、当前 source-input tree 与 `outputs/validation_snapshot_provenance.json` 记录的关键 artifact SHA-256/size。checker 通过后，再核对 repair validation、stratified audit、Golden、矩阵、evidence 与报告中的 GO、GO WITH CAVEATS 或 NO-GO。
<!-- capability-anchor: CAPABILITY.validation_verdict -->
<!-- capability-anchor: BEHAVIOR.validation_manifest_controls_freshness -->

`manifest.source_commit` 是运行时观察值。当前 HEAD 与它相同是最直接匹配；artifact commit 或 merge commit 改变 SHA 时，只有 checker 证明完整 source-input tree digest 和文件数仍一致、当前 source closure clean，才允许以 warning 继续。`+dirty` 只说明整个工作树含改动，不能区分生成 outputs 与源代码；任一 source byte/path set 或关键 artifact byte 变化都失败。

验收断言：Golden 必须是配置/generator/fixture 推导的 exact assertion set 且唯一；stratified audit 必须与当前 metrics 推导的五层样本 exact set 一致且唯一；request log 必须与整表 row-count/hash manifest、Git HEAD/base 已审核有序前缀、下游 locator 和已存 response sidecar 一致；full snapshot provenance 的 source closure、核心 artifact digest key set 与 `evidence/request_attempts/` recursive exact file set 也必须完整。任一缺行、重复/多余集合、已发布 snapshot 后相对 sidecar exact set 的 request attempt 删除/新增/篡改/alias、P0 repair validation、workspace 完整性、full 关键检查 `NOT_EVALUATED_MISSING_EVIDENCE`、source/tree mismatch 或 artifact hash/size mismatch 必须阻止正常通过；流水线自判不能替代外部审计接受。
<!-- capability-anchor: BEHAVIOR.gate_failure_propagates_to_verdict -->
<!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 5. 失败与受限验证行为

非法配置、未知阶段、关键 SEC 请求失败、未声明的不完整 workspace、dirty source closure、最终 gate 或 provenance publication/self-check 失败时，相关 CLI 必须明确报错并非零退出；不得用旧产物、旧 provenance 或空集合伪装成功。
<!-- capability-anchor: BEHAVIOR.fail_fast_on_invalid_or_incomplete -->

repair validation 的 status 只允许 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。缺少验证材料时不能返回 PASS；full 的关键 NOT_EVALUATED 阻止 GO，light 的 skipped / NOT_EVALUATED 只能进入 manifest caveat。light review 只有在缺少 full materials 且存在显式 marker 时才成立；没有 marker 的不完整工作区是 `WORKSPACE_INCOMPLETE`。
<!-- capability-anchor: BOUNDARY.light_package_not_full_validation -->
<!-- capability-anchor: BEHAVIOR.light_validation_is_explicitly_limited -->

验收断言：任何 light 结果都不得被描述为 full validation。`LIGHT_PACKAGE_NO_GIT` provenance 只能证明随包 bytes 未漂移；无 Git light 包缺少任一显式 singleton source 文件时必须失败，不能通过删文件缩小 source closure。

## 6. 责任边界

- 运行负责人提供有效 SEC organization/contact email，维护 registry，并控制从 source-input closure clean 的工作区顺序运行；当前示例邮箱不能作为生产合规证明。空/null/空白 organization、无合法 dotted domain 的邮箱或 example 域会同时被 acceptance 与 `SecHttpClient` 在网络请求前拒绝。
  <!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
- 业务与方法负责人复核近似、定性、缺失、解析失败和 `NEEDS_REVIEW`，并承担最终决策。
  <!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->
- 流水线提供证据、自判与 byte-level provenance，不签发投资、信用、报价、监管或外部审计结论。
  <!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 7. 可见性与可移植性

用户应以 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`、period 和 concept/section 定位来源。filing raw material 的 URL、accession、document、resolved path 与 hash 必须联合指向同一份 SEC 文档，不得用其他 accession 的同名同 hash 文件回填。新 artifact 不写生成机器绝对路径；历史 CSV 的 `local_path` / `source_path` 只是一条 relocation hint。旧绝对路径若含多个仓库目录 anchor，系统必须用当前 clone 的联合身份选出唯一后缀；同一 request 的 body 与 headers 还必须丢弃同一个旧仓库根前缀，不能把两个 clone 候选各自命中的文件拼成一条 observation。legacy request locator 会先查 exact snapshot；ledger body hash/length 必须命中 single-link regular body，同 body 多 attempt 只把不晚于 ledger timestamp 的最新匹配 `saved_at_utc` sidecar 归给该 row。snapshot body 不存在才验证原 working pair；body 存在但 header 缺失显示 `NOT_EVALUATED_MISSING_EVIDENCE`，body identity 错、同时间多匹配、大小写 namespace alias、symlink 或 hardlink 时失败，不选择 first/last candidate。新 SEC 请求的每次已发 attempt 必须落一条 observation，有响应体时 request-log locator 指向 content-addressed immutable body/header；最终文件名被 symlink/hardlink 抢占时必须失败且不得覆盖 victim。初始 URL 必须是精确官方 HTTPS origin，HTTP redirect 只记录首跳 3xx 与 Location，不会隐式请求下一跳。`evidence/requests_log_manifest.json` 以严格 JSON key/type 和 CSV 行 schema 绑定整表 bytes；working ledger 必须保留 HEAD 有序前缀；PR checker 先要求 base/HEAD 的每条 current/legacy row 与声明 schema 精确同宽，再对 legacy base 独立规范化 portable 完整字段、对 current base 逐字段保留有序前缀，之后只允许合法尾部追加，下游/sidecar 再反向覆盖完整集合。同一 repository 的 request-log publication 会在 cooperating threads / POSIX processes 间串行化；这不提供跨 client 全局限速，不承诺网络文件系统锁语义，也不构成对恶意同 UID 进程的 WORM。无 Git history baseline 或历史 row 的原 bytes 时必须显示 `NOT_EVALUATED_MISSING_EVIDENCE`，不能仅凭自签 manifest、URL 或文件存在宣称完整、可复现。
<!-- capability-anchor: BEHAVIOR.artifact_locator_is_clone_portable -->

validation snapshot provenance 同样是仓库内完整性机制，不是外部签名、透明日志或 WORM；它证明当前 source/artifact bytes 与已发布 sidecar 一致，不证明业务方法本身正确，也不能约束能同时改写全部文件并重签的人。

当前仓库未登记 UI、API、CI、部署状态、专用支持渠道或紧急联系人。

## 8. vNext recorded shadow 的可观察行为（尚未切流）

仓库已包含可离线复核的 vNext recorded shadow：Requirement/Spec、table-grid Reader input、recorded AI response、机械 Evidence、整单 Review、freeze/replay、Spec-driven Calculator、Projector 与 publication transaction primitives。它面向开发者、运行负责人和 reviewer，不是当前业务结果的新入口，也不替代第 3–5 节的 00–12 验收。
<!-- capability-anchor: CAPABILITY.vnext_recorded_shadow -->

### 8.1 审核酒店 disclosure group

reviewer 只能针对一个 run-scoped `ReviewUnit` 决策。`review.md` 必须显示 untrusted filing notice、完整目标表格、稳定 row/column 坐标、selected/competing/unresolved claims、mechanical Evidence、source/Spec identity 与 required claims。filing 中的 HTML、Markdown、prompt-like 文本、control、zero-width 或 bidi code point 都只是可见数据，不是 reviewer 或程序应执行的指令。完整表格以集中资源预算为前提：超出 HTML/表数/行列/span/entity 数字词法/span 展开 cell/文字上限时，table-grid 明确失败且不裁剪；超长 cell 在 review 中无损物理分行，总 review bytes 超限则不生成残缺审核页。
<!-- capability-anchor: BEHAVIOR.vnext_table_grid_resource_budget -->
<!-- capability-anchor: BEHAVIOR.vnext_review_renderer_resource_budget -->

批准是整个 ReviewUnit 的 HUMAN 决定，不是只批准一个数字。CLI 只显式收到 run directory、review unit hash、reviewer ID、decision、UTC time、reason 与 supersedes identity；它不要求 reviewer 复述系统已有的 claims：`REJECT` 自动形成空 approved claims，`APPROVE` 自动采用 ReviewUnit 的全部 required claims。缺字段、非 HUMAN identity、两个并行有效决定、底层 append 绕过或 OPEN 期磁盘 mutation 都会在 append/finalize/freeze/replay 的重验边界失败。Candidate、locator、source、Spec、unresolved、canonical context、renderer semantic version 或 rendered bytes 任一改变，旧决定不得继续生效。
<!-- capability-anchor: BEHAVIOR.vnext_review_binds_visible_unit -->
<!-- capability-anchor: BEHAVIOR.vnext_review_decision_semantics_replayed -->

### 8.2 freeze、replay 与结果读取

`OPEN` 只表示 Run 仍可追加记录；`FROZEN` 只表示完整 bytes/graph 已封存，不自动等于 validation PASSED 或 candidate PUBLISHABLE。`PASSED`、`FAILED` 与 `NOT_RUN` receipt 都可以 freeze 供审计/replay；后两者禁止 publication，`PASSED` 也仍须通过其他 publication gates。STARTED AI attempt 不能永久进入 FROZEN；每条 attempt 必须已是 SUCCEEDED/FAILED，每条 SUCCEEDED raw response 都会重放 Reader schema，即使没有 Candidate 引用也不跳过。Run 明确声明缺少 required source role 时，只允许把全 WITHHELD 结果封成审计 Run，任何 PUBLISHED Result 都会使 freeze 失败。Run 在创建时从 registry/profile 配置确定性投影并冻结 company traits，同时冻结 fiscal year 与精确 `YYYY-MM-DD` period start/end；fiscal-year 标签必须落在该期间内且期间不超过 53 周，跨年财年仍合法。workflow/finalizer 不接受调用方再次输入 traits、MetricSpec、metric/unit 或期间，freeze 还会从仓库重算 traits。freeze 前会从 RawBlob bytes 重建 table-grid，从 Run 内 content-addressed request/task/raw-response bytes 重建 Reader 请求和 Candidate，按原 payload、locator 与 compiled Spec constraint 重放 Evidence；B01/B03 结构化路径还必须从 SourceReference 绑定的 Company Facts raw bytes 重建 fact 选择与计算，B03 复用的 B01 Observation 即使没有独立 B01 Result 也不能跳过其自身 Spec 重放。ExecutionTrace 保存 exact calculation target；即使 structured Result 没有 selected Observation 且状态为 WITHHELD，freeze 仍从 raw bytes 重跑并核对失败原因。1.01% cross-check rejection 必须能形成 FROZEN/replay audit Run；被拒分支只保留 cross-check/rejection 证据，不得留下已丢弃 component Observation ID。每个 ReviewUnit 必须已有唯一有效 HUMAN decision；批准/拒绝后的 Observation roles 和 published Result/Trace 必须是完整 exact set。freeze 从仓库 Spec 重建全部 reviewed Observation并重跑 Calculator，所有非 supporting Observation 必须被 Trace 精确消费；随后比较 Result/Trace 的 metric、closure、unit、company、期间、scope、quality、applicability、publication 与 reason。数值结果 quality 取 input Observation 与 accepted Spec branch 声明中更保守者；因此 Pfizer 的 OI reconstruction 即使组件均为 EXACT，仍必须保持 APPROX。空 approval effect 不能把 AI-table 指标伪装成 structured input。Run validation receipt 还必须用 immutable-view hash 绑定 company/period/Spec/Requirement/source 身份，并绑定实际 records、decisions、review 与 attempt artifact exact set；receipt 后任一项漂移都不能 freeze。历史 FROZEN Run 的 replay 不接受 AI 凭据或网络对象；replay 只从这些冻结字节重算并比较。
<!-- capability-anchor: BEHAVIOR.vnext_company_traits_repository_authority -->
<!-- capability-anchor: BEHAVIOR.vnext_result_business_state_rebound -->
<!-- capability-anchor: BEHAVIOR.vnext_structured_withheld_replay -->
<!-- capability-anchor: BEHAVIOR.vnext_freeze_accepts_audit_validation_states -->
<!-- capability-anchor: BEHAVIOR.vnext_publication_requires_passed_validation -->

vNext MetricResult 同时暴露 `applicability`、`quality`、`publication` 与 `reason_code`。`N_A_STRUCTURAL`、`NOT_MEANINGFUL` 和 `WITHHELD` 不得折叠；non-lodging 会留下可 freeze/replay 的 N/A Run/Result/Trace，同时保持 source/AI 调用数为零。任何 APPLICABLE/WITHHELD 都会把整个 candidate 标为 BLOCKED。BatchManifest 从 registry、traits/applicability 与 release plan 派生完整 company×metric exact set，再逐个重载 PASSED FROZEN Runs；单公司 Run、缺 N/A、重复/额外坐标或跨 period 混批不会得到完整 batch。Projector 先要求 legacy metrics/evidence/Golden 精确匹配 frozen baseline，再从该 batch 实际生成 metrics/evidence/compatibility 与 repair execution bytes；Spec 声明的常量覆盖相应字段，review source 未拥有的 legacy metadata 保留 frozen baseline。同一 registry-mapped `(company_id, metric_id)` 多 scope 不会隐式覆盖，evidence 方法字段变化必须逐 cell 留痕。publisher 以 bundle 内 ProjectionManifest 与 batch/run/result row proof 为准，不接受游离 `migrated_results`、任意 legacy/staging bytes或调用方自写 PASS 改写结论。
<!-- capability-anchor: BEHAVIOR.vnext_withheld_cannot_publish -->

### 8.3 candidate、active 与 latest

事务原语区分三种可见身份：staging candidate、上一成功 active publication、最近一次 latest Run/batch publication。正式读取者必须 pin 一个 `PublicationView` 后从同一 bundle 读取 metrics/evidence/coverage/Golden/validation/report inputs；不能在一次读取中重新解析 pointer 或混用根目录 bytes。report input loader 只读，不触发 repair、AI、SEC 网络或 authoritative write。publication gate runner 在重新执行 Projector 与 semantic audit 后，从 verified candidate 生成 coverage/scalability/stratified、`PASSED_RECORDED_ONLY` manifest 与 recorded README/report，再产生 receipt；只有逐 byte 相等的已有文件可保留。只有 PASS 名称、自写 repair/report PASS 与自洽 hash、没有 execution evidence 的调用方自签 receipt 会被 prepare 拒绝。该 recorded proof 不等于现行 Stage 10/12 已对 active pinned view 完整重跑；真实十公司 staging/full gate 仍属于 Cutover 前置项。

若 latest Run 失败或 withheld，`latest_run_status` 必须显示失败原因、candidate status、active publication ID、空的 latest publication ID 以及 `active_is_latest_success=false`。单个 FROZEN Run 也只能显示 `NOT_EVALUATED`，不能代表完整 batch；prepared publication 的 latest identity 来自 BatchManifest。writer 只接收 persisted `run_dir` 或 publication ID，在 publication pointer lock 内加载其真实状态，再重读并验证 active pointer/bundle；调用方不能提交 `FAILED/BLOCKED` 枚举、`active_is_latest_success` boolean、view 或 manifest 让 writer 打假。只有 latest/active publication ID 相同且 latest 为 `FROZEN/PUBLISHABLE` 时，派生值才是 `true`；staging 尚未 commit 时即使全部 Run 已冻结也必须为 `false`。active 仍是上一成功版本，不能被描述成“最新运行成功”。storage、active pointer/lock、latest status 与 compatibility mirrors 全部从单一 publication root 固定派生，commit/rollback/recovery/view/status API 不再分别接受这些路径。缺 bundle 文件、ProjectionManifest/receipt required check/evidence hash、candidate view、artifact path/SHA-256/size 任一不匹配，或发生 row drift、hash drift、CAS loss、mirror write/postcondition 失败，都不能移动 active。rollback 只允许切回当前 active pointer 记录的 committed predecessor；prepared 但从未 committed 的 sibling 不能借 rollback 激活。read-back 会重算 bundle 内的 row/gate/content proof 与 byte integrity，但不会重新访问已清理的 Run/legacy 目录或把当时的外部 full validation 再跑一遍。
<!-- capability-anchor: BEHAVIOR.vnext_latest_active_separate -->

### 8.4 当前不能执行的承诺

截至本次 recorded 实现，request-ledger 有序前缀/membership adapter 与单 Run 跨进程多写者编排尚未进入 full staging，D-01 仍 PENDING，SEC 配置仍是示例邮箱，且没有第二真实 lodging filing、实现冻结后的独立 holdout、remote live 三轮相同 review hash、完整十公司 staging parity、旧 lodging/B03 producer 退出、active Cutover 或真实 rollback/full acceptance 证据。因此：

- `tools/run_acceptance.py --scope recorded` 的最高状态是 `PASSED_RECORDED_ONLY`；
- `--scope full` 必须把可能联网的 stage 00–11 保持为 NOT_RUN，但仍真实执行纯离线 Stage 12 与 snapshot checker；任一离线失败使 receipt 为 FAILED，离线通过但外部前提未满足时返回 BLOCKED，不能让 D-01/示例邮箱掩盖 active snapshot 漂移；
- 根目录现行 report/CSV/manifest 继续按第 3–5 节读取；不存在可供业务用户采信的 vNext active publication。

这些限制是当前能力边界，不是 caveat 可豁免项。
<!-- capability-anchor: BOUNDARY.vnext_cutover_not_complete -->
