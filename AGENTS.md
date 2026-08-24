# SEC_metrics Agent 工作入口

## 0. 按任务选择阅读路径

首次进入仓库时先判断任务，再读取对应的标准流程。`SOP.md` 是标准工作流的一级导航；专项文档负责提供具体事实和命令。

### 只读取当前结果

```text
SOP.md「只读取现有结果」
→ docs/business_user_guide.md
→ outputs/validation_run_manifest.json
→ python3 tools/check_validation_snapshot.py
→ REPORT_十公司财务指标.md
→ outputs/metrics_matrix.csv / outputs/metric_evidence.csv
```

manifest 不是成功证明本身。`result` 必须是 `PASSED` 或 `PASSED_WITH_CAVEATS`，且 snapshot checker 必须证明当前 source-input tree 与关键 artifact bytes 仍和该 run 绑定。

### 执行完整批次

```text
SOP.md「SOP 1：SEC 阶段 00-12 完整批次运行」
→ README_RUN.md
→ TESTING.md
```

阶段 `00`–`11` 保留采集与非迁移 candidate 能力，阶段 `12` 是独立终态 gate。每个formal terminal cycle以同一pinned transaction贯穿Stage10/11/12；内部candidate命令通过`sec_pipeline.py --workspace-dir <absolute-isolated-root> <stage>`显式选择源码checkout外的数据根，legacy Stage04/09/11不能在源码repository root、其任意子目录或含active pointer的workspace覆盖mirrors。stage 11 exit 0 本身不代表完整批次成功。

### 分层验收或失败定位

```text
SOP.md「SOP 2：分层验收与失败定位」
→ TESTING.md
→ README_RUN.md
```

### 修改代码或 review PR

```text
architecture.md
→ capability_contract.json
→ interact.md
→ TESTING.md
→ PR_Checklist.md
```

需要发布 PR 时，先读取 `SOP.md` 的 PR 发布章节，再执行 `PR_Checklist.md`。涉及 SEC 访问、证据、manifest、verdict、source provenance 或 artifact publication 的改动，必须同时核对用户可观察后果和负例测试。

### 开发、复核或执行 vNext Cutover

```text
requirements/issue_15_v1/CONTRACT.md（Issue #15 exact authority）
→ requirements/issue_15_v1/transfer_manifest.json
→ requirements/issue_15_v1/decision_register.json
→ requirements/issue_15_v1/baseline_manifest.json
→ requirements/issue_15_v1/legacy_semantic_producer_inventory.json
→ requirements/issue_15_v1/source_strategy_baseline_receipt.json
→ requirements/issue_15_v1/foundation_verification_receipt.json
→ requirements/ai_first_v3_3_1/（immutable inherited foundation）
→ architecture.md「vNext Cutover 实现」
→ TESTING.md「vNext recorded / formal Cutover」
→ SOP.md「vNext operator 与正式 Cutover」
```

Issue #15 / `issue_15_v1` 是全部未来开发与验收的唯一入口。父快照继续提供不可变 R2/R3、既有实现和历史 Decision 链；新快照原样携带 13 条历史记录，以 D-01/D-26 同 ID 新 tip 和 D-30–D-38 新根记录形成自包含 authority。Issue #15 owner 在冻结后以同 ID D-36/D-35/D-26 新 tip 禁用仓库金额预算门禁：外部 API 账户余额是花费权威，仓库不存在 per-call/batch/owner monetary cap 或金额 preflight blocker；cost/token/usage/cache 只可作非阻断 observability。随后同 ID D-07 新 tip 保留全部文档表、原始顺序与无 selector/prefilter，把 `utf8_byte_upper_bound` v1 的 inclusive estimated-input threshold 提高到 200000，并批准 family-scoped readiness：shared closure drift 失效全部依赖 family，family-local context/resource/authority failure 只阻断 owner family。最新同 ID D-07 tip 仅批准实现一个绑定 Marriott development source、`lodging_occupancy_table_v2` 与 serializer v2 的一次性 actual-prompt-token measurement exception；`live_measurement_authorized` 仍为 false，任何真实执行必须另获绑定当时 exact HEAD 的外部授权，且该 exception 不改变普通 qualification 的 200000 门、不授权 selector、live qualification、SEC egress 或 publication。`HTTP_402` 仍零自动重试并终止 execution 与 batch，payload/context/resource limit 仍是独立非金额 fail-closed 安全类。WB-1 只冻结并验证 authority，不自动切换 Reader、transport、publication 或业务语义。

