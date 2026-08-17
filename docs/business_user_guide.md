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
- 当前没有前端、API、daily scheduler或生产数据库服务；vNext Cutover与full acquisition编排已实现，本轮SEC acquisition已执行并通过receipt，但live Reader因provider余额失败，committed active publication/full receipt仍不存在。
  <!-- capability-anchor: BOUNDARY.not_production_service -->
- 不替人做投资、信用、报价、监管或外部审计决定。
  <!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->

## 4. 第一次阅读的最短路径

1. 先读 `outputs/validation_run_manifest.json`，确认 mode、result，以及本次真正刷新的 tracked validation/audit artifact；`FAILED` 或 `IN_PROGRESS` 时停止验收。
2. 运行 `python3 tools/check_validation_snapshot.py`。`config/validation_source_policy.json` 无效、SOP 权威引用角色不一致、source-input tree dirty/不一致、显式 acceptance source 缺失、provenance 缺失，或关键 artifact SHA-256/size 失配时停止验收。
3. checker 通过后再读 `REPORT_十公司财务指标.md`，了解本批次摘要、coverage、例外和 verdict。
4. 在 `outputs/metrics_matrix.csv` 按 company 与 `metric_id` 找到具体结果。
5. 用 `outputs/coverage_matrix.csv` 和 `outputs/exceptions_and_review_items.md` 判断缺口类型。
6. 需要采信非空数值时，在 `outputs/metric_evidence.csv` 核对同一 company/metric 的来源与口径。
7. 最后只核对 manifest `refreshed_artifacts` 中的 `repair_validation_results.csv`、`stratified_audit.csv` 等证据；旧文件存在不代表本次运行已评估。
<!-- capability-anchor: BEHAVIOR.validation_manifest_controls_freshness -->
<!-- capability-anchor: BEHAVIOR.validation_snapshot_binds_source_and_artifacts -->

`manifest.source_commit` 与当前 HEAD 相同是最直接的匹配；artifact commit 或 merge commit 改变 SHA 时，只有 checker 证明完整 source-input tree digest 和文件数仍一致、当前 source closure clean，才允许以 warning 继续。`+dirty` 只说明整个工作树含改动，不能单独判断源代码是否参与运行。

对既有legacy snapshot，只有其原始阶段 `00` 至 `11` 已完整运行、独立阶段 `12` 与snapshot checker都通过，才能按该证据等级读取；这不等于vNext正式Cutover。formal vNext只在`python3 tools/run_acceptance.py --scope full --execute-live`真实返回0并产生绑定Cutover与new/rollback/restore的full receipt后才是正式完整批次。仅看到报告、candidate、recorded receipt或成功manifest都不够。
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

`LIGHT_PACKAGE_NO_GIT` provenance 只证明随包 source/artifact bytes 与 sidecar 一致，不补足 Git history 或 raw evidence。无 Git light package 缺少 source policy、`01_SOP...md`、CIK identity rules、能力契约、指标定义、AGENTS/SOP/TESTING/architecture/interact 或其他 policy-declared acceptance source 时，checker 必须失败，不能通过删文件缩小 source closure。

## 9. 什么时候必须找人

出现以下情况时，停止把输出当作自动完成的结论：

- status 为 `NEEDS_REVIEW`、`PARSE_FAILED` 或关键 `NOT_EXTRACTED`。
- `OK_APPROX`、`TEXT_QUAL` 或复杂表格结果将影响高风险决定。
- 需要改变 company registry、报告期、指标定义或 successor/predecessor 口径。
- live 刷新前缺少 `SEC_CONTACT_EMAIL` 或 `DEEPSEEK_API_KEY`；SEC organization 固定为 `axaxl`，email 只从环境读取。acceptance 与 SEC client 共用 validator，缺失、畸形和 example/reserved-domain 邮箱都会在联网前失败。
- Golden、P0 validation、workspace 完整性、分层审计或 snapshot checker 出现失败，或 full 关键检查为 `NOT_EVALUATED_MISSING_EVIDENCE`。
- 需要外部审计接受、生产发布或正式业务批准。

