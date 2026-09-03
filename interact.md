# SEC_metrics 用户可观察行为

## 1. 文档关系与读者

`capability_contract.json` 是能力、限制、责任与行为承诺的机器可读真相源；本文档把这些契约翻译成业务人员、运行负责人和 reviewer 可以直接验收的 CLI 与文件行为。`docs/business_user_guide.md` 只负责首次使用教学，不得扩展本文档未声明的能力。

当前项目没有 UI、API 或聊天入口。这里的“用户可观察”是指终端退出状态、仓库内文件、CSV 字段、证据链、validation manifest、snapshot provenance 和最终报告中能够直接核对的结果。

## 2. 当前定位

PR-B B0 is an offline developer/reviewer interface baseline. A scoped request
contains only certified windows, while the complete filing and native Evidence
checks stay local. Its synthetic PASS never means a provider answered correctly,
a fixture earned live qualification credit, or R4 was published. Deterministic
token estimates are labeled estimates; actual provider usage remains NOT_RUN.
<!-- capability-anchor: CAPABILITY.r4_offline_b0_interfaces -->

PR-B 的真实来源离线结果区分9个scoped positive、3个structured positive和4个zero-call class；不是16次或12次模型执行。Citi A03显示真实`2025Q4`，A13显示international net revenue而非net income。数值/scale/窗口及同源scope证明可按原始locator独立核验，旧原型失败报告保留为历史，不伪装成当前成功。v2尚未激活；可读结果与边界见`docs/r4_offline/README.md`。
<!-- capability-anchor: CAPABILITY.r4_offline_source_bound_evidence -->

SEC_metrics 是配置驱动、SEC-only、单财年批处理研究流程。它能为 `config/company_registry.csv` 中配置的逻辑公司生成最新年度申报的指标、治理、风险与事件结果，并保留可审计证据。
<!-- capability-anchor: CAPABILITY.sec_latest_fiscal_batch -->
<!-- capability-anchor: CAPABILITY.sec_governance_risk_event_signals -->

它不是自然语言问答系统，不会在运行时追问公司、日期或指标；也不是实时行情、生产API、daily scheduler或报价模型。当前committed active为R3，含24指标/240个vNext结果keys/327行public matrix，previous精确为R2。历史provider余额失败不是当前R3不存在的证据；但R3仍不代表financial/text完成或39指标最终full acceptance。
<!-- capability-anchor: BOUNDARY.configured_batch_not_interactive -->
<!-- capability-anchor: BOUNDARY.sec_only_point_in_time -->
<!-- capability-anchor: BOUNDARY.not_production_service -->

## 3. 入口与完整完成态

没有active pointer时，业务用户可以继续读取既有root snapshot，但legacy Stage04/09/11不得在源码repository root重写它；内部operator用`sec_pipeline.py --workspace-dir <absolute-isolated-root> <stage>`把完整candidate链显式指向同一隔离数据根，这些stage只生成非迁移输入并对migrated写入fail closed。正式刷新使用`tools/vnext_operator.py`/`tools/vnext_cutover.py`的同一recorded/live状态机；完整验收由`tools/run_acceptance.py --scope full --execute-live`编排Cutover及new/rollback/restore三轮，每轮只启动一次`tools/vnext_terminal_cycle.py`并在单次pin中完成Stage10 Golden、Stage11 report、Stage12 active validation与snapshot publish/verify。任何source byte漂移都不能full PASS。
<!-- capability-anchor: BEHAVIOR.final_state_requires_full_sequence -->

业务验收对象是上述formal顺序最终恢复的active bundle及其root mirrors。隔离legacy candidate中的阶段08/11产物可能仍含待repair值，不能因报告存在或stage11 exit0而当成active。active Stage11只读bundle report；active Stage12再验证formal receipt、全部mirrors与provenance，任一失败都阻止full PASS。

legacy/isolated candidate 的 stage 11 一旦改变 artifact，旧 `outputs/validation_snapshot_provenance.json` 就因 byte mismatch失效；stage 12开始时再显式移除旧sidecar。active stage 11不修改sidecar或root mirrors。stage 12在主gate前读取source policy，并机械检查`SOP.md`的权威引用是否已分类；未分类引用或把explanatory non-authoritative文件放在权威引用列都会失败。只有Golden/repair/report或active PublicationView terminal validation成功，并且source-input tree与关键artifact digest sidecar已原子写入、重新读取且验证通过后，stage 12才返回零。active provenance postflight失败只失效新sidecar并从official pointer恢复mirrors，不能把bundle-derived manifest/report改写成synthetic FAILED/NO-GO。
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

- 运行负责人维护 registry、提供环境凭据并控制 clean checkout 运行。SEC organization 固定 `axaxl`，程序自动读取 `config/sec_config.json.contact_email`，可用 `SEC_CONTACT_EMAIL` 显式覆盖；DeepSeek key 仍只从 `DEEPSEEK_API_KEY` 读取。选中邮箱缺失、畸形或使用 reserved domain 时会在联网前失败，secret 不写入 artifact。
  <!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
- 业务与方法负责人复核近似、定性、缺失、解析失败和 `NEEDS_REVIEW`，并承担最终决策。
  <!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->
- 流水线提供证据、自判与 byte-level provenance，不签发投资、信用、报价、监管或外部审计结论。
  <!-- capability-anchor: RESPONSIBILITY.external_auditor_owns_acceptance -->

## 7. 可见性与可移植性

用户应以 `source_url`、`repo_relative_path`、`content_sha256`、`accession`、`document_name`、period 和 concept/section 定位来源。filing raw material 的 URL、accession、document、resolved path 与 hash 必须联合指向同一份 SEC 文档，不得用其他 accession 的同名同 hash 文件回填。新 artifact 不写生成机器绝对路径；历史 CSV 的 `local_path` / `source_path` 只是一条 relocation hint。旧绝对路径若含多个仓库目录 anchor，系统必须用当前 clone 的联合身份选出唯一后缀；同一 request 的 body 与 headers 还必须丢弃同一个旧仓库根前缀，不能把两个 clone 候选各自命中的文件拼成一条 observation。legacy request locator 会先查 exact snapshot；ledger body hash/length 必须命中 single-link regular body，同 body 多 attempt 只把不晚于 ledger timestamp 的最新匹配 `saved_at_utc` sidecar 归给该 row。snapshot body 不存在才验证原 working pair；body 存在但 header 缺失显示 `NOT_EVALUATED_MISSING_EVIDENCE`，body identity 错、同时间多匹配、大小写 namespace alias、symlink 或 hardlink 时失败，不选择 first/last candidate。新 SEC 请求的每次已发 attempt 必须落一条 observation，有响应体时 request-log locator 指向 content-addressed immutable body/header；最终文件名被 symlink/hardlink 抢占时必须失败且不得覆盖 victim。初始 URL 必须是精确官方 HTTPS origin，HTTP redirect 只记录首跳 3xx 与 Location，不会隐式请求下一跳。`evidence/requests_log_manifest.json` 以严格 JSON key/type 和 CSV 行 schema 绑定整表 bytes；working ledger 必须保留 HEAD 有序前缀；PR checker 先要求 base/HEAD 的每条 current/legacy row 与声明 schema 精确同宽，再对 legacy base 独立规范化 portable 完整字段、对 current base 逐字段保留有序前缀，之后只允许合法尾部追加，下游/sidecar 再反向覆盖完整集合。同一 repository 的 request-log publication 会在 cooperating threads / POSIX processes 间串行化；这不提供跨 client 全局限速，不承诺网络文件系统锁语义，也不构成对恶意同 UID 进程的 WORM。无 Git history baseline 或历史 row 的原 bytes 时必须显示 `NOT_EVALUATED_MISSING_EVIDENCE`，不能仅凭自签 manifest、URL 或文件存在宣称完整、可复现。
<!-- capability-anchor: BEHAVIOR.artifact_locator_is_clone_portable -->