代码已具备同一 recorded/live operator、D-06 optional HUMAN/SYSTEM audited Review、固定 DeepSeek/SEC 边界、资格门、legacy migrated producer 退出、PublicationView consumers、正式 publication/rollback primitives 与 new/rollback/restore 终态编排。Issue #15 R1 已只读导入 verified legacy A，以 immutable SEC attempts 冻结十公司 B01/B03 successor B，并真实完成 A→B、rollback→A、restore→B。R2 又以 commit-bound immutable SEC blobs、完整submissions current/history shards和request-ledger绑定的acquisition receipt补集累计加入其余14个DET_ONLY与C01/E01–E05。两档public rows均先从Result/Trace/Claims/catalog独立渲染，再以legacy作18×20/141×20字段oracle；最终active含22指标、220个Result坐标、79个新增structural keys和309行public matrix，approved/unexpected delta均为空。R1/R2的real-model egress与paid call均为0，projection/retirement/read-back/key-set receipts已持久化。该事实仍不证明WB-4以后、AI Reader、39指标最终Cutover或full acceptance；历史DeepSeek `Insufficient Balance`失败仍是后续AI档证据。

## 1. 文件简介

### 核心治理与工作流文档

- `AGENTS.md`：agent 入口、文件地图、项目规则与文档关系。
- `architecture.md`：当前 CLI 批处理架构、边界、数据流、状态、错误与扩展点。
- `capability_contract.json`：当前能力、限制、责任和行为承诺的机器可读真相源。
- `interact.md`：CLI 与文件交付中用户可观察行为和验收不变量。
- `docs/business_user_guide.md`：面向首次读取结果的业务人员的派生指南。
- `docs/validation_snapshot_provenance.md`：source-input tree、artifact digest、publication 顺序与 checker 语义。
- `TESTING.md`：测试层级、真实命令、full/light 边界与副作用。
- `SOP.md`：标准流程的一级导航，只保留动作、权威引用与验收。
- `PR_Checklist.md`：仅在用户明确要求发布时使用的发布治理流程，不属于批次 acceptance source。
- `.github/pull_request_template.md`：长期 PR body 发布治理模板，不属于批次 acceptance source。
- `.gitignore`：本地缓存、环境与临时 PR 草稿的忽略规则。
- `requirements/issue_15_v1/`：Issue #15 的 exact Contract、自包含 Decision Register、post-freeze D-36/D-35/D-26/D-07 tips、parent transfer/baseline、39 指标 legacy semantic producer inventory、matrix baseline 与 foundation verification；是后续开发 authority，冻结 Contract 和 inherited parent bytes 均不因新 tip 被改写。
- `requirements/ai_first_v3_3_1/`：不可变 inherited foundation；其 exact FSD、R2/R3、历史 Decision、旧基线与 inventory 继续供 parent closure 验证，任何文件不得因 Issue #15 开发被改写。

### 核心配置