运行配置与完整阶段由仓库运行负责人负责；指标口径与 caveat 由财务方法复核人负责；最终业务与外部接受由相应负责人承担。
<!-- capability-anchor: RESPONSIBILITY.operator_owns_sec_identity_and_run -->
<!-- capability-anchor: RESPONSIBILITY.human_reviews_caveats_and_decides -->

仓库目前没有登记具体联系人、即时通信频道或紧急升级路径。需要升级时应由仓库负责人明确分派，不能在文档中虚构渠道。

## 10. vNext 当前如何复核

vNext 已提供同一套 recorded/live operator、固定DeepSeek/SEC边界、完整表格输入、模型候选留痕、机械 Evidence、整单HUMAN或D-06 SYSTEM Review、freeze/replay、Spec-driven B03、qualification、formal publication/rollback 与 pinned PublicationView consumers。recorded 模式强制离线且不修改正式 active/root outputs；generic publish只能准备inactive recorded bundle，public generic formal receipt/commit入口会fail closed，正式写入只归Cutover orchestrator所有。实现测试不等于已经发布。Issue #12 的 R4 快速验收只并发运行六个本地直接边界用例，不运行全仓、隔离仓库或 freeze/replay 测试；它最高只产生 `PASSED_FAST_LOCAL_ONLY`，不是 CI、live 或 Cutover 成功。
<!-- capability-anchor: CAPABILITY.vnext_recorded_shadow -->

运行负责人可以不读源码，从 `tools/vnext_operator.py fixture list/show` 发现仓库已经绑定的真实 SEC recorded fixture，再运行 `tools/vnext_cutover.py --fixture-id ...`。首次命令会创建真实 structured/OPEN Runs；既有HUMAN decision优先，否则D-06会以固定可审计SYSTEM身份写入完整approval并继续。之后同一Cutover命令完成freeze/replay、complete Batch、Projector，并在request closure通过后把结果CAS提交到该workspace自己的`recorded-publication`再用PublicationView读回。recorded Cutover只接受`artifacts/vnext/recorded-*`专用workspace；live固定使用repository-owned `artifacts/vnext/cutover`，caller传入任何live `--workspace-dir`都会在读取或写入前以`LIVE_WORKSPACE_OVERRIDE_FORBIDDEN`失败。recorded closure可验证历史ledger中唯一、path/hash/headers/size exact的legacy locator并明确保留tier/class；formal/live仍只允许immutable attempt，resume时还会对当前解释器、固定五命令、ledger tail与inventory bytes重验acquisition receipt。这是socket=0的操作训练与transaction证据；正式active pointer、root CSV/报告、formal namespace及SEC ledger不会变化。自动测试中的`TEST_ONLY_EXPLICIT_REVIEW`不是正式HUMAN签署，sandbox publication也不是live、active或full结果，不能交给业务人员作为新数据入口。
<!-- capability-anchor: CAPABILITY.vnext_recorded_cold_start -->

正式live core还exact固定module-owned repository、`artifacts/vnext/cutover`、`outputs` legacy snapshot与publication root，fault matrix也不接受caller root。每次有效live调用（包括HUMAN或SYSTEM/committed resume）都会fresh执行SEC acquisition；旧receipt只能重验历史pinned semantic plan，本次receipt会单独进入current audit/full closure。

第二布局与holdout不是把网页下载后手工拼成 fixture：运行负责人只能从 `fixtures/vnext/qualification_candidates.json` 选固定ID，并用 `tools/vnext_capture_qualification_fixture.py` 统一请求官方 SEC、写入ledger/raw bytes、调用固定DeepSeek并保存provider envelope、Reader response与回放excerpt。该工具不接受URL、公司、期间、模型或secret覆盖；录制完成后，qualification 本身仍是 socket=0 回放。

但它尚未成为业务结果入口。业务人员当前仍从第 4 节所列 root manifest、snapshot checker、report 和 CSV 开始，不应在 `artifacts/vnext/` 中自行挑选一个 OPEN/FROZEN Run 当成正式结果。