validation snapshot provenance 同样是仓库内完整性机制，不是外部签名、透明日志或 WORM；它证明当前 source/artifact bytes 与已发布 sidecar 一致，不证明业务方法本身正确，也不能约束能同时改写全部文件并重签的人。

当前仓库只登记了在 PR 上运行 fast suite 的 GitHub CI check；未登记 UI、API、生产 scheduler、部署状态、专用支持渠道或紧急联系人。CI green 只证明该 fast boundary，不表示 live、full acceptance 或部署完成。

R1–R3继续按不可变bundle与历史schema读取；successor五文件snapshot使用保留的versioned engine。三个SUCCESSOR_* record subtype必须携带独立generation与完整id/closure/hashes，删除这些字段不能落回legacy。旧ReleasePlan原本已有id/closure，不会被误判为successor；旧RUN/Publication的hashes必须等于所选历史Requirement。后来合法root catalog/config变动不改变已记录parent closure，但新执行必须符合自身execution authority。policy内容来源、closure校验、exact-head activation与live grant分别显示；PR #29当前NOT_ACTIVATED，transition不改变active R3、14 mirrors、指标值或live能力。
<!-- capability-anchor: CAPABILITY.issue_28_profile_requirement_authority -->

## 8. vNext formal Cutover 的可观察行为（R3 partial active）

仓库已包含同一套recorded/live operator与formal publication primitives。当前active pointer是Issue #15 R3业务入口，覆盖24个累计指标、240个累计vNext Result keys和327行public matrix；recorded sandbox仍不能修改或冒充它。previous pointer精确指向R2，不能把这个partial active写成39指标最终Cutover。
<!-- capability-anchor: CAPABILITY.vnext_recorded_shadow -->

Issue #15 WB-2 另外提供一份可机械加载的39指标SourceStrategy registry，只描述target route；当前ratchet set只能从不可变ReleasePlan chain的`cumulative_metric_ids`读取。loader要求parent累计metrics、vNext keys与retired producers分别为child子集，并显式推导removed/unretired exact set为空；同步重签全部hash不能合法化删除。该registry完成时root `outputs/metrics_matrix.csv`仍与WB-1冻结SHA-256一致，未执行任何adapter、SEC/模型调用或active publication；不能把“route已登记”读成“指标已迁移”。
已发布R1/R2 ReleasePlan继续显示其发布时Requirement closure；current D-07/Requirement closure另行显示，二者不同不是plan stale或active drift。系统不得为了让historical plan等于current closure而重签plan/index/publication；future plan才绑定创建时的current authority。
<!-- capability-anchor: CAPABILITY.issue_15_source_strategy_registry -->

WB-2B 的确定性 router 使用同一 `sources[]` 形状表达单源与多源，并以pinned SEC submissions current/history shards、仓库immutable acquisition receipts补集和SourceSetManifest union证明发现集完整；不从legacy events反推source set。R2已用该路径正式发布；C01/E03共用Item 5.02 claims，E02/E04零值绑定完整8-K集合，E01 matched key set在Result生成后与legacy逐项相等。
<!-- capability-anchor: CAPABILITY.issue_15_deterministic_source_router -->

WB-3 把模型调用表达为 release-input plan→AI invocation plan→execution→immutable attempts。provider response必须先通过严格schema、task contract、Candidate构造和真实mechanical Evidence，形成绑定Spec/source/DerivedAsset/Candidate/Evidence的acceptance receipt，才可标记SUCCEEDED并成为exact reusable response；resume会重新验证该完整closure，Workflow重算结果也必须与其exact一致。若成功response已持久化但execution尚未seal，dead reservation会以原marker/attempt/acceptance/response重建原`SUCCEEDED` terminal，不得产生带marker的`REUSED_SUCCESS`；execution seal后archive中断只补archive。无 reusable response 时只有通过独占 reservation 的 owner 可以打开唯一provider opener。context限制来自版本化provider/model authority；当前`UTF8_BYTE_UPPER_BOUND`是安全上界而非exact token数。operator 可分别观察 real egress、paid-endpoint call 和 mock invocation：paid-endpoint call由billing class与真实egress marker联合推导，不表示provider已确认账单。`UNKNOWN_REMOTE_OUTCOME` 必须人工核对，不会自动重试；由于没有封存的WB-3 attempt receipt，Run attempt不得声称一个provider request ID，必须与WB-3的空request-ID set一致。仓库不显示或执行金额 cap，cost 只作观测；资源 hard limit 仍在 egress 前拒绝。本 PR 的 zero-AI R1/R2 只产生三种计数为 0 的 structured-only 证据。
<!-- capability-anchor: CAPABILITY.issue_15_invocation_control -->