- `config/sec_config.json`：SEC User-Agent、请求速率、重试与退避参数。
- `config/vnext_release_plan.json`：Projector 的仓库级 release identity 与 migrated metric exact set；不能由 Run 结果反推。
- `config/source_strategy_registry.json`：Issue #15 的 39 指标 target SourceStrategy、reader family 与family-owned production literal truth source；不保存当前迁移状态。
- `config/table_qualification_matrix.json` / `catalog/table_task_contracts.json`：PR-3阶段A的table-family qualification来源/布局/holdout/limits冻结与单角色table task catalog；它们不启动qualification，不拥有迁移状态。
- `config/issue_15_release_plan.json`：Issue #15 ratchet 的content-addressed索引，只保存active plan identity与不可变plan路径；`config/release_plans/issue_15_zero_ai_r1.json`、`issue_15_zero_ai_r2.json`分别保存完整parent/delta/cumulative keys/retirement/reader versions/Requirement closure，只有各档`cumulative_metric_ids`拥有迁移集合。
- `config/company_registry.csv`：逻辑公司、CIK role、行业 profile、财年底与连续性。
- `config/metric_applicability.yaml`：SIC/profile 规则、extractor 路由与行业参数；当前由 JSON parser 读取，内容必须保持 JSON 兼容。
- `config/validation_source_policy.json`：机器可读的 runtime/acceptance source、full artifact directory、生成 artifact、发布治理和解释性文档角色；qualification、request attempts、failure-first、fault与portable live audit receipts都属于full artifact closure；provenance closure 的真相源。
- `catalog/`：vNext JSON-compatible MetricSpec、disclosure group 与 company trait 目录；业务选择、guard、quality、projection 和 identity constraint 的仓库级 truth source。
- `catalog/deterministic_metrics.json` / `catalog/event_routes.json` / `catalog/zero_ai_public_projection.json`：R2确定性公式/approved concepts、事件item/keyword路由与22指标完整public-row投影；均被Issue #15 Requirement runtime authority逐byte绑定，approved public delta exact set当前为空。
- `catalog/event_routes.json`：C01/E01–E05 的声明式零 AI item/keyword route authority；冻结 E01 aliases、text normalization、match mode、brief source priority 与 legacy projection。

### 核心模块