运行负责人还必须核对release input plan的SEC request binding：系统按exact URL/body hash/accession/document选择最后一个验证通过的attempt。recorded离线审计可以保留唯一且逐path/hash/headers/size验证的`LEGACY_WORKING_LOCATOR`，并在portable closure明确绑定tier/class；formal live只接受`IMMUTABLE_ATTEMPT`，legacy会以`LIVE_SOURCE_ATTEMPT_INCOMPLETE`停止。plan后ledger身份变化会以`SOURCE_LEDGER_BINDING_AMBIGUOUS`停止，不能继续AI、staging或publication。

审核 recorded lodging ReviewUnit 时：

1. 确认 `review.md` 显示完整目标表，而不是只显示命中行；所有 filing 文本均标为 untrusted data。
2. 同时阅读 selected、competing、unresolved、cell locator、local scope labels、机械检查与 required claims。
3. 具名 HUMAN reviewer 可以批准整单；若无HUMAN，只有D-06固定SYSTEM identity可批准。required claims 必须来自仓库中重新编译且 hash-bound 的完整 Spec，只批准 B10 或一个数值、忽略 B11/ADR/competing/unresolved 都不成立。
4. 任一表格、locator、source、Spec、unresolved 或 reviewer 实际看到的 rendered bytes 改变，原决定应失效并重新审核。
5. Company traits 只能从 registry/profile 配置投影，并在入口与 freeze 两次核对；调用方不能把 Pfizer 临时标成 lodging。Run 还会固定精确 `YYYY-MM-DD` 起止日和 role→metric/unit；财年标签必须落在最长 53 周的精确期间内，但允许跨日历年。B10 把 percent 转为 ratio，B11/ADR 若不是 USD 则整单 WITHHELD。B01 结构化结果保留 SEC fact 的 reported unit，不把 EUR 数值改贴 USD 标签。
6. 每个 ReviewUnit 在 freeze 前必须已有唯一有效 HUMAN 或D-06 SYSTEM decision；published/supporting Observation 和最终 Result/Trace 必须按批准范围完整出现，不能删掉一项后只验证剩余记录。AI-table 指标不能用空 approval effect 冒充 structured input，未被 Trace 消费的游离 Observation 也不能进入 FROZEN Run。
7. STARTED AI attempt 不能进入 FROZEN Run；每条 attempt 必须已终止为 SUCCEEDED/FAILED。freeze 会从保存的exact request/task/schema重建请求，从每条SUCCEEDED structured assistant output重放严格Reader schema，并独立核对完整provider envelope；Candidate必须绑定同attempt的assistant-output hash，即使该attempt没有Candidate引用也不跳过。随后逐字段重建reviewed Observation、重跑Calculator并比较Result/Trace的值、scope、quality、applicability、publication与reason。Candidate binding使canonicalizer semantic version 2→3，source request binding使其3→4，旧路径 inventory冻结Git blob binding使projector semantic version 2→3，D-06 SYSTEM review渲染使review renderer semantic version 2→3；当前semantic runtime versions hash为`sha256:f724d52688b92935d5de6e2e8000fb3c65a3ee66b316dc8c646c8bef11b551a9`，任一变化都使旧closure/approval/Run/Batch/publication失效。只有相邻对象中的digest、ID或自洽公式字符串相同，不构成审计证明。
8. B01/B03 还会从 SourceReference 绑定的 Company Facts raw bytes 重新选择结构化 fact。B03 即使不发布独立 B01 Result，也必须先按 B01 Spec 重算复用的 Revenue Observation；没有 selected Observation 的 structured WITHHELD 也要从 Trace 保存的 exact calculation target 重跑，不能把调用方传入的 Revenue 或失败理由当成已验证事实。
9. Run validation receipt 必须同时绑定 Run 的 company/period/Spec/Requirement/source 身份与实际 records、decisions、review、AI bytes；receipt 后改变任一项都不能 freeze。manifest 明确声明缺少 required source role 时，只允许冻结全 WITHHELD 的失败审计，不能同时保留 PUBLISHED Result。
<!-- capability-anchor: BEHAVIOR.vnext_review_binds_visible_unit -->