PR-3阶段A新增的table transport/scope/task freeze仍是离线开发证据：expanded grid不变，模型传输只可用可逆compact payload；Reader/Evidence/attempt可见六项expanded/compact/decoder/round-trip binding。一个scope locator可机械支持多个raw dimension；Evidence必须逐字节重取完整locator，再以唯一边界严格的literal/token-sequence proof分别验证raw value，系统仍只按MetricSpec exact enum alias规范化。未知alias显示为Candidate `REVIEW_REQUIRED`并只能进入HUMAN review，绝不变成新的quality或SYSTEM auto approval。`config/source_strategy_fallback_representation.json`必须先以SourceStrategy SHA-256验证fallback table/text语义；由此派生的每个catalog task只拥有一个role、MetricSpec scope/schema/prompt identity，matrix 的task ID会实际进入formal Workflow、Run manifest、prepared Reader request、provider envelope、attempt audit、Review、FROZEN validation和fresh replay，每次仍输入全文档全部table set且不得回退schema-v1 disclosure request。含catalog task binding的Run从创建、optional SYSTEM review至remote transport replay固定使用Issue #15 effective D-01/D-06；将父Requirement hashes写进这种Run会在freeze/replay失败，保留historical disclosure Run才使用父closure。catalog LIVE task不能由普通 Workflow 参数直接执行：唯一qualification executor从current matrix、freeze、Stage-A snapshot、immutable source、task plan和provider policy重建opaque authorization，shared Workflow在读source或进入WB-3前重验它；成功attempt同时成为qualification evidence并写入cycle-owned ledger。每次freeze validation也独立重建R2 active publication、pointer和四个root business artifact binding；任何改变都以`r2_root:*`使全部authorized family失效。executor以requested family scope重验Stage-A snapshot identity、historical R2/root/freeze binding，并复用freeze已验证的shared与该family local closure/loader；另一family即使source bytes缺失或SHA不符、task缺失、MetricSpec无法解析，也只产生owner family的稳定local reason，不会阻断当前family plan/authorization。完整source tree/file-count与artifact-only equivalent-tree模型继续由无family scope的离线snapshot checker严格验证。WB-3 regression receipt v2只记录稳定test outcome/test source identity，不把unittest elapsed line、stdout/stderr hash、PID或临时路径混入content-addressed freeze ID；同一commit和frozen timestamp的完整freeze可重建为同一receipt ID。旧 `vnext_qualification prepare` 只拥有disclosure fixture，会在选择任何family gate前以`TABLE_TASK_CONTRACT_REQUIRED`拒绝，未来也必须改接显式catalog task。freeze以传递shared engine closure保护共用执行语义并传播到全部依赖family，以matrix/task/MetricSpec family fragments保护局部语义；`require_table_qualification_freeze(family_id=...)`只消费shared closure、该family local closure及其自身context/resource状态，不能用另一family blocker拒绝当前family；schema-v3 `table_qualification_freeze_receipt`可见11组round-trip、每个本地development source×task envelope、split-cost baseline、WB-3 mock regression、token/context estimates、R2 root/active equality、protected hashes、本cycle三种real egress计数，以及每个family的`context_gate/resource_gate/protected_closure_gate/live_ready/blocking_reason_codes`。effective D-07的200000门为inclusive；当前lodging最大392447并记录`ESTIMATED_CONTEXT_LIMIT`，financial完整grid记录`NOT_AVAILABLE_RESOURCE_LIMIT`与`EXPANDED_GRID_RESOURCE_LIMIT`，因此`live_ready_family_ids=[]`。这不是qualification失败；receipt不重签R2、也不等于live qualification，尚不得开始capture、qualification、AI迁移、publication或R3。

上一段中的schema-v3与“lodging全部context blocked”是Stage-A历史界面。当前schema-v4 freeze新增`readiness_by_task_request`：每个task/request显示exact provider request SHA、estimated tokens、`ESTIMATED_BOUND`或`PROVIDER_REPORTED_EXACT_BINDING`、attestation ID、resource/closure状态；family overall只在全部required task/request通过时为true。当前attested Marriott request虽estimated=392447，但exact Stage C-B binding的actual prompt=160937，因此该request context PASS；sibling request的exact SHA/task hash不同，显示`EXACT_CONTEXT_BINDING_MISMATCH`与`EXACT_CONTEXT_EVIDENCE_REQUIRED`，所以lodging family仍`live_ready=false`、`live_ready_family_ids=[]`。context PASS不等于qualification authorization；measurement response仍不可作为generic reusable success或qualification evidence。

Stage-B context investigation receipt面向reviewer显示当前provider/system/table逐字节分解、raw/normalized与重复结构census、五个research-only候选的per-source/task exact envelope和maximum。连续运行使用相同source bytes会产生相同receipt ID；当前没有候选低于200000。`machine_reversible=true`只表示工具decoder逐字段恢复expanded authority，不能读作模型提取准确率不下降；dictionary/string reference、raw-only normalization、delta coordinate和combined-role task均需另行qualification且当前未进入production。

Stage-B financial grid census receipt面向reviewer显示JPM exact HTML binding、全部679张表的order/table-id候选/shape/source/rectangular/blank/span/text/size、top 50及production 100000门的exact触发表。工具得到124761个rectangular coordinates，但不创建完整expanded dict/list；materialization benchmark显示`NOT_RUN_RESOURCE_SAFETY`。OPTION-A提高cap、OPTION-B immutable per-table shard+ordered manifest、OPTION-C较小development source都只记录可复算事实与风险，`selected_option=null`，不代表owner已选择任何路线。

current owner packet以`OWNER_APPROVED`和`STILL_UNDECIDED`两个顶层区块避免把“已批准门禁”与“仅调查路线”混写。它同时显示每family readiness、两份调查receipt identity、active/root equality、actual prompt tokens与三类egress；pointer更新不会删除旧packet。当前空live-ready set是诚实Stage-B终态，不是qualification失败，也不授权operator继续live。

Stage C-A新增的`vnext_table_context_measurement.py plan`只离线重建并保存一个exact lodging usage-measurement plan，显示estimated-input、普通qualification 200000门仍阻断、Marriott/task/serializer/prompt/schema/request/provider/protected-closure binding及`repository_head_binding=REQUIRED_AT_EXTERNAL_AUTHORIZATION`。`execute`不会接受family/task/source/serializer/provider override；除exact `AUTHORIZE_ONE_TOKEN_MEASUREMENT`、当前clean HEAD和UTC授权时间外，还要求独立PR top-level review comment URL与该评论绑定的exact provider request SHA-256。provider socket/mock egress立即前的marker是互斥claim：任何既有marker（即使bytes相同）都返回`AUTHORIZATION_CONSUMED`，只有`O_EXCL`唯一创建者在file+directory fsync后继续。确定性双进程测试以相同authorization/clock和callback barrier证明总opener=1；顺序第二次同样稳定拒绝。marker前失败保留未消费状态但不会自动继续。terminal measurement evidence只显示provider raw usage、HTTP/transport状态、request/response hash、token/cache字段与egress计数；缺prompt/input usage显示`FAILED_USAGE_UNAVAILABLE`，绝不从bytes/token历史比例猜值。该evidence明确`qualification_credit=false`、`publication_eligible=false`、`response_reuse_for_qualification=false`。
<!-- capability-anchor: BEHAVIOR.vnext_table_stage_c_token_measurement -->