- `scripts/sec_pipeline.py`：阶段调度、解析、计算、富化、repair、验证、审计与报告的单体内核。
- `scripts/sec_http.py`：集中验证有效 SEC organization/contact email，并负责精确官方 SEC origin、无隐式 redirect、进程内节流、重试、immutable attempt body/header、request ledger、整表 manifest 与 cooperating-process publication lock。
- `scripts/sec_urls.py`：集中构造 SEC 官方 endpoint。
- `scripts/git_workspace.py`：集中清理 Git 重定向环境，并校验 checkout 与 object/ref 存储边界。
- `scripts/validation_provenance.py`：读取 source policy、校验 SOP 权威引用角色、捕获 source-input tree、发布关键 artifact digest sidecar，并在 postflight 失败时使终态 fail closed。
- `scripts/00_*.py` 至 `scripts/12_*.py`：薄单阶段 CLI；04/09 只接受`--workspace-dir <absolute-isolated-root>`，11 无参数时只作active read-back、带该参数时构建legacy candidate，其余wrapper保持无参数。candidate全链统一经`sec_pipeline.py --workspace-dir ... <stage>`；legacy stage 11 mutation使旧provenance失配，stage 12负责终态publication，active stage 11只读。
- `scripts/vnext/`：vNext的canonical/schema/state、source/table-grid、latest verified request-attempt与locator-tier source plan、Spec/constraint、固定DeepSeek OpenAI-compatible Chat Completions adapter、Evidence/Review/Calculator、Run freeze/replay、complete BatchManifest/Projector、固定SEC Stage00/01/02/03/05 acquisition/inventory、资格门、正式Cutover编排、pinned `PublicationView`与publication/rollback transaction实现。recorded可exact验证并闭合legacy working locator，正式live只允许immutable attempt；二者仍受各自Review、staging与publication gates约束。
- `scripts/vnext/source_strategy.py`：严格加载39指标registry与Issue #15 ReleasePlan，机械验证exact source-mode mapping、family literal union、迁移状态分离、全部authority hashes及parent→child metric/key/retirement三类no-removal子集门。已发布R1/R2 plan按content ID保留其历史Requirement closure，loader另返回current closure；post-publication D-07 tip不得重签历史plan或active bundle，未来新plan必须显式登记current closure。
- `scripts/vnext/deterministic_router.py`：以统一 `sources[]`/SourceSetManifest 闭合 companyfacts、accession XBRL、ECD XBRL、auditor fact 和 8-K item index 五个 adapter；它生成非模型 DeterministicVerifiedClaim，再投影为 VerifiedObservation/Result/ExecutionTrace。
- `scripts/vnext/invocation_control.py`：绑定 release-input/invocation/execution 三层身份；生产adapter在exact provider envelope形成plan后才进入`O_CREAT|O_EXCL` owner-only socket路径。terminal reservation归档后释放，dead owner的egress marker+缺terminal receipt从磁盘封存为UNKNOWN；plan/request/egress/attempt/execution/response均可重算三种调用计数，不包含仓库金额 cap/preflight。
- `scripts/vnext/table_context_measurement.py`：Stage C专用、与qualification隔离的一次性actual-token measurement边界；离线重建exact Marriott/lodging occupancy/serializer-v2/provider envelope plan，只有外部`AUTHORIZE_ONE_TOKEN_MEASUREMENT`绑定clean exact HEAD后才签发opaque capability。marker前失败不消费，任一marker后永久消费且零重试；独立evidence永不获得qualification/publication credit。Stage C-A只实现并mock测试，禁止真实执行。
- `scripts/vnext/table_payload.py` / `scope_contract.py` / `table_task_contracts.py` / `table_qualification_freeze.py`：分别实现expanded grid的可逆compact transport、支持多维共享locator的Spec exact-enum scope v2、由SourceStrategy SHA-256绑定fallback representation schema机械派生的单角色table task catalog、以及无网络qualification freeze；matrix task ID经formal Workflow进入Run manifest、adapter、Review、FROZEN validation和fresh replay，金融/酒店各自绑定MetricSpec scope closure。非空catalog task binding从Run创建、optional SYSTEM review到remote replay都机械选择Issue #15 Requirement closure，空binding的历史disclosure Run才保留父closure；catalog binding配parent hashes会fail closed。catalog LIVE path另有唯一qualification executor：它从current matrix/freeze/Stage-A snapshot/immutable source/task/provider重建opaque authorization并绑定cycle workspace，普通 Workflow 不能越过该capability；LIVE attempt同时写入Run、attempt、qualification evidence和cycle ledger。schema-v3 freeze以传递shared engine closure和family-local matrix/task/MetricSpec fragments保护后续资格语义，并记录11组round-trip、所有本地development source×task的离线测量及`readiness_by_family`；validator先重验immutable aggregate/shared evidence，并在所有requested-family gate前重哈希Marriott provenance、10份Hilton/Hyatt manifests与有序11份WB-4 source bytes；missing/extra/order/manifest/actual-SHA drift以`shared_measurement:round_trip_source_set`阻断全部family，`RECORDED_LAYOUT_FIXTURE`也单独打开并验证manifest声明的actual source。无`family_id`时维持完整全局离线验证，execution path传入requested `family_id`后只解引用该family的matrix sources、task contracts、MetricSpecs和local measurements，不重新加载sibling local authority。source missing/SHA mismatch、task缺失或MetricSpec无法编译都成为owner family的结构化local reason，而不要求siblings先成功重建；aggregate summary不作为跨family门。200000 inclusive context门和resource门按family判定，shared drift失效全部依赖family，local failure/drift只失效owner family；plan、authorization、Workflow task rebuild和replay均按task family解引用，Stage-A完整source-tree比较只属于离线snapshot checker。当前lodging以392447被`ESTIMATED_CONTEXT_LIMIT`阻断，financial以`EXPANDED_GRID_RESOURCE_LIMIT`阻断，`live_ready_family_ids=[]`。unknown alias不由SYSTEM批准，freeze只绑定未来资格前提，不是live qualification。
- `scripts/vnext/zero_ai_release.py`：R1 module-owned formal orchestrator；只用 immutable SEC attempts 冻结 B01/B03，从release专属invocation namespace与structured-only route exact set推导零调用，先独立渲染20个完整public rows、再比较18×20字段，生成projection/strict compatibility/retirement receipts，并执行 cold-start new→rollback→restore。
- `scripts/vnext/zero_ai_r2.py` / `scripts/vnext/public_projection.py`：R2确定性ratchet与共享public renderer；从companyfacts/accession XBRL及submissions shards+immutable acquisition receipts的完整8-K union生成claims/observations/results/traces，在无legacy migrated rows/events输入时机械闭合220坐标并渲染220 rows，随后单独比较141×20字段、event key parity、309-key union与publication-bound retirement。
- `tools/check_validation_snapshot.py`：独立复核当前 checkout、manifest、provenance sidecar 与关键 artifact bytes；PR-3 Stage-A仅在R2历史artifact检查除source drift外完全通过、另有current-source overlay且root bytes不变时，才可用双层证据返回零，绝不重写R2 sidecar。
- `tools/check_no_company_literals.py`：递归扫描 `scripts/`、`tools/` 全部生产 Python identity literal 的扩展性 gate；支持把真实 scanner 结果写到调用方显式指定的隔离 CSV，供 publication runner 生成并在 prepare 时重验。
- `tools/check_capability_contract_alignment.py`：能力契约 anchor、文档路径与 `file::symbol` 的机械结构 gate；不证明 claim 语义成立。
- `tools/check_vnext_semantics.py`：从 SourceStrategy family literal union 派生业务语义扫描器，并扫描 vNext/bridge executable 的 AI adapter authority 与 secret token 泄漏；secret root/递归 namespace 中任意 symlink 都 fail closed，receipt 绑定 registry 与 gate source bytes。
- `tools/check_provider_egress.py`：扫描`scripts/**`与`tools/**`的provider opener、boundary caller、repository transport caller和remote adapter constructor exact set；唯一opener必须由reservation-owner capability到达。
- `tools/vnext_operator.py` / `tools/vnext_review.py`：同一套 recorded/live operator 与 HUMAN review CLI；支持fixture list/show、prepare/status/review/finalize/replay/project/publish/rollback/restore/acceptance，默认隐藏 traceback 并可输出 JSON。fixture catalog拥有recorded source/response/Spec/company/period authority，拒绝caller业务覆盖。
- `tools/vnext_capture_qualification_fixture.py`：PR-2期间在SEC/provider构造前稳定返回`AI_QUALIFICATION_EGRESS_NOT_ENABLED`；WB-4+未明确授权并接入完整WB-3 execution/reservation/acceptance以前不得恢复真实capture。
- `tools/freeze_table_qualification.py` / `tools/create_stage_a_validation_snapshot.py`：前者仅从现有本地SEC bytes、WB-3 mock regression和当前代码生成content-addressed table qualification freeze receipt；后者只绑定当前clean Stage-A source tree与未变R2 root/历史provenance。两者不得调用SEC/provider或进入qualification。
- `tools/investigate_table_context_minimization.py`：Stage-B decision-neutral离线研究入口；逐字节分解当前provider/table payload，覆盖Marriott development与Hilton/Hyatt distinct source hashes×两个lodging task，构造五个research-only候选并逐字段round-trip。候选不接入production serializer/task catalog，不调用SEC/provider；dictionary/indirection只证明机器可逆，明确仍需真实qualification验证模型可读性。
- `tools/investigate_jpm_financial_grid.py`：只读、interval-based JPM完整grid census；复用production raw parser/text transform但不构造完整expanded dict/list，输出679表逐表矩形/blank/span/text/canonical-size、100000门首次触发点和A/B/C decision-neutral option matrix。它不改`resource_limits.py`、不筛表/分片/换source、不调用SEC/provider；full materialization benchmark固定诚实记录`NOT_RUN_RESOURCE_SAFETY`。
- `tools/vnext_table_context_measurement.py`：`plan`仅写content-addressed离线plan；`execute`无family/task/source/provider override，必须同时收到exact授权词、当前HEAD与UTC时间才可能进入一次真实provider边界。本轮不得运行`execute`。
- `tools/create_table_qualification_owner_decision_packet.py`：在新freeze与Stage-A overlay均可重验后，生成schema-v3 owner packet；顶层严格分开`OWNER_APPROVED`（200k、全表/原序/无prefilter、family-scoped readiness、shared global invalidation）与`STILL_UNDECIDED`（serializer/live measurement/financial strategy/source/selector），并绑定context+census receipts、unchanged R2 root和三类零egress。旧packet保留，只更新content-addressed pointer。
- `tools/vnext_qualification.py` / `tools/vnext_cutover.py`：前者的legacy `prepare` 在读取fixture或创建Run前直接要求显式catalog task，不能用disclosure schema-v1回退或以全局family循环替代family-scoped gate；未来若另行授权，只能由通过该family三项readiness gate的显式task plan接线第二布局/holdout。其余正式 qualification/Cutover路径先验证第二真实布局，再冻结production semantic tree及pre-holdout inventory，最后验证post-freeze holdout；live Cutover在release planning前固定执行SEC acquisition/inventory并持久化命令、ledger tail、inventory receipt与portable all-attempt audit closure。受控`--fixture-id` cold-start走同一Run/Batch/Projector状态机，只接受`artifacts/vnext/recorded-*`专用workspace；live core exact固定module-owned repository、`artifacts/vnext/cutover`、`outputs` legacy snapshot与formal publication root，caller override在load/write前拒绝；formal fault matrix沿用同一固定root。每次有效live调用（包括HUMAN resume）都会fresh执行SEC acquisition，再复用source-exact pinned semantic plan，并把本次receipt单独回绑audit/full closure。receipt按当前解释器binary、五条固定命令、ledger prefix/tail、attempt exact set与inventory current bytes重验；recorded resume只向`<workspace>/recorded-publication`做sandbox CAS/PublicationView read-back，正式active/root与formal namespace保持不变，TEST_ONLY review不构成formal HUMAN证据。
- `tools/vnext_terminal_cycle.py`：formal new/rollback/restore各调用一次；在单进程中pin一次publication transaction，依序验证Stage10 Golden、Stage11 report、Stage12 active publication、snapshot publish与snapshot verify，并把exact gate set、pointer/mirror hash和零网络/repair/write计数形成content-addressed结果。
- `tools/vnext_zero_ai_release.py`：repository-owned 零 AI ratchet CLI；不接受 workspace、source、metric、provider 或 publication-root override。
- `tools/run_acceptance.py`：recorded scope在macOS `/usr/bin/sandbox-exec` process-tree边界强制离线，剥离child live secrets，并绑定clean source/Requirement、隔离gate exact artifacts、formal namespace exact trees、pointer lock/latest status与SEC ledger bytes；sandbox递归拒绝live Cutover/qualification/request-attempt/publication/publication-switch/fault/live-audit写入，并保护pointer lock/latest status单文件。缺sandbox、alias/special entry或任一漂移均fail closed，root drift即使恢复也保持失败，ledger不回滚。持久receipt以`$REPO_ROOT`、`$ACCEPTANCE_OUTPUT`、`$PYTHON_CURRENT`、`$PYTHON39`和`$SANDBOX_EXEC`替代host-local路径，并用runtime binary SHA-256保留执行身份。full未显式授权时返回稳定错误；获授权后编排acquisition、Cutover、三次单进程terminal validation、rollback、restore与最终evidence binding，并在HUMAN/失败子进程意外commit时恢复调用前authority且保留原blocker。7200秒默认值只是单命令上限；只有实际完整返回0才是full PASS。