任何 APPLICABLE/WITHHELD 或不完整 bundle 都不能替换 active。Projector 必须加载由 registry/applicability/release plan 派生的 complete BatchManifest 及全部 PASSED FROZEN Runs，生成 strict-compatible candidate；formal publisher还必须绑定qualification、live三轮portable audit closure、有效review、ledger与全部gate。首次Cutover把冻结legacy root bytes严格重验后只读导入为immutable predecessor A，再提交绑定A的formal B；导入、rollback与restore都不会运行旧parser。rollback只能回到current pointer记录的committed predecessor。

qualification 的顺序不是任意的：先用同一 Reader/Evidence/Review path完成第二真实布局，并取得有效 HUMAN 或D-06 SYSTEM `APPROVE`、全量`PUBLISHED` Result和`PASSED` validation的资格receipt；`REJECT`/WITHHELD 只保留审计，不能进入freeze。随后冻结production semantic tree并记录pre-holdout fixture/Run exact inventory，最后才加入不同company/CIK的独立holdout。若holdout在freeze前已存在，或加入后production semantic hash变化，Cutover必须停止。每个new/rollback/restore终态cycle只启动一次公开terminal CLI，并在单进程、单次pinned publication transaction中依序执行Stage10 Golden、Stage11 report、Stage12 active validation、snapshot publish与verify，防止读取过程中pointer切换造成混合视图。

publication switch在改root mirrors前先于独占锁内写`outputs/publication_switch_intents/<sha256>.json`。共享锁读取者遇pending、多份或被篡改的intent只会fail closed，不会擅自清理；恢复者仍持独占锁，pointer已经是proposed时完成switch edge并重建proposed mirrors，pointer仍是previous时撤销本事务edge并恢复previous，其他状态停止。initial A→B失败还会清掉本次A孤儿edge、pointer与intent；整个恢复过程不运行旧parser，也不回滚request ledger。

可提交的acceptance receipt不会保存操作者机器的绝对路径。它以`$REPO_ROOT`、`$ACCEPTANCE_OUTPUT`、`$PYTHON_CURRENT`与`$SANDBOX_EXEC`等portable token记录locator，并在`runtime_bindings`保存executable name及binary SHA-256；命令结果、return code、duration与stdout/stderr digest仍完整保留。operator不能把`--output-dir`指向正式authority自身、祖先或后代。R4不再启动 Python 3.9 全量测试或隔离 repository/worktree；这不会削弱真实 live 发布仍需的凭据、HUMAN 和 Cutover receipts。
<!-- capability-anchor: BEHAVIOR.vnext_withheld_cannot_publish -->

判断展示版本必须同时读取 active pointer 与 latest run status：active 是当前可用的上一成功完整版本；latest 可能失败、withheld 或仍在 staging。status writer 只接收 persisted Run directory 或 publication ID，在 pointer lock 内加载真实状态并验证 active pointer/bundle；不接受调用方自报的状态枚举、boolean、view 或 manifest。bundle storage、pointer/lock、status 和 mirrors 全部从单一 publication root 派生，调用方不能分别定义互相矛盾的路径。`active_is_latest_success` 由两者 publication ID 是否相同派生。FAILED/BLOCKED 不得携带 latest publication ID，不能把旧 active 描述成最新运行成功。
<!-- capability-anchor: BEHAVIOR.vnext_latest_active_separate -->

当前还没有可供业务采信的 vNext active publication。effective D-01 已固定为DeepSeek，D-06允许可审计SYSTEM review，legacy migrated producers 已退出代码路径，Stage 10/11/12 也具备 pinned active 分支；Hilton/Hyatt真实布局qualification与SEC acquisition均已完成，但三次live Reader因provider `Insufficient Balance`失败，故仍缺十公司 formal staging、active publication、rollback/restore和 full receipt。首次A→B会创建previous publication，故其预先不存在不是blocker。root CSV/报告仍是业务入口。root mirrors未来只保证逐byte等于一个 active bundle，不向绕过 PublicationView 的任意 reader承诺跨文件组原子性。
<!-- capability-anchor: BOUNDARY.vnext_cutover_not_complete -->

## 11. 最短建议

先看 manifest，再跑 snapshot checker，然后看 status 与 evidence，最后看 gate。看到空值不要猜，看到零值先确认语义，看到 GO WITH CAVEATS 要继续读 caveat。