Stage D已复用同一plan/executor/marker/evidence边界完成唯一RevPAR measurement：review绑定exact head `290c1119…`与request `1dbe25dd…`，provider usage为160928 prompt、535 completion、161463 total，HTTP 200、retry=false、real model/paid/SEC=`1/1/0`。同一`TABLE_CONTEXT_FEASIBILITY_ATTESTATION` record type生成`d3824ed2…`，不新增packet/pointer/state machine；历史occupancy bytes不改写。两个measurement authorization现均永久消费，新plan/execute稳定拒绝。两份response仍不得计入qualification ordinal、business Result或publication，key未写入任何artifact。

上述“新plan稳定拒绝”只适用于旧prompt/request generation。三次qualification schema terminal后，2026-08-26 owner明确覆盖旧no-remeasurement规则，但只覆盖两个修订prompt request：schema/MetricSpec/source/serializer/provider/model/API不变，旧attestation保持historical且不给current credit。CLI现在必须用exact-enum task ID分别生成两个新plan；同一one-shot executor为每个content-addressed cycle单独claim marker，独立exact-head review后每task最多一次、retry=0。新response只供usage/attestation，仍无qualification、Result或publication credit；两份新attestation都有效前qualification保持关闭。

Stage C-A JPM benchmark入口先显示hard-guard preflight，再决定是否启动child。当前receipt为`NOT_RUN_RSS_GUARD_UNAVAILABLE`：Darwin共享虚拟映射使512 MiB RLIMIT无法可靠设置，所以完整parser/materialization从未开始。界面必须把peak RSS、wall time、canonical JSON bytes与DerivedAsset ID显示为null/NOT_RUN，不得拿Stage-B估算填充；仍可核验exact JPM SHA、Stage-B 679/124761 census、test-only 187142仅属于未启动child、production 100000 bytes不变、active/root相等及0/0/0 egress。该结果是Stage C-A BLOCKER。
<!-- capability-anchor: BEHAVIOR.vnext_table_stage_c_financial_materialization -->

Stage C-A packet界面按`OWNER_APPROVED`、`IMPLEMENTED_NOT_EXECUTED`、`MEASURED_OFFLINE`、`STILL_UNAUTHORIZED`、`BLOCKERS`显示，不把实现或NOT_RUN写成live evidence。当前measurement只显示plan ID，`authorization_id=NOT_ISSUED`；packet绑定review 5014458726与其旧exact head，B1只可显示`RESOLVED_PENDING_INDEPENDENT_REREVIEW`，不能由作者自判APPROVED。JPM显示guard blocker及四个null measurement；active publication、309 rows、root before/after和0/0/0 egress必须逐byte可复算。snapshot checker的Stage C-A PASS表示历史R2非source artifacts与当前source overlay同时闭合，不表示benchmark completed、真实measurement、qualification或publication。
<!-- capability-anchor: BEHAVIOR.vnext_table_stage_c_a_packet -->

Stage C-B packet界面显示独立review 5014622571锚定的exact head/tree、plan/cycle/authorization，以及唯一marker、provider request ID、raw response/evidence/usage hashes。当前terminal必须显示`COMPLETED`、HTTP 200、160937 prompt、576 completion、161513 total、0 cache hit、160937 cache miss、retry=false和real model/paid/SEC=1/1/0。界面还必须同时显示authorization已永久消费、额外measurement未授权、qualification/publication credit=false、普通200000门仍阻断。Stage C-A 0/0/0 packet继续作为历史对象，不得重写为1/1/0；JPM仍显示`NOT_RUN_RSS_GUARD_UNAVAILABLE`、四个null与`F3_NEED_MORE_EVIDENCE`，active R2/309 rows/root不变。Stage C-B packet和snapshot checker都是离线验证入口，不得再次调用provider，也不代表qualification、R3/R4、publication或Issue完成。

新的post-attestation Stage-C packet不改写Stage C-B历史1/1/0；它显示本PR自身real model/paid/SEC=`0/0/0`，并把attested request、sibling request与family overall分三层展示。attested request显示full request SHA、392447 estimated、160937 actual、39063 headroom、`CONTEXT_FEASIBLE / PROVIDER_REPORTED_EXACT_BINDING`，同时显示qualification credit/reuse均false；sibling显示`EXACT_CONTEXT_EVIDENCE_REQUIRED / NO_SOUND_CROSS_TASK_TOKEN_BOUND`，不展示任何比例外推。packet还显示measurement authorization永久消费、additional measurement/live qualification/fresh ordinals/R3/publication均未授权，financial仍`F3_NEED_MORE_EVIDENCE`，active publication和四个root hashes逐byte不变。
<!-- capability-anchor: BEHAVIOR.vnext_table_stage_c_b_packet -->
<!-- capability-anchor: BEHAVIOR.vnext_table_exact_context_attestation -->
<!-- capability-anchor: BEHAVIOR.vnext_table_sibling_context_analysis -->

任何`egress_attempted=true`的catalog attempt都必须在Run manifest、attempt、`TABLE_QUALIFICATION_EVIDENCE`和freeze receipt指定的唯一provider ledger中持有逐字节相同的authorization；缺其中任一项时，finalize、freeze、load和replay均fail closed，只有`egress_attempted=false`的recorded catalog attempt可保留为离线证据。cycle validation还从receipt-owned WB-3 workspace读取actual egress marker/execution/attempt/success/UNKNOWN closure；WB-3、Run attempt、ledger和evidence四个terminal set必须完全相等。远端FAILED/UNKNOWN attempt若缺payload、ledger、evidence或cycle closure，会显示未物化状态并在同一Run补齐，期间绝不再次调用provider；只有完整closure才返回最终`FAILED_TERMINAL`或`UNKNOWN_REMOTE_OUTCOME`。`egress_attempted=false`的credential/local preflight失败不生成remote ledger/evidence，修复本地条件后仍可继续该ordinal。429/timeout/recoverable 5xx穷尽时，WB-3必须是`FAILED_RETRYABLE_FINAL`，其两个marker、attempt序列及最后provider request ID与Run attempt精确相符。恢复中的Run只有payload hash、Candidate/Evidence/ReviewUnit binding、review context/Markdown assets和checkpoint清理都完成后才显示`COMPLETE_OPEN_PENDING_REVIEW`；HTTP 400/401/402/422、schema或Evidence terminal failure显示`FAILED_TERMINAL`且不再次调用provider。authorization从matrix重建exact target period、source media type、deterministic Run ID/目录与ordinal terminal identity，不能被重用于其他财年、期间、媒体或任意Run；ledger append先验证receipt的before SHA-256/row-count prefix，再通过独占锁追加。validator不信任receipt自报的readiness：它先重算immutable receipt内部的aggregate D-07/shared evidence，并在每个execution family gate前重验Marriott provenance、10份layout manifests和有序11份WB-4 source bytes的path/declared SHA/actual SHA/size exact set；任一missing、manifest或source-byte drift都以shared reason阻断两个family，恢复exact bytes后才恢复ready。execution scope只加载requested family的matrix sources、task/MetricSpec与measurement slice，无法重建的local authority转换为owner family reason，不要求siblings loader成功；aggregate maximum/any只作receipt evidence，不能作为跨family执行门，unexplained round-trip/estimator drift仍按shared dependency传播。同一进程只可复用由requested matrix/task/MetricSpec、Requirement/D-07、actual source SHA及measurement engine bytes绑定的非持久结果，任何相关输入漂移均重新测量。effective D-07已决，所以`d07_decision_required=false`；family未ready只返回自己的稳定reason codes，shared drift仍传播到全部依赖family。此段最后的未授权结论只属于pre-RevPAR历史freeze/packet；current live scope以下段为准。