### 业务逻辑与运行入口

- `01_SOP_SEC_10公司单年指标计算_直接SEC.md`：当前运行路径中的业务方法输入，属于 acceptance source；其中 M0–M7 是概念阶段，不是当前 `scripts/00_*`–`12_*` 的物理顺序，实际运行以 `README_RUN.md` 为准。
- `02_指标定义_SEC_10公司单年指标.md`：指标定义、候选链、公式、适用性与降级语义。
- `SEC_metrics_Project_Overview_and_Expert_Guide.md`：解释性非权威文档；其中历史数量或历史验收结论不是当前状态源，也不得作为 SOP 运行权威。
- `README_RUN.md`：完整阶段顺序、验收入口、主要输出和 light review 说明。
- `CIK变更应对方案.md`：CIK、successor/predecessor 与实体连续性规则，属于 acceptance source。
- `evidence/requests_log.csv`：按 request attempt 记录的请求 ledger。
- `evidence/requests_log_manifest.json`：绑定 request CSV 的 schema version、row count 与整表 SHA-256；缺失或失配时 request history 不能视为完整证据。
- `evidence/request_attempts/`：content-addressed immutable response body/header attempts。
- `outputs/`：inventory、指标、证据、coverage、Golden、validation 与审计派生产物。
- `outputs/validation_run_manifest.json`：最近一次 repair validation 实际刷新/未刷新的证据清单，不是 runtime checkpoint，也不单独证明当前 checkout。
- `outputs/validation_snapshot_provenance.json`：成功 stage 12 对 source-input tree 与关键 artifact bytes 的绑定。
- `REPORT_十公司财务指标.md`：当前批次的派生中文报告，不独立定义能力、指标口径或成功状态。
- `artifacts/vnext/`：Run、review、qualification、immutable publication bundle、PR-3 table qualification freeze/Stage-A source overlay receipt、Stage-B decision-neutral investigation receipts 与 latest attempt 状态的本地运行域；OPEN/FAILED workspace 和凭据不得提交，也不得替代 root CSV/报告。freeze/overlay/investigation都是离线前提证据，不是qualification/live/publication。
- `outputs/active_publication.json`：正式 active identity 的唯一 committed pointer。当前 pointer 指向 Issue #15 R2 zero-AI successor；只能按其22指标bundle/receipt范围解释，不能把partial ratchet写成最终Cutover/full PASS。

测试文件和 fixture 的职责统一由 `TESTING.md` 管理，不在此逐项复制。新增、删除或改变上述核心文件职责时，必须同步更新本节。

## 2. 权威边界

- 架构事实以代码、配置、测试和 `architecture.md` 为准。
- 指标业务口径以 `02_指标定义_SEC_10公司单年指标.md` 和实现/validation 为准。
- 能力边界以 `capability_contract.json` 为准。
- 用户可观察验收以 `interact.md` 为准。
- 业务指南只能派生解释能力契约与用户行为，不能自行承诺功能。
- 测试策略以 `TESTING.md` 为准；SOP 和 PR checklist 只引用，不复制易漂移细节。
- source/document 角色与 acceptance source closure 以 `config/validation_source_policy.json` 为准；SOP 权威引用必须被 policy 分类，解释性非权威文档不得作为运行权威。
- 当前运行状态只能从 validation manifest、snapshot checker 与报告共同判断；长篇 Markdown 中的历史数量或结论不是当前状态源。
- 生成报告和 CSV 是当前代码与输入的 snapshot，不替代源代码、契约、provenance sidecar 或独立 gate。
- vNext 实现能力以 FSD、immutable R2、R3 Addendum、effective Decision、catalog、代码与测试为准；当前运行状态只由 qualification/live/staging/publication/full receipts 和 active pointer 证明。没有 active pointer 时，现有 root 结果入口不因代码已实现而自动切换。