latest D-07已把live qualification限定到lodging两个current task。`vnext_qualification.py table-plan`显示matrix-owned phase/source/request：second layout=Marriott FY2024、replacement holdout=Marriott FY2023、fresh=Marriott FY2025；CLI不接收source/company/period override。同issuer独立性必须重验不同fiscal year、accession和source bytes，并机械证明至少两项layout差异。FY2023 exact source由既有`SecHttpClient`一次HTTP 200/retry=0获取；offline proof定位唯一`table_000011`，同表含2023 RevPAR 124.70、Occupancy 69.2、`Comparable Systemwide Properties`与`Worldwide`，全文档table count为66（FY2024=67、FY2025=68），且FY2023/FY2024目标表第11/13行span geometry不同。source-only fixture不含可复用模型response。每个`table-execute`仍生成新的WB-3 execution、provider ledger row、qualification Evidence、Review、Result与FROZEN Run；estimated超200000的plan只可在独立exact-head review逐plan/request绑定后执行，并由各自新response的provider usage terminal判断，缺usage或actual prompt超限立即terminal、零重试并停止后续lodging plans。两个second-layout task都FROZEN后，`table-freeze`用既有`PRODUCTION_SEMANTIC_FREEZE`类型绑定production tree和ledger prefix；holdout只能在freeze后，三个fresh ordinals只能在两个holdout task FROZEN后。该顺序不新增measurement、不复用历史response，也不自动授权R3 publication。

R3 module-owned路径复用现有Issue #15 ReleasePlan、catalog task Workflow、Projector、ValidationReceipt和CAS bundle verifier。它重新读取十个committed qualification terminal并机械重跑DerivedAsset/Evidence/Review/Calculator，只把两个final fresh Run用于APPLICABLE production coordinates；其余18个company×metric坐标由零AI structural FROZEN Runs产生。strict compatibility仍以冻结legacy A作oracle，完整public assembly以pinned R2作predecessor，形成24个累计指标、240个累计vNext keys、327个public rows。正式CAS提交、bundle read-back与root mirror equality均已通过；修复header-only audit文件的换行兼容时还真实执行了R3→R2 rollback→修正版R3，当前previous精确为R2。
<!-- capability-anchor: CAPABILITY.issue_15_r3_ratchet_prepare -->

Fresh ordinal在CLI上仍显示同一个exact provider request SHA，这是稳定输入而不是response复用许可。每个task plan会显示不同的plan/terminal/Run identity，并在cycle父目录下使用plan-owned WB-3 namespace；因此相同request bytes仍必须真实产生新的provider request ID、egress marker、attempt、response、acceptance、ledger row和FROZEN Run。cycle状态从全部plan namespaces聚合，业务人员不能把前一ordinal的success文件复制或链接到后一ordinal。执行顺序按ordinal-major跨两个task推进，任一terminal failure或usage门失败会阻断全部剩余fresh。

plan-owned修复后的SECOND_LAYOUT Occupancy只调用一次并报告159479/560/160039、HTTP 200、retry=0，但模型从serializer-v2 cell tuple复制了normalized `x[6]="Worldwide (2)"`，没有复制exact raw `x[5]="\nWorldwide (2)"`，所以Evidence以`SCOPE_LABEL_TEXT_MISMATCH`终态拒绝，RevPAR未调用。latest frozen prompt只把既有tuple语义明示为`c=[caption,caption_raw_text]`与`x=[row_index,column_index,rowspan,colspan,header,raw_text,text]`，并要求scope raw text只取`c[1]`/`x[5]`、禁止`c[0]`/`x[6]`。这不改变serializer/schema/source/task/model或业务口径；旧response不能修补或复用，新plan仍需exact-head审核。

首个schema-v3 Hilton Occupancy response结构合法，但Evidence发现目标表自身caption为空而response引用了另一表或邻近正文，因此`SCOPE_LABEL_TEXT_MISMATCH`终态保留且不能修补。latest frozen prompt只新增目标表绑定：caption必须来自同一目标表的非空supplied caption raw text；否则scope evidence必须从同一目标表的一格复制八字段locator与exact raw text。旧161282/161263 attestations不再给新request current credit；新Occupancy/RevPAR measurements实际prompt为161433/161422并形成两份exact attestation，均retry=false、usage-only且不可复用。same-ID D-07已接受新proof并关闭additional measurement；current freeze/Stage-A重建通过前仍不能进入qualification。

Marriott FY2024 Occupancy新execution的usage为159376/550/159926并通过context gate，但模型把本地`"\nWorldwide (2)"`的leading LF删掉，Evidence以`SCOPE_LABEL_TEXT_MISMATCH`拒绝；RevPAR未执行且旧review授权随evidence commit失效。owner随后只批准raw-whitespace prompt强化：首尾空格/换行必须逐字保留并用JSON escapes输出，禁止trim/normalize/collapse；其他冻结边界不变。两份161433/161422 attestation因此只保留historical，additional measurement继续禁止，所有修订后的SECOND_LAYOUT、POST_FREEZE_HOLDOUT与FRESH_STABILITY samples改由exact-reviewed新qualification response usage裁决。

新cycle的FY2024两个second-layout task随后都达到FROZEN。Hyatt FY2025 Occupancy holdout虽以91588/704/92292通过context，却因目标表空caption、缺`Comparable Systemwide Properties`与`Worldwide`而`SCHEMA_VIOLATION`；RevPAR按stop rule未执行。owner批准的replacement只改变holdout source与独立性条件，不改变scope/Evidence/prompt/schema/serializer/provider/model/API或业务口径；Marriott FY2023 fixture必须先完成上述同表literal/value/layout证明，新cycle全部qualification response仍要求新execution且不可复用旧response。