### Source provenance 与当前 checkout

`manifest.source_commit` 是运行时观察值，不应被孤立解释：

1. exact commit 相同且 source-input closure clean，是最直接的匹配；
2. artifact commit 或 merge commit 改变 SHA 时，只有 `tools/check_validation_snapshot.py` 证明完整 source-input tree 等价，才可继续；
3. closure 由 `config/validation_source_policy.json` 定义；policy 自身、runtime source 目录或 acceptance source 文件中的任一 tracked/untracked 改动、文件缺失、symlink、tree digest 变化或关键 artifact hash 变化都使 snapshot 不可验收；
4. `+dirty` 只说明整个工作树含改动，最终判断必须看 source-input closure 和 tree digest。

## 3. 工作规则

1. 先读本文件，再按第 0 节和 `SOP.md` 选择对应流程；明确区分实现就绪、recorded、staging、active 与 full 证据，不把代码能力写成已完成 active Cutover，也不虚构 Databricks、前端、API、CI、部署或调度。
2. 主分支为 `main`。只有用户明确要求 commit、push 或 PR 时才执行发布；对 `main` 的合并通过 PR。
3. 用户未要求发布时，只保留并报告本地修改，不擅自创建分支、commit、push 或 PR。
4. 工作区可能包含用户已有修改；只处理任务范围，禁止覆盖、重置或混入无关 diff。
5. 修改能力边界时先更新或确认 `capability_contract.json`，再检查 `interact.md` 和 business guide。
6. 修改用户可观察行为时更新 `interact.md`，并判断 business guide 是否需要同步。
7. 修改模块边界、调用链、数据流、状态、错误、依赖、配置、artifact publication 或扩展点时更新 `architecture.md`。
8. 修改测试、fixture、测试副作用或推荐顺序时更新 `TESTING.md`。
9. `PR_BODY.md` 是被忽略的本地发布草稿，只在用户明确要求 PR 时由长期模板生成，永不提交。
10. 修改生成型 README/report 行为时改 generator 或稳定 post-processor；不得只手工编辑生成文件。
11. 新增或改变会影响运行/验收的文件，先更新 `config/validation_source_policy.json` 的角色；新增 SOP 权威引用必须由 policy 覆盖并通过 provenance 回归。