修订后FY2024 Occupancy response的159479/562/160041 usage与leading LF、Evidence PASS、SYSTEM APPROVE、Result均已持久化，但本地finalization因registered Marriott的registry traits覆盖fixture-bound traits而返回`Run company traits differ from repository`，Run保持OPEN且无qualification credit；RevPAR未执行。修复后，只有`SECOND_LAYOUT`/`POST_FREEZE_HOLDOUT` authorization优先使用exact fixture traits，`FRESH_STABILITY`与普通production仍使用registry，历史无authorization外部fixture只在registry miss时fallback。该OPEN response只作失败诊断证据，不复用到新cycle。

当前D-07已授权lodging qualification，但每个authorization仍绑定`qualification_response_origin_policy=NEW_PROVIDER_EXECUTION_ONLY`与provider usage policy。Stage C-B raw response即使request SHA相同也不能进入qualification workspace或evidence；generic `REUSED_SUCCESS`的`egress_attempted=false`同样被拒绝。provider response必须存在prompt/input、completion/output与total usage，actual prompt不得超过200000；缺失或超限在success/acceptance持久化前成为`CONTEXT_LIMIT` terminal，controller只写一个attempt、不自动retry，并把后续ordinal列为skipped。context gate、task request ready与family ready只允许形成受审查plan；没有匹配当前exact head与request SHA的独立审核评论仍不能执行模型调用。
<!-- capability-anchor: BEHAVIOR.vnext_table_transport_scope_and_freeze -->

R1的module-owned入口保留A→B→A→B历史。R1/R2的migrated public rows先由Result/Trace/Claims、registry和repository-bound projection catalog完整渲染，legacy rows只在随后独立比较器中作为18×20/141×20字段oracle；approved delta和unexpected delta exact set均为空。R2在R1 B上累计22指标/220坐标，79个新增key均为`N_A_STRUCTURAL`，public matrix为309行；projection independence、event parity、retirement、active/read-back receipts均持久化。既有8-K body/header缺request-attempt locator时，只有request row和当前commit Git blob同时匹配才成为`IMMUTABLE_GIT_BLOB`，不会发起SEC网络。
<!-- capability-anchor: CAPABILITY.issue_15_zero_ai_r1_active -->
<!-- capability-anchor: CAPABILITY.issue_15_zero_ai_r2_active -->

正式 CLI 支持 prepare/init、status、review list/show/decide、resume/finalize、freeze/replay、project、publish、rollback、restore 与 acceptance。默认输出稳定错误且不显示 traceback，`--debug` 才显示 traceback，`--json` 提供机器可读结果。HUMAN decision 可选；若未写入，D-06 会以固定且可审计的 SYSTEM identity 写入完整APPROVE claims，绝不把SYSTEM伪装为HUMAN。

本PR未授权AI qualification；`tools/vnext_capture_qualification_fixture.py`与底层capture入口均在SEC/provider构造前稳定返回`AI_QUALIFICATION_EGRESS_NOT_ENABLED`。后续只有在WB-4+明确获准且capture也接入完整AIInvocationPlan/execution/reservation/acceptance closure后，才可重新开放第二布局或holdout录制。

冷启动 recorded operator 不要求阅读源码或 tests。`fixture list`/`fixture show --fixture-id ...` 会从仓库 catalog 返回 byte-verified fixture binding、SEC source/provenance identity，以及不含 caller business override 的可复制 prepare/Cutover 命令。运行 `tools/vnext_cutover.py --fixture-id ... --workspace-dir artifacts/vnext/recorded-<workspace>` 时，第一次调用从同一 release plan 创建 structured FROZEN Runs 与适用的OPEN review Run；既有HUMAN decision优先，否则D-06 SYSTEM decision使其继续完成finalization、validation、freeze、无网络 replay、complete BatchManifest、Projector、recorded validation，再只在固定 `<workspace>/recorded-publication` 内执行 pointer CAS、root-mirror materialization 与 pinned PublicationView read-back。

这条 cold-start flow 的 source/response/Spec/period/company authority 来自 catalog，调用方覆盖会以 `RECORDED_FIXTURE_OVERRIDE_FORBIDDEN` 失败；recorded Cutover workspace 第一层必须是 `artifacts/vnext/recorded-*`。live workspace固定为repository-owned `artifacts/vnext/cutover`，显式传入任何`--workspace-dir`都会在fixture/load/write前以`LIVE_WORKSPACE_OVERRIDE_FORBIDDEN`失败；qualification、publication、live-audit 与 Run namespace 不能由caller改作authority root。sandbox publication还必须闭合Batch实际消费的request rows：recorded可以验证历史row声明的唯一`LEGACY_WORKING_LOCATOR`，但body/headers的repository path、SHA-256、size必须exact并把locator tier/class及原bytes写入portable closure；formal/live只接受`IMMUTABLE_ATTEMPT`。live acquisition resume还会以当前解释器name/binary SHA-256、五条固定命令、ledger prefix/tail、attempt exact set与inventory current bytes重验pinned receipt。整个 recorded workflow socket=0，并在结束前 exact 比较正式 publication state、formal namespace tree 与 SEC ledger bytes，不能改 `outputs/active_publication.json`、repository root mirrors 或正式 evidence/audit namespace。测试中的 `TEST_ONLY_EXPLICIT_REVIEW` 只证明公开 UX/transaction path，不是 formal HUMAN 决定、live Reader、active Cutover 或 full acceptance。sandbox CAS 不扩大 generic authority：`publish --commit` 和 public generic formal commit API 仍稳定 fail closed。
live core还在任何业务read/write前exact固定module-owned repository、`artifacts/vnext/cutover`、`outputs` legacy snapshot与formal publication root；fault-matrix public/core入口也拒绝caller root。每次有效live调用（包括HUMAN 或SYSTEM/committed resume）都fresh执行固定SEC acquisition，再复用source-exact pinned semantic plan；本次receipt单独进入audit/full binding，旧disk receipt不能替代本次执行。

<!-- capability-anchor: CAPABILITY.vnext_recorded_cold_start -->

release input plan会先验证request-ledger manifest，再按exact SEC URL/body hash/accession/document从有序ledger选择最后一个验证通过的request attempt，并把attempt ID、body/header locator与locator class纳入plan identity。recorded离线Run可保留唯一且逐path/hash/headers/size验证的`LEGACY_WORKING_LOCATOR`，portable closure保留tier/class；formal live只允许`IMMUTABLE_ATTEMPT`，遇legacy class必须返回`LIVE_SOURCE_ATTEMPT_INCOMPLETE`。plan生成后ledger binding漂移则返回`SOURCE_LEDGER_BINDING_AMBIGUOUS`，均不得继续调用AI或准备publication。