## 4. SEC 与数据规则

1. 所有生产网络请求只允许访问官方 SEC 域名，并统一经过 `SecHttpClient`。
2. live 请求的 organization 固定为 `axaxl`；contact email 只从 `SEC_CONTACT_EMAIL` 环境变量读取。缺失、畸形或 example/reserved-domain 邮箱必须在联网前以稳定错误失败。
3. 所有请求尝试保留 UTC 日志；有响应体时保存 immutable raw bytes、headers 与 SHA-256。
4. `requests_log.csv` 与 `requests_log_manifest.json` 共同构成 ledger publication；row count/hash、CSV schema、HEAD/base 有序前缀、下游 locator 与 sidecar 任一失配都不能 PASS。
5. 禁止使用第三方数据、新闻、搜索结果或模型记忆为 SEC 指标补数。
6. 可采信的非空数值必须有 matching metric evidence；证据不足时使用明确 status 和 notes，不得猜数。
7. 公司身份、CIK role、行业 profile 与适用性来自 `config/`；生产代码不得按公司名、CIK、ticker、固定 accession 或固定财年日期写业务分支。
8. 新 artifact 使用 `source_url`、`repo_relative_path`、`content_sha256`、`accession` 与 `document_name`；历史绝对 `local_path` / `source_path` 只作 relocation hint，绝不是跨机器权威地址。

## 5. 代码规范

1. 与用户沟通使用中文；代码、文档和数据文件使用 UTF-8，时间使用 UTC。
2. Python 遵循 PEP 8；函数调用优先显式关键字参数，公共函数和类保持有意义的 docstring。
3. 必需字段通过显式检查 fail fast；不得用隐式 `None` 或宽泛异常吞掉预期外错误。
4. `try/except` 只捕获可处理的具体异常，并保留足够诊断；无法处理的错误在当前边界失败。
5. 输入、输出和阶段 handoff 通过明确数据契约表达，避免隐藏全局状态与不可见副作用。
6. 重复规则抽成共享函数或配置；优先减少代码量，但不得牺牲证据、状态语义和可维护性。
7. 修改生成逻辑时改源代码并重跑适用验证，不把手工编辑生成 CSV/报告当作实现修复。

## 6. Review 与测试

- Issue #15 的 effective D-26 保留 fast/local 主入口 `python3 tools/run_fast_tests.py --jobs 4` 与快速静态 gate；不把全仓/双解释器、隔离 repository/worktree 或长串行套件列为必跑项。金额 budget preflight 不再是必测项；必须保留 single-flight、HTTP 402 一次调用后停批、UNKNOWN_REMOTE_OUTCOME 不自动重试、frozen replay/rollback/restore 零网络和 structured-only 零模型调用的短小确定性证据。`PASSED_FAST_LOCAL_ONLY` 不是 CI、live 或 Cutover。
- 发现 Bug 时遵循 `TESTING.md`：先补稳定复现，再修实现；跨阶段问题同时补场景级证据。
- 不用 quick unittest 替代 Golden、repair gate、snapshot checker 或完整场景，也不用 light review 冒充 full validation。
- 真实运营中会写 `evidence/`、`outputs/` 或报告的命令仍须遵循其受控 authority；它们不是 R4 测试。
- 用户要求 PR 时，逐项完成 `PR_Checklist.md`；任何豁免、未运行测试、known limitation 和未解决决策写入 PR body。

## 7. SOP 清单

需要执行标准流程时，先读取 `SOP.md` 中对应章节：

- 只读取现有结果
- SEC 阶段 00-12 完整批次运行
- Issue #15 Requirement authority 与后续 ratchet 开发
- vNext operator 与正式 Cutover
- 分层验收与失败定位
- PR 发布（仅用户明确要求时）