HUMAN reviewer 可以亲自执行 decide；既有HUMAN decision优先，Agent、模型、fixture helper 与 acceptance runner都不得伪装为HUMAN。只有 ReviewUnit、rendered context、Spec/source/Evidence exact 且 decision 仍为 effective tip，旧决定才可复用。无HUMAN时仅D-06固定SYSTEM identity可写入APPROVE。错误 supersedes 会显示 Run ID、ReviewUnit hash、requested/current tip、chain 摘要与恢复命令。qualification 只接受有效 HUMAN 或D-06 SYSTEM `APPROVE`、disclosure Spec exact Result set全部`PUBLISHED`且Run validation=`PASSED`的receipt；`REJECT`或WITHHELD必须保留为审计结果，不能冻结为第二布局或holdout的Cutover资格。qualification CLI 对意外错误也只给结构化`QUALIFICATION_COMMAND_FAILED`，只有`--debug`显示traceback。

active pointer 尚不存在且 qualification chain 已失败时，运行负责人可以使用 `qualification reset --reset-at-utc ... --reason ...`。该命令只接受稳定原因，先保存content-addressed reset receipt（旧manifest、blocker和UTC时间）再清空当前资格索引；它不删除任何 Run、fixture、receipt 或 SEC ledger，并在 active publication 存在时fail closed。reset 后必须从新的second layout重新走到freeze和holdout，不能混接旧链。
<!-- capability-anchor: BEHAVIOR.vnext_qualification_requires_approved_published_layout -->

### 8.1 审核酒店 disclosure group

reviewer 只能针对一个 run-scoped `ReviewUnit` 决策。`review.md` 必须显示 untrusted filing notice、完整目标表格、稳定 row/column 坐标、selected/competing/unresolved claims、mechanical Evidence、source/Spec identity 与 required claims。filing 中的 HTML、Markdown、prompt-like 文本、control、zero-width 或 bidi code point 都只是可见数据，不是 reviewer 或程序应执行的指令。完整表格以集中资源预算为前提：超出 HTML/表数/行列/span/entity 数字词法/span 展开 cell/文字上限时，table-grid 明确失败且不裁剪；超长 cell 在 review 中无损物理分行，总 review bytes 超限则不生成残缺审核页。
<!-- capability-anchor: BEHAVIOR.vnext_table_grid_resource_budget -->
<!-- capability-anchor: BEHAVIOR.vnext_review_renderer_resource_budget -->

批准是整个ReviewUnit的HUMAN或D-06 SYSTEM决定，不是只批准一个数字。CLI只显式收到run directory、review unit hash、reviewer ID、decision、UTC time、reason与supersedes identity；`REJECT`自动形成空approved claims。v2 scope下SYSTEM只从Evidence exact-enum normalized scope生成APPROVE claims，unknown alias、缺维度、competing/unresolved或contract不满足时必须拒绝SYSTEM；HUMAN可在同一Spec scope contract内做决定。旧v1 record继续按ReviewUnit全部required claims重放。SYSTEM identity与reason必须是D-06固定值；缺字段、非HUMAN/SYSTEM授权身份、两个并行有效决定、底层append绕过或OPEN期磁盘mutation都会在append/finalize/freeze/replay的重验边界失败。Candidate、locator、source、Spec、unresolved、canonical context、renderer semantic version或rendered bytes任一改变，旧决定不得继续生效。
<!-- capability-anchor: BEHAVIOR.vnext_review_binds_visible_unit -->
<!-- capability-anchor: BEHAVIOR.vnext_review_decision_semantics_replayed -->

### 8.2 freeze、replay 与结果读取

`OPEN` 只表示 Run 仍可追加记录；`FROZEN` 只表示完整 bytes/graph 已封存，不自动等于 validation PASSED 或 candidate PUBLISHABLE。`PASSED`、`FAILED` 与 `NOT_RUN` receipt 都可以 freeze 供审计/replay；后两者禁止 publication，`PASSED` 也仍须通过其他 publication gates。STARTED AI attempt 不能永久进入 FROZEN；每条 attempt 必须已是 SUCCEEDED/FAILED。每条SUCCEEDED attempt的structured assistant output都会重放Reader schema，完整provider envelope另以`raw_response_sha256`独立审计；Candidate必须绑定同attempt的`assistant_output_sha256`，即使没有Candidate引用也不跳过attempt重放。Candidate新增该binding使canonicalizer semantic version 2→3，source-plan request-attempt binding使其3→4，legacy inventory冻结Git blob binding使projector semantic version 2→3，D-06 SYSTEM review渲染使review renderer semantic version 2→3；当前semantic runtime versions hash为`sha256:f724d52688b92935d5de6e2e8000fb3c65a3ee66b316dc8c646c8bef11b551a9`，任一变化都使旧closure/approval/Run/Batch/publication失效。Run 明确声明缺少 required source role 时，只允许把全 WITHHELD 结果封成审计 Run，任何 PUBLISHED Result 都会使 freeze 失败。Run 在创建时从 registry/profile 配置确定性投影并冻结 company traits，同时冻结 fiscal year 与精确 `YYYY-MM-DD` period start/end；fiscal-year 标签必须落在该期间内且期间不超过 53 周，跨年财年仍合法。workflow/finalizer 不接受调用方再次输入 traits、MetricSpec、metric/unit 或期间，freeze 还会从仓库重算 traits。freeze 前会从 RawBlob bytes 重建 table-grid，从 Run 内 content-addressed request/task/schema/assistant-output/provider-envelope bytes 重建 Reader 请求和 Candidate，按原 payload、locator 与 compiled Spec constraint 重放 Evidence；B01/B03 结构化路径还必须从 SourceReference 绑定的 Company Facts raw bytes 重建 fact 选择与计算，B03 复用的 B01 Observation 即使没有独立 B01 Result 也不能跳过其自身 Spec 重放。ExecutionTrace 保存 exact calculation target；即使 structured Result 没有 selected Observation 且状态为 WITHHELD，freeze 仍从 raw bytes 重跑并核对失败原因。1.01% cross-check rejection 必须能形成 FROZEN/replay audit Run；被拒分支只保留 cross-check/rejection 证据，不得留下已丢弃 component Observation ID。每个 ReviewUnit 必须已有唯一有效 HUMAN 或D-06 SYSTEM decision；批准/拒绝后的 Observation roles 和 published Result/Trace 必须是完整 exact set。freeze 从仓库 Spec 重建全部 reviewed Observation并重跑 Calculator，所有非 supporting Observation 必须被 Trace 精确消费；随后比较 Result/Trace 的 metric、closure、unit、company、期间、scope、quality、applicability、publication 与 reason。数值结果 quality 取 input Observation 与 accepted Spec branch 声明中更保守者；因此 Pfizer 的 OI reconstruction 即使组件均为 EXACT，仍必须保持 APPROX。空 approval effect 不能把 AI-table 指标伪装成 structured input。Run validation receipt 还必须用 immutable-view hash 绑定 company/period/Spec/Requirement/source 身份，并绑定实际 records、decisions、review 与 attempt artifact exact set；receipt 后任一项漂移都不能 freeze。历史 FROZEN Run 的 replay 不接受 AI 凭据或网络对象；replay 只从这些冻结字节重算并比较。

production Run 的 traits 继续只认 registry/profile；外部真实布局的 `run:qualification:<fixture-id>` 是唯一受控例外，且不能引用production registry。freeze 必须从该fixture的exact manifest与source bytes重新推导 company、traits、period、CIK及SourceReference，任一字段漂移都失败；调用方仍不能传入或修改这些值。
<!-- capability-anchor: BEHAVIOR.vnext_company_traits_repository_authority -->
<!-- capability-anchor: BEHAVIOR.vnext_result_business_state_rebound -->
<!-- capability-anchor: BEHAVIOR.vnext_structured_withheld_replay -->
<!-- capability-anchor: BEHAVIOR.vnext_freeze_accepts_audit_validation_states -->
<!-- capability-anchor: BEHAVIOR.vnext_publication_requires_passed_validation -->

vNext MetricResult 同时暴露 `applicability`、`quality`、`publication` 与 `reason_code`。`N_A_STRUCTURAL`、`NOT_MEANINGFUL` 和 `WITHHELD` 不得折叠；non-lodging 会留下可 freeze/replay 的 N/A Run/Result/Trace，同时保持 source/AI 调用数为零。任何 APPLICABLE/WITHHELD 都会把整个 candidate 标为 BLOCKED。BatchManifest 从 registry、traits/applicability 与 release plan 派生完整 company×metric exact set，再逐个重载 PASSED FROZEN Runs；单公司 Run、缺 N/A、重复/额外坐标或跨 period 混批不会得到完整 batch。Projector 先要求 legacy metrics/evidence/Golden 精确匹配 frozen baseline，再从该 batch 实际生成 metrics/evidence/compatibility 与 repair execution bytes；Spec 声明的常量覆盖相应字段，review source 未拥有的 legacy metadata 保留 frozen baseline。projection multiplier 与 Golden tolerance comparison 使用固定 28/ROUND_HALF_EVEN context，调用进程修改全局 Decimal precision 不会改变 candidate bytes 或 gate verdict。同一 registry-mapped `(company_id, metric_id)` 多 scope 不会隐式覆盖，evidence 方法字段变化必须逐 cell 留痕。publisher 以 bundle 内 ProjectionManifest 与 batch/run/result row proof 为准，不接受游离 `migrated_results`、任意 legacy/staging bytes或调用方自写 PASS 改写结论。
<!-- capability-anchor: BEHAVIOR.vnext_withheld_cannot_publish -->

### 8.3 candidate、active 与 latest

事务实现区分 staging candidate、上一成功 active publication 与最近一次 latest Run/batch。正式读取者必须 pin 一个 `PublicationView` 后从同一 bundle 读取 metrics/evidence/coverage/Golden/validation/report；每个terminal cycle只运行一个公开进程，把同一pinned publication transaction贯穿active Stage10/11/12与snapshot publish/verify，不在cycle中重读pointer。report input loader 不触发 repair、AI、SEC 网络或 authoritative write。recorded publication 生成 `PASSED_RECORDED_ONLY` 文档且不得改正式 pointer；generic operator `publish --commit`和public generic formal receipt/commit API均fail closed，formal mutation只由Cutover orchestrator持有。formal publication 只有在 qualification、portable live三轮audit closure、有效review、complete staging 与 strict compatibility 均通过时才可生成 `FULL_VALIDATION/PASSED` candidate。root CSV/报告是 active bundle 的 compatibility mirrors，但绕过 PublicationView 的任意 reader 不获得跨文件组原子保证。

若latest Run失败或withheld，`latest_run_status`必须显示失败原因、candidate status、active publication ID、空的latest publication ID以及`active_is_latest_success=false`。单个FROZEN Run也不能代表完整batch；active仍是上一成功版本，不能被描述成“最新运行成功”。首次formal commit先把冻结legacy root bytes严格重验并只读导入为immutable predecessor A，不调用旧parser/resolver/repair；formal B必须绑定A，隔离root完成14项fault matrix并持久化受绑定receipts后，才允许私有initial-chain primitive执行official lock/CAS。每次switch先在exclusive lock内写`outputs/publication_switch_intents/<sha256>.json`；reader在shared lock看到pending、multiple或tampered intent只返回稳定失败，不修改authority。writer recovery在pointer==proposed时完成connected edge并重建proposed mirrors，在pointer==previous时清理本事务edge并恢复previous，其他状态失败；initial A→B失败还必须清除A孤儿edge、pointer和intent。因此mirror/pointer/switch-receipt中途hard crash不得产生可读的成功半成品。rollback只允许切回current pointer记录的committed predecessor，prepared sibling不能借rollback激活；rollback到imported A也只切pointer、从目标bundle重建mirrors并验证legacy import identity，绝不重新启用旧parser或旧producer。
<!-- capability-anchor: BEHAVIOR.vnext_latest_active_separate -->

Issue #15 acceptance并发运行直接边界用例；fast整体仍仅为`FAST_LOCAL_ONLY`，不能升级R3或后续scope证据。

### 8.4 当前不能执行的承诺

R3已形成committed partial active并保留R1历史、R2 predecessor以及R3→R2→修正版R3的rollback/restore证据，但financial、text、39指标最终Cutover和full receipt仍不存在。因此：

- `tools/run_acceptance.py --scope recorded` 强制离线且不修改 pointer/root mirrors，按 R4 只封存并发快速本地证据，最高状态是 `PASSED_FAST_LOCAL_ONLY`；
- `--scope full` 未带 `--execute-live` 返回 `LIVE_EXECUTION_NOT_AUTHORIZED`；带授权但凭据或qualification缺失时返回 BLOCKED且不开始 Cutover；首次A→B不要求预先存在previous publication；
- 只有 `python3 tools/run_acceptance.py --scope full --execute-live` 完成 new→rollback→restore 三次单进程、单次pin terminal cycle并最终返回 0，才是 full PASS；
- 当前根目录report/CSV/manifest来自R3 successor，只能按24指标/240累计vNext keys/327行public matrix的partial ratchet解释；不能写Issue #15最终Done或`Closes #15`。

这些限制是当前能力边界，不是 caveat 可豁免项。
<!-- capability-anchor: BOUNDARY.vnext_cutover_not_complete -->
