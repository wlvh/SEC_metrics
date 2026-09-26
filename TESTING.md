# SEC_metrics 测试与验证流程

## 正常年度输入选择

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_normal_annual_input -v`在保存真实材料上检查非自然财年、52周期间、修订与普通原件分离、十公司保留/故障隔离，以及季度冒充年度、错主体、缺历史分片和后来来源失败反例。测试禁止网络及旧结果读取，不模拟财务答案。组件通过只证明输入准备，未证明指标执行或新SEC发现。fast入口逐项登记以保持30秒单项上限。
<!-- capability-anchor: CAPABILITY.normal_annual_input_selection -->

## 后继来源内容组件

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_financial_duration tests.vnext.test_text_coverage -v`验证原件期间、同表脚注、月底起点、目录/片段/章节/来源篡改；synthetic反例不计真实获取。真实九公司普通年报由normal输入选择后与text组件联测，报告为component integration，不称文本指标已完成。
<!-- capability-anchor: CAPABILITY.financial_source_measurement_period -->
<!-- capability-anchor: CAPABILITY.source_text_coverage -->

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_b06_disclosure_v2 -v`使用PR43两历史原件和保存的新信用协议组正例，验证分母冲突、已知计量改写、额外借款及未知叙述。新10项模块超过30秒；fast逐method登记，完整原生v2冻结/冷读另作接线验收，不能以组件通过代替。旧13项及旧原生材料维持原规则，首次漏洞/修后结果分别保存。
<!-- capability-anchor: CAPABILITY.b06_successor_content_checks -->

## 确切年度候选正式采纳接线

fast白名单共35入口，保留v1发布模块，并加入`tests.vnext.test_annual_publication_authority`。
短测试覆盖冻结政策解析、pending Requirement、真实评论边界与无本地JSON权限。
完整材料集成独立运行，不把SKIP或模板成功视为正式发布。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_annual_publication_authority -v
```

在clean final implementation上先用真实候选prepare v2，再设置
`ANNUAL_FORMAL_TEST_ROOT`、`ANNUAL_FORMAL_TEST_ID`、`ANNUAL_FORMAL_TEST_REPORT`、
`ANNUAL_FORMAL_V1_ROOT`和`ANNUAL_FORMAL_PR39_MERGE`，执行
`python3 -m unittest tests.vnext.test_annual_formal_rehearsal -v`。整个进程树禁网，
实际仓库/原运行历史/v1材料禁写；独立临时目标根允许原生发布、故障、回退/恢复。
只在`annual_candidate._github`注入明确TEST_ONLY返回，并使用原生fault callback，
不mock核心validator成功或构造权限对象。新“操作预留后、native intent前”checkpoint
验证仍旧active且不自动重试；原指针前后checkpoint验证同一authority绑定的恢复。
用真实PR39 Git merge对象单独证明关闭PR的合并关系，不据此签发B的生产权限。

新schema2原生切换日志必须带plan/action/permission IDs；旧schema1与v1包兼容。
来源/Run等原有深度反例可另对本次v2完整包运行
`AnnualPublicationRehearsalTest.test_rebound_bundle_counterexamples`，保留实际退出状态。
完整包验证/内容审核、隔离TEST_ONLY授权和实际生产激活/发布是三个不同证据层。

<!-- capability-anchor: CAPABILITY.annual_candidate_formal_adoption -->

## 普通年度候选完整发布链隔离验收

`tools/run_fast_tests.py` 的白名单入口包括
`tests.vnext.test_annual_publication` 整个模块（4项短边界测试）。GitHub fast CI
执行同一入口；CI日志中的模块名、实际测试数、退出码和非SKIP结果共同证明覆盖。
完整真实包演练仍是单独集成层，不能用fast绿色替代。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_annual_publication tests.vnext.test_invocation_control tests.vnext.test_successor_invocation_control tests.vnext.test_r4_publication_boundaries -v
```

完整演练测试消费由真实成功候选准备出的完整隔离包；不模拟核心validator或采纳
成功。设置 `ANNUAL_PUBLICATION_TEST_ROOT`、`ANNUAL_PUBLICATION_TEST_ID` 和可选
`ANNUAL_PUBLICATION_TEST_REPORT` 后运行：

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. GIT_OPTIONAL_LOCKS=0 python3 -m unittest tests.vnext.test_annual_publication_rehearsal -v
```

测试没有上述真实材料时明确SKIP，不能当作验收成功。完整运行以进程树网络禁止、
实际仓库及PR38原现场禁止写入的sandbox执行，具体完整命令在本轮交付记录中。
只在现有fault checkpoint注入软失败/模拟进程中断，所有来源、原生图和发布门禁
均实际执行。覆盖240/327完整继承、错来源/外来Run/缺Result与Review、重签外层
的包内脚本和假身份、正式权限拒绝、指针前后恢复、回退/恢复和重复准备。
每个输出文件独立，不覆盖原始失败；不运行真实SEC/provider、旧生产函数或实际
Stage12/正式切换。原R3、旧候选和原失败的保护hash在运行前后核对。

<!-- capability-anchor: CAPABILITY.annual_candidate_publication_rehearsal -->

## PR38 标签表示修复回归

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_annual_repair -v
python3 tools/check_annual_label_repair.py --output <new-external-regression.json>
```

原失败原文/response字节不改，旧RAW拒绝、新政策PASS和业务错误反例分别报告。
原生集成只模拟外部GitHub/provider HTTP，真实socket禁用；使用临时新预算目录，
原失败只读并继续作为历史1次计数，模拟记录不消费真实新增额度。
fast保留V7政策隔离smoke；18项原始材料回归及完整原生模拟单独运行，
不将长回归加入30秒fast单例限制。旧V6阶段历史测试不在新代码追认旧执行许可。

<!-- capability-anchor: CAPABILITY.annual_b10_label_repair -->

## 固定代码年度候选运行定向验收

在clean committed checkout执行：

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_annual_runtime -v
```

测试仅模拟GitHub/provider外部返回，禁止真实socket；新data目录无Git，实际代码
始终从原目录执行。覆盖真实FY2024起点到FY2025的原生B01/B10链、新进程去重、
失败不覆盖成功、总额度不因计划改变复位、owner/来源/规则副本篡改、伪造成功引用。
新增清单字节通过模拟SEC客户端写入外部data root；它是行为证据，不是实时发现。
保留旧annual_input/update定向回归和fast/static gates。旧PR36执行测试因历史
execution-authority bytes绑定在其受审提交，不能在新代码重签后冒充历史重验。
真实SEC=0、B10最多一次反馈只在本阶段独立代码审阅通过且新批准登记后执行。
不运行Stage12/root刷新、qualification、measurement或正式发布，不声称full PASS。

<!-- capability-anchor: CAPABILITY.marriott_annual_candidate_runtime -->

本文件是项目测试策略、真实命令、full/light 边界和测试副作用的权威入口。所有命令默认在仓库根目录执行；完整阶段顺序以 `README_RUN.md` 为准。

## Issue #15 D-26 快速验收执行政策

Issue #15 的自包含 Decision Register 以 post-freeze D-26 effective tip 继承并替换父 R4 测试政策。必跑快速入口保持：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_fast_tests.py --jobs 4
```

`.github/workflows/vnext-fast.yml` 在每次 `pull_request` 上以只读 repository 权限、无业务 secret、固定 Python 3.14 执行同一命令；该 GitHub check 只把 fast boundary 自动化，不运行 provider、SEC、portable R3 closure 或 full acceptance。它并发执行直接、非隔离边界用例，每例硬上限 30 秒；Requirement smoke现在加载profile-driven `issue_28_v1`及其exact `issue_15_v1` parent，其余WB-2/WB-2B/WB-3/R1及Stage-C/D用例继续覆盖producer scope、39指标registry、E01 parity、invocation故障矩阵、JPM guard terminal、历史packet/attestation/usage和formal predecessor smoke。recorded acceptance 的任一快速/静态 gate 硬上限 60 秒。不得把全仓 discover、Python 3.9 双跑、临时 Git repository/worktree 或长串行套件列为必跑项。runner 的最高证据层级仍是 `PASSED_FAST_LOCAL_ONLY`：本地 PASS 不等于 GitHub check 已运行，CI green 也不等于 successor full acceptance。

<!-- capability-anchor: BEHAVIOR.r4_fast_concurrent_test_policy -->

Issue #28 的 `S-TEST-POLICY`逐字段继承D-26的fast政策；完整artifact、篡改副本、version evolution和portable history属于另列的定向/integration gates，不挤入30秒fast tier。policy-content来源、snapshot加载PASS、exact-head activation和live授权必须分别报告。

PR-B 增加 `issue_28_v2` 五文件 revision smoke：它保留 activated v1 和 R1–R3 历史解释，只提出尚未激活的 A03/A12 composite scope、A13 INTERNATIONAL_NET_REVENUE 和有界 parser 政策。Requirement revision 2 使用独立的 profile engine 3；两个编号没有一一对应关系。完整 owner-provenance/fragment/重签负例、真实 source fixture、性能对照与磁盘回放按下表分别执行，不以 fast green 代替。provider/paid 调用为零；两个已授权 SEC acquisition 的历史计数单列，离线测试不再联网。

effective D-36 不允许仓库金额 hard cap 或 preflight blocker；estimated/actual cost 超过任意值不得因金额门禁阻止 execution。这不放宽非金额安全边界：HTTP 402 仍只调用一次并终止 batch，payload/context/resource 超硬上限仍 fail closed。Requirement 定向负例会在同时重签外层 file binding 后攻击这些 effective tips，避免只测外层 SHA-256。
<!-- capability-anchor: BEHAVIOR.issue_15_repository_monetary_budget_disabled -->

latest same-ID D-07 chain在one-shot measurement历史tip之后追加exact-binding context feasibility successor；authority定向测试必须重算四段D-07单链、measurement exception、exact-attestation policy、owner comment证据、D-01 8 MiB payload护栏及DeepSeek provider/model/API/1000000 context authority。`live_measurement_authorized=false`、authorization consumed与`live_qualification_authorized=false`继续阻断额外调用。普通qualification default path仍以estimated 200000为inclusive门；只有完整request binding匹配attestation时，该一个task/request可context PASS，且不得复用measurement response。

WB-3生产接线的成功边界必须运行真实Candidate构造和`check_evidence`，不得mock acceptance validator。schema-valid但Evidence失败或task/disclosure mismatch时，唯一injected transport调用形成`EVIDENCE_FAILURE` terminal、释放reservation、停止batch，且acceptance/success/reuse exact set为空；Evidence PASS后首次调用形成content-addressed acceptance，第二次exact operator resume的mock invocation为0并复用同一acceptance identity。reuse负例还会在临时目录篡改持久Candidate后重签外层receipt，要求在transport前fail closed。

provider egress机器门为`python3 tools/check_provider_egress.py`：扫描`scripts/**`与`tools/**`全部生产Python，唯一直接opener必须是`ai_adapter.py::_open_provider_request`，其provider transport caller、repository transport caller和remote adapter constructor exact set固定；capture/context-free factory必须含稳定fail-closed码。动态canary同时证明未授权公共入口opener=0，只有受控operator→Workflow→plan→reservation→egress marker后injected opener=1。context负例在payload bytes未超限而UTF-8 byte token上界超限时以`CONTEXT_LIMIT`、transport invocation=0失败。`paid_model_provider_call_count`只统计billing class为`PAID_MODEL_ENDPOINT`的真实provider marker，不是账单确认；receipt保存`PROVIDER_POLICY_BILLING_CLASS_X_EGRESS_MARKER`来源。

PR-3阶段A新增的必跑离线定向证据为：`tests.vnext.test_compact_table_payload`（Marriott、Hilton七组、Hyatt三组的`decode(encode(expanded))`逐字段相等及compact篡改负例）、`tests.vnext.test_scope_contract`（D-31共享`99% one-day VaR` locator的多维raw proof、exact enum唯一自动规范化、unknown alias→`REVIEW_REQUIRED`且SYSTEM拒绝）、`tests.vnext.test_table_task_contracts`（SourceStrategy SHA-256绑定fallback representation schema的exact table family/metric set、legacy qualification prepare在选择family gate前直接要求显式catalog task；无authorization的synthetic remote catalog attempt不能finalize/freeze/replay，而recorded非egress catalog Run仍可formal freeze/replay）、`tests.vnext.test_table_qualification_authorization`（public/shared catalog LIVE callee缺opaque authorization时在source/transport前失败；synthetic lodging-ready/financial-resource-blocked与反向context-blocked场景只允许ready family形成plan且opener=0；test-only real-builder no-D07 authority以mock provider只形成一次cycle-bound canary，并将同一binding写入Run/attempt/evidence/receipt-owned ledger/replay；target period、media、Run/terminal、family/task/ordinal/source/freeze/cycle/prompt/schema以及evidence/ledger/request/transport mutation全部在opener或formal freeze前拒绝；双并发append保留两个exact ledger row；WB-3 success-response持久化到execution seal、及execution seal到reservation archive的两段崩溃均必须恢复原`SUCCEEDED` terminal；Run recovery覆盖payload、attempt、ledger、evidence、Candidate/EvidenceCheck、ReviewUnit、review assets和checkpoint清理的崩溃点；HTTP 400/402、UNKNOWN与retry-exhausted terminal分别在payload/attempt/ledger/evidence中断后无第二次调用地补齐closure，pre-egress failure不形成remote evidence；cycle closure从WB-3 marker/execution/success/UNKNOWN authority而非Run records起算，未物化terminal阻断另一terminal的finalize/freeze；429/timeout/recoverable 5xx穷尽时精确验证`FAILED_RETRYABLE_FINAL`两条marker/attempt及最后provider request ID）和`tests.vnext.test_table_qualification_freeze`（200000/200001 inclusive boundary、传递shared serializer/Evidence/WB-3 closure、lodging-local与financial-local matrix/task/MetricSpec mutation、11组round-trip、每个本地development source×task envelope与split-cost receipt；伪造family live-ready并重算receipt ID时，current effective D-07/measurement/readiness validator仍拒绝）。冻结后运行`tools/freeze_table_qualification.py --freeze-commit <sha> --frozen-at-utc <UTC>`与`tools/create_stage_a_validation_snapshot.py --frozen-at-utc <UTC>`；`python3 tools/check_validation_snapshot.py`必须同时验证历史R2 artifact bytes与current Stage-A source overlay。所有工具只跑本地WB-3 mock回归和已有SEC bytes；它们必须记录`actual_prompt_tokens=NOT_RUN`、three real egress counts=0、R2 active/root before-after equality。effective D-07以`utf8_byte_upper_bound` v1执行inclusive 200000 family/request门；family-local context/resource failure只阻断该family，shared protected-closure drift阻断全部依赖family，local authority drift只阻断owner family。当前lodging最大392447并记录`ESTIMATED_CONTEXT_LIMIT`，financial记录`NOT_AVAILABLE_RESOURCE_LIMIT`/`EXPANDED_GRID_RESOURCE_LIMIT`，`live_ready_family_ids=[]`；不得加入selector或继续qualification。

Fresh stability重复请求必须额外运行`test_repeated_fresh_request_uses_plan_owned_wb3_namespaces`：同一task的ordinal 1/2要重建为相同provider request SHA但不同qualification task-plan ID与不同plan-owned WB-3 workspace，并真实经过两次mock transport、两个marker/execution/acceptance；cycle validator必须跨两个namespace聚合后仍与统一ledger/Run/Evidence exact-set相等。它禁止用ordinal 1的content-addressed success满足ordinal 2。`test_cycle_blocks_other_terminal_until_wb3_success_materializes`与`test_cycle_exact_set_uses_complete_concurrent_authorized_terminals`继续证明namespace隔离不削弱跨plan的未物化阻断与并发ledger闭包。

family-scoped gate的验收必须走真实public composition而不是只调用`_readiness_by_family`：`test_public_paths_preserve_family_scoped_local_drift`在两个family均synthetic-ready时分别制造lodging-local与financial-local合法matrix drift，不mock `validate_table_qualification_freeze`，要求未受影响family同时形成plan和opaque authorization，owner family则在source/provider opener前以`TABLE_QUALIFICATION_FAMILY_NOT_READY`停止。`test_public_paths_block_shared_serializer_evidence_and_wb3_drift`分别改变serializer、Evidence和WB-3 regression source，要求两个family的plan/authorization都在opener前失败。Stage-A全树比较继续由无`family_id`的snapshot checker负责；authorization必须以requested `family_id`验证shared closure与该family local closure，不能让另一family local dirty path先触发全局source-tree异常。

failure containment还必须覆盖无法重建的local authority，而不只是合法diff：`test_public_paths_contain_nonrebuildable_family_local_failures`使用distinct、ledger-bound synthetic development sources，双向制造source SHA mismatch，并覆盖lodging source missing、lodging task缺失和financial MetricSpec无法解析。测试不得mock freeze validator；故障owner必须持久返回`FAMILY_LOCAL_AUTHORITY_DRIFT`及`LOCAL_SOURCE_BYTES_MISMATCH`/`LOCAL_SOURCE_MISSING`/`LOCAL_TASK_AUTHORITY_INVALID`/`LOCAL_METRIC_SPEC_INVALID`，未受影响family必须继续形成plan与opaque authorization，owner family仍在source/provider opener前停止。

requested-family fast path还必须重验shared WB-4 current-input exact set：`test_public_paths_bind_shared_round_trip_current_inputs`在synthetic-ready authority上分别修改/移除Hilton-v1 source、修改lodging required Hilton-v7 second-layout source及修改Hilton-v1 manifest，要求两个family都以`shared_measurement:round_trip_source_set`在source/provider opener前阻断；恢复exact bytes后两个family必须重新形成plan和authorization。该gate只重哈希Marriott provenance、10份Hilton/Hyatt manifest及有序11份source bytes，不得重新加载sibling development/task/MetricSpec。`test_shared_round_trip_input_closure_is_exact_and_global`另验证11行顺序、actual/declared SHA、authority binding和shared传播。

`tests.vnext.test_table_qualification_authorization` 还逐项篡改 active publication ID、pointer bytes及matrix/evidence/report root bytes，要求所有依赖family的authorization在opener前失败且三种真实egress仍为0；对明确位于qualification closure外的`public_projection.py` drift，则要求无family scope的Stage-A checker继续失败、两个family authorization不被该无关source越权阻断。

当前schema-v4附加定向测试为：`tests.vnext.test_table_context_attestation`逐字段验证Stage C-B→occupancy attestation机械派生、additive RevPAR successor只允许四个明确protected paths变化，以及source/task/prompt/schema/serializer/provider/model/API/request/Requirement/protected closure mutation仍失败；RevPAR terminal落盘后同一suite还要验证第二个exact request只能由自己的attestation通过。`tests.vnext.test_table_context_qualification_guard`验证measurement response/evidence reuse拒绝、qualification未授权时opener=0，以及missing/excess usage只产生一个terminal attempt并skip下一ordinal；`tests.vnext.test_table_context_comparison`保留历史两full provider request exact comparison且不含ratio外推；freeze测试验证`readiness_by_task_request`不能自报或family-wide传播。

`tests.vnext.test_table_qualification_freeze` 对WB-3 regression receipt提供两类确定性证据：不同unittest elapsed/stdout/stderr模拟输出得到同一nested receipt ID；同一clean source tree、freeze commit和UTC timestamp连续构造两次完整freeze也得到相同table qualification freeze receipt ID。

Stage-B lodging context调查运行`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_table_stage_b_context_minimization -v`及连续两次`PYTHONDONTWRITEBYTECODE=1 python3 tools/investigate_table_context_minimization.py`。测试要求Marriott current 392447/392438 exact envelope、Hilton/Hyatt distinct hash×两个task、provider与compact分解byte sum、重复字符串exact set、五候选逐字段/semantic machine round-trip、production serializer hash、root equality及三类egress=0全部闭合；任何dictionary/indirection只能标为需要真实qualification，不能把round-trip写成模型准确率证据。当前五候选maximum为286407/337587/337056/386572/392671，全部仍高于200000。

Stage-B financial grid调查运行`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_table_stage_b_financial_grid_census -v`及连续两次`PYTHONDONTWRITEBYTECODE=1 python3 tools/investigate_jpm_financial_grid.py`。测试锁定exact JPM 12927325 bytes、679 tables、60348 origins/source cells、124761 rectangular cells、62748 span duplicates、1665 synthetic blanks、0.01334552/0.50294563 ratios及table_000588的99975→100050 gate crossing；完整expanded object必须保持未物化，benchmark为`NOT_RUN_RESOURCE_SAFETY`，OPTION-A/B/C均未选择，production parser/resource/root与三类egress不变。

one-shot measurement必须同时运行`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_table_context_measurement -v`。terminal test继续重验历史RevPAR plan/marker/raw/evidence、160928/535/161463 usage、1/1/0与non-credit；revised-policy tests另证明旧attestation不给新prompt credit、两个lodging task生成不同plan/request/cycle/marker、每task第二次使用稳定`AUTHORIZATION_CONSUMED`、跨task不共享marker、retry=0且mock无真实provider。真实CLI的`plan`与`execute`都必须显式给出D-07 exact-enum `--task-contract-id`，不得接受family/source/provider覆盖。

Stage C-A packet运行`PYTHONDONTWRITEBYTECODE=1 python3 tools/create_stage_c_a_packet.py --validate`及`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_table_stage_c_a_packet -v`。packet必须把OWNER_APPROVED、IMPLEMENTED_NOT_EXECUTED、MEASURED_OFFLINE、STILL_UNAUTHORIZED与BLOCKERS分区，authorization ID保持`NOT_ISSUED`，benchmark null值不得用Stage-B估算代填。`check_validation_snapshot.py`只在历史R2 verifier除source drift外完全通过时接受Stage C-A source overlay；旧Stage-A/freeze/snapshot/packet不得重签。

Stage C-B真实命令不是回归测试，只有review 5014622571逐字绑定的clean exact head才可执行一次；marker存在后任何测试、repair或operator都不得再次运行`execute`。提交terminal artifacts后运行`PYTHONDONTWRITEBYTECODE=1 python3 tools/create_stage_c_b_packet.py --validate`及`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_table_stage_c_b_packet -v`。validator只离线重算plan/cycle/authorization、reviewed head/tree ancestry、protected files、唯一marker/evidence/raw response、provider usage hash、1/1/0计数、ordinary 200k blocking、active/root equality和JPM F3 blocker；它不得创建transport。snapshot checker只在Stage C-B packet与current clean source tree共同闭合时接受该post-egress overlay，Stage C-A 0/0/0 packet仍作为历史pre-egress对象原样保留。

修订prompt后的两次真实measurement不是回归测试：先提交代码并生成blocked-current freeze/Stage-A，再分别运行`python3 tools/vnext_table_context_measurement.py plan --task-contract-id <occupancy-or-revpar>`；独立reviewer必须在同一PR top-level comment绑定clean head/tree、两个plan ID、两个provider request SHA及one-shot边界。随后每task只运行一次同CLI `execute --task-contract-id ...`；任一task marker后绝不重跑。usage缺失或actual prompt>200000保存terminal并输出`OWNER_DECISION_REQUIRED`；两者都<=200000时，用既有`create_table_context_feasibility_attestation.py --task-contract-id ...`各生成一个新attestation，再追加same-ID D-07 acceptance successor和新freeze。measurement response仍不能成为qualification ordinal或publication evidence。

lodging qualification source/phase回归运行`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_table_qualification_samples -v`。它必须证明Marriott FY2024 second-layout、Marriott FY2023 post-freeze holdout、Marriott FY2025 fresh source都从matrix/fixture manifest解析到不同fiscal-year/accession/source-byte的immutable attempt；两个task的provider request SHA/estimates exact且plan阶段socket=0。FY2023 holdout的唯一`table_000011`必须同表含2023 RevPAR 124.70、Occupancy 69.2及两个冻结scope literals；全文档table count 66/67/68和FY2023/FY2024 target rows 11/13 span-geometry差异机械证明至少两项layout差异。same-issuer fixture只能由matrix exact点名，不能放宽caller source/company/period通道；SEC URL/accession/document/request ledger和错误CIK仍fail closed。真实顺序固定为：两个`table-plan --phase SECOND_LAYOUT --ordinal 1`经exact-head review后分别`table-execute`并FROZEN → `table-freeze`绑定production semantic tree和provider-ledger prefix → 两个holdout plan/execute/FROZEN → 每task三个fresh ordinals。raw-whitespace shared prompt修订后，Marriott FY2024 second-layout、FY2023 holdout和FY2025 fresh中estimated超200000的request都必须在review comment逐SHA绑定，并由各自新的qualification response actual usage terminal裁决；缺usage/超限停止后续lodging plans。每个Run都要重验qualification ledger/Evidence、Review、Result、validation/freeze，不得复用measurement raw response，也不得新增measurement。

Fresh三轮必须按全family ordinal-major顺序执行：Occupancy 1 → RevPAR 1 → Occupancy 2 → RevPAR 2 → Occupancy 3 → RevPAR 3；ordinal N的两个task均FROZEN前，任一ordinal N+1必须在adapter前失败。相邻Fresh ordinal的provider request SHA可以逐字相同，但qualification task-plan ID与WB-3 namespace必须不同，每个ordinal都要有新的provider request ID、marker、attempt、response、acceptance与execution。任何`REUSED_SUCCESS`、跨plan acceptance、缺usage、actual prompt>200000或terminal failure都停止剩余fresh。

历史post-attestation PR只运行离线命令并禁止qualification；其packet/comparison继续作为pre-RevPAR历史对象按原content ID验证，不得重签为当前状态。current回归改由两份attestation、consumed measurement terminal、dual-ready freeze与lodging qualification phase tests承担。

新freeze/Stage-A/packet生成后运行`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_table_stage_b_owner_packet -v`。测试从current pointer回读并按packet自己的UTC重建同一ID，要求旧packet仍存在；`OWNER_APPROVED`只含200k/full-table/family scope/shared drift，`STILL_UNDECIDED`五项均为null；context/census exact IDs、lodging/financial blockers、空live-ready set、NOT_RUN actual tokens、R2 active/309 rows/root equality与0/0/0 egress全部闭合，不得出现qualification/Issue completion claim。

## Marriott 年报变化检查与输入刷新定向验收

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY -u SEC_CONTACT_EMAIL PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_annual_update -v
```

使用仓库真实保存的 FY2024 成功 B10 Run 和 FY2025 submissions/原文/Company Facts，
验证新旧申报及实际期间、重复下载/无关8-K、缺少/陈旧来源、修订/未知日期/歧义/
补充分片/冲突/获取失败、失败不前移成功基线、真实本地 Git head 改变和数据目录移动。
仅 `sec_http.urlopen` 的外部 HTTP 返回被模拟；真实 `SecHttpClient` 完成零重试、
body/header 保存与追加 ledger，真实 `annual_input` 准备参数。所有 socket 禁止。
模拟清单明确标注，临时来源目录和少量测试 Git 对象不成为真实历史证据。
这些测试不生成 B10 响应、不重跑资格、不写 active 或 root 结果。
PR37阶段收口增加未知form（含可能的新年报）、Company Facts嵌套容器错误、真实
immutable写入冲突/headers序列化故障、完整CLI的503失败JSON反例。CLI测试只复制
已发布bundle作只读基线并配置临时来源根，不替换判断或客户端；只模拟外部HTTP。
失败诊断走stderr，stdout仍为一个JSON；持久化无法完整确认时保留未知SEC计数。

本轮按用户限定只运行此定向验收、适用静态 gates 与现有 fast；不全仓重验、不运行
Stage12/root刷新或重签历史 source drift，不把这些 NOT_RUN 写成 full PASS。
可运行例子与可复核的证据分级见 `docs/annual_update.md`。
<!-- capability-anchor: CAPABILITY.marriott_annual_update_inputs -->

## 普通 B10 候选接入定向验收

冻结本轮代码和新 snapshot 后，在 clean committed checkout 执行：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_annual_candidate -v
```

此组只模拟 `_github` 的外部批准来源和 DeepSeek opener 的 HTTP 返回；真实执行
授权 validator、输入准备、catalog request、WB-3 reservation/terminal、Evidence、
SYSTEM Review 和 Calculator。HTTP mock 使用仅与 FY2025 exact request 相等的
历史 answer bytes 构造模拟新 envelope/usage，不能作为真实新响应或理解能力证明。
测试中的 LIVE-shaped marker/counter 是模拟路径记录，不是项目真实付费调用。
新进程重入通过独立 Python 子进程检验，禁止所有真实 socket connect。

覆盖正常 B10 native Result、FY2024/FY2025 来源与计划区别、错误批准作者/内容/编辑、
错误来源/期间/task/request/代码/Run/目录、qualification 许可互用拒绝、缺失/矛盾/
超限 usage、内容失败、429 与 UNKNOWN 后单次 HTTP 上限、controller 证据缺失拒绝
及正式 active/matrix/SEC ledger 不变。旧 qualification 和 controller 采用差异回归。
所有模拟批准和业务候选仅在临时目录，不写真实激活、授权或历史记录。

适用但未执行的真实步骤：新 Requirement exact-head 激活、独立一次调用批准、
provider/paid 执行及实际 usage、真实候选内容检查。SEC 刷新、完整 qualification、
正式发布及 full acceptance 均不属于本轮。历史冻结源码/响应/收据不为此重签。

## 保存的年度输入局部回归

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_annual_input -v`
验证Marriott FY2023/2024/2025原始submissions/10-K/Company Facts独立准备输入，
通过既有结构化Run产生B01（原生附带B03），并以FY2025原始绑定响应验证B10。
recorded adapter消费响应前必须逐字节比较reader request，随后比较task/schema。
测试拦截实际文件读取，禁止metrics/evidence旧表；沿实际调用栈仅允许
sec_pipeline的通用submissions解析，不允许其语义生产函数。缺失原文、
重复/修订申报、原始期间矛盾和同目录重复触发必须失败；所有Run写到临时目录。
参考值与历史响应只在测试端，不进入生产输入准备函数。

年报日期负例在合成原始submissions parallel arrays中注入空值、null和无效
日期，保留真实清单转换路径。较新10-K不得静默回退，10-K/A不得在默认或
显式年度下消失；均须以ANNUAL_REPORT_DATE_INVALID在目标原文与Company
Facts读取前停止。合成输入不改写任何历史原始材料或收据。

相关未变机制可定向复用：
`tests.vnext.test_scope_contract.ScopeContractTest.test_unknown_alias_requires_human_and_never_system_approval`
与 `tests.vnext.test_invocation_control.InvocationControlTest.test_cutover_success_reuses_exact_accepted_response`。
后者使用mock transport，不能证明真实付费去重。上述证据均不证明新材料
上的模型正确性、在线发现、正式更新或qualification；不运行full live验收。

## 1. 测试原则

- 测行为与契约，不用脆弱的源码字符串或固定数量断言替代真实结果。
- R4 必跑集只在当前工作树运行直接边界用例；既有 fixture、临时工作区和本地 evidence 仅保留给历史诊断或真实运营流程。
- 单元级成功不能替代 Golden、repair gate、snapshot checker 或完整阶段场景；light review 不能替代 full validation。
- 新增测试前先说明它覆盖的真实缺口；避免为 13 个薄 wrapper 重复编写同构测试。
- Bug 修复先加入能稳定复现的最小回归，再修实现；跨阶段状态事故还需要场景级回归。
- 真实 live 运营命令仍须在其受控 authority 边界内确认配置；它们不是 R4 final acceptance 的测试替代物。
- 测试记录必须包含原样命令、结果、证据路径和未运行原因；不能把预期结果写成已通过。
- capability `test_status` 只是受控证据分类，必须与 `test_anchor` 有无一致；alignment checker 验证该结构，但 symbol 存在和标签本身都不证明 statement 语义成立。
<!-- capability-anchor: BEHAVIOR.capability_test_status_controlled -->

## 2. 环境与前提

- 运行时兼容边界仍为 POSIX 本地文件系统上的 Python 3.9+，当前代码只导入标准库和本地模块；R4 只在当前默认解释器运行快速验收，双解释器全量回归不再是必跑项。
- 仓库没有 `pyproject.toml`、requirements 或 tox；唯一 CI workflow 是在 `pull_request` 上以 Python 3.14 运行本节 fast suite。Python 3.9 下限仍由本测试契约和专项回归维护，不由这个单解释器 CI job 证明。
- 快速测试建议设置 `PYTHONDONTWRITEBYTECODE=1`，避免在仓库生成 `__pycache__`。
- live SEC 命令读取 `config/sec_config.json`，只允许官方 SEC 域名，并写入请求日志和 raw evidence。阶段 11 也可能在 C04 AuditorName 本地材料缺失时条件式联网。
- SEC organization 固定为 `axaxl`；自动读取 `config/sec_config.json.contact_email`，显式 `SEC_CONTACT_EMAIL` 优先，非法覆盖值不得回退。选中值缺失、畸形或使用 reserved domain 时返回既有稳定错误。`python3 -m unittest tests.vnext.test_sec_identity -v` 离线验证配置、覆盖、客户端和 acceptance 共用规则；不发起请求。
- stage 12 full 模式要求 provenance source-input closure clean；closure 内 tracked、staged 或 untracked 改动会在主 gate 前失败。生成的 evidence/outputs 不属于 source closure。
- vNext 快速测试只使用 recorded response/test double，并在 replay、Reader 或 report input 边界阻断 socket；它不需要 AI 或 SEC 凭据，也不能证明 live 稳定性。
- `tools/run_acceptance.py --scope recorded` 的离线边界覆盖整个子进程树：当前 macOS 支持路径必须经 `/usr/bin/sandbox-exec` 执行 `(deny network*)`，Python `sitecustomize` audit hook 只作为第二道诊断保护。`sandbox-exec` 缺失时稳定返回 `OFFLINE_PROCESS_SANDBOX_REQUIRED`，不得降级成较弱的同进程 socket monkeypatch；recorded gates 及 full 的 terminal-validation 子进程都会剥离 `DEEPSEEK_API_KEY`、旧`OPENAI_API_KEY`和`SEC_CONTACT_EMAIL`。
- `requirements/issue_15_v1/` 是R1–R3历史回读authority，其旧loader继续验证exact Contract、parent closure、Decision单链及producer/matrix/foundation receipts；`requirements/issue_28_v1/` 是successor开发authority。两者都不能仅凭Requirement bytes把Reader、transport、publication或业务语义写成已实施。

## 3. 真实测试与验证层级

| 层级 | 命令 / 入口 | 网络 | 仓库写入 | 通过条件 | 不能替代 |
|---|---|---:|---:|---|---|
| R4 新绑定正常执行路径 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_r4_bound_label_execution -v` | 无 provider/SEC；worker network-none | 仅当前新版本的临时副本及一个 recorded scoped Run/三个零调用前置 Run | 正常 acceptance→FROZEN→新进程 replay；当前源码哈希真实校验；发布侧版本读取 | live 资格、完整12次aggregate、发布、性能benchmark |
| R4 标签候选与失败收尾定向回归 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_r4_label_representation -v` | provider/SEC/socket 均禁止；本地 Docker worker 保持 network-none | 仅临时 source-input 副本与 recorded Run | 真实原响应旧规则拒绝、新候选经过 Reader/Evidence/Review/Calculator；九份请求、错误主体/值/期间/scope/位置负例；真实失败 finalizer 终态与后续零调用 | 候选政策批准、旧失败追认、新 live qualification、完整生产 freeze/publication；输入副本保存旧证书绑定，测试执行候选 Python，明确不冒充新 execution authority |
| vNext 快速回归 | `PYTHONDONTWRITEBYTECODE=1 python3 tools/run_fast_tests.py --jobs 4`；同一命令由 `.github/workflows/vnext-fast.yml` 在 PR 上执行 | 否 | 否；32个子进程条目只读当前工作树，负例只写小型临时数据 | 保留原29条，并加release aggregate shape、typed publication hook、registry/Spec exact-grid三个短边界；全部返回0并标记`FAST_LOCAL_ONLY`。不在30秒tier重放完整source/portable R3，未提高timeout | 真实来源R4离线资格、10倍性能、live/full acceptance |
| PR-B successor release gates | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_r4_release_gate tests.vnext.test_r4_projection tests.vnext.test_r4_publication_boundaries -v` | 否 | 只写小型临时数据/原生N/A Run；真实merge ancestry使用独立临时Git | aggregate重绑定、owner/activation/merge/head、六Spec/6+54 exact set、native zero-source terminal、recorded/private capability、legacy API及pointer/recovery hooks | 完整15-Run资格或真实发布；形状测试不冒充这些证据 |
| PR-B portable dependency preflight | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_r4_portable_dependencies -v` | 否 | 复制绑定的authority数据；scanner输出只写临时目录；macOS OS禁止网络、原checkout读取与副本写入 | 新进程加载successor ReleasePlan/六Spec/6+54，并运行原生产semantic/scalability扫描；legacy foundation的四个immutable receipt及旧ReleasePlan进入封存闭包 | 不替代完整15-Run或60-coordinate bundle回放 |
| PR-B recorded release rehearsal | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_r4_live_qualification -v`中的`test_z_isolated_successor_release_readback_rollback_restore_no_credit` | 否；cold child OS禁止网络及bundle写入/读取原checkout | 仅在独立复制root生成60-coordinate batch、R4 bundle和临时switch receipts；真实R3不变 | 同一15-Run recorded执行选择六生产值、54原生N/A、strict compatibility、冻结authority新进程回放、R4→R3→R4及crash/mirror负例；credit始终NONE_RECORDED_REHEARSAL | G4、真实publication/live资格/模型准确率；与16-case performance final replay分别报告 |
| PR-B dormant R4 execution seam | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.vnext.test_r4_live_qualification`，并定向运行`test_r4_live_plan`、`test_r4_live_authority`、`test_r4_run_store`、`test_r4_structured_run`、`test_live_scoped_reader`、`test_successor_invocation_control` | GitHub/provider/SEC opener均不调用；guarded Docker worker为network-none | 全量15-Run测试仅在临时release副本；不写正式cycle/freeze/Stage-A或active pointer | 12个独立recorded scoped execution +3个native structured Runs +4个零调用分类；完整artifact重签篡改、usage/UNKNOWN/崩溃/前缀终态负例；新进程portable replay不依赖后来变化的原checkout/engine/canonical | 真实provider准确率/usage、live资格、v2 activation、publication；该回放与16-case离线性能benchmark分开 |
| PR-B B0 shared interfaces | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_source_scope tests.vnext.test_scoped_reader tests.vnext.test_offline_execution_session` | 否 | 只读小型synthetic完整source/authority；最终replay独立重读磁盘 | SourceScope/full asset/task binding、native Candidate/Evidence、scoped request/attempt、零调用四类、window/pin tamper、session一次构造/六child/一次最终replay及UNKNOWN stop | 真实来源认证、performance target、freeze/cycle/Stage-A或live授权 |
| PR-B v2 policy / full artifacts | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_issue28_v2 tests.vnext.test_sec_contact_requirement_policy tests.vnext.test_composite_scope tests.vnext.test_r4_fixture_authority tests.vnext.test_r4_offline_qualification` | 否 | 负例只改系统临时副本 | A03季度/firm/average、A12同源scope、A13净营收、安全上限、622个parent fragment、真实Run/ReleasePlan、完整Scope/attempt与所有重签tamper拒绝；SEC contact真实评论/配置绑定、显式环境优先且非法不回退、历史与current execution分离；不改变旧V1/V2 engine | v2 activation、live qualification/publication |
| PR-B real-source corpus / aggregate performance | `tools/qualify_r4_offline.py` 和 `tools/benchmark_r4_offline_session.py`（完整参数及同一closure见`docs/r4_offline/summary.md`） | 否；worker network-none | 只写新的`docs/r4_offline/`离线证据；不写正式Run/cycle | 六指标各production/alternate及四个zero-call class；native structured-first/Evidence；真实相同输入/解释器cold-vs-session；>=6 prior terminal Runs；>=10x aggregate（含共同的最终replay成本）；恰好一次新进程最终磁盘回放 | actual model tokens、provider响应、live stability、生产freeze/Stage-A或R4 publication |
| Issue #15 authority integration | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_issue15_authority -v` | 否 | 只在系统临时目录复制并篡改测试快照，仓库只读 | 先完整验证并pin一次active R3 publication chain，再让全部历史artifact断言复用该chain；child/parent closure、18 个 effective tips、13 条历史 hash、post-freeze D-36/D-35/D-26/D-07 exact tips、D-07 same-ID与200000 threshold负例、金额/resource 负例、230 行/39 metric baseline、producer exact set、复用 helper scope 的 exact-base callsite 派生、foundation 零 egress通过 | WB-2+ runtime、live、active/full |
| Issue #28 successor Requirement | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_issue28_requirement_transition.Issue28RequirementTransitionFastTest tests.vnext.test_issue28_requirement_transition.Issue28RequirementTransitionTest -v` | 否 | 仅复制五文件child、historical snapshots及既有bound fixtures到系统临时目录 | 五文件closure、recorded-parent binding、477个fragment唯一分类、versioned engine、Decision fork/unknown kind/hash/parent/transfer tamper及legacy兼容通过 | R3 portable read-back、R4实现、live/full |
| PR #29 semantic/artifact rework | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_issue28_rework.Issue28SemanticReworkTest tests.vnext.test_issue28_rework.Issue28ArtifactReworkTest tests.vnext.test_issue28_rework.Issue28PublicationReworkTest -v` | 否；真实Run/publication场景禁止socket | 仅系统临时副本；不写任何repository evidence | 完整Run build/freeze/replay、ReleasePlan file round-trip、publication bundle/read-back；删除1/2/3项identity或generation均失败；legacy错Requirement/bogus hashes失败；outer rebind后安全bounds仍拒绝；V2/R5/pending approval及四种多ratchet invariant通过；policy/activation/live分离 | live/provider执行、R4业务实现、正式发布 |
| PR #29 root independence integration | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_issue28_rework.Issue28RootIndependenceIntegrationTest -v` | 否 | 复制immutable R3/R2/R1 bundle与mirrors到系统临时目录后只改变临时root catalog | 禁止调用Issue #15 live adapter时parent closure仍相同；R3/R2/R1与14 mirrors读回通过；旧execution binding拒绝root drift，新revision使用自身current authority | 变更旧snapshot、实际新Ratchet qualification |
| Issue #28 historical read-back integration | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_issue28_requirement_transition.Issue28HistoricalReadBackIntegrationTest -v` | 否 | 仓库只读；环境需既有ignored零字节publication lock | 完整open active R3一次并pin chain；exact R2/R1、R3 receipt index、14 mirrors及Issue #15 closure不变 | R4实现、live/full |
| WB-2 SourceStrategy | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_source_strategy_registry -v` | 否 | 否；负例只篡改系统临时副本 | 39 metric exact set/四种source mode、family literal、不可变R1→R2→R3 parent/delta/cumulative-key chain、reader versions、historical plan closure/current Requirement separation与authority hashes通过；R3累计24指标/240 keys且只新增B10/B11；删除parent metric/key/retired producer并完整重签仍由no-removal门拒绝 | WB-2B adapters、provider调用、active publication |
| WB-2B deterministic router / public projection | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_deterministic_router tests.vnext.test_zero_ai_release.ZeroAiReleaseTest.test_r1_public_rows_render_without_legacy_rows tests.vnext.test_zero_ai_release.ZeroAiReleaseTest.test_r2_projection_and_producers_survive_legacy_canary -v`；`PYTHONDONTWRITEBYTECODE=1 python3 tools/check_zero_ai_projection.py` | 否；socket constructor 是立即失败 canary | 否；Run只写系统临时目录，其余只读immutable bytes | 五adapter、统一`sources[]`、submissions+acquisition SourceSetManifest、14财务/事件producer无legacy语义入参；R1 18×20、R2 141×20字段全等，approved/unexpected delta为空；屏蔽legacy migrated rows/events后仍生成20/220 rows、79 structural keys、309行与固定key hash；AST证明renderer/producer和oracle分离 | 正式R2 publication、WB-3 invocation control |
| WB-3 invocation control | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_invocation_control tests.vnext.test_wb3_transport_contract -v` | 否；transport均为mock/injected，禁止真实API | 只写系统临时 invocation namespace | 三层身份、生产adapter→controller→repository transport接线、exact reuse、`O_EXCL` owner-only egress、terminal reservation释放、402停批、真实子进程egress后退出的磁盘UNKNOWN恢复、usage/cache/cost观测、payload/context hard limit及空namespace推导零计数通过；完整wire/envelope、secret不落盘、无observation或错误host/policy不得生成success receipt | 真实模型egress、AI qualification、active publication |
| Issue #15 zero-AI R1 active | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_zero_ai_release -v` | 否 | 否；只读正式pointer、bundles、switch/ratchet receipts与root mirrors | A→B→A→B链、20坐标、18 strict-compatible替换、2 structural新增、232-row key set、retirement/read-back与三种零调用计数通过 | R2、AI Reader、39指标最终Cutover、full acceptance |
| Issue #15 zero-AI R2 chain integration | 同上 | 否 | 否；独立projection canary写系统临时Run，formal证据只读 | 完整验证并pin一次active R3，再沿verified predecessor edge完整验证exact R2与R1；22指标、220坐标、141×20 strict-compatible字段、79 structural新增、309-row exact union、submissions+acquisition完整event set、事后event-key parity、projection-bound retirement/read-back与三种零调用计数通过 | WB-4以后、AI Reader、39指标最终Cutover、full acceptance |
| Issue #15 R3 prepare / formal active | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ratchet_release -v`；正式证据只读验证`outputs/active_publication.json`、R3/R2 bundles、ratchet/switch receipts与root mirrors | 否 | 测试只写系统临时workspace与publication root；正式证据验证只读 | 十个committed qualification terminal重跑DerivedAsset/Evidence/Review/Calculator；20-coordinate delta Batch、18个零AIstructural Runs、legacy-A strict oracle、R2 predecessor assembly、24指标/240累计keys/327-row union、portable bundle closure、qualification binding与tamper负例通过；current active=修正版R3、previous=R2，R3→R2→修正版R3 switch chain可重验 | R4、financial/text、39指标最终Cutover、full acceptance |
| vNext semantic gate | 由 `tools/run_acceptance.py --scope recorded` 把一次性 token 注入 scanner 环境后执行 `tools/check_vnext_semantics.py`；本次 acceptance 不把 token 写入被扫描文件 | 否 | 覆盖 `outputs/semantic_audit_receipt.json` | 从 registry family literal union 派生 scanner，production/bridge executable 无业务 parser literal，AI adapter 无越权 I/O；通用词不会形成 false positive，token/symlink 负例 fail closed，receipt 绑定 registry、checker、scalability checker 与 producer bytes | 业务结果 parity、producer canary、强进程沙箱 |
| R4 acceptance receipt | `PYTHONDONTWRITEBYTECODE=1 python3 tools/run_acceptance.py --scope recorded` | 由 macOS process-tree sandbox 强制为否 | 只在 `outputs/acceptance_receipts/` 下写本次 receipt 与 gate artifacts；正式 pointer/root mirrors、formal namespace与SEC ledger不属于允许写集合 | sandbox 存在；R4 并发快速集、semantic/scalability 与 capability alignment 均真实 return code=0；开始/结束 authority 不变时返回 `PASSED_FAST_LOCAL_ONLY` | CI、full acceptance、stage 00–12、live 三轮、Cutover |
| vNext operator | `python3 tools/vnext_operator.py --help`；按正式 runbook 使用 fixture list/show、prepare/status/review/finalize/freeze/replay/project/publish/rollback/restore | recorded 否；live 显式授权后是 | 写显式 Run/publication root；recorded 不写正式 active/root mirrors | stable error、JSON、HUMAN优先或D-06 SYSTEM单链、catalog authority、同一 recorded/live 状态机与 pinned read-back 回归通过 | 真实 live、full receipt |
| Cold-start recorded fixture | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_recorded_fixture_operator -v` | 否；测试对 socket constructor 设立即失败 canary | 只在 `artifacts/vnext/recorded-*` 专用 workspace 创建 structured/OPEN/FROZEN Runs、staging 与 `<workspace>/recorded-publication`，结束清理；live/formal namespace与正式 root 不变 | fixture list/show 可发现 byte-bound source；既有HUMAN decision优先，否则D-06 SYSTEM decision使同一命令完成freeze/replay、Batch、Projector、sandbox CAS与PublicationView read-back；formal/reserved recorded workspace与任意live workspace override都在workflow前稳定拒绝；正式state exact不变 | 真实 live、active Cutover、full acceptance |
| Cutover qualification | `vnext_capture_qualification_fixture.py --fixture-id <second>`→`prepare --fixture-id <second>`；`freeze --frozen-at-utc <UTC>`；新增holdout后`vnext_capture_qualification_fixture.py --fixture-id <holdout>`→`prepare --fixture-id <holdout>`；`status` | capture 是；replay 否 | capture 只追加SEC ledger/raw和仓库fixture，qualification 写 content-addressed receipts/Run与freeze-bound pre-holdout inventory | capture 的业务坐标只来自 `fixtures/vnext/qualification_candidates.json`，SEC/DeepSeek secret只存在于进程环境；第二布局先于freeze，且每个布局只有有效 HUMAN 或D-06 SYSTEM `APPROVE`、全量`PUBLISHED` Result与`PASSED` validation才可签receipt；holdout bytes/Run在freeze前不存在且company/CIK独立；两者均走同一Reader/Evidence/Review path、至少两项布局差异，且holdout后semantic tree hash不变 | live 三轮、十公司 staging、active Cutover |
| Failed qualification reset | `vnext_qualification.py reset --reset-at-utc <UTC> --reason <STABLE_REASON>` | 否 | 保存content-addressed reset receipt后重置当前qualification索引；不删除旧Run、fixture、receipt或SEC ledger | 仅当当前chain不可验证且无active pointer时允许；旧manifest SHA、blocker和UTC均进入receipt，重启后必须从新的second layout开始 | 删除审计、在active后重置、拼接旧链 |
| Formal full acceptance | `python3 tools/run_acceptance.py --scope full --execute-live` | 是 | live只使用固定`artifacts/vnext/cutover`；先执行固定SEC Stage00/01/02/03/05 acquisition/inventory，再导入verified legacy A、提交formal B、更新mirrors并执行rollback/restore三个terminal cycles | acquisition receipt按当前解释器binary、五命令、ledger prefix/tail、attempt与inventory exact重验；portable live audit closure、formal staging、A→B commit；new/rollback/restore每轮只调用一次`tools/vnext_terminal_cycle.py`，以单进程单次pin完成Stage10/11/12与snapshot publish/verify；rollback、restore、final binding全部真实返回0；任何NOT_RUN均不通过 | 外部审计接受 |
| Provenance 专项（历史诊断） | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_validation_provenance tests.test_validation_provenance_light_package` | 否 | 会使用临时目录和临时 Git 仓库 | 仅在人工定位 provenance 故障时按需运行；不是 R4 必跑项 | 业务指标、Golden、SEC evidence |
| 能力文档对齐 | `python3 tools/check_capability_contract_alignment.py`；PR 再加 `--base-ref <base>` | 否 | 否 | 清除会重定向仓库的 Git 环境变量并禁用 replacement refs 后，证据路径存在于 HEAD、是 regular blob 且工作树 bytes 未偏离 HEAD；anchor grammar/唯一性、type/status 枚举、受控 `test_status` 与 `test_anchor` 有无一致、null anchor 的 `untested_reason`/`pending_since`、`file::symbol` 与 Markdown directive 均合法；跨 base tombstone 不删除/复用，base 与 HEAD 的每条 request row 严格匹配其 current/legacy CSV schema，legacy row 独立规范化为 portable 完整字段，current row 逐字段保留有序前缀且只尾部追加 | claim 语义与证据强度判断；label/symbol 存在不证明 statement |
| 静态扩展性 gate | `python3 tools/check_no_company_literals.py` | 否 | 是，覆盖 `outputs/scalability_audit.csv`；publication runner 使用显式隔离输出 | 递归扫描 `scripts/`、`tools/`（含 `scripts/vnext/`）后无禁止 identity literal，进程退出 0；publication prepare 重跑同一 executable | 指标正确性、场景回归 |
| Golden | `python3 scripts/10_run_golden_assertions.py` | full 模式会联网；light 不联网 | full 模式覆盖 Golden outputs，并可能追加 evidence/log | 所有适用 assertion PASS；light 只能得到受限完整性结果 | repair gate、snapshot checker、外部验收 |
| Repair / validation gate | `python3 scripts/12_validate_repair.py` | 否 | legacy路径覆盖validation/audit、manifest、报告与sidecar；active路径只替换provenance sidecar | 原有full/light或active PublicationView terminal条件通过，且source/artifact provenance publication/self-check成功 | live 数据采集、完整场景 |
| Snapshot 复核 | `python3 tools/check_validation_snapshot.py` | 否 | 否 | source closure clean/等价；artifact key set、SHA-256 与 size 匹配 | 重新运行 Golden/repair、外部审计 |
| Report build | active：`python3 scripts/11_build_report.py`；legacy candidate：`python3 scripts/sec_pipeline.py --workspace-dir <absolute-isolated-root> 11_build_report` | active分支否；legacy隔离candidate条件式联网 | active分支只读pinned bundle并打印报告；legacy只允许显式隔离candidate写入 | 命令完成只证明指定view/candidate可读或已生成 | 独立阶段12/checker |
| Live smoke | `python3 scripts/00_smoke_test_sec_access.py` | 是 | 是，写 request log 与 raw response | 官方 SEC 请求满足脚本判据 | 后续指标与验证 |
| Legacy完整candidate场景（运营） | 对同一绝对隔离数据根按`README_RUN.md`逐次执行`sec_pipeline.py --workspace-dir <root> <stage>`；不得让Stage04/09/11写源码repository root | 是 | 是，大量candidate evidence/outputs/report | 仅为实际非迁移运营流程；不属于 R4 开发/PR/final acceptance 测试 | formal Cutover/full acceptance |

## 4. 快速回归覆盖

本节的既有覆盖目录是历史测试资产清单，不把其中 freeze/replay、隔离 Git fixture 或大规模场景升级为 R4 必跑项；R4 的精确测试集合只由 `tools/run_fast_tests.py` 定义。

### 4.1 vNext recorded / formal Cutover 实现

`tests/vnext/` 当前覆盖：

- strict JSON duplicate/non-finite/surrogate、NFC、ordered/set、Decimal 28/HALF_EVEN、跨 Python 3.9+ 一致的扩展日期/UTC 时间、semantic runtime version 与 content identity；Candidate新增assistant-output binding使canonicalizer semantic version 2→3，source plan绑定latest verified request attempt及locator class并让live拒绝legacy working locator使其3→4，legacy inventory冻结Git blob binding使projector semantic version 2→3，D-06 SYSTEM review渲染使review renderer semantic version 2→3。当前semantic runtime versions hash为`sha256:f724d52688b92935d5de6e2e8000fb3c65a3ee66b316dc8c646c8bef11b551a9`，任一变化都使旧closure/approval/Run/Batch/publication失效。Run/Review/Validation/Publication 状态分离，PASSED/FAILED/NOT_RUN 均可 freeze，而 FAILED/NOT_RUN publication 负例失败关闭。FROZEN Run 不接受 STARTED attempt；每条 SUCCEEDED attempt 都要从structured assistant output重放schema并独立验证provider envelope bytes，即使没有 Candidate 引用也不能跳过。
- Requirement Snapshot exact bytes/hash、Decision 单链、`catalog/` MetricSpec 默认展开、ordered `choose_first`、selection policy closure、dependency、cardinality、未知 op/guard、AST depth 32/node 256 和 Python 3.9 syntax surface。
- SEC-only portable SourceReference、同 bytes 多 observation identity、完整 HTML table-grid、merged-cell locator round-trip、ReaderInputManifest exact table set；release input plan必须先验ledger manifest，再按URL/body hash/accession/document选择有序ledger中最后一个验证通过的attempt并绑定attempt/body/header/class。后续ledger使plan不可重导时返回`SOURCE_LEDGER_BINDING_AMBIGUOUS`；recorded可保留唯一且exact验证path/hash/headers/size的`LEGACY_WORKING_LOCATOR`并把tier/class写入portable closure，formal live只允许`IMMUTABLE_ATTEMPT`，遇legacy必须返回`LIVE_SOURCE_ATTEMPT_INCOMPLETE`。业务词变化不能筛掉或重排输入表。集中资源预算负例覆盖 span 面积、表数、span/entity 十进制词法、解析期 source cell、展开 cell、cell/table text 与全 filing 总量；Python 3.9 在大整数转换前即失败，其他超限也必须在下一次对象/矩形物化前稳定失败且不裁剪。
- provider-neutral recorded AI attempt把request、task contract、output schema、structured assistant output与provider envelope分别保存为content-addressed bytes；OBSERVATION_CANDIDATE绑定attempt的`assistant_output_sha256`，`raw_response_sha256`只绑定完整provider envelope审计bytes，两者不能互相替代或协同伪造。shared output schema v3对scope-evidence locator做cross-field exact约束：caption分支只含table locator，cell/header/row/label分支必须含八字段cell locator；测试机械核对两个互斥分支，防止provider schema再次接受Reader/Evidence必拒的组合。freeze 从仓库 Spec 重建请求并重算digest/Candidate，schema failure 不回退；`run_ai_attempt` 只接受 adapter、`PreparedReaderRequest` 和 clock，重新校验完整 table set/system/task binding，固定 temperature=0 与严格 Reader validator，不接受 caller sampling mapping 或 callback。recorded/approved adapter 只能由仓库 builder 构造为私有 exact type；authority 在 `complete` 前校验，duck object、子类与实例级方法替换都不能取得 filing bytes。approved adapter 不保存 transport；每次 attempt 在 D-01/payload preflight 后从模块 registry 新建并验证 exact-policy transport，调用方替换 `_transport` 不会被调用。该普通 Python 对象用于降低误用自由度，不是安全边界；freeze/load 仍从持久化 bytes 与仓库 Spec 独立重放。remote adapter 只能从模块固定 repository root 的 Requirement Snapshot 与 effective APPROVED D-01 编译，approved workflow 的 payload root 必须与该 authority 是同一物理 repository；caller policy/root/transport 被拒且 cross-root 在任何 payload read/transport 前失败。批准测试 snapshot 将十个字段交给仓库 factory；每次 outbound 前重读 policy/closure，已构造 adapter 遇到 D-01 撤回时transport=0；policy mismatch 与 payload 超限在 egress 前失败，host mismatch和带observation的timeout分别产生记录实际`TransportObservation`的FAILED attempt；异常或旧式tuple缺observation时失败且不生成猜测审计。freeze/replay对直接写入的SUCCEEDED attempt重新执行assistant-output schema、provider-envelope byte binding与recorded/effective D-01 policy。测试只证明仓库调用图、policy执行与审计绑定，不声称同进程强安全沙箱或remote live稳定性。

- scope-bound prompt回归必须证明两个lodging task使用同一精确prompt：caption只有在selected target table的supplied `caption_raw_text`非空时才允许，且输出`raw_text`逐字相同；否则cell/header/row/label必须从同一目标表的一格复制完整八字段locator与exact raw text。测试还必须证明another-table/nearby-prose被prompt明确禁止、shared schema hash保持v3不变、旧attestation无法给新request credit、qualification在两份新attestation被D-07接受前关闭。
- raw-whitespace prompt回归还必须证明leading/trailing space、LF、CR与tab都属于exact `raw_text`，provider JSON只能用`\n`/`\r`/`\t`等合法转义表示，禁止trim、normalize或collapse。历史159376/550/159926 Occupancy terminal必须离线重放为`SCOPE_LABEL_TEXT_MISMATCH`，不得修补response；161433/161422 attestations对新prompt request只能是historical。owner禁止新增measurement后，SECOND_LAYOUT、POST_FREEZE_HOLDOUT与FRESH_STABILITY都必须由各自exact-head-reviewed新qualification response提供terminal usage，缺失/超限零重试并停止后续lodging plans。
- compact-raw-text prompt回归必须证明两个lodging task逐字共享`c=[caption,caption_raw_text]`、`x=[row_index,column_index,rowspan,colspan,header,raw_text,text]`字段说明，caption scope raw text只能来自`c[1]`，cell/header/row/label只能来自`x[5]`，并显式禁止`c[0]`/`x[6]`。当前159479/560/160039 Occupancy失败terminal必须保留为HTTP 200/retry=0、context PASS但`SCOPE_LABEL_TEXT_MISMATCH`，不得给Review/validation/qualification/publication credit或复用；schema hash、serializer-v2 bytes/round-trip、source/task/provider/model/API与业务口径必须保持不变。
- registered qualification fixture回归必须使用历史FY2024 OPEN Run证明：即使`marriott_international`存在于production registry，`SECOND_LAYOUT`/`POST_FREEZE_HOLDOUT` authorization的traits/CIK仍由点名fixture重建；`FRESH_STABILITY`与普通production Run保持registry-first，无authorization外部fixture保持registry-miss fallback。历史159479/562/160041 success、Evidence/Review/Result不得因本地finalization bug获得qualification credit或被新cycle复用。
- Reader 一次返回 lodging disclosure group 的三角色；Evidence 只重读给定 cell/local label，不搜索相似值；1% identity 0.99/1.00/1.01% 边界；完整表格安全渲染和 invisible/control/bidi 可见化。超长 cell 全文保留并通过 HTML comment 限制物理行，总 review bytes 超限明确失败，不静默截断。
- 整个 ReviewUnit 的 canonical/rendered binding、HUMAN identity、approved claims 与 supersedes 单链；HUMAN CLI 从 ReviewUnit 派生 APPROVE 全量 claims 或 REJECT 空 claims，不要求 reviewer 复述 claim 文件；REJECT+claims 与 partial APPROVE 在低层 append 拒绝，append 后直接改磁盘的负例还覆盖 finalizer 和 freeze reload。每个 ReviewUnit 必须有唯一 effective decision，published/supporting Observation roles 和 published Result/Trace 必须 exact-complete。workflow 只接收 disclosure locator、外部 source facts 与 adapter，内部从 repository/RawBlob 派生 compiled Spec closure、Requirement hashes、derived URI 与 temperature=0；finalizer 不接受调用方 traits 或二次 compiled semantics/metric/unit/period。production Run在入口与freeze从registry/profile重算 traits；唯一`run:qualification:<fixture-id>`外部issuer例外从该fixture的exact manifest/source重新绑定traits/period/CIK/SourceReference，production registry不能伪装为该例外。fiscal-year 标签必须落在不超过 53 周的精确期间内；freeze 重建全部 reviewed Observation、按仓库 Spec 重跑 Calculator、拒绝 AI-table metric 伪装 structured input与未被 Trace 消费的游离 Observation，并把 Result/Trace 的 value/formula/scope/quality/applicability/publication/reason 回绑 Run target、decision、input 与仓库 Spec。FROZEN Run byte tamper 拒绝，无 socket replay。
- B01 reported unit 原样携带、B03 component unit exact guard、B10 percent→ratio、B11/ADR 非 USD WITHHELD，以及 B01 observation reuse、B03 direct/fallback、D&A 防双计、cross-check、Decimal、quality、NOT_MEANINGFUL 与 Marriott/Pfizer legacy anchor。Pfizer 真实 Company Facts 的 APPROX 结果必须逐位匹配 legacy `OK_APPROX` 并完成 freeze/replay；0.99/1.00% PUBLISHED 与 1.01% WITHHELD 必须贯穿 calculate→append→freeze→replay。freeze 从 raw bytes 重建 B01/B03 fact set，在 B03 没有配套 B01 Result 时仍按 B01 Spec 重算复用 Observation；被拒分支不保留 selected component IDs，结果 quality 取 Observation 与 accepted Spec branch 中更保守者。通用 Calculator executable 不含指标/公司/行业业务 literal。
- 完整 legacy row projection、B03 source-grain component evidence/reconciliation、evidence identity exact cells、方法字段 old→new receipt、legacy write gate；content-addressed BatchManifest 从 registry/display mapping、traits/applicability、release plan 与全部 PASSED FROZEN Runs 派生 company×metric exact set。baseline manifest 同时绑定 legacy metrics/evidence/Golden 的 schema、row count、size 与 SHA-256，合法 schema 中增加任意非迁移行也在投影前失败。Projector默认入口保持四个locator；只有module-owned ratchet可传repository-derived child plan、active predecessor、committed-Run loader与outer Requirement，不接受CLI caller hash/status/metric mapping。它实际生成并逐 byte 重验 metrics/evidence/compatibility/frozen Golden/固定 repair execution rows；projection multiplier 与 Golden tolerance comparison 使用 canonical 28/ROUND_HALF_EVEN context。真实reviewed table Observation缺少`form/filed`时按Spec常量/冻结baseline补齐；public locator只有在URL/accession/document/content hash及本地bytes全部相同时保留历史路径，内部SourceReference仍绑定immutable attempt。缺公司/缺N/A/重复或额外坐标、单公司冒充整批、跨period、Run locator symlink、dependency冒充顶层输出和同一key多scope均失败。结构不适用workflow必须在source/AI=0时持久化可freeze/replay的N/A Result/Trace。
- Recorded publication 正向 fixture 必须通过生产 `write_publication_validation_receipt()` 执行 gate，不得用测试 helper 自签业务 PASS receipt。runner 与 prepare 都不接收 caller `ledger_binding`：它们从 verified Batch 中实际产生 Observation 的 SourceReference，以及实际 AI attempt 引用的 ReaderInputManifest source exact set 派生使用集合；SEC attempt ID 由 current-schema ledger 行及其有序位置重算，并联合验证整表 manifest、SourceReference URL/accession/document/raw hash和row声明的body/header locator。`IMMUTABLE_ATTEMPT`必须命中content-addressed pair；recorded `LEGACY_WORKING_LOCATOR`必须唯一、逐path/hash/headers/size重验并把locator tier/class及其portable bytes写入closure，不能伪装成immutable。formal/live receipt拒绝任何legacy class。receipt 只绑定截至最后一个已消费 row 的最小有序前缀，后续未被该 Batch 使用的合法 append 不改变 candidate view；ledger 缺失、attempt 不属于该前缀、已用 prefix/locator/bytes 漂移均在 PASS receipt 或 `PUBLISHABLE` 前失败。runner 还重跑 Projector、真实 semantic-audit executable 与真实 company-literal scalability executable；后者递归扫描 `scripts/`、`tools/`，不能漏掉 `scripts/vnext/`。runner 从 candidate 生成 coverage、scanner-derived header-only scalability PASS artifact、覆盖全部 migrated numeric rows及其全部 evidence rows的 stratified audit、`PASSED_RECORDED_ONLY` validation manifest 和 recorded-only README/report；已有 caller bytes 必须逐 byte 相等。semantic receipt 必须绑定 checker 自身、scalability checker 与其 producer bytes，publisher 在执行 checker 前独立核对 hash。随后 runner 验证 candidate CSV/frozen Golden binding/compatibility/Result-row/evidence/Projector repair 与每项 required check，prepare 再次执行 Projector 与两道 executable gate，并要求 evidence hash、candidate view 与 artifact path/hash/size 一致。任意文本、自签 PASS、伪造 header-only scalability CSV、在顶层或 vNext 源码加入 identity branch、替换 checker 重放旧 PASS、自写 repair/report PASS、删除/增加 migrated row、CSV value 与 Run 不一致、畸形 nested JSON 或 storage symlink 均不能准备 bundle。完整 batch→projection→prepare→recorded read-back正向场景断言bundle bytes与Run-derived matrix一致且包含N/A行。formal public receipt/initial-chain/forward-commit symbols和operator `publish --commit`必须全部fail closed，只有Cutover orchestrator可调用私有mutation primitive。首次formal chain必须只读导入严格重验的legacy bytes为A，再提交绑定A的B；该导入和rollback终态测试不得调用legacy parser。该 recorded Golden 证明来自 frozen baseline + strict parity；它不冒充 active pinned view 的现行 Stage 10/12 full 重跑。immutable read-back 重算持久化 proof 与 bundle bytes，不依赖历史 Run/legacy locator，也不冒充外部 full validation 重跑。
- 当正式active pointer存在时，Stage10/11/12各自的独立wrapper只打开一次pinned `PublicationView`；formal full不把三个wrapper当作同一轮证据，而是每个new/rollback/restore cycle只启动一次`tools/vnext_terminal_cycle.py`，在单进程中pin一次transaction后依序验证Stage10 Golden、Stage11只读bundle report、Stage12 formal receipt/root mirrors、snapshot publish与verify。测试断言整轮AI socket=0、SEC socket=0、repair=0、Stage11 authoritative write=0，Stage12不得改bundle/root mirrors，并覆盖任一步pointer切换使整轮fail closed。没有pointer时，业务用户仍读取现有root snapshot。
- legacy B01/B03/B10/B11 写入口、旧 lodging/B03 resolvers 和 active root 的 legacy stage 写入均 fail closed 为 `LEGACY_PATH_STILL_ACTIVE`；full-flow 回归把旧 resolvers monkeypatch 为立即抛错，公开流程仍通过。该代码退出证明不等于已经提交 active publication。
- formal operator/review CLI 覆盖命令面、稳定错误、JSON、默认无 traceback、TOCTOU、Decision 单链与恢复命令；模型、fixture 与 runner均不能伪装为HUMAN，缺HUMAN时仅D-06固定SYSTEM decision可APPROVE。Issue #15 live transport 读取 effective D-01，retry/batch-stop 读取 effective D-35；retryable 最多一次，terminal/UNKNOWN 不进入后续 attempt 或 stability ordinal。
- cold-start recorded 场景通过公开 `fixture list/show` 和 `tools/vnext_cutover.py --fixture-id`，不使用 tests helper 作为入口：catalog 会逐 byte 绑定 source/response/excerpt/Spec/provenance并拒绝 caller business override；首次调用创建完整 planned structured Runs 与 OPEN review Run，返回 `review.md`、ReviewUnit hash及可复制命令且不创建publication；测试再用显式 `TEST_ONLY_EXPLICIT_REVIEW` 决定，重跑同一命令完成finalize/freeze/replay、complete Batch、Projector、recorded validation、`<workspace>/recorded-publication` CAS与PublicationView read-back。测试同时以 socket canary 证明调用数为0，并 exact 比较正式 pointer/root mirrors前后不变。该TEST_ONLY决定只证明UX/transaction，不满足formal HUMAN或full证据；generic formal commit仍fail closed。
- acceptance runner保留原样argv、解释器、真实return code、duration、stdout/stderr SHA-256/size、artifact hash与NOT_RUN原因，但持久化前递归portable化：`runtime_bindings`以`$PYTHON_CURRENT`、`$SANDBOX_EXEC`等token记录executable name与runtime binary SHA-256，repository/output locator使用`$REPO_ROOT`/`$ACCEPTANCE_OUTPUT`，剩余host path只保留hash，不写本机绝对路径。`--output-dir`与任一正式单文件或namespace存在equal/ancestor/descendant关系时，recorded/full都必须在首次写入前以`ACCEPTANCE_OUTPUT_DIR_OVERLAPS_FORMAL_AUTHORITY`失败。R4不启动Python 3.9全量测试或probe。recorded scope通过真实socket blocker，sandbox以literal保护正式单文件（含pointer lock/latest status）、以subpath保护live Cutover、qualification、request-attempt、publication、publication-switch、fault与live-audit tree，并在前后重验active/mirrors、目录exact set、文件hash/size、pointer lock/latest status与SEC ledger bytes。full未授权立即返回`LIVE_EXECUTION_NOT_AUTHORIZED`；已授权但prerequisite缺失时不执行Cutover。前提齐全后，Cutover先在release planning前固定执行SEC Stage00/01/02/03/05，证明ledger仅合法尾部追加并保存inventory/acquisition receipt；三次live attempt被复制到`outputs/vnext_cutover_audits/<content-id>/`，acceptance在原Run workspace清理后仍重验request/schema/assistant-output/provider-envelope/model/TransportObservation/Candidate/Evidence/Review/compatibility exact closure。随后导入verified legacy A、prepare formal B、在隔离root运行14项fault matrix，先持久化并绑定acquisition/staging/Cutover/audit/fault receipts，最后才执行official private initial-chain CAS。再按new B、rollback A、restore B三个terminal cycles各调用一次公开terminal CLI，在同一pinned transaction内完成Stage10/11/12与snapshot publish/verify，最终绑定Run/Batch/pointer/mirror/snapshot和结构化terminal result的文件SHA-256。任何NOT_RUN、HUMAN blocker或中途失败都不能PASS。
- acceptance command row 同时记录逻辑 `argv`、实际含 sandbox wrapper 的 `executed_argv`、wrapper 与sandbox profile hash；这些字段同样经过上述portable边界。CLI 默认 `--timeout-seconds 7200` 只是每条命令的上限，不是成功条件；实际超时仍记录 `FAILED`/`COMMAND_TIMEOUT`。recorded 开始前备份正式 pointer、root mirrors 与 provenance sidecar；即使意外漂移已经逐 byte 恢复，receipt 仍以 `RECORDED_ACTIVE_STATE_CHANGED` 失败，观测失败则恢复后以 `RECORDED_GATE_EXECUTION_FAILED` 失败。full 在每次 Cutover 子进程返回后都从 official pointer read-back；非零、`HUMAN_REVIEW_REQUIRED` 或非法返回若意外提交 publication，必须恢复声明的 predecessor（首次无 pointer 时恢复原 root bytes）并保留原 blocker，不能把补偿恢复当作 HUMAN 或 full PASS。
- publication switch failure-first覆盖content-addressed intent：writer在mirror mutation前于同一exclusive lock写`outputs/publication_switch_intents/<sha256>.json`；共享锁reader遇pending/multiple/tamper只fail closed，不能自行清理。writer recovery在pointer==proposed时补齐或幂等验证switch receipt并重建proposed mirrors；pointer==previous时移除本事务receipt、验证previous tip并恢复previous mirrors；其他状态失败。动态测试同时覆盖pointer写入后hard crash、pre-pointer crash、initial A→B失败恢复原root/no pointer与重试。
- `RunbookGeneratorTest`要求无active时checked-in `README_RUN.md`逐byte等于`build_readme()`；active时只允许其后追加由immutable bundle绑定的zero-AI postscript，生成器前缀仍须exact。测试继续机械锁定第二布局→freeze→holdout、resume不重复freeze、public formal authority fail-closed与portable audit closure文案；Stage11场景的mock README/report也必须保留正式标题。

本轮真实运行证据包括Issue #15 zero-AI R1 A→B→A→B历史、R2 predecessor，以及lodging qualification和R3 cumulative formal active。SECOND_LAYOUT、POST_FREEZE_HOLDOUT与三个FRESH ordinal的Occupancy/RevPAR共十个新qualification execution均有provider usage、Evidence PASS、SYSTEM APPROVE、全量PUBLISHED Result与PASSED validation；R3在R2上新增B10/B11，形成24指标、240个累计vNext Result keys、18个新增structural keys和327行matrix。发布期间真实完成R3→R2 rollback→修正版R3，当前previous精确为R2。该证据仍不能替代financial/text qualification、39指标最终Cutover或full acceptance。

完整性负例必须按不变量覆盖全部入口，而不是只保留最初复现：Spec 身份同时覆盖 published Result/Trace 与 supporting Observation；期间覆盖 Run/Candidate/Observation/Result/Batch；digest 同时覆盖 request-only、Attempt/Candidate 协同 response 篡改与 FAILED attempt 的 task-Spec 替换；batch 覆盖 missing/extra/duplicate company×metric 与 locator alias；projection 覆盖 delete/add/value drift；receipt 覆盖自签 PASS、missing execution evidence、missing/extra/hash/size/internal FAIL/missing required check/旧 view；状态机覆盖 prepared-only sibling rollback 与 FAILED/BLOCKED+latest-success。新增权威参数或凭证入口时，必须在这些贯穿场景中增行。

| 不变量 | 已覆盖入口 | 贯穿 mutation test |
|---|---|---|
| repository authority | registry/profile company traits；published Result/Trace；supporting Observation；AI-table source mode；Company Facts raw fact/selection；跨 MetricSpec structured dependency；无 selected Observation 的 structured WITHHELD；AI adapter exact type/factory authority；D-01 Requirement closure、固定 root、workflow payload 同 root 与仓库 transport factory；workflow/finalizer API | `test_freeze_rejects_company_traits_detached_from_registry`、`test_non_lodging_stops_before_source_or_ai`、`test_freeze_rejects_result_metric_spec_identity_substitution`、`test_freeze_rejects_supporting_role_identity_and_unit_substitution`、`test_freeze_rejects_ai_metric_disguised_as_structured_input`、`test_freeze_rejects_structured_value_absent_from_raw_bytes`、`test_freeze_rejects_forged_structured_dependency`、`test_freeze_rejects_false_structured_withheld_result`、`test_run_attempt_rejects_caller_adapter_before_complete`、`test_remote_adapter_binds_policy_owned_repository_transport`、`test_remote_workflow_rejects_payload_root_outside_authority` |
| remote policy 与事实 | D-01 十字段；每 attempt 新建的 factory transport 与 caller `_transport` 替换；payload preflight；actual host；带 observation 的 timeout/transport failure；缺 observation fail hard；no-egress fact；disk-reloaded SUCCEEDED attempt | `test_remote_adapter_binds_policy_owned_repository_transport`、`test_remote_transport_policy_enforcement_matrix`、`test_freeze_rejects_remote_success_bypassing_adapter` |
| untrusted resource budget | span/table/row/column/source cell/expanded cell/text/filing-total；review physical line 与 total bytes | `test_table_grid_resource_budget_matrix`、`test_review_renderer_resource_budget_matrix` |
| complete reviewed graph | CLI derives whole-unit claims；effective HUMAN decision 与决定自身 APPROVE/REJECT claims 语义；published/supporting Observation role exact set；published Result/Trace exact set与业务状态；Observation+accepted Spec branch quality；Calculator value/formula；Observation consumption exact set | `test_review_cli_derives_claims_from_review_unit`、`test_freeze_requires_effective_decision_for_each_review_unit`、`test_review_decision_semantics_cross_every_trust_boundary`、`test_freeze_rejects_supporting_role_identity_and_unit_substitution`、`test_freeze_rejects_result_business_state_detached_from_inputs`、`test_pfizer_approx_real_bytes_freezes_and_replays`、`test_b03_cross_check_boundaries_freeze_and_replay`、`test_freeze_recalculates_reviewed_result_from_observation`、`test_freeze_rejects_unconsumed_structured_observation`、`test_freeze_rejects_applicable_result_rebranded_structural` |
| exact business coordinates | Run fiscal-year/日期/最长 53 周；Candidate；Observation；Result/Trace calculation target；B01/B03/B10/B11/ADR unit | `test_loaded_run_reapplies_period_and_trait_invariants`、`test_run_period_is_the_only_finalization_period`、`test_freeze_rejects_false_structured_withheld_result`、`test_b01_preserves_selected_reported_currency`、`test_b03_mixed_component_currency_fails_closed`、`test_reviewed_currency_mismatch_materializes_withheld_results` |
| digest/schema from bytes | successful/failed task contract；request/schema；每条SUCCEEDED assistant output与provider envelope独立binding；Candidate→assistant output；Evidence replay；STARTED terminal gate | `test_freeze_recomputes_attempt_digests_from_exact_bytes`、`test_freeze_rebuilds_failed_attempt_request_from_task_spec`、`test_freeze_replays_every_successful_ai_response`、`test_freeze_rejects_nonterminal_ai_attempt` |
| receipt proves exact view | Run immutable identity/artifacts；publication Requirement/Batch/Projection、从 consumed source 派生的真实 ledger membership/最小已用 prefix/声明 locator/predecessor、required gate execution evidence、artifact exact set/SHA-256/size | `test_run_validation_receipt_binds_immutable_manifest_view`、`test_missing_request_ledger_blocks_before_validation_receipt`、`test_batch_source_absent_from_request_ledger_cannot_validate`、`test_unrelated_ledger_tail_preserves_used_publication_prefix`、`test_declared_request_ledger_locators_must_identify_attempt`、`test_self_signed_pass_without_gate_execution_cannot_prepare`、`test_receipt_binds_exact_artifacts_checks_and_view` |
| state follows committed history | forward commit；rollback；prepared sibling；mirrors/pointer | `test_rollback_rejects_prepared_never_committed_sibling`、`test_pinned_view_survives_forward_commit_and_rollback` |
| validation/source/publication 分离 | PASSED/FAILED/NOT_RUN freeze；FAILED/NOT_RUN publication block；missing-role+PUBLISHED block；missing-role+WITHHELD audit freeze；SOP 状态表 | `test_freeze_accepts_each_audit_validation_state`、`test_nonpassed_validation_receipt_cannot_prepare`、`test_missing_source_role_cannot_freeze_published_result`、`test_human_rejection_materializes_withheld_results`、`test_sop_structured_validation_state_contract` |
| projection authority | repository-derived complete BatchManifest；persisted FROZEN Run full reload；non-lodging durable N/A；legacy/candidate/gate exact set；dependency Spec 不冒充缺失输出；legacy compatibility key uniqueness；bundled ProjectionManifest/result-row identity；fixed Decimal arithmetic context | `test_projector_rejects_single_company_as_complete_batch`、`test_projector_reloads_the_persisted_frozen_run`、`test_projector_requires_persisted_projection_inputs`、`test_projector_requires_complete_release_result_set`、`test_projector_rejects_intermediate_run_locator_symlink`、`test_non_lodging_stops_before_source_or_ai`、`test_candidate_row_mutations_cannot_prepare`、`test_complete_batch_projects_publishes_and_reads_active_view`、`test_projector_arithmetic_ignores_global_decimal_context` |
| status cannot contradict itself | persisted latest Run/publication locator；lock 内重验 latest bundle；pointer-verified active publication；root-derived path layout | `test_active_run_cannot_be_rebranded_failed_in_latest_status`、`test_latest_success_binds_corresponding_publication`、`test_latest_status_revalidates_candidate_inside_pointer_lock`、`test_publication_layout_is_derived_from_one_root` |
| shared external gates | acceptance 与 live client 共用 SEC identity validator；semantic scanner 对 symlink 与 token 泄漏 fail closed | `test_sec_identity_gate_and_http_client_share_fail_fast_rules`、`test_secret_scan_fails_closed_for_every_symlink_shape` |

### 4.2 现行 00–12 快速回归

当前 `tests/test_sec_pipeline_validation.py` 覆盖：

- `LIGHT_REVIEW_MODE` 与 `WORKSPACE_INCOMPLETE` 的工作区形状和 marker 行为。
- light snapshot、fixture 与 metrics matrix 篡改检测。
- metrics matrix 的配置派生 `(company, metric_id)` unique exact set，以及 coverage 与 matrix exact key set 对齐；删一补重复、删一补未知和 coverage 缩集均不能 PASS。
- full Golden 的配置/fixture expected assertion exact set、唯一性与删行/增行检测；stratified audit 的五层 deterministic exact set、唯一性与缩集检测。
- 8-K 从 manifest 验证后的有序 request ledger 取得 request-bound base/supplement submissions bytes（当前 bytes 必须匹配同 URL/document 的最新成功 200 完整身份），推导 FY inventory，再从 raw hdr/primary bytes 重放 item，并与 `events.csv` 做 row-multiset exact set；删除 filing/event、重复 item、回滚到旧成功 submissions 后同步缩减 inventory/events、修改未登记工作副本、删除 supplement、正向 count/accession 或其他确定性 metric 字段漂移、删除 component evidence，以及把真实命中伪装成零均不能 PASS。filing-bound raw 文档出现冲突成功 bodies 也必须失败。hdr 无 item时的 primary fallback、primary-only 成功路径与两者都无 item 的失败边界由固定 fixture 覆盖；正向事件按每个被计数组件保留独立 filing identity，零值必须保留完整 scan evidence。
- Basel threshold 排除、actual ratio 选择与 iXBRL scale/parser route；inline namespace fixture 同时覆盖官方 DEI URI 的自定义 prefix、伪 DEI prefix 和冲突 namespace 声明 fail closed。
- captive finance recall/exclusion 与第 11 家 financial institution fixture。
- 10-K/A 到同期间原始 10-K full-instance fallback。
- AST string-addition constant folding 与 I1-I8 implementation map。
- 缺失 JPM CET1 evidence 不得形成空 failure list 或 PASS。
- full/light 中 `NOT_EVALUATED_MISSING_EVIDENCE` 对 report verdict 的不同影响。
- validation run manifest 的 refreshed/not-refreshed 清单、stale CSV 隔离，以及报告写入失败时不得提前暴露成功终态。
- clone A 生成 locator、移动到不同绝对路径的 clone B 后直接执行阶段 11；clone A 的祖先目录与仓库内目录重复使用 `evidence` anchor 时，迁移必须按 hash、URL、accession、document 与 filing directory 选择唯一的当前 clone 后缀，无匹配或多匹配均 fail closed，不能简单取首个或最后一个 anchor。同一 request 的 body/header 必须来自同一个旧仓库根；body 只命中内层候选而 sidecar 只命中外层候选的混合 observation 必须由生产迁移和独立 checker 同时拒绝。已有 hash 不得被迁移重签，`..` 与 symlink 不得逃逸仓库；同名同 hash 的跨 accession 文件不得被重定位；多 source/accession 对单路径的豁免只能由明确的 `events.csv` 派生语义触发，不得根据字段数量猜测。
- RPO claim 所需 instance fact 缺失、Golden fixture 缺失或 metrics 为空时不能 PASS。
- 同一逻辑请求路径的多次 attempt 保留各自 content-addressed body/header；legacy locator 即使 working body 仍匹配也必须优先解析 snapshot，避免相同 body 掩盖被覆盖的 header。同 body 多 attempt 只把不晚于各 row `timestamp_utc` 的最新匹配 `saved_at_utc` 归给该 row；删掉原 header、仅留后一次 header 不得 PASS，同时间多个匹配必须 FAIL。validator 只允许按 ledger body SHA/length 读取 single-link regular content-addressed body；snapshot body 不存在才验证原 legacy pair，body 存在但 header 缺失仍为 NOT_EVALUATED，body identity 错、latest eligible timestamp 并列多 sidecar、snapshot symlink/hardlink 与 reserved namespace 大小写别名为 FAIL，已声明 immutable locator 的篡改不得回退。两个独立进程并发追加同一 request ledger 时不得丢行，且 manifest 必须保持有效；request-log manifest 的 JSON key/type 与 CSV 行列宽必须严格。working ledger 必须保留 Git HEAD 的完整有序前缀；runtime committed-HEAD parser 与 PR checker 都拒绝 current row 的多余/缺失单元格，checker 的 current 接受集合不得比 runtime 更宽。PR checker 还对 legacy/current base 与 HEAD 的 prefix、appended tail 逐行校验精确 shape，对 legacy base 独立规范化 portable path、hash、URL-derived accession/document，并以独立实现覆盖重复 anchor 的唯一命中与歧义拒绝；current base 比较完整 row，之后只允许合法尾部追加。重排、删行、identity 字段改写及重签不能把旧响应重新定义为最新。下游 locator、已存 response sidecar 与 URL/accession/document 联合身份继续提供反向约束；hash mismatch 显式 NOT_EVALUATED，并报告 unavailable 总数后最多展示前 20 条明细。
- mock transport 的 response-read timeout、`IncompleteRead` 和已发请求后的 persistence failure 必须形成明确 observation；初始 URL 必须是精确官方 HTTPS origin，redirect 只保留首跳 3xx observation 而不自动请求下一跳；snapshot symlink、大小写 namespace alias、目录型文件目标、hash-prefix symlink，以及最终文件名在检查后的 symlink/hardlink 注入均不得覆盖仓库内外 victim；working/log/manifest hardlink 必须通过新 inode 替换断开，UUID transaction path 预占必须 fail closed。
- C04 必须先检查 `target_10k`（含 10-K/A），只有本地 AuditorName 不可用时才回退同 CIK、同期间原始 10-K；已有有序候选事实时不触发 fetch。空白或纯标点名称不是事实，不同 canonical 名称冲突时不得 first-win 或联网掩盖；后续 200 material observation 覆盖同 identity 的旧 503 current row。full C04 gate 必须从 request-bound accession index 分别重建当期候选/上期 10-K 实例集；同一 filing-bound URL/document 的多个成功 bodies 必须一致，删除 derived material row 不能隐藏已有原始事实；validator 不得复用生产 metric/evidence row builder。两期事实可用时 evidence 必须保留双 raw locator；事实缺失/冲突时必须精确绑定对应 raw scan，把 locator 换成同 accession 的无关合法文档也必须失败；同步篡改完整 C04 metric 与 evidence 不能替代原始 DEI 事实重算。C04 期间起点只取同 CIK prior；没有同 CIK prior 时回退当年 1 月 1 日，不能跨 successor/predecessor CIK 拼接；生产 repair 路径必须把该期间同时写入 metric 与 evidence，不能只测试 period helper；损坏 metrics/evidence/inventory row schema 必须返回 FAIL 而非逃逸崩溃。
- numeric OK evidence 必须同时匹配 value、unit、period、accession，并具备 SEC source、concept/section 与 extraction method。
- capability contract 的 live alignment、repo root 必须等于实际 Git toplevel、HEAD regular blob 与工作树逐字节一致、Git replacement ref/assume-unchanged/仓库重定向环境变量不得改写证据、anchor/directive grammar、type/status 枚举、null metadata、跨 base tombstone 不复用、legacy/current request row 精确行形状、legacy→portable 独立规范化、current→current 完整字段有序前缀，以及本地 `PR_BODY.md` 隔离；嵌在父 Git 仓库、无 `.git` 的离线包、object-store symlink 或 `objects/info/alternates`/`http-alternates` 不能借用其他 checkout 的 HEAD。真实 `git worktree add` 场景中，无 alias 的登记目录必须通过；gitdir 最终 component、gitdir 中间 component 和 commondir 中间 component 任一为 symlink 时，即使 Git 本身仍能解析 HEAD，guard 与下游 source-commit / base-history 读取也必须 fail closed。

`tests/test_validation_provenance.py` 与 `tests/test_validation_provenance_light_package.py` 额外覆盖：

- `config/validation_source_policy.json` 的 exact schema、互斥角色与 SOP 权威引用分类；`01_SOP...md` 或 CIK identity rules 作为 acceptance source，Expert Guide 作为解释性非权威文档，PR Checklist 作为发布治理；
- 只修改 `01_SOP...md` 时 source capture 必须明确拒绝，不能保持相同 digest/count 与 `GIT_CLEAN`；从 policy 删除该 SOP 权威输入也必须 fail closed；
- clean full/light round-trip、manifest source-commit 绑定和内容等价 merge commit warning；
- staged、untracked、ignored 或修改后的 source input 拒绝；
- 无 Git light package 缺少任一显式 singleton source 文件时失败，不能通过删文件缩小 closure；
- provenance key set、artifact hash/size、source tree、stale/unsafe sidecar 和 postflight failure 篡改检测；
- full snapshot 发布后，`evidence/request_attempts/` recursive exact set 的删除、新增、bytes 篡改、symlink 与 hardlink 检测；light package 不把该 full-only directory 冒充随包 evidence；
- stage 11 wrapper 不做 pre/post authoritative write，active read-back保持 sidecar/mirrors；legacy README/report notice 由 candidate producer负责，stage 12 wrapper负责 provenance publication与幂等/fail-closed行为。

边界说明：

- `validation_package_mode()` 的 `FULL_VALIDATION` 工作区分类目前没有独立 unittest；完整模式仍依赖真实完整工作区、Golden 和 repair gate 的运行证据。
- `FullInstanceFallbackTest` 只覆盖 10-K/A 到同期间原始 10-K 的 full-instance fallback，不得计入 package-mode coverage；它在缺少 `evidence/submissions/` 时整类 skip，必须在测试记录中保留 skip 数量与原因。
- 依赖当前 full 工作区的 8-K 真实证据回放测试，只在 submissions 或对应 raw 8-K 材料不可用时 skip 该真实形状用例；request-bound 缩集、primary fallback 和 parser 固定 fixture 不依赖 full 工作区，不得被同步 skip。
- 快速回归中的重复-anchor clone A/B 场景覆盖 locator 迁移、唯一身份选择、歧义拒绝、request body/header 共同旧仓库根和阶段 11 消费边界；它仍不等于真实 SEC 全批次重跑。
- 8-K expected-event replay 与生产路径共用 item parser；固定 hdr/primary parser fixture 只锚定已支持格式，不是独立的通用 SEC 文档 oracle，因此 full gate 不单独证明所有未见格式的解析完整性。
- 快速回归不访问网络，也不证明阶段 00-12 的完整 artifact handoff。

## 5. Fixture 简介

| 路径 | 用途 |
|---|---|
| `tests/fixtures/sec_10_company_spike/golden_expected_values.csv` | 固定结构与数值 Golden expected |
| `tests/fixtures/eleventh_company_smoke/` | 配置驱动的新增公司/profile 行为与去公司特例边界 |
| `tests/fixtures/inline_scale_route/mock_inline_scale.xml` | iXBRL scale、sign 与 parser route 回归 |
| `tests/fixtures/regression/previous_ok_status_snapshot.csv` | 已有 OK recall 的回退防护 |
| `tests/fixtures/vnext/sample_lodging.html` | recorded lodging 完整 table-grid、merged cells、三角色、adversarial untrusted text 与 review/replay fixture；不是第二真实 filing 或独立 holdout |
| `fixtures/vnext/recorded/operator_fixture_catalog.json`、`marriott_2025_*` | catalog及从仓库既有 Marriott 10-K bytes 派生的真实 table-grid excerpt、recorded response 与 provenance；支持公开 fixture list/show、cold-start OPEN review和sandbox PublicationView场景，证明同一 production Reader/Evidence/Review path，但TEST_ONLY review不冒充formal HUMAN，也不冒充第二布局、post-freeze holdout、live attempt或full acceptance |
| `tests/fixtures/vnext/companyfacts_b03_crosscheck/CIK0000078003.json` | B03 0.99/1.00/1.01% cross-check 的最小 Company Facts 场景；使用 production parser/calculator/freeze/replay，不冒充第二真实 filing |

fixture 可以包含公司身份；生产 `scripts/` 与 `tools/` 不得用公司身份触发业务分支。

## 6. FULL、LIGHT 与不完整 workspace

`validation_package_mode()` 当前按工作区形状判定：

1. `evidence/`、`evidence/requests_log.csv` 和至少一个 `outputs/concept_inventory/*.csv` 存在时，进入 `FULL_VALIDATION` 形状；required-input gate 仍逐项检查核心输出和每家公司需要的 instance/ecd evidence。
2. 上述材料有缺失且根目录存在 `LIGHT_REVIEW_PACKAGE.marker` 时，返回 `LIGHT_REVIEW_MODE`。
3. 材料有缺失且没有 marker 时，返回 `WORKSPACE_INCOMPLETE`。

重要限制：

- `FULL_VALIDATION` 只是初始形状分类，不证明每个 raw evidence 文件都齐全；缺少关键 domain evidence 必须写成 `NOT_EVALUATED_MISSING_EVIDENCE` 并阻止正常 GO。
- 完整工作区优先于 marker；不能仅靠 marker 强制降为 light。
- repair validation 的 status 只允许 `PASS`、`FAIL`、`SKIPPED_LIGHT_PACKAGE`、`NOT_EVALUATED_MISSING_EVIDENCE`、`WORKSPACE_INCOMPLETE`。
- light 中依赖 raw evidence 或 concept inventory 的检查必须显示 `SKIPPED_LIGHT_PACKAGE` 或 `NOT_EVALUATED_MISSING_EVIDENCE`，manifest result 只能是带 caveat 的受限通过。
- 无 Git light package 的 provenance 只证明随包 source/artifact bytes；显式 singleton source 文件缺失时必须失败，且永远不能升级为 full validation。
- helper 缺少验证所需 evidence 时不得用空 failures 形成 PASS。
- 未声明的部分工作区必须硬失败，不能自动降级为 light。

## 7. 写入副作用

### 7.1 静态扩展性 gate

`tools/check_no_company_literals.py` 会覆盖 `outputs/scalability_audit.csv`。运行后必须用 `git status --short` 检查是否产生非预期 diff。

### 7.2 Golden

full 模式会通过 G2 访问 SEC companyconcept，可能更新 `evidence/requests_log.csv` 和 raw response，并覆盖：

- `outputs/golden_results.csv`
- `outputs/golden_candidates.csv`

light 模式只做随包 snapshot integrity，不能被记录成 full Golden 重算。

### 7.3 Repair gate

阶段 12 在任何 validation 写入前创建 `outputs/validation_run_manifest.json`，然后逐项登记 `refreshed_artifacts`。它总会先重建 implementation map 与 spec audit；full 模式还写 stub-period sidecar。FULL/LIGHT 工作区继续重建 stratified/scalability audit 与 repair validation。若工作区为 `WORKSPACE_INCOMPLETE`，它只写 repair validation 的失败行，不会刷新 stratified/scalability audit；此时已有文件必须留在 `not_refreshed_artifacts`，不得作为本次运行证据。阶段 12 先用 projected terminal manifest 构建并写入报告，报告持久化成功后才把 manifest 从 `IN_PROGRESS` 写成终态；报告写入失败必须保留 `IN_PROGRESS`。它是 gate，但不是只读检查。

### 7.4 Report build

当active pointer存在时，Stage11只从一个pinned PublicationView读取bundle report，不执行下述legacy写入、repair或网络。没有pointer时，下述legacy Stage11只允许通过`sec_pipeline.py --workspace-dir <absolute-isolated-root> 11_build_report`运行，源码repository root会以`LEGACY_PATH_STILL_ACTIVE`失败：它先把locator-bearing artifact迁移为portable identity，在exact-set manifest通过后normalize request log，再执行bounded P0 repair并生成coverage、crosscheck、审计、manifest、report与README；C04本地材料不足时可能最小补抓官方SEC material。该candidate路径继续验证request-bound 8-K/C04原始链、ledger有序前缀、immutable attempts与完整降级语义，但绝不允许写B01/B03/B10/B11，也不能自行发布root mirrors。内部deferred validation不能替代独立Stage12/checker。

### 7.5 Validation snapshot provenance

legacy candidate publication开始时会使旧provenance失效；formal active的纯report read-back不失效、不修复也不重签任何artifact。Stage12只在terminal gate成功后计算source-input tree、动态active bundle/pointer/mirrors与其他artifact closure的SHA-256/size，原子写sidecar并从磁盘重验；postflight失败必须fail closed。checker本身只读。

`config/validation_source_policy.json`把`fixtures/`纳入runtime source，并把qualification、zero-AI Run、immutable request attempts、publication bundles/switch receipts、zero-AI ratchet receipts、failure/fault/live-audit receipts列为full artifact directories。full或R1 active正例必须真实创建对应scope的content-addressed bytes；缺失、symlink、extra/tamper或只引用临时文件均失败。

### 7.6 vNext semantic 与 acceptance receipts

单独执行时，`tools/check_vnext_semantics.py` 默认覆盖 `outputs/semantic_audit_receipt.json`，`tools/check_no_company_literals.py` 默认覆盖 `outputs/scalability_audit.csv`。acceptance 不复用这两个可变 root artifact：它为每次执行创建 `outputs/acceptance_receipts/recorded_gate_runs/<run-id>/`，通过显式 `--output` 生成且只接受 `semantic_audit_receipt.json`、`scalability_audit.csv` 两个 exact artifacts，并在 `outputs/acceptance_receipts/<receipt_id>.json` 记录各自仓库内路径与 SHA-256。缺文件、多文件或 hash 漂移均不能 PASS；receipt 自身不进入被它记录的 artifact hash 集合。

`--scope recorded` 在上述 process-tree sandbox 下运行，并校验 active pointer/root mirrors/provenance sidecar 前后不变；R4 只运行并发快速集、semantic/scalability 与 capability alignment，最高只能返回 `PASSED_FAST_LOCAL_ONLY`。receipt 顶层 `authority_binding` 绑定 clean source commit/tree/file count，以及 baseline、Decision Register、FSD、immutable R2、legacy inventory、exact R3 Addendum、release plan 和 semantic runtime 的完整 Requirement hash map；`runtime_bindings`以portable token和binary SHA-256绑定实际解释器/sandbox，嵌套command与artifact reference也不能泄漏host-local绝对路径。recorded gates 后必须重读并 exact 相等。`--scope full` 仍会从 repo-owned artifact reference 重新打开 gate files并重算SHA-256，且要求formal evidence exact回绑同一authority；caller自报路径、旧receipt或dirty/drift source都不能PASS。

`--scope full`未带`--execute-live`返回`LIVE_EXECUTION_NOT_AUTHORIZED`；带授权后先校验effective APPROVED D-01、`DEEPSEEK_API_KEY`、`SEC_CONTACT_EMAIL`、clean source closure与qualification receipts，缺项时不启动Cutover。前提齐全后，runner执行live Cutover；Cutover先运行固定SEC Stage00/01/02/03/05并保存command/ledger-tail/inventory receipt，再将verified legacy A导入为首次链的predecessor、提交formal B，并对new publication、rollback A、restore B各只运行一次`tools/vnext_terminal_cycle.py`。每次结构化结果必须是五项gate exact set、绑定expected publication/pointer/root authority与snapshot file hash，并证明AI/SEC/repair/report authoritative write均为0。final full binding通过`formal_receipts.sec_acquisition`机械绑定该receipt的path、bytes、SHA-256、ID、type/status，并同时绑定exact Requirement、attempts、Runs、Batch、pointer、mirrors、migration/fault/rollback/restore与snapshot。只有最终状态`PASSED`且进程返回0才是full acceptance；NOT_RUN永远不能计为PASS。

## 8. 按变更类型选择测试

| 变更类型 | 最低证据 | 追加证据 |
|---|---|---|
| 纯工作流文档 | `python3 tools/check_capability_contract_alignment.py`、JSON 解析与 `git diff --check` | 只有文档声明引用了代码行为时，运行相关快速回归 |
| 普通 Python 逻辑 | 快速回归 | scalability gate；涉及指标/验证时再跑 Golden 与 repair gate |
| 公司、CIK、profile 或 extractor 配置 | R4 快速回归、scalability gate | 真实运营变更才按 SOP 执行受影响阶段；隔离 checkout/Golden/repair 不属于 R4 测试 |
| parser、期间、证据或 CSV schema | R4 快速回归 + 静态结构检查 | 真实运营变更才按 SOP 执行阶段；完整场景、Golden、repair 与产物 diff 不属于 R4 测试 |
| validation / report verdict / provenance | R4 快速回归 + source policy JSON/SOP authority alignment | 实际发布才运行阶段 11/12 与 snapshot checker；它们不是 R4 final acceptance 测试 |
| SEC HTTP 客户端或 URL | 快速回归中的本地 persistence failure/path、read-timeout、symlink 与 request-log exact-set 测试 | 有效身份下的 live smoke 与 retry/backoff mock，再按影响范围跑场景 |
| 仅报告文案 | 生成器相关检查，不能手改生成报告替代代码 | 若运行阶段 11，必须随后运行阶段 12 和 snapshot checker |
| vNext Requirement/Spec/Reader/Review/Calculator/Publication | R4 快速回归、semantic/scalability gate、capability JSON/anchor 结构检查 | 第二真实布局、holdout、live 三轮、staging/Cutover/rollback 是实际运营证据，不属于 R4 测试 |

纯文档变更不强制重跑联网阶段 00-11；不得为了“全绿”无谓覆盖已审计的 evidence 与 outputs。

## 9. 推荐执行顺序

### 9.1 普通代码改动

1. 运行 `python3 tools/run_fast_tests.py --jobs 4`。
2. 运行受影响的静态结构检查。
3. 检查 `git status`，确认没有引入非预期 artifact。

### 9.2 数据采集、阶段 handoff 或 schema 改动

1. 这不是 R4 测试路径。仅在获准执行真实数据运营时，创建受控 candidate 数据根，并通过`sec_pipeline.py --workspace-dir <absolute-isolated-root> <stage>`显式传入同一数据根；不得把legacy Stage04/09/11指向源码repository root或active publication root。
2. 确认有效 SEC 身份配置与目标 scope。
3. 按 `README_RUN.md` 执行完整阶段。
4. 显式执行阶段 12。
5. 运行 snapshot checker。
6. 核对 metrics/evidence/coverage/report、请求日志与 artifact diff。

### 9.3 纯工作流文档同步

1. 验证 `capability_contract.json` 是 UTF-8 合法 JSON。
2. 运行 `python3 tools/check_capability_contract_alignment.py`；PR 场景再以实际 base 运行 `python3 tools/check_capability_contract_alignment.py --base-ref <base>`，机械检查 HEAD regular-file/blob 与工作树 bytes 一致性、anchor、必填 metadata、test symbol、tombstone 历史，以及 base/HEAD request row 的严格行形状和有序前缀。
3. 运行与所引用行为相关的快速回归。
4. 运行固定上游对应的 workflow docs 机械检查。
5. 记录机械检查只证明最终文件状态，不证明分析、审计或测试历史。

### 9.4 vNext recorded / formal Cutover 改动

1. 先运行 `python3 tools/run_fast_tests.py --jobs 4`。Requirement transition还必须运行Issue #28完整tamper/identity suite、Issue #15 authority regressions和Issue #28 historical read-back integration；后者完整重放active R3→exact R2/R1，不能塞回30秒fast tier。不得把全量 `tests/vnext/`、Python 3.9 双跑或无关长串行套件扩大为必跑项。
2. 在 commit 后运行 `python3 tools/check_capability_contract_alignment.py`；工作树未提交时 checker 按设计拒绝 HEAD/worktree bytes 不一致，必须如实记录，不能把 JSON parse 成功替代 alignment。
3. 运行 `python3 tools/run_acceptance.py --scope recorded`，保留 `PASSED_FAST_LOCAL_ONLY` receipt ID 与路径；它只封存 R4 快速本地证据。
4. 第二真实布局、production freeze、holdout、live 三轮、十公司 staging、Cutover、rollback/restore 与 `--scope full --execute-live` 仍是外部实际运营/发布门，不能由本测试流程制造、替代或宣称已通过。

## 10. 失败定位

- unittest：从失败 test method 回到对应 helper 与 fixture；不要用改 expected 的方式消除真实回归。
- Golden：查看 `outputs/golden_results.csv` 的 expected、actual、evidence path 与 notes。
- Repair：先读 `outputs/validation_run_manifest.json`，只打开 `refreshed_artifacts` 中的 validation/audit 文件；再查看 `outputs/repair_validation_results.csv` 的 `check_id`、status 与 details。
- Snapshot：运行 `python3 tools/check_validation_snapshot.py`，先区分 source policy schema/角色或 SOP authority mismatch、missing/unsafe sidecar、source dirty/tree/file-count mismatch、manifest identity mismatch 与具体 artifact SHA-256/size mismatch。
- 指标/证据不一致：先核对 `metrics_matrix.csv` 是否恰好包含 registry/profile/applicability contract 推导的 unique `(company, metric_id)` set，再与 `metric_evidence.csv` join；8-K 指标还要从 request ledger→submissions bytes→inventory→raw filing bytes→events→metric/component evidence 顺向核对。
- coverage：先核对 `coverage_matrix.csv` 的 unique key set 是否与 metrics matrix 完全一致，再检查 status、has_evidence、needs_review 与 reason。
- live 请求：在阶段顺序运行前提下，先核对 `evidence/requests_log_manifest.json` 的整表 row count/hash、Git HEAD/base 有序前缀、下游 locator 与已存 sidecar 反向覆盖，再检查 `evidence/requests_log.csv` 的 URL、status、User-Agent、retry_attempt、error，以及 body/header locator 与 `content_sha256`；完整性不一致是 FAIL，历史 bytes mismatch 只能是 NOT_EVALUATED。同一 repository 的 log publication 在 cooperating threads / POSIX processes 间串行化，但限速仍是 per-client，且不承诺网络文件系统锁语义。
- light 包：先确认 marker、manifest mode/result、显式 source singleton 与缺失材料，禁止把 skipped、NOT_EVALUATED 或 `LIGHT_PACKAGE_NO_GIT` 当作 full PASS。

## 11. 新增或修改测试

- 行为性 Bug 必须先有可复现的最小回归。
- 只有跨阶段累计状态、阶段间 artifact 或固定顺序才能暴露的问题，必须增加 scenario 级回归；单 helper 测试不能替代。
- 测试新增或职责改变时更新本文件的覆盖与 fixture 简介。
- 不为薄 wrapper 重复写同构测试，不用正则统计源码中的指标/检查数量，不自动测试教学文案风格。

## 12. 已知高价值缺口

- `validation_package_mode()` 的 `FULL_VALIDATION` shape 缺少临时工作区单元测试。
- mock transport 已覆盖精确官方 origin、禁用自动 redirect、response-read timeout、请求前 working/root/namespace alias preflight，以及响应后动态 snapshot/persistence failure observation；尚未覆盖 User-Agent 与完整 retry/backoff 矩阵。
- immutable request snapshot 与 validation provenance sidecar 都是仓库内完整性机制，不是外部签名、透明日志或针对恶意同 UID 进程的 WORM；能同时修改全部文件并重签的人仍在本地信任边界内。
- Git workspace 回归证明检查时已存在的 gitdir/commondir lexical path alias 会被拒绝；guard 与后续 Git CLI 不是原子系统调用，尚未覆盖恶意同 UID 进程在两者之间主动切换 namespace 的 TOCTOU。
- 尚无使用录制 SEC fixture、临时工作区贯穿阶段 00-12 artifact 契约的离线 scenario test。
- lodging已具备Marriott FY2024 materially different SECOND_LAYOUT、production freeze后的Marriott FY2023 HOLDOUT和Marriott FY2025三个FRESH ordinal的合格真实bytes/receipts；每个qualification terminal均绑定有效D-06 SYSTEM `APPROVE`、全量`PUBLISHED` Result、`PASSED` validation及独立provider usage。该family证据不外推到financial或text。
- D-01 已由R5形成唯一effective DeepSeek决定，D-06使HUMAN可选；lodging的三轮remote fresh stability已完成，financial/text仍无相应qualification闭包。
- Issue #15 R1/R2/R3已在正式root形成R1历史、R2 predecessor和R3 successor；`tests/vnext/test_zero_ai_release.py`重验R1/R2 predecessor chain，`tests/vnext/test_ratchet_release.py`重验R3的十个qualification terminals、20-coordinate Batch、327-row key set、portable closure与tamper负例。当前active/read-back为R3且previous=R2；这只证明24指标partial ratchet，不能写成financial/text完成、39指标最终Cutover或full acceptance。
- vNext release input plan会从通过manifest验证的ledger选择latest verified request attempt并绑定locator class；recorded可保留唯一且exact验证path/hash/headers/size的legacy working locator，portable closure必须保存其tier/class和bytes，formal live只允许immutable attempt并拒绝legacy class。SourceReference 会重新校验 exact SEC origin、portable locator 与 raw/header hash，freeze 也会从 RawBlob bytes 重建 table-grid；recorded publication 从 verified Batch 的实际消费路径派生 SourceReference/attempt exact set，先验证 request-ledger 整表 manifest，再绑定截至最后一个已用 row 的最小有序前缀。该适配器尚未经过真实十公司 full staging，scoped recorded fixture 不能替代 full 闭包证明。
- vNext freeze 负例必须覆盖 Candidate 缺成功 attempt/response binding、自报 PASS Evidence 与 cell/constraint 重放不一致、ReviewUnit required claims 脱离仓库 compiled Spec、Observation provenance 字段脱离 SourceReference，以及 MetricResult status/reason/value 脱离 Trace `result_contract_hash`；只验证各对象能自哈希不算通过。
- vNext Run mutation primitive 当前按单 Run 单写者使用；publication commit 已有 POSIX lock/CAS 并发回归，但不能把它外推为 Run append/review/freeze 的跨进程编排证明。

## Metrics reference 参考表专项检查

Issue #44 的 `catalog/reference/` 参考表有独立、不依赖 fast suite 的检查；CI workflow `.github/workflows/metrics-reference.yml` 在每个 pull request 上执行下面两条命令，不做路径过滤，也不替代或缩减 vNext fast suite。

```bash
python3 tools/generate_metrics_reference.py --check
python3 -m unittest tests.test_metrics_reference -v
```

- `--check` 只读：核对 `source_selection.json` 声明的 41 个输入的摘要（数据/文档整文件 sha256；三个代码引用目标只对 `ast` 定位的被引用顶层符号块取摘要，含装饰器；重复绑定明确拒绝），再在内存中生成并与 `catalog/reference/generated/` 逐字节比较；输入内容变化报 `SOURCE_DRIFT`，须显式运行 `--refresh-source-digests` 后重新生成并审阅差异。符号块摘要不覆盖传递依赖或运行行为。
- `tests/test_metrics_reference.py`（52 项）覆盖：商业银行 B06 按所选 R5 定义的 `bank_scope` 为 CONDITIONAL（独立读取 `config/r5_b06_structured_v1.json` 与 `docs/evidence/r5_b06_scope/debt_scope_relationships.json`）且 NOT_APPLICABLE 行的 basis 只含定义层来源；把不完整证据编码为 NOT_APPLICABLE、或 NOT_APPLICABLE basis 引用授权状态均被拒绝；39 个 ID 与 10 个基线 SIC 范围的 390 行完整唯一网格；定义表 `applicable_sic_ranges` 由映射表独立重算；B03 复用 B01、有序 fallback、1% cross-check 与四项范围/单位 guard；酒店 KPI 仅对 7010–7019 适用及其 required claims/单位；事件与文字指标不伪造 tag/算式；D04 的参考实现（legacy 关键词）与目标路线（auditor_fact_v1 + text 回退，取自 `config/source_strategy_fallback_representation.json`）分开且不出现 AuditorName；每条记录的 primary path/sha256/member 与实际解析文件一致；版本选择按 active R3 / R4 离线计划 / R5 政策 / 表格合同 / 文字定义的显式绑定；确定性公式模板与 `scripts/vnext/zero_ai_r2.py::_formula_value` 数值一致；只含声明输入的干净临时副本可逐字节复现；反例包括来源漂移、缺失摘要、篡改生成文件、缺失/多余/重复规则、DEFAULT 顺序、结构性不适用被标为适用、未知 trait、SIC 范围重叠、未选择版本、错误 metric_id、B06 偏离 R5 政策、历史 Spec 角色作 primary、变体角色错误、deterministic/event/text 跨类别或伪装内容引用、回退表示权威未绑定注册表、代码引用符号/字面量缺失、未知状态、`--check` 零写入，以及被引用符号块的边界（无关新增不漂移；函数体修改、新增装饰器、顶格注释后的函数体修改必须漂移；重复定义与直接重绑定必须拒绝）。
- 该测试只读取仓库文件并在临时目录复制声明输入；不写 `outputs/`、active 指针或任何运行根，不调用 git，不联网，不 import PR #43 代码。

## 年度连续更新

短测试：`python3 -m unittest -v tests.vnext.test_annual_continuity`；新增两项年度进度回归与该模块列入tools/run_fast_tests.py。完整真实材料/新进程流程另在checkout外运行，必须保护实际active、14兼容副本、原候选、旧包和原请求账；所有工具显式指定输出，禁用默认根审计副本写入。保存响应回放与模拟GitHub/provider边界不得算作新provider成功。独立review、固定实现、真实阶段许可通过前禁止业务请求。

连续更新完整材料入口：`CONTINUITY_REHEARSAL_ROOT=<新的外部目录> CONTINUITY_MATERIAL_AUDIT=<独立原材料索引> CONTINUITY_PRIOR_STAGE_BINDING=<原关闭阶段stage-binding.json> python3 -m unittest tests.vnext.test_annual_continuity_rehearsal -v`。仅GitHub/HTTP I/O和既有文件替换/原生切换故障点注入测试行为，原生验证器不mock；回放与新provider执行分别记账。覆盖真实当前起点（无历史参数）、两轮接续、成功引用中断、指针提交后恢复、B01成功/B10失败和禁止重抽。历史fast数据根复用原冻结receipt，不覆盖真实发布镜像。

PR41续验：当前许可为2/2/0，旧关闭阶段1/1/0经原内容身份重验，合计上限3/3/0。完整材料回放只在外部HTTP边界派生model/id外壳，原assistant内容保持；故意失败分支另外替换测试content，分别保存原始与派生SHA，不声称新provider执行。最新终态与独立审阅见`docs/evidence/annual_update_continuity/continuation/README.md`。

分组提示增量：`python3 -m unittest tests.vnext.test_annual_group_prompt -v`进入fast。完整保存材料下可定向运行`AnnualContinuityRehearsalTest.test_prompt_native_candidate_and_saved_snapshot`，使用最新关闭阶段的`CONTINUITY_PRIOR_STAGE_BINDING`；只在HTTP外部边界回放原正确assistant内容，并在既有success-reference文件替换点停止后续发布，验证新任务身份的原生候选和封存snapshot重放。它不替代新provider执行；既有完整发布故障套件未变部分按原证据复用。

## R5 B06结构化主路径

短测试：`python3 -m unittest tests.vnext.test_r5_b06 -v`，已列fast白名单。覆盖总额不加adder、同族/跨族、lease-only与noncurrent、冲突和独立债务、零/负权益、单位/时点/主体/来源、工业范围及生产权限拒绝。完整材料：`python3 tools/vnext_r5_b06.py prepare --candidate-root <新外部目录> --output-json <新外部JSON>`，随后同CLI read与重复prepare；OS级禁网和正式根只读，独立记录执行、包与代码身份。原PR41短测试读取冻结提示/模型，同时明确旧执行权限对R5改动失效，不修改历史v8绑定来制造可执行性。

完整候选正反例：`R5_B06_CANDIDATE_ROOT=<已生成完整候选目录> python3 -m unittest tests.vnext.test_r5_b06_material -v`。缺环境直接报错，不以SKIP满足验收。覆盖完整读、旧B06生产函数抛错时新原生结果仍可生成、删除范围来源后重算Run仍拒绝、包内来源自洽但独立Git原件身份不同时拒绝、生产写权限拒绝及重复prepare。临时反例仅写外部测试目录；不注入core validator成功。

PR42来源修订短回归：`python3 -m unittest tests.vnext.test_r5_b06_followup -v`，进入同一fast白名单。覆盖两项缺日期漏判、无效身份/日期、非自然年度、相关历史分片、两份完整原文修订判断及重hash后财务事实/Item8反例、两种真实账面对账、同基础CF/XML冲突与原冲突在无证明时仍拒绝。旧v1的读取由其Spec语义选择，不能重开旧v1执行。完整包仍用既有R5 material测试与CLI冷读；未变的PR41模型及长演练不重跑。

### B06统一债务集合

`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_r5_b06_scope -v`：11项短测试接入fast，覆盖真实来源组成/原5坐标、Pfizer/JPM/Ford完整性拒绝、精度区间、重复/漏项、未知原件/资产冒充以及嵌套具名表达式。旧9项/10项模块显式读取保留的v1/v2 Spec，不修改旧期望。`R5_B06_CANDIDATE_ROOT=<外部目录> PYTHONPATH=scripts python3 -m unittest tests.vnext.test_r5_b06_material -v`用于实际完整候选，需干净检出；运行中不要编辑文档，所有输出显式置于checkout外。

### B06 新来源定向验证

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_b06_new_source -v`
进入fast白名单。测试以PR42材料及明确TEST_ONLY语义变造为输入，真实来源哈希重新
建立；验证原文否定/分列冲突、计算白名单外融资、BS新增行、资产/付款冒充、
完整性伪造、真正自洽但不可信的模拟获取账本及成组金额动态重算。
原本当前Southwest另有供应商融资性质缺口，不以测试修复抹去；派生零余额正例仅
测试支持模式。固定历史两材料的正常Run、冷重放、重入和历史包兼容另作材料层
验收，保存首次失败与修后结果；完整候选prepare与生产发布不属于本轮执行。

真实新来源材料层：`B06_NEW_SOURCE_MATERIAL_ROOT=<本轮外部根> PYTHONPATH=scripts python3 -m unittest tests.vnext.test_b06_new_source_material -v`，6项测试实际执行，缺材料报错。包括两个正常FROZEN Run、冷读来源准入、旧入口抛错、零调用重入和重绑定伪验证记录拒绝。便携包恢复后用新进程只读CLI，额外证明没有Git目录仍可重验checkpoint与原生结果。

CI首次将13项新测试作为一个入口时触发既有30秒入口上限。已将同样13项分别登记为入口，不提高超时、不删测试或放宽断言。当前fast共60入口，实际测试数仍182；首次CI失败保留。


## 普通治理与文本原生接线

`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_replay tests.vnext.test_record_schemas tests.vnext.test_text_results`在本次接线后70项通过；随后增加文本Projector原文/字节定位及禁止倍率反例。历史Projector fixture通过既有`copy_foundation_receipts`取回原模型配置，执行当前验证器；不改历史authority。`tests.vnext.test_normal_source_authority`检验无Git导入、caller基线/账本/原件/headers/主体变造；`tests.vnext.test_normal_governance_input`及`test_governance_signals`/`test_governance_compensation_table`检验自动输入与薪酬/审计师语义。

本次D01/C03/C04/B06真实OPEN整图检查及首次失败分别保存；不把OPEN重放、70项回归或fast当最终冻结、完整包或生产PASS。完整金融组件55项另行运行（约153秒），不能塞入30秒单case fast上限。
<!-- capability-anchor: CAPABILITY.normal_saved_source_admission -->
<!-- capability-anchor: CAPABILITY.normal_governance_input -->
<!-- capability-anchor: CAPABILITY.native_text_source_excerpts -->


## 普通保存来源候选批次

当前GitHub CI包含两层测试和独立原生Run检查：`python3 tools/run_fast_tests_v2.py --suite fast --jobs 2`检查95个短测试入口，每项30秒；`--suite source-material --jobs 2`检查38个完整来源材料入口，每项240秒，整个job上限20分钟。先前124个入口的并集全部保留，并新增九个普通来源/输入材料套件；没有删除断言。旧`tools/run_fast_tests.py`保持原字节，历史acceptance入口不改。单次全文LCR已在托管机超过30秒，故不再把全文材料误列为短测试；原失败日志保留，材料通过不能改称原30秒测试已通过。两层本地分别通过，不替代实际GitHub或完整390验收。

<!-- capability-anchor: CAPABILITY.ordinary_zero_ai_native_components -->
<!-- capability-anchor: CAPABILITY.ordinary_companyfacts_native_components -->

普通零AI来源组件的材料测试：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_normal_companyfacts_results tests.vnext.test_normal_zero_ai_results
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts /usr/bin/python3 -m unittest tests.vnext.test_fiscal_year_labels tests.vnext.test_going_concern_source tests.vnext.test_regulatory_investigation_candidates
```

前一命令17项通过，覆盖十公司原件/110目录坐标、B01/C01原20坐标、新增B03/五事件、独立源金额核算、JSON和无Git数据根重建、篡改拒绝。后一命令Python3.9的48项通过。测试拒绝网络和旧矩阵答案，不创建Run或freeze，不写正式结果；完整材料另存源码外。后继运行命令和原失败证据见`docs/evidence/issue28_continuous/successor-source-components/`，业务范围见`docs/normal_source_components.md`。

短边界覆盖`test_normal_run_authority`、`test_normal_candidate_cli`及最小文本输入。V13公共入口的独立实际验收包含两份合法OPEN图和14个规格/来源/期间负例，详见`docs/evidence/issue28_continuous/successor-open-fb76/`；其信用只属于受审草案，不覆盖后续CI清单或D02改动。
<!-- capability-anchor: CAPABILITY.normal_current_run_admission -->

完整材料测试会真实冻结当前安装规则，应在草案实现和输入文件稳定后执行：

```bash
NORMAL_RUN_MATERIAL_ROOT=/absolute/new/open-material PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_run_material
NORMAL_NATIVE_MATERIAL_ROOT=/absolute/new/native-material PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_native_material
PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_projection tests.vnext.test_normal_text_projection_v2
PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_numeric_projection
```

第一条只验证两个真实OPEN基线及规格/来源/期间文件负例，禁止冻结。第二、三条覆盖真实Run/冻结/新进程冷读和文本CSV；第四条目前验证实际数值记录的展示，不授FROZEN信用。它们不塞进30秒fast入口，不替代390坐标或正式发布。V12旧材料见`frozen-candidates/`；本轮V13最终冻结材料仍在执行准备中，不能把测试文件存在写成已通过。
<!-- capability-anchor: CAPABILITY.normal_saved_candidate_batch -->

<!-- capability-anchor: CAPABILITY.ordinary_accession_native_components -->

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_normal_accession_results`及同命令改用`/usr/bin/python3`分别6项通过（27.533s、44.509s）。覆盖30原生坐标、实际3数值与27结构性状态、单位ID改名/错误单位、主体/维度差别、实体标识方案、错误数字分组和JSON/异目录变更拒绝。十公司材料及JPM/Salesforce两个新进程无Git数据根冷读见`docs/evidence/issue28_continuous/ordinary-accession-components/`。仍无Run、freeze或生产写入。

<!-- capability-anchor: CAPABILITY.ordinary_integrated_run_graph -->

V14/issue_28_v13草案的实际Run材料使用全新外部目录，默认不冻结：

```bash
NORMAL_V14_MATERIAL_ROOT=/absolute/new/open-material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_run_v3_material
ORDINARY_PROJECTION_MATERIAL_ROOT=/absolute/completed/cli-batch PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_projection_material
```

普通修订与债务来源组件另有 `test_annual_amendment_scope`、`test_b06_combined_borrowings`、`test_b06_financing_inventory`，均在240秒来源材料层登记。真实原件、原说明中的错误用途/期间/附件、金额/单位/命名空间冲突、原生事实与显示金额及声明舍入边界均有正反例；来源清单不推导缺失零值，不产生完整B06或生产信用。

逐笔债券与明确无融资租赁的新路线由`test_b06_note_carrying`核对完整原件及细分维度漏检反例；`test_note_debt_run_material`读取显式新建的Enphase/Marriott B06普通批次，复核原生Run及公共行，并拒绝重新计算并重签的虚假债务图和旧规格替换。后者通过`NOTE_DEBT_NATIVE_BATCH`和`NOTE_DEBT_ATTACK_ROOT`指定隔离目录，在current-instant CI job执行；命令见`docs/note_debt_source.md`。无新SEC/provider调用和正式发布。

上述原生批次现在加入Macy’s，共三个实际Run与四个伪造重算/旧规格替换反例；Marriott检查还禁止进入新债务解析器，验证原非正权益保护的先后顺序。`test_b06_bond_leases`在来源层核对债券/租赁/供应商及独立清单，涵盖细分额外借款、无金额的其他借款、跨文件金额、条款/引用变更、未来购买承诺及真实比较期的非零当前借款。比较期检查不声称已取得过去主文档。

已完成修复批次的公共行可用 `ORDINARY_REPAIR_MANIFEST=/absolute/repair-batches.json PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_ordinary_repairs_material` 重建。清单包含 `amendment`、`denominator`、`selection` 三个实际CLI批次绝对路径；检查14个修订修复坐标、四个NOT_MEANINGFUL空值及证据、JPM具体来源失败/正向选择，逐字节比较实际CSV。该命令不新建Run、不冻结、不写正式结果；失败原批次及修后批次分别保存。

材料包含真实B03依赖图、Salesforce时点/Macy’s跨年时点、文本审阅、事件Claim及文件负例。重签假收入图使用真实Calculator重新生成完整记录，再从原始来源拒绝；删依赖/事件事实、改规格/来源/财年、删审阅和改输入主指标分别验证。第一次删B01依赖结果被误接受、文本审阅顺序失败、事件Claim/来源角色失败和测试异常分类错误均保留，不能拿后续PASS改写首次结果。旧V13 D01/C03冻结数据根用新共享代码冷读仍通过。

普通来源解释的原始引语/字符反例、财年v2与22路线测试仍分开执行；生成的20项普通Spec文件必须重编译出完全相同的既有目录语义。V14尚未冻结，不应运行旧的V13新建材料命令来复制不匹配的当前共享执行字节；旧冻结读取仍按其原数据根进行。

GitHub另有独立的`vNext ordinary native Runs` job，在Runner临时目录运行上述V14真实OPEN材料及文件负例，30分钟上限。它不冻结或修改正式输出，也不替代最终390验收。

### D04离线解释输入与响应协议

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_r6_semantic_review` 检查真实来源的完整输入、嵌套XML重建、请求/单元缺漏、错误引文/索引/类型、主体/时间分类及冲突保留，纳入source-material层。测试响应由测试程序构造，不是provider执行。十公司输入组织不证明模型语义理解正确，也不创建D04 Run。具体入口和界限见`docs/r6_interpretation_protocol.md`。

### 普通更新的来源发现

来源更新测试会话用 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_source_session` 检查，纳入fast层。网络和HTTP入口均被测试禁用；正例通过现有SEC持久化/追加及基础年度读取，负例覆盖伪造追加/终态、前缀/原件变化、未知结果、失败后停止、测试额度及路径别名。输入比较区分内容变化与仅请求身份变化。独立材料使用同一原文的新测试记录调用原生计算器；不创建Run、不授真实来源信用。

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_source_requirements` 已加入source-material层。实际Marriott/Salesforce/JPM材料覆盖可用来源、最终失败GET和历史清单冲突；外部副本删除新主文件仍能发现其地址，删除/篡改目录不会宣布子文件齐备；后续年报元数据的纯解析不授予新来源信用。十公司实际CLI命令为 `python3 tools/vnext_normal_update.py --discover-sources --output /absolute/new-external-directory/source-requirements.json`；有缺口返回2并保留所有公司，不执行指标或请求。说明见`docs/normal_source_discovery.md`。

C04正常保存来源更新用 `python3 tools/vnext_normal_update.py --process --data-root /absolute/saved-source-root --state-root /absolute/persistent-update-root --company marriott_international --metric C04`。此入口明确选四形式后继并记录到`metrics/C04-registration-v3`，旧普通控制器与共享`normal_run_v3`默认行为不改。`tests.vnext.test_c04_update_cycle.C04UpdateCycleMaterialTest`已追加在source-material选择器列表末尾，核对Marriott原件正向Run和相同输入不重复建Run。`docs/evidence/issue28_continuous/c04-normal-update-20260926/`另以两份已经保存、内容不同的真实SEC清单录制更新：新输入形成第二个版本，旧版可读；失败、指针中断与资料不足的Paramount状态分别保留。该材料禁网且不发真实GET，不能替代新财报实际发现/获取、十公司C04完整验收或正式生产。

有限来源刷新入口 `python3 tools/vnext_ordinary_refresh.py --company marriott_international --metric C04 --state-root /absolute/persistent-update-root --max-sec-requests 0 --max-provider-requests 0 --output /absolute/new-report.json` 现在显式选择同一C04后继；共享`ordinary_refresh_cycle.refresh_and_process`默认仍使用原路线。`tests.vnext.test_c04_refresh_cycle.C04RefreshCycleMaterialTest`以两份真实保存的Marriott清单及Company Facts逐次录制刷新，经来源发现、获取会话、后继Run、版本保留及旧版重读，全部禁网、真实调用0。旧实际来源根里的三项历史处理副本不会为C04原地改写；新Run安装当前规则，不相关规则漂移仍拒绝，见`tests.vnext.test_c04_source_only_install`。只刷新清单而没有刷新所需Company Facts，或本次完全没有刷新元数据时，协调器仍可报告整体`UPDATES_INCOMPLETE`；不能把C04候选存在误写成来源已是最新。当前绑定、原账本零调用候选及独立冷读见`docs/evidence/issue28_continuous/c04-normal-refresh-20260926/`，不等于实际新财报获取或生产调度。

该两版录制selector在`2f3a36da`的CI达到单项240秒上限，其余12个主作业成功；`c04-source-ci-runtime-20260927/`记录了只移除测试内额外旧Run重放后的180.047秒本地通过。两版来源/Result及前驱断言保留，旧版的独立冷读证据另存；最终仍须以修后head的CI终态为准。

后继范围回修见`docs/evidence/issue28_continuous/c04-normal-refresh-scope-repair-20260927/`：公开CLI的B01-only选择仍走原控制器；C04来源副本兼容只允许单独C04请求用于实际获取。旧处理副本存在时混合B01+C04调用不得借C04标记发任何SEC请求，现有保存来源的C04可继续形成候选，B01标为当前处理输入未满足，整体仍未完成；这不是旧根已自动更新所有普通指标。

单次有限SEC上限不足时，C04可用 `tools/vnext_ordinary_refresh.py --company marriott_international --metric C04 --state-root /absolute/same-update-root --max-sec-requests 1 --max-provider-requests 0 --resume-report /absolute/previous-immutable-report.json --output /absolute/new-report.json` 作一次**异常续接**。它重读前次真实账本收据和同一更新历史，再从已验证来源状态重建待刷新集合，逐项比对外部报告；不能靠改报告或重领已取得URL继续。`tests.vnext.test_c04_refresh_resume`在source-material层使用录制来源验证两条不同SEC依赖、篡改与重复报告拒绝。正常运行应为预计来源设置足够的有限上限，此路径不是日常人工指定URL或指标答案，也不扩大发送许可。实际第193槽的待办篡改拒绝和当前正向预检见`docs/evidence/issue28_continuous/c04-refresh-resume-repair-20260927/`；第二条真实GET须另看其结果，离线通过不是实际刷新完成。

### 普通主体接续与期末余额

来源规则与十公司原生组件用 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_instant_balance_amendment tests.vnext.test_normal_companyfacts_results` 验证；两模块均在source-material层。实际Part III修订和链接更正保留不同证明，覆盖额外用途、错原报告日、正文更正/余额、已发生重述、封面标志、引语和新增原生财务事实。缺少修订原件必须拒绝源重放。

实际Run先由 `tools/vnext_normal_candidate.py --company paramount_skydance_paramount_global --metric B08 --metric B09 --output-root /absolute/new/instant-runs` 创建，再设置 `INSTANT_BALANCE_NATIVE_BATCH`、`INSTANT_BALANCE_ATTACK_ROOT` 两个外部目录执行 `tests.vnext.test_instant_balance_run_material`。核对原生时点/主体及公共行，并以真实Calculator构造90亿美元假现金图、删除修订原件，检查重放拒绝。CI独立的current-instant native任务包含这两个步骤，各原生命令和20分钟任务上限不变。4e02565首次把全部原生检查串在一个任务内，在最后一步达到20分钟上限而被取消，原始记录见`docs/evidence/issue28_continuous/instant-ci-timeout/`；这不是反例通过。拆分仅调整独立检查的调度，不把组件或测试准备说成Run执行通过。

### 普通B10/B11的确定性来源与原生记录

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_lodging_table_source`使用三年原件核对同范围/同年列、跨页说明和地域脚注，拒绝错误范围、表外标签、竞争表、重复全球行、季度/货币限定和引用说明。它在source-material层登记，保留原料和首次失败，不调用模型、不改旧AI规格。

实际原生验收先运行 `python3 tools/vnext_normal_candidate.py --company marriott_international --company southwest_airlines --metric B10 --metric B11 --output-root /absolute/new/lodging-runs`，再设置 `LODGING_NATIVE_BATCH` 为该目录、`LODGING_ATTACK_ROOT` 为另一全新外部目录，运行 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.vnext.test_lodging_run_material`。检查无AI响应/假review的原生记录，拒绝重签错误值、删除网格及旧AI Spec替换。GitHub native-runs job包含这两个实际步骤；本地另有十公司20坐标完整范围检查，不能把它扩称390全验收。

<!-- capability-anchor: CAPABILITY.ordinary_b06_current_input -->

`test_b06_current_input`核对真实修订、原政策范围不变、债务/权益更正、额外原生事实、输入门先于权益保护及合法WITHHELD路径；`test_b06_current_input_material`以显式新目录创建真实Paramount B06 Run及公共行，并拒绝删掉修订原件或重签删除检查的输入。历史解析WITHHELD证据不改写。后者在普通native CI job执行，仍无SEC/provider调用、冻结或生产写入。

<!-- capability-anchor: CAPABILITY.ordinary_b06_inclusive_table -->

`test_b06_inclusive_table`使用完整原件检查已含租赁、当前主体/权益、收购日估值、不同计量精度和全部147项潜在融资事实；反例包含错误继任表头、缺租赁、金额冲突、额外票据/借款/附注、错误权益范围、收购值冲突及收入履约维度冒充借款。`test_b06_current_input_material`另用实际Calculator重建重复计租赁及前任金额的错误图，并验证重放拒绝这两图、旧Spec、删修订及自签输入，共五类原生反例。

59fd27b的current-instant CI因合并作业超过20分钟而取消，前三项作业通过，不记为全绿。债务Run与反例现拆为独立`vNext debt native Runs`作业，仍20分钟；来源和ordinary-native总作业上限改为30分钟，单个来源案例的240秒上限不变。所有原测试保留，新范围不代替390最终验收。


<!-- capability-anchor: CAPABILITY.recorded_source_run_admission -->

新增`test_ordinary_source_authority`在fast层核对安装目录登记、冷读、伪造信用/记录、未登记追加及失败/未知终态。`ORDINARY_SOURCE_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_source_run_material`创建五个实际Run（B03含B01依赖，另有B08/B09/B10/B11），比较原文计算值/期间，并验证来源记录缺漏、重签信用、未登记追加、假收入图及缺依赖五类拒绝。网络/HTTP/DNS在材料中禁用，来源新增三份测试请求但财务原文未变，仍无实际SEC信用。

该材料通过独立`vNext recorded source update Runs` CI作业执行，30分钟上限；不替代真正新财报获取/更新、全部路线和390验收。首次B01材料的/tmp别名及首次跨路线酒店内层仍调用旧验证器的失败保留；修后新目录另验，不重签旧失败。复制运行包的无Git冷读单独记录。


<!-- capability-anchor: CAPABILITY.remaining_current_source_adapters -->

`REMAINING_SOURCE_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_remaining_source_run_material`从原来源准备完整依赖，再登记测试请求并创建Marriott六项/JPM六项原生Run与公共行；验证原有数值/期间、SYSTEM文本审阅、B06保护及改金额图/删除审阅拒绝。`REMAINING_SOURCE_COMPANY`可限定其中一家公司；CI以此分两个45分钟作业。已完成材料可改用`REMAINING_SOURCE_EXISTING_ROOT`执行只读重放及独立攻击副本，不重跑创建。测试信用和真实来源获取、39项完成及正式发布分别记录。

本次十二路线创建耗时845.782秒，完整重放/反例314.233秒；新CI按公司拆分，并给每个原生材料作业45分钟总上限，保持全部断言及来源规则不变。

已完成十二路线材料可设置`REMAINING_SOURCE_EXISTING_ROOT`及可选的新`REMAINING_SOURCE_ATTACK_ROOT`重放并检查攻击副本。首次金融反例因传入多余Calculator目标字段而停止；原日志保留，改为精确五字段后12场景及两类反例通过。


<!-- capability-anchor: CAPABILITY.ordinary_update_cycle -->

`ORDINARY_UPDATE_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_update_cycle`使用真实Run及两份原始清单版本验证内容身份、重复请求、失败/恢复、成功终态与引用写入中断、未完成意图、并发、伪造引用、改公共行和相同WITHHELD输入不重复建Run。网络/HTTP/DNS均禁用。新增历史测试请求只能选择受信不可变尝试，相关源会话测试继续在fast层运行。材料不等于实时新财报或完整生产生命周期验证。 同一实际材料增加十项记录反例：最新/更早终态编号与类型、未知终态、错意图/配置、更早意图类型/成功前驱及缺失旧终态；改意图时连带重签终态绑定，以验证实际一致性而非仅哈希失配。最后恢复原件并重验不新建Run。

338bbc8的来源CI中，B06当前输入模块六项测试合计达到240秒而超时，其他七项CI作业成功。当前source-material选择器将这六项按实际方法分别运行，仍保持每项240秒，方法集合与源码逐项核对无遗漏；源码选择器总数由45变为50。旧超时不重写为通过，拆分后的六项单独复验。

<!-- capability-anchor: CAPABILITY.ordinary_update_metric_isolation -->

`ORDINARY_UPDATE_COMPANY_MATERIAL_ROOT=/absolute/new/company-material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_ordinary_update_cycle.OrdinaryCompanyUpdateTest`使用实际Pfizer B01/B06/B08检查独立成功、受限、重复输入、前项输入故障后后项继续、历史期间/当前状态分离、改公共行隔离及旧组历史不静默重置。所有网络入口禁止。


<!-- capability-anchor: CAPABILITY.continuous_call_allowance -->

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_continuous_call_ledger` 检查新累计账本的跨进程互斥、重启累计、额度耗尽、重复请求、缺终态和402/UNKNOWN停止、末记录/目录删除及测试身份篡改。只用带身份的测试材料，模拟计数不充当真实 provider/paid/SEC。加入当前 fast 选择器。

<!-- capability-anchor: CAPABILITY.continuous_semantic_call_wiring -->

`CONTINUOUS_WIRING_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_continuous_semantic_calls` 使用 Enphase 保存原件，走后继授权、工厂、实际请求和 WB-3。socket/DNS/SEC 被拒绝，官方 opener 只返回明确测试 wire，原生 marker 为 MOCK。验证私有出口令牌缺失与请求变造拒绝、未知 usage/费用不归零、父 V14 闭包不变。结果不是语义可行性结论或真实调用；加入 source-material 选择器，仍用原每项240秒限制。

780d9ba CI 暴露当前未冻结 V14 的执行文件绑定漏更新；确切该提交有4个执行文件字节与绑定不同。修复保留e1ac/6341530原快照，只更新当前执行绑定；B13 Spec语法增量另占第5项变化。`NORMAL_V14_MATERIAL_ROOT=/absolute/new/material PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_run_v3_material` 的5个真实基线/10个反例已重验；另用复制运行包独立进程回读B03与Python3.9 D01。新调用测试验证当前父绑定及历史e1ac快照的原闭包分别成立。

<!-- capability-anchor: CAPABILITY.b13_source_and_comparison_draft -->

`PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_capacity_utilization_source.CapacityComparisonTest` 验证80/100、零产量及超过名义产能的比值复用既有Calculator，并拒绝销量/出货/装机/规划量、错主体/单位/期间/产品设施及错误目标口径。`B13_SOURCE_MATERIAL_ROOT=/absolute/new/material PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_capacity_utilization_source.CapacitySourceMaterialTest` 从Ford/Enphase实际保存原文形成来源候选，保留11/5条相关披露和8/0个可能产量线索。测试未将候选数视为语义覆盖，也未将无匹配推成NOT_AVAILABLE_SEC；没有B13原生Run信用。两类分别加入fast/source层。

<!-- capability-anchor: CAPABILITY.ordinary_continuity_policy_terminal -->

`PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_companyfacts_results`覆盖当前10公司×11项源结果、原有正向/来源反例、新主体不可比规则及错误守卫不得留下数值证据。Paramount六项定向CLI为`tools/vnext_normal_candidate.py --company paramount_skydance_paramount_global --metric B02 --metric B04 --metric B05 --metric B07 --metric B08 --metric B09 --output-root <新外部目录>`；前四项NOT_MEANINGFUL，后两项EXACT，全部OPEN及公共行均须形成。`docs/evidence/issue28_continuous/ordinary-continuity-policy/`保存首次通用Run校验拒绝、修后材料、有效重签的虚假数值/无关空输入理由拒绝及复制运行包的Python3.9冷读。无真实调用或正式发布信用。

<!-- capability-anchor: CAPABILITY.continuous_sec_acquisition -->

`SEC_ACQUISITION_MATERIAL_ROOT=/absolute/new/material PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_continuous_sec_acquisition`复制固定原始来源，测试记录成功/503失败、前缀与两种信用隔离、禁止原件重抽/跨公司URL、保留有效来源、导入检查记录变造拒绝，并在单独未登记的隔离目录验证原SecHttpClient的真实HTTP构造和503零重试。随后将选中的新测试请求装入JPM A08原生Run，并在复制的运行包中冷读和重建预览。测试网络全部阻止，不创建真实获取信用。加入source-material层，保持每项240秒限制。

### 普通SEC文档身份与同正文刷新

`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_storage_identity`核对同一不可变请求的物理/URL文件名等价，拒绝不同文档、URL、请求ID和可变旧文件映射。`tests.vnext.test_continuous_sec_acquisition`的完整来源方法使用同正文元数据刷新，实际安装候选并从复制的运行文件冷读；首次漏带旧头文件失败保留。当前快速入口包含文档身份测试。真实13次获取不在这些离线测试中重发；审核与还原命令见ordinary-document-identity材料。

### 普通B06银行和工业范围

`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_special_debt_scope`读取JPM/Ford原HTML/XML，验证融资分项小计及明确非数值限制，并拒绝金额冲突、假会计命名空间、工业列改标及原件未绑定变造。该6项来源测试已加入当前SOURCE_TESTS。`SPECIAL_DEBT_NATIVE_BATCH=<两项原生批次> SPECIAL_DEBT_ATTACK_ROOT=<新外部目录> PYTHONPATH=scripts python3 -m unittest tests.vnext.test_special_debt_run_material`验证原生结果仍WITHHELD，重新签名的完整比值/无披露记录不能替换。普通CLI两项批次的exit2表示预期保留两个缺证状态，不得写成完整B06成功。

文档身份单元测试现包含两个真实持久化的模拟清单（当前/历史），验证仅更换逻辑引用、原准备对象及日志不改；重新签名的虚假发现集合被拒。新增JPM/Salesforce C04原生与Python3.9冷读。此次未改SEC/计数/传输代码，按执行字节差异核对复用bdc41的82.459s SEC材料，未声称该套件本轮重跑；当前工厂仍执行36.843s禁网接线。见ordinary-history-identities的reuse audit及材料索引。

CI的current-instant/debt原生任务在bdc41实际运行到20分钟上限被取消，原日志保留。两项任务上限现为30分钟，仍需完整成功终态；没有改变单个SEC/模型请求的context/resource/重试边界。新head实况不借旧取消结果推定通过。

注册事件范围的来源发现新增3项（含原8项共11项）检查，覆盖主/前身、既有窗口、缺前身清单及错CIK；命令仍为tests.vnext.test_normal_source_requirements。完整SEC材料新增第三笔RECORDED前身头文件获取，只证明出口范围准入，不授事件内容信用；实际断言验证3条记录。首次打印摘要遗留2的旧字面量，原日志/摘要保留，独立重读3条并修正报告为读取实际账本；没有重跑未变执行，仅报告输出修正。材料见ordinary-registered-events。

接续事件完整材料测试：设置REGISTERED_EVENT_NATIVE_BATCH、REGISTERED_EVENT_SOURCE_ROOT及新的REGISTERED_EVENT_ATTACK_ROOT后运行tests.vnext.test_registered_event_run_material。它验证6项原生及窗口，模拟当前主体单独产出结构合法的E02=0，再恢复注册表规则重读，必须因输入绑定不同拒绝；通用两年Run坐标仍须拒绝。该真实来源材料检查本轮在本地显式执行，不能把没有这些材料的CI跳过写成新覆盖。旧normal_zero_ai_results中收入的接续守卫不变；C01在未补原件的仓库源集由未实现转为真实缺源，定向回归分别断言。

128fe33完整SEC材料在CI单项240秒超时，原日志已归档；当前仅tests.vnext.test_continuous_sec_acquisition为480秒，其他SOURCE_TESTS仍240秒，各项实际时限写入JSON。source-material job35分钟，所有选择项/断言保留；未改任何真实请求资源上限。

CURRENT_INCOME_NATIVE_BATCH/CURRENT_INCOME_ATTACK_ROOT指定原生及新反例目录，运行tests.vnext.test_current_income_run_material，验证B01/B03原146天年度守卫与真实观察，重新签名的“短期值当全年”/“前身拼接值”均拒绝。tests.vnext.test_ordinary_income_input的5项检查加入SOURCE_TESTS；收入更正反例通过真实变造HTML并重建修订scope，未以静态关键词命中代替来源绑定。旧normal_zero_ai_results的对应分类方法单独回归，其他路径保持。

2026-09-14语义入口修复还核对实际DeepSeek请求的thinking disabled、stream=false和4096输出上限，以及从每份真实来源单元重建的必评索引集合。原0032/0033/0034终态经CLI零外发重放分别exit0/2/2。真实六次可行性调用及失败、后继提示响应见docs/evidence/issue28_continuous/semantic-live-repair及semantic-focus-repair；101fast PASS80.216s不代替完整语义或390验收。

`tests.vnext.test_r6_regulatory_semantics`覆盖Pfizer原件/原生事实保留、引用/日期/状态/上下文约束及原opener/WB-3；`tests.vnext.test_r6_semantic_verification`只读核对原始LIVE提议，把新调用保持MOCK，检查候选完整集合、篡改与引用范围拒绝。两套已加入source-material；通过不表示模型在新公司的业务语义已正确。

历史控制的`tests.vnext.test_r6_historical_controls`校验元数据选择、错公司/URL/刷新拒绝、原noninline正文及错头文件拒绝；新调用保持RECORDED_TEST_ONLY。`tests.vnext.test_r6_semantic_scope`用实际旧响应作明确recorded回归，保留旧v2失败并检查历史/其他主体不能进入当前目标，加入fast层。真实provider对照与禁网MOCK严格分开记录。

### B13完整输入与D03事实关系增量

短反例：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_capacity_semantic_source.CapacitySemanticSourceTest tests.vnext.test_regulatory_statement_facts.RegulatoryStatementFactsTest -v`。覆盖重签后的来源缺项、关键词未命中仍保留隐藏事实，以及否定、假设、历史/引语、其他主体、与政府行动没有直接关系的诉讼。

完整材料：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_capacity_semantic_source.CapacityCompleteSourceMaterialTest tests.vnext.test_regulatory_statement_facts.RegulatoryStatementSourceMaterialTest -v`，禁网读取Ford/Enphase及JPM已存原件，后者从原文别名定义重建339段并验证响应冲突。两类分别加入当前fast/source-material入口；可选B13_COMPLETE_SOURCE_OUTPUT和D03_STATEMENT_MATERIAL_OUTPUT只写全新外部测试路径。JPM属于已参与修复的回归样本，模拟响应与执行者自查不算真实模型通过、原生或独立审阅。

D03后继的**录制响应字节保存**用`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_d03_recorded_response_store`在source-material层验证：已保存JPM原件与合成响应的原字节、来源和请求身份、未决及录制信用，经独立文件重读；改原响应、把录制信用改签LIVE、不完整包和写入原真实账本均被拒。`D03_RECORDED_PACKET_COPY=/absolute/new/external-root`可保留测试时的有效包供独立进程禁网冷读，证据见`docs/evidence/issue28_continuous/d03-recorded-response-20260927/`。这是离线持久化步骤，不是D03真实请求、原生Result/Run或完整公司结论。
<!-- capability-anchor: CAPABILITY.b13_complete_source_input -->
<!-- capability-anchor: CAPABILITY.regulatory_aggregate_statement_fact -->

B13定向反例另覆盖伪概念命名空间、伪货币命名空间、实物单位和相除单位；完整Ford材料逐条核对13项真实货币额度，保留原单位定义与事实。

### B13 新原生链与来源分组性能

<!-- capability-anchor: CAPABILITY.b13_visible_source_role_guard -->

`tests.vnext.test_capacity_visible_source_roles`覆盖股票额度/债务/治理误标、正确产能计划与产品能力、混合块、无关债务否定以及真实取消/条件计划；包括完整响应级P2回归。`b13-170-source-audit/`仅输出诊断，不改原170或把去重/改标签的数据登记成功。126fast与定向检查分开记录；独审提出P2后的父会话修复仍待独立闭环。

112—114定向验证：`tests.vnext.test_continuous_source_unit_bytes`、`tests.vnext.test_d04_native_assessment`、`tests.vnext.test_capacity_reference_contract`及`tests.vnext.test_native_unit_index`。原114保存响应只作离线回归，混合真实疑虑不因活动类别重叠被排除。紧凑引用测试拒绝错类型编号、越界类别、布尔编号、漏单元及过长理由。`failures-112-114-repair/`保存实际来源禁网接线、输出测量、成功复用与冷读实际结果；不得把录制样本升级真实信用。

`tests.vnext.test_continuous_source_unit_bytes`验证U+037E在NFC JSON中被改写时，`SemanticRequest.validate`在付费申领前拒绝不一致的单元字节/哈希/ID。原Greek字符和普通ASCII合法输入仍通过；原113失败和摘要算法不改；新增反例同时核对无损source/request/HTTP及普通ASCII字节兼容。当前D04实际工厂禁网接线另见d04-remaining-20260922/preflight-current-wiring.log。

<!-- capability-anchor: CAPABILITY.continuous_recovery_110 -->

`tests.vnext.test_continuous_recovery_110`与旧账本测试覆盖无授权停止、指定一次申领、原始文件/计数不变、重启/并发及申领中断、新停止保留、错误终态/摘要/模式/审批来源拒绝。`recovery-110-20260922/offline_wiring.py`用当前Enphase原业务工厂禁网验证402、受限新claim、原生成功及原成功复用，业务摘要必须与真实110相同；只计录制接线，不计真实结果。

`PYTHONPATH=scripts:. python3 -m unittest -q tests.vnext.test_continuous_batch33 tests.vnext.test_continuous_call_ledger tests.vnext.test_continuous_recovery_110`验证新用户授权的服务器评论/原文/组集合绑定、原171停止只在D04首组申领时受限解除、113/114式相同摘要新执行、跨进程单次消费、中断/新402保留停止、旧110兼容及批次前缀冷读。另检查批次首组之前SEC不能插队，之后原总委托SEC请求不带批次标记、与批次provider claim穿插时冷读前驱仍完整；provider新402不误停独立SEC通道。本测试不批准新的SEC费用或请求。`batch33-authorization/`另保存原件禁网分组、当前工厂/模拟opener/controller、113损字旧失败对照及录制Enphase六组普通Run机械重读；这些都不产生真实公司或生产信用。真实调用前仍须当前执行文件绑定、必要限定独审和最终禁网接线收据通过；新的真实失败不得由测试模式或本地批准布尔值重发。

第172次新HTTP402的默认关闭接线同在`tests.vnext.test_continuous_batch33`：无新授权拒绝同摘要再次申领；录制专用的独立恢复记录绑定旧402、请求/来源字节与批次组，申领一次即消费，并发、删除授权、新402和冷读失配均拒绝。`batch33-authorization/recovery172_offline_wiring.py`将当前Enphase真实保存来源经过禁网工厂、模拟传输与原生收集，旧114失败、模拟172式402及新成功各保留独立身份；只有新成功取得当前输入信用。录制链和用户充值说明都不授权真实第173次；正式决定、服务器记录、最终执行绑定、限定独审与原账本核验另行要求。

`tests.vnext.test_capacity_reference_contract`验证后继显式引用：未知/错类型/重复/歧义/跨单元引用、漏答、重签合同、旧109同类错误拒绝，以及原生Evidence和请求集合重建。`b13-strict-references-20260922/offline_material.py`禁网检验Enphase六组完整原生链及Ford十一组计划、代表性controller与漏单元失败；记录响应不计真实语义成功，耗时/结果以对应日志为准。

2026-09-22：B13 native及program-role两个CI作业总时限均为30分钟，保留原步骤与断言。program-role单次本地完整计时604.545秒通过（隔离Python3.13.5、tokenizers0.22.2）；CI仍使用Python3.14，实际终态单独登记。证据见`docs/evidence/issue28_continuous/ci-capacity-timeouts-20260922/`。该调整不改变真实请求120秒限制。

`test_semantic_source_grouping.SemanticSourceGroupingTest` 比较原分组边界、共享字典、单独大对象与超限拒绝；其 MaterialTest 从真实两公司原件重建全部81个单元，与优化前材料逐字段相同。JPM完整来源/三种错误分类测试仍保留原240秒限制。性能剖析的中断不算PASS，修复后的完整测试须独立返回成功。

`test_capacity_semantic_review` 验证字段共享的精确恢复、JSON键重排后的相同请求、缺单元、遗漏候选、假引文及两个真实完整包。`test_capacity_native_assessment` 从实际原件经过原factory/opener/WB-3，在禁网下验证原生Candidate/Evidence成功、遗漏单元终态失败，以及单个成功请求不能产生全范围缺失结论。`test_capacity_text_results` 检查真实季度产能原文经Review/Calculator成为TEXT_V1，拒绝假完整标记、掩盖数值对、错期间、原件变化和缺有效Review。

`B13_NATIVE_RUN_MATERIAL_ROOT=/absolute/new/material PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_capacity_run_material` 在新目录完成26个明确MOCK来源请求、创建者登记、同一普通OPEN Run及公共行，拒绝重签遗漏请求和测试改成LIVE。原请求/响应/失败均保留，测试没有真实provider/paid/SEC或生产信用。该测试会在原仓库私有来源登记目录新增明确RECORDED_TEST_ONLY记录；不会替代真实输入或恢复旧额度。最后还需用复制的运行包和Python3.9独立冷读。

B13后继协议v2的`test_sales_only_source_cannot_be_labelled_actual_production`复现真实54的分类/原文冲突；销售/出货类可保留，不能改为实际产量。原54失败不重签；明确JSON类型和独立枚举后需新请求接线验证，不能原样重抽。

B13 v3改为来源kind/index选择，由程序恢复完整原文；保留provider原响应。字段/引用反例、完整记录响应Run及行（172.465秒）、B13实际工厂禁网接线（14.242秒）和D04回归（12.575秒）通过，106fast通过85.781秒。原55的AMPTC重抄错误不重签为成功。

B13 v4增加`test_clear_capacity_with_no_production_is_a_calculation_limit`：无产量可作为计算限制保留，但已有产能时不能同时宣称本单元没有产能；本单元限制不升级为整份年报缺失。原59终态不变。

B13来源编号与内容反例：`test_capacity_semantic_review`检查原始ordinal449不能引用为行位置0、JSON键重排仍保持非单调原顺序，并直接拒绝原始68及拆分的税收抵免余额反例。`test_capacity_text_results`使用独立合成无相关披露原件检查完整集合、Review、非数值结果及程序范围证据；不把Enphase原年报改称未披露。`PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_capacity_applicability`检查批准两家公司不能成为不适用，并从实际来源创建范围外Run，拒绝合法重新签名的假披露缺失结果。短测试和完整材料分别登记在当前fast/source-material入口。

D04原生：`tests.vnext.test_d04_native_assessment`覆盖历史/当前分离、引用、引语、估值/网络安全/干净意见反例及原生Review文字结果；`test_d04_native_wiring`禁网验证实际来源工厂、原opener和WB-3，并拒绝缺单元。`D04_NATIVE_RUN_MATERIAL_ROOT=/absolute/new/root PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_d04_run_material`执行27个明确记录响应请求、登记、Review、完整Run及公共行，拒绝缺请求和测试改LIVE；这不是模型判断通过。独立CI作业避免把完整D04材料塞进30秒fast入口。`test_native_assessment_replay`从已存原材料恢复一个旧原生请求，验证保留原计划ID、改请求/响应和重签新计划拒绝、历史视图无执行权限。

PR43 review5205267507回归：B13合成source_packet明确包含metric_id=B13，来源与请求哈希由真实工厂重算，共享检查不提供默认指标。test_capacity_text_results继续执行完整集合、无Review和缺覆盖拒绝。D04原生测试增加同原件/同引用的肯定否定互换、其他主体/历史/其他含义排除攻击、具体未决保留、原生接受函数拒绝及最终公共未披露行拒绝；历史正例必须在原句中明确历史期间，不能只改模型标签。普通原生CI原先叠加B13后超过30分钟总时限，B13原有完整测试现独立为capacity-native-runs作业（15分钟），所有原步骤保留，不延长原作业时限。

B13数值增量：CapacityComparisonTest新增原件数量/倍率、改写源块、分类排除、跨产品/设施、年度/季度、税收抵免和引语/假设例子反例。tests.vnext.test_capacity_numeric_run实际执行数量读取、Calculator、Run记录图和公共行，拒绝重签的0.81替代原文80/100；其来源准备、来源准入和外部登记明确使用合成替代，不能当作真实SEC/provider/冷读验收。该场景随独立capacity-native-runs作业运行，完整实际材料test_capacity_run_material继续覆盖原来源/登记门。

D04活动延续增量按动作及对象核对招聘、用户和融资渠道语句，避免把特定活动与主体持续经营混同；真实原句在测试工厂中覆盖正确排除和错误疑虑拒绝。当前13项D04回归通过。上下文分词只完成官方参考与12份历史实际usage核对，现有运行计数/资源限制未改；材料见docs/evidence/issue28_continuous/d04-activity-and-context。

D04作用域回归：`PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_d04_native_assessment`；原三个反例完整Run和公共行在`tests.vnext.test_d04_run_material.D04RunMaterialTest.test_scoped_assertions_complete_run_and_final_public_row`，明确合成来源/准入替身。新格式完整记录响应链使用`D04_REFERENCE_CONTEXT=1`或`B13_REFERENCE_CONTEXT=1`运行相应原生material测试；固定离线依赖用`python3 -m pip install --no-deps --require-hashes -r requirements-continuous-context.txt`。计数/格式/资源篡改与usage反馈测试为`tests.vnext.test_continuous_request_context`；CI fast及相应来源/原生作业安装同一固定包，不扩大原资源上限。


普通后继增量：`PYTHONPATH=.:scripts python3 -m unittest -v tests.vnext.test_capacity_quantity_roles tests.vnext.test_native_source_runtime_policy tests.vnext.test_native_refresh_execution tests.vnext.test_registered_native_update.RegisteredNativeUpdateTest`覆盖源数量不能被错误排除、运行规则/原件根分离、新请求有限协调及旧成功复用边界。计数协调短测试中的账本/执行器/登记为明确替身；不能替代WB-3完整接线。

`ORDINARY_NATIVE_UPDATE_SOURCE_ROOT=/absolute/registered-source ORDINARY_NATIVE_UPDATE_LEDGER_ROOT=/absolute/recorded-ledger ORDINARY_NATIVE_UPDATE_METRIC=D04 ORDINARY_NATIVE_UPDATE_COMPANY=enphase_energy ORDINARY_NATIVE_UPDATE_MODE=RECORDED_TEST_ONLY ORDINARY_NATIVE_UPDATE_MATERIAL_ROOT=/absolute/new/retained-root PYTHONPATH=.:scripts python3 -m unittest -v tests.vnext.test_registered_native_update.RegisteredNativeUpdateMaterialTest`执行完整原生候选、重复无新Run、输入损坏保留和恢复。材料保留根可选，须全新且在源码外；省略则临时清理。较早bf71当前实现材料实际1项2482.985秒通过，后续差异及真实复用另验，不机械复跑该大测试。固定tokenizers依赖按本节既有安装命令准备。

私有发布：`ORDINARY_ISOLATED_PUBLICATION_PREPARATION=/absolute/verified-preparation ORDINARY_ISOLATED_PUBLICATION_ROOT=/absolute/new/private-root PYTHONPATH=.:scripts python3 -m unittest -v tests.vnext.test_ordinary_isolated_publication`。完整材料为显式可选测试；未提供变量时其SKIP不是PASS。准备包必须来自同一执行绑定下的完整原生重放，不能重签旧Run。旧入口退出预备使用既有冻结producer清单，在一次性进程里验证116语义导出阻断和39项两种写边界；原公开历史仍可读取，实际源码/active不改，见ordinary-release-preparation/legacy-exit-preparation。


请求构造短作用域：`PYTHONPATH=.:scripts python3 -m unittest -v tests.vnext.test_native_request_construction`，需要既有固定tokenizers依赖。覆盖完整原字符/输入类型/字段顺序、返回对象突变、实际规则/分词状态变更、源真实性仍逐次执行；只缓存确定性请求字节，原生收据和含义检查不缓存。完整源声明、预算和请求格式未改变。注册形式短回归`tests.vnext.test_registration_event_discovery`使用明确合成metadata；真实4原件及完整metadata检查单列，不依赖私有固定目录或永久missing状态。

Issue #47 历史期间选择与目录：`PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_normal_history_catalog tests.vnext.test_historical_period_results`。目录测试用仓库自身已保存的 submissions 字节检查最近五个年度报告期末、其前一年依赖、去重后的缺口计划、未保存/不一致分片保持显式缺口、非自然年与53周期末按原样保留、修订归入自身期间而非第六个年度；候选一律 `fiscal_year=null`，财年标签只能由该申报自身 DEI 读出。期间选择测试检查重签的 selection 不能换入另一份申报、跨公司 selection 被拒、财年请求按发行人定义而非日期算术解析、候选原件未保存时如实报 `CANDIDATE_SOURCE_UNAVAILABLE`。历史结果测试的预期值在测试内由原始 Company Facts JSON 直接取值并独立算术得到，不调用被测选值器：Marriott FY2024 的 B02/B04/B05 与独立计算一致，FY2023 因前一年原件未保存只让 B02 WITHHELD 而 B04/B05 仍为 EXACT。两个入口按已保存原件读取，列入 saved-source 层（240秒），不放进30秒 fast 层。

历史期间安装与冷重放：`HISTORICAL_PACKAGE_MATERIAL_ROOT=/absolute/new/root PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_historical_package_material`，独立 CI 作业 `historical-period-package`。覆盖异目录安装后在数据根内重建出相同绑定、新进程冷重放恢复相同绑定/期间/数值/选择身份且新增调用为0、两个期间并存不互相覆盖、未知绑定被拒。该测试不创建原生 Run：重放进程是新的、无网络、输入与来源全部来自已安装数据根，但代码来自开发 checkout，所以它证明的是新进程中的输入重建，不是可移植交付。`_external` 拒绝的是代码根与数据根**重叠**（同一棵树、或数据根位于代码根内部），并不拒绝同一交付包下 `runtime/` 与 `data/` 并列；先前写成「自包含包被现有不变量禁止」是错的，已更正，脱离开发 checkout 的可移植交付仍待实现与验证。原生 Run 的接缝成本由 `tools/vnext_requirement_seam.py` 测量，见 `docs/evidence/issue47_history/requirement-seam-2026-09-18/`：已证明的是已安装的 v13 数据根在改动后的运行时下仍可加载 Requirement、通过 Run 身份校验并重建输入；**未证明**完整 v14 兼容，也没有创建任何原生历史 Run。不在此处以放宽冻结合同的方式绕过。

脱离开发 checkout 的交付重放：`python3 tools/vnext_historical_delivery.py --runtime-root <已应用注册补丁的树> --data-root <已安装数据根> --run-dir <已冻结 Run> --delivery /tmp/delivery --output portable-delivery.json`。`runtime/` 由该 Requirement 的执行授权加上全部 `requirements/` 快照组装，`data/` 与 `run/` 与它并列；重放在独立解释器中以 `-I` 运行，工作目录为 `/`，环境只有 `PATH` 与 `PYTHONDONTWRITEBYTECODE`，无网络。实测 45.2 MB（runtime 13.8 MB、data 31.5 MB、run 24 KB），Marriott FY2024 B04 = 2375000000 EXACT，公共行连同 row_hash 渲染成功，且 `vnext_modules_outside_the_delivery` 与 `sys_path_entries_outside_the_delivery` 都是空的——载入的 99 个 vnext 模块全部落在交付目录内，所以「不依赖开发 checkout」是被检查出来的，不是被声称的。

这条更正了本分支 `51b024b` 的结论。当时把 `B06_EXTERNAL_CANDIDATE_ROOT_REQUIRED` 读成禁止自包含交付，那是错的：`_external` 拒绝的是数据根与代码根**重叠**，并列不算重叠。该工具需要注册补丁才能产出可用交付，在未打补丁的 checkout 中会在第一次加载 Requirement 时失败；它报告中的 `extra_beyond_authority` 列出四个任何执行授权都没有点名、但 `requirement_profile_v4`–`v7` 在加载 Requirement 时按运行时根相对路径读取的策略文件。

执行授权的导入闭包：`PYTHONPATH=scripts python3 tools/vnext_authority_closure.py --requirement-id issue_47_v1 --require-complete --require-own-routes`，其断言登记在 `tests.vnext.test_historical_requirement_snapshot`。从授权点名的 Python 模块出发走导入图，分三类报：模块作用域闭包里出现而授权没点名的，是缺陷（照授权组装的交付根本起不来）；只在函数内被父代码导入的，是信息；**本世代自有规则文件直接导入（一跳）却未被点名的，是缺陷**。第三类是补加的——`historical_text_input.py` 每次 D02 Run 都执行，却既不在规则集也不在继承授权里，因为 `historical_run` 与 `historical_results` 都在函数内导入它，它一直躺在第二类那份"不是缺陷"的清单里。必须是一跳而不是传递闭包：13 个规则文件经父代码可达 215 个模块中的 206 个，传递判断什么也断言不了。反例已实测——退回未登记该模块的快照时 `--require-own-routes` 退出码 1 并点名 `historical_text_input.py` 与 `historical_text_results.py`，登记后退 0。`issue_28_v13` 实测 `authority_is_import_complete: false`，缺的是 `scripts/vnext/requirement_profile_v11.py`——`requirement_profile.py` 在授权内且在模块作用域导入 v10 到 v14，五个里只漏了 v11。`issue_47_v1` 点名了它；父级 manifest 与闭包哈希不动。

Requirement 快照与代码树一致：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_requirement_snapshot`，已登记进 `tools/run_fast_tests_v2.py` 的 30 秒层（实测 7.5 秒，不读任何来源材料，只对 12 个规则文件做哈希）。`requirements/issue_47_v1/baseline_manifest.json` 记录这 12 个文件的 sha256，`load_profile_requirement_snapshot` 会在数据根与代码根两侧核对；规则文件改了而没有重新 mint，快照就装不进任何数据根，而在真正尝试安装之前没有任何东西会报错。本分支已经因此漂移过两次（`25c8d72` 改了 historical_package/historical_run，`f59b614` 改了 historical_projection，两次都没重新 mint），当时唯一的防线只是 README 里一句「请运行 --check」——那不是防线。用例同时含一个反例：只让一个规则文件的哈希不同，`--check` 必须失败并点名 `baseline_manifest.json`，随后诚实的树仍然通过，以证明失败来自漂移而不是检查本身坏了。

原生历史 Run 端到端（需先应用注册补丁）：`HISTORICAL_RUN_MATERIAL_ROOT=/absolute/new/root PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_historical_run_material`。覆盖固定期间选择 → 输入安装（Requirement 为 `issue_47_v1`）→ 原生 Run 创建与冻结 → **独立进程**冻结重放 → 公共行与收据，全程新增调用为 0，并核对该行带的是被固定的年度而不是公司最新年度。

该用例有**两道跳过闸**，第二道是重点：链路需要 `issue_47_v1` 引擎在 `requirement_profile.PROFILE_ENGINES` 中登记并由 `run_store` 分派，那是 `issue_28_v13` 执行授权内**三个文件的八处改动**，以补丁形式交付在 `docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch`，不在本分支直接应用。

这个数字被实测修正过三次，每次都由执行而不是阅读给出：估计时是两处；建第一个 Run 时发现结构化重放的分派是第三处；跑 Macy's 非自然年度时发现 `point_in_time_fiscal_label` 由两份硬编码 id 集合决定（`run_store` 与 `records` 各一处），是第五、六处；接 D02 文本路线时发现 `prepare_text_contexts` 与 `text_handlers` 是两条独立的 requirement-id 链，是第七、八处。`tools/vnext_dispatch_map.py` 现在把这些分派点机械列出来（打补丁后 17 条 if/elif 链加 4 个集合成员点，`issue_47_v1` 出现在其中 6 个路由点），并在同一条链重复测试同一个 id 时失败——那类死分支不改变任何行为，任何 Run 都不会因它失败，只有读才能发现，本分支确实写进去过一条。补丁未落地时该用例 skip。**skip 不是 PASS，不得按 rc=0 记为通过**；因此它没有登记进 `tools/run_fast_tests_v2.py` 的任何层。已实测：在应用补丁的隔离运行时中两个用例都通过（合计 199 秒），在本 checkout 中两个都跳过。

第二个用例 `test_a_structured_fact_without_a_verified_claim_still_renders_its_evidence` 钉住的是一个真实缺陷，不是假设的。公共行的证据有两条路：一条给带 verified claim id 的观察，一条给不带的观察（结构化 XBRL 事实绑定的是事实本身，不是谁核实过的声明）。`historical_projection` 原先只移植了第一条，于是每个 Company Facts 指标都会得到一个自身 Run 判为 EXACT、却渲染不出行的结果，报 `HISTORICAL_PROJECTION_OBSERVATION_WITHOUT_CLAIMS`。B04 走的是 claim 那条路，所以第一个用例从未碰到它；这是靠把矩阵真正跑起来才发现的，读代码没有发现。用例同时断言该观察确实不带任何 claim id，以免将来某次改动让它走回 claim 分支而断言依旧通过。

同一隔离运行时中另测得：改动后运行时读取**补丁之前安装的 `issue_28_v13` 包**，`issue_28_v11/v12/v13` 的 Requirement、v13 的 Run Requirement 身份与历史输入重建五项探针全部 OK，即注册后继不会作废此前安装的包。代价是 `issue_47_v1` 必须按补丁后的字节记录那两个文件，`issue_28_v13` 的 manifest 与闭包哈希不变，因此一个数据根只能满足两者之一；`tools/vnext_mint_historical_requirement.py` 每次运行都会打印这一点，`--check` 在快照与代码树不一致时失败。

Requirement 接缝成本实测：`python3 tools/vnext_requirement_seam.py --data-root <已安装的历史包> --work <新的外部目录> --binding-id <绑定> --company-id <公司> --metric-id <指标>`。它复制该包、在副本上加一条引擎登记与一条 Run 授权分支，然后分进程测量同一个已安装包分别被原运行时和改动后的运行时读取的结果，并单独测量 `_external` admit 哪些代码根/数据根布局。它不写开发 checkout、不写 #28 的工作现场、不创建 Run、不发任何请求。它给 `load_run_requirement_snapshot` 的身份三元组取自刚加载的 Requirement，因此校验的是 Run 身份的 Requirement 一侧，**不读取也不产生任何真实 Run 记录**；数据根未持有的 Requirement 相关探针记为 `NOT_COVERED` 而不是失败。这是一次测量而不是一个测试：它的结论会随 `issue_28_v13`／`issue_28_v14` 的 manifest 变化，所以不进任何测试层，只在需要重新核对接缝成本时运行并把输出存进证据目录。

历史期间 CI 作业待人工添加：本会话的 GitHub App 没有 `workflows` 权限，无法提交 `.github/workflows/vnext-fast.yml`。改动以补丁形式交付，不用照抄：`git apply docs/evidence/issue47_history/ci-job-patch/0001-add-historical-period-package-job.patch`。该补丁只追加一个 `historical-period-package` 作业（12 → 13 个作业，其余作业逐字节不变），沿用该文件既有原生作业的形状：同样固定的 `actions/checkout` 与 `actions/setup-python` SHA、Python 3.14、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONPATH=scripts`，以及 `runner.temp` 下的 per-run 材料根；`timeout-minutes: 20`（该测试在本容器约 85 秒）。已用 `git apply --check` 对本分支 head 验证可直接应用。在该作业加入前，这条材料测试只有本地执行记录，不能写成 CI PASS。

同一执行内共享解析：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_shared_sources`（saved-source 层，7 个用例 37 秒）。不只测"更快"，而是测三种可能出错的方式：身份被跨调用复用（同字节改称另一期间/另一主体必须仍被拒）、对象被跨调用共享（调用方清空拿到的 blocks，下一次必须完好）、复用泄漏到块外（`_SHARED_SOURCES` 在块外必须为 None）；另加键对字节敏感（改一个字节即换键）与作用域可重入（内层必须共享外层字典，而不是绑新字典）。可重入那条是整 Run 普查抓到的真实 bug：80 次解析只降到 25 次而非 5 次。端到端实测同一 Run 同一输入：80 次解析→5 次、105.9 秒→63.7 秒、`result_id` 相同；新进程冷读不进作用域、重新解析原始证据并返回相同 status/quality/条目数。

`test_table_context_qualification_guard` 实测独立运行 29.9 秒，对着 30 秒的 fast 上限——单独跑通过、`--jobs 4` 下超时，已连续两次让 fast 层报 FAILED（rc=124，不是断言失败）。fast 层的超时来自冻结的旧入口、不能为单个用例提高，该用例又确实读取完整已保存 qualification 材料，因此移入 240 秒来源材料层。移后 fast 层 123 个用例 71.6 秒全过。

覆盖汇总只读：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_coverage`（saved-source 层，7 个用例实测 23 秒，原为逐位置重算）。验收条件不是"看起来只读"：`test_the_report_entry_computes_no_metric_outcome` 把三个指标解析器、两个文本候选工厂与 `create_system_review_decision` 全部替换为抛异常，报告仍必须产出 195 个位置。它刻意**不**禁止所有 `HTMLParser.feed`——计划层为确定期间要读申报自身 DEI，一律禁止会因成本问题而失败，而成本属于另一项。`test_a_recorded_exact_result_is_not_a_verified_outcome_when_a_defect_names_it` 用临时 run 目录证明：同为 `VALUE_EXACT`，被缺陷登记点名的那条退出 `verified_outcome` 而状态不被改写；`test_an_edited_run_directory_is_not_the_run_its_manifest_describes` 改一字节即 `RUN_RECEIPT_FILE_CHANGED`。原"一个适配器的限制不移除另一个已解析的指标"用例改为直接调用三个 resolver——该性质在 resolver 里，不靠让报告去跑它们。端到端实测同样 390 个位置：260.4 秒 → 4.7 秒。

内容接受层（同一文件，`ContentAcceptanceIsBoundToTheValueTest`）：默认跑构造输入，
不需要任何批次；要连带验证它接到覆盖表上，设 `HISTORICAL_RUNS_ROOT=/absolute/runs/root`
指向一批冻结 Run，否则该用例按名跳过并说明原因。承重的一条是
`test_an_acceptance_does_not_survive_the_value_changing`：同一坐标改一位数字，按坐标匹配
的实现会通过其余每一条而只挂这一条。两次注错（只按坐标匹配、让接受盖过撤回）各由且仅由
对应用例抓到，记录在
`docs/evidence/issue47_history/content-acceptance/cross-source-read.json`。接受登记
`docs/evidence/issue47_history/accepted_result_content.json` 由
`build_acceptance_register` 从四份读取产物生成，不手写；改了任一读取产物要重新生成，
`test_the_registered_acceptances_cover_real_positions` 会核对每条都点名它所依据的产物
且该文件存在。

C02 的 pinned 路线（`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_governance_text`，saved-source 层，四个用例实测 47 秒，默认 240 秒足够）：当期两个用例拿**普通链路自己的答案**当预期并逐项比对——计划级别、每份准入申报的 accession、以及选中的块号；只断言"产出了东西"的用例，对一条悄悄放宽或收窄来源集的 pinned 路线同样会通过。Marriott 走代理级、Paramount 走 Part III 级，两级各测一家，因为只接第一级的实现会让第二家拿到第一级的答案。Part III 原件证明单独断言，理由写在用例里：它不是选择的输入，跳过它块号完全不变、上面那条比对照样过。更早期间的预期是**申报自身的日期**而不是选择器的输出：FY2024 必须点名 2025-03-27 那份代理、FY2023 必须点名 2024-03-27 那份，并以 `SAVED_SOURCE_MISSING` 停下；取最新代理的实现会在这里找到一份已保存的 2026 文档并产出数值，所以这条同时断言 accession 和拒绝。第四条是 D02 的对照：Macy's 同一个块里有代理，所以无条件放宽表单集合的版本会给 D02 填上代理角色并改变它的 scope 记录。六次注错五次被抓；`WIDEN_THE_FORMS_FOR_EVERY_METRIC` 没被抓且**本来就看不见**——表单集合与角色赋值守同一件事，去掉一半另一半仍答对，`GIVE_D02_THE_PROXY_ROLES_TOO` 同时去掉两半才被抓，如实记录。

Form 10-K 不编号项的章节边界：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_text_boundary`（saved-source 层；最早 4 个用例实测 44 秒，现 25 个用例、读九份年报原件，2026-09-26 实测 1029 秒，运行器预算相应改为 1500 秒——此前的 480 秒预算落后于用例增长，saved-source 层在那里把它判为超时）。四个用例的预期值都从文档自身的块读出，不由被测边界规则产生：Pfizer 的 ITEM_3 必须结束在标题块自己的下标；修正后的块集合必须是冻结集合的**真子集**，且差集恰好等于冻结集合与高管章节的交集（"没有少抓"的强形式，不是章节数比较）；Macy's 第 774 块在 Item 8 内点名首席执行官却不是标题，它的整套记录必须与冻结模块逐字节相等——语料自带这个反例，不需要构造；路由只把 D02 接到后继模块，C02 仍回父模块。另三个用例覆盖被引用附注，预期全部是从申报原文读出的**字面块号**，不是被测解析器返回的范围——上一版用生产解析器返回的整个附注范围当预期，结果整取了 Marriott 自己刚判定应排除的担保表、信用证与保险赔付，以及 Lumen 的合同承诺段，测试却通过。现在每家同时给"必须包含"与"必须排除"两组块号，并要求冻结集合一块不少：Marriott 必含 1312–1318、必排除 1292–1308 与 1319–1320；Lumen 必含两个并入小节的正文、必排除 3433–3454；Paramount 必含 Legal Matters 全节、必排除长期承诺/表外安排/赔偿说明及四处重复页眉。Salesforce 引的是 Note 14 自己的标题而不是其中一节，必须整取该附注；Pfizer 的 Note 16A 解析为`WIDER_PARENT_NOTE`，必须不整取。回归护栏：边界修复后九家里八家逐字节不变、Pfizer 58 条 22,982 字降到 32 条 18,373 字；附注修复后四家增加而零块丢失（Lumen 15→41、Paramount 16→27、Salesforce 9→15、Marriott 10→11），其余五家逐字节不变。第八个用例把“路由指向哪个 Spec”钉成一个决定而不是一处漂移：断言 `TEXT_SPEC_PATHS["D02"]` 仍是 v1，v1 声明 64 而 v2 声明 192，并且**从冻结渲染器自己读出协议的界**——给 `render_text_payload` 65 条格式完全合法的条目，必须抛 `TEXT_PAYLOAD_ITEMS_INVALID`，去掉一条后必须渲染出 64 行。这是读行为而不是读字面量，所以那个 64 被改动时用例会失败而不是默默跟着变。第九个用例说明 Pfizer 这个坐标被什么拦住：在 v1 下 `create_deterministic_text_candidate` 以 `EXCEEDS_ITEM_BOUND` 拒绝；换成 v2 的界之后同一批输入得到 92 条、41,860 字、Evidence PASS，且字符数严格小于 `max_text_chars`——即拦住它的是条目数，不是范围也不是体量。第八与第九个用例在容量那一轮已按性质改写（路由指向 v2；同一批参数喂给两个 Spec 身份，旧界按条目数拒绝、新界接受完全相同的集合），因为断言状态的版本在路由改动后就不再拒绝了。

页眉判据的覆盖面（`PageFurnitureInEveryScopeTest`，三个用例）：判据本身不变——块在自己 scope 内重复且邻块也重复即为 running header——变的是它只挂在本世代自己构造的 scope 上，`ITEM_3` 与整取附注没有。期望值由用例**自己从文档重算**，不读规则写出的字段，否则就是拿被测对象当预期。Ford 的 Note 24 必须恰好有 8 个这样的块且一个都不在摘录集里，集合大小 45；另外五份申报的摘录数必须仍是 96/41/15/25/18 且与页眉集合不相交——**多丢的那种错误在这里才看得见**；Enphase 的页脚必须仍在摘录集里、且必须**不**被该判据识别，同时其缺陷条目必须在登记里，所以将来有人修好它时这条会失败并把人送到登记表而不是静默生效。第三条是 D03 的护栏：Macy's 的 1566/1573（养老金附注里重复出现的表格行）必须仍是 D03 候选、且必须确实被该判据识别为页眉——两半都断言，因为只断言前半的用例在"判据根本没识别到它"时也会通过。四次注错三次被抓，`RECOMPUTE_EVERY_SCOPE_INCLUDING_THE_SUB_NOTE` 没被抓且本语料区分不了它，如实登记。

二十五个用例实测 240 秒（准备第六份申报 Ford 约 21 秒），`SOURCE_TIMEOUT_OVERRIDES` 给到 480 秒。

Spec 修订机制本身：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_spec_revision`（30 秒层，实测 0.02 秒，只读两个 Spec 文件）。七个用例。断言冻结编译器**仍然**拒绝 v2（它哪天接受了，这个模块就是死代码）；断言修订只带来 `max_items` 一处差异且两个哈希都变；断言未登记为修订的 Spec 走冻结路径且结果逐字段相同；七种“改了别的”的后继（sections、字符界、allowed_source_roles、name、disclosure_group、quality_rule、metric_id）一律被拒，每一种都是拿**真实的 v2 前置内容**改一个字段生成的，不是构造的 fixture；超过后继上限的界被拒；最后一个用例断言 `SPEC_FIELDS` 的 24 个字段全部落在 `compiled` 或 `prompt_bundle` 两侧之一——少一个字段，那个相等判断就有一条能被绕过的缝。另有一个用例走反向：空 `applicability` 与非法 `renderer` 必须由冻结编译器**先**拒（消息里不带 `Revised Spec`），以证明后继路径只加检查、不减检查。

后继文本结果协议：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_text_protocol`（30 秒层，实测 0.03 秒，不读来源材料）。十三个用例，分三组。

第一组是**差分**，这是全部保证所在：同一批 payload 同时喂给冻结的 `text_results.render_text_payload` 和后继实现，在冻结上限之内两者必须返回完全相同的值、抛出**完全相同的错误消息**（不是"都拒了"）。26 个变异覆盖冻结渲染器的每一项检查——字段多一个/少一个、版本与种类与渲染器、三个审阅哈希格式、coverage 空/乱序/重复、items 空/非列表、逐项顺序/相邻交换/多键/少键/空文本/控制字符/非 NFC/超长/非法观察 ID/空角色/非字典、角色重复、观察 ID 重复。另有一个用例断言省略 `max_items` 参数时默认值就是冻结上限，所以没有东西靠"不传参"拿到容量。

第二组是**容量确实只改了容量**。64 仍拒 65；提高后 65/92/192 都渲染出对应行数且最后一行是最后一条；193 被拒。关键的一个用例把每个逐项变异**在第 80 项**再做一遍——冻结上限之内的 payload 永远到不了那里，而"只校验前 64 条"正是这里可能出错却看起来正常的方式——要求同一理由被拒；另一个用例断言 92 条渲染出正好 92 行、逐行等于第 0…91 条，即合法的第 92 条没有被悄悄丢掉。字符上限用精确算术钉住：192 条 × 332 字符加 191 个分隔符是 63,935，在 64,000 之内；192 × 333 加 191 是 64,127，超出并以 `TEXT_VALUE_EMPTY_OR_TOO_LARGE` 被拒。分隔符必须算进去，否则 192 × 333 = 63,936 会看起来还在预算内。

第三组是**容量跟 Spec 身份走**。只有本仓库能重新编译出来的修订 Spec 身份才拿到 192；未知哈希、空串、`None`、整数 192、字符串 `"192"` 一律回落到 64。一个伪造记录同时写 `"max_items": 192` 和一个重建不出的 `spec_closure_hash`，必须以 `TEXT_PAYLOAD_ITEMS_INVALID` 被拒，换成能重建的身份才通过——这就是"payload 不能自报容量"的实测形式。v1 的身份仍拿 64。最后一个用例在临时根里把 v2 的 `max_items` 改成 100，要求重新读出 100 而不是命中缓存返回 192：缓存一个权限和缓存一次解析是两回事。

第四组是**轨迹的逐项检查也要走到第 92 条**。渲染器的检查在第二组已经覆盖，但 `verify_text_trace` 在渲染通过**之后**还要把每一条摘录和它点名的那份观察逐项比对——来源内容、语义角色、审阅质量、批准效力、顺序、Spec 身份、候选与审阅单元哈希、coverage。这段循环是复制来的代码，**一个在第 64 条之后停止比对的副本，照样渲染出 92 行、照样通过前三组**。

这里的攻击形式要选对：把已建好的观察就地改一个字段，会被 `validate_record` 重算身份提前拦下——那证明的是记录层有效，不是轨迹比对有效。所以十种替换里有七种用生产工厂 `_build_text_observation` **重新构造一份内容不同但完全合法的观察**，再登记到轨迹仍然点名的那个身份下；`quality` 与 `approval_effect_hash` 不参与观察身份，可以直接改；最后一种是整条移除。每种都在第 7 条和第 80 条各做一遍，必须以**同一条理由**被拒。另有一个用例把 `input_observation_ids` 截到前 64 条，必须以 `TEXT_TRACE_INPUT_EXACT_SET_CHANGED` 被拒。

这一组同样验了承重：把后继的逐项循环改成 `payload["items"][:64]`，16 个用例中 **10 个失败**；改回后全过。

修订件准入：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_amendment_admission`（saved-source 层，实测 37.9 秒，读两份 10-K 与两份 10-K/A 的完整字节）。

七个用例全部跑**真实申报**而不是构造 fixture——一份只在构造 fixture 上成立的政策，不能证明它判得了真申报。语料里两份修订件的差别正是政策存在的理由：Southwest 更正一个 exhibit 超链接、Paramount 补 Part III Items 10–14，所以同一个问题（这个指标可以解析吗）**按公司、按输入类别给出不同答案**。

第一个用例先证明语料确实各带一份 10-K/A、Ford 确实没有——否则后面几个在断言空气。随后：链接更正清除两个输入类别；Part III 清除事件窗口而不清除报表数值，且拒绝理由必须含分类名、**必须不含 `NOT_IMPLEMENTED`**；政策的九个 `not_covered_metric_ids` 两家都拒；报表类与事件类不能合在一次判定里（`MIXED_INPUT_CLASSES`）；空事件集合时一切按报表类处理，即取更严的一侧而不是更松的一侧。

承重的是 `test_the_two_companies_do_not_get_the_same_answer`：**一条无视分类、对任何修订都放行的路线，会通过其余全部用例，只挂在这一条上。**

已登记前身的年份（Issue #47 §7.3）：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_predecessor_periods`（saved-source 层，23 个用例实测约 75 秒，读 Paramount 两个注册人各自的 submissions、FY2024 与 FY2025 的年报与 10-K/A）。每个用例守一条边界，都在申报实际所在的地方检查：窗口先取后继自己的年份、再接前身四年，前期只在同一注册人内取（后继首年没有前期、前身每年的前期是它自己的上一年）；后继自己的年份永远不由前身回答（`_predecessor_period` 对不早于后继最早年报的期末不查前身）；注册表没为该公司点名的 CIK 一律不读；把今天的 successor-only 政策塞回前身年份、或把 reporting_cik 改成别的公司，重签后仍被重推拒绝；前身年份的钉期输入读它自己的 10-K（FY2023 原件未存则按名报来源缺口）；**重新推导期间选择时读到的每一个 submissions 块都必须在钉期输入的已准入来源里**——第一次跑这些年份时每个指标都以 "Request-ledger locator evidence is invalid" 失败，正是因为前身期间的推导先读后继目录、而后继目录没随输入安装。前身 FY2024 的 10-K/A 措辞不在已批 Part III 模式之内：事件窗口按政策失败闭合、具名拒绝，而身份/期间类完整性错误照旧抛出；后继那份仍按 Part III 分类；B06 对这份修订走"输入未决"而不是异常。同一个已批拒绝在零 AI 路线上也以扣留结果（同理由码与类别）承载而不是让尝试失败，且扣留的 B03 带着同样扣留的 B01——否则 Run 以依赖集不完整失败。九次注错全部被抓，见 `docs/evidence/issue47_history/paramount-predecessor-years/fault-injections.json`。

E01 的 8.01 阅读：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_e01_eight_o_one_reading`（saved-source 层，14 个用例实测约 1.5 秒，读七个窗口里 22 份 8-K 主文件）。路线的 8.01 关键词拿去比的是 hdr 给出的固定文字，永远匹配不上，所以这份阅读不复用路线的任何事件模块（用例按导入树断言），而是按申报自己的标题定位 8.01、读到 Item 9.01 为止。每一步都在需要它的那份申报上检查：Pfizer 的标题是 "Results of Other Events"（第一版只认 "Other Events"，把这份读成空——和路线同形的漏法）；Macy's 的关键词只在 Item 1.01 的契约条款里，不能算作 8.01 带关键词；8.01 止于 Item 9.01。判定规则只在**三种读法都给出已发布值**时接受，一种读法同意不够——否则 Lumen、Macy's、Marriott 会凭尚未决定的口径被接受；缺判断的 8.01 使阅读不完整；已提交阅读中每份 8.01 的正文摘要与关键词必须能从已保存字节重算。五次注错全部被抓，其中"表头计数重新接受 E01"是以接受编号重复的方式粗粒度抓到，见 `docs/evidence/issue47_history/e01-keyword-branch/fault-injections.json`。

B03 的 D&A 取数范围：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_b03_depreciation_scope`（saved-source 层，3 个用例，读九份 10-K 主文件）。已批链条按顺序取第一个出现的直接 D&A 概念、从不与后面的比较；这组用例守的是发现这一点的普查：Salesforce 把链条第一个概念标在物业设备附注里的"Depreciation and amortization of fixed assets totaled $1.2 billion"上，普查必须读到它（早先那次阅读没读到，并据此写下"路线是对的"）；九份申报的直接候选只在 Salesforce 一处不一致；登记的缺陷仍撤回已发布的 0.2295，释放只点名定向 Run 里那个扣留结果与它的闭包（修复之前这条断言的是"未被释放"，修复后按设计过期，已改写）。注错：让普查跳过精度低于百万的事实（模拟早先的盲区），两条用例同时失败。

报表指标的跨来源阅读：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_statement_fact_reading`（saved-source 层，11 个用例，读十份 10-K 主文件约 30 MB，实测不到 1 秒）。这份阅读授予 75 条接受，此前它的代码从未提交，且用 `int()` 解析数值、失败就静默跳过——Salesforce 那条写成 "1.2"（scale 9）的折旧因此看不见。现在由 `tools/read_statement_facts.py` 产出：数值按小数解析，SEC 的 fixed-zero 横线读作零，读不出的所需事实列出而不丢弃，重复事实只在互相舍入一致时合并为一个；两个"总 D&A"概念数值不一致时 B03 不接受（收入、净利润、利息链的后位概念是定义有意排在后面的不同口径，只记录、不当矛盾）。已提交阅读的每个位置、每个指标都必须能从已保存字节重算。五次注错全部被抓，其中 fixed-zero 与不一致重复两条只有构造用例能看见（本语料没有这种事实），见 `docs/evidence/issue47_history/reading-producers/statement-injections.json`。

事件计数阅读：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_event_count_reading`（saved-source 层，8 个用例）。C01 与 E02–E05 的 35 条接受来自这份阅读；它原先的代码同样没提交，且用未排序的 glob 在所有已存尝试里挑 submissions 索引——挑哪份取决于目录顺序。现由 `tools/read_event_counts.py` 产出：索引取账本里最近一次成功的那份（与路线读的是同一份），七个窗口的申报清单与计数逐个能从已存字节重算；8-K/A 作为独立条目计入（去掉它 Marriott 的 C01 由 3 变 2，注错即被抓）。E01 不从这份阅读接受。另一个闭包的结果写进自己的一份阅读（`--case` 必须配 `--output`，否则按名拒绝——一份阅读里的位置都比对同一闭包的结果）：Paramount 前身 FY2024 的五个事件值读自 `event-count-read-paramount-2024.json`，重算用例对两份阅读逐位置运行。

C02 核心事实核查：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_c02_core_fact_reach`（fast 层，6 个用例，不读已存材料）。`docs/evidence/issue47_history/c02-board-read/core_fact_reach.py` 在当前代码下重推十个位置的选择与治理文档的块，核对 `core-fact-judgements.json`；用例用测试内构造的选择与块，分别断言四种拒绝：记为在值里的块其实没入选、记为漏选的块其实入选了（Marriott 的 1217 第一次就是这样被记错的）、入选块在 246 条判读里不是构成事实、文本起首变了（两侧都查）。另一例要求判断文件恰好覆盖已提交的十个位置、且"没有"与"值里没有入选块"互相等价。

治理阅读（C03/C04）：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_governance_reading`（saved-source 层，6 个用例）。14 条接受来自它；原代码同样未提交且用 `int()` 静默跳过。`tools/read_governance_facts.py` 把 SEC 的 fixed-zero 横线读作零之后，暴露出旧代码靠跳过才碰巧读对的一处：薪酬-业绩对照表给每个做过 PEO 的人都留一列，某年没任职就填横线——Southwest 2025 年那格是 Gary C. Kelly 的占位。规则从表格本身陈述：同一人在其他年份有非零 PEO 薪酬，则本年的横线是占位、放到一边并记录证据；从未被支付的人的横线照常计入（构造用例）。三次注错全部被抓，见 `docs/evidence/issue47_history/reading-producers/governance-injections.json`。

住宿表、RPO 与薪酬表阅读：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_single_readings`（saved-source 层，5 个用例）。`tools/read_lodging_table.py` 与 `tools/read_single_facts.py` 取代原先未提交的产出代码；住宿表取范围字面量之后的 Worldwide 行（该表第一行 Worldwide 是自营物业），RPO 列出未取的两条事实（上一期、带收购业务维度的部分），薪酬行的各列必须加总等于合计。至此每一份授予接受的阅读都由已提交代码产出、并能从已保存字节重算；D02 那份是逐块人工判断的记录，没有可复现的"代码"，它的复核方式是逐块重读。

**后继协议的接线**（与上一条不同，这条测的是"有没有接上"而不是"实现对不对"）：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_protocol_wiring`。条目上限在三个文件、五处生效，模块本身正确不等于 Run 走得通，所以这三个用例直接调生产入口——`records.validate_record`、`constraints.verify_trace_observation_values`、`projector._projection_value`——each 喂一个 92 条的 payload（Pfizer D02 的真实条数）。

它和 `test_historical_run_material` 一样需要注册补丁，**未打补丁时 skip，skip 不算 PASS**，所以同样不登记进 `tools/run_fast_tests_v2.py` 的任何层。跳过条件是从补丁**实际改到的三个模块源码**里数 `historical_text_protocol` 出现三次读出来的，不是去读补丁文件——补丁只打了一半时应当 skip 而不是报 PASS。

**反例才是这组的承重墙**：每个用例都跑两遍，一遍让 payload 声明修订 Spec 的身份，一遍声明前驱的身份，后者必须以 `TEXT_PAYLOAD_ITEMS_INVALID` 被拒。两遍都通过就意味着这条路线只是给所有人放宽了上限，那正是这套安排要避免的失败。已实测该反例确实承重：在打补丁的运行树里把容量查找强制改成"对任何身份都返回 192"，三个用例**全部失败**；改回后全过。记录本身也按生产形状构造（`validate_record` 在到达文本校验之前先查完整 schema，半成品记录会因为错误的理由被拒、什么也证明不了）。

实测在打补丁的运行树里 3 个用例 0.01 秒，在本 checkout 里 3 个 skip。

历史目标年不能用 accession 实例替代主文档：`tests.vnext.test_historical_period_results.HistoricalCompanyfactsResultTest.test_an_accession_instance_cannot_establish_an_issuer_fiscal_label` 固定这条边界。前期年度路线可以读该 accession 自身的 XBRL 实例，因为它只需要该申报的起止日期与相邻性；发行人财年标签是另一回事，冻结政策要从完整文档读发行人自己的显式定义，`inspect_fiscal_year_labels` 对实例直接返回 `FISCAL_LABEL_FULL_DOCUMENT_REQUIRED`。Salesforce 是现成反证：同一个 `2026-01-31` 期末，其发行人标签为 FY2026 而 DEI focus 为 2025，Macy's 同一期末的标签则是 FY2025。因此目标年缺自身主 HTML 时如实记为来源缺失，不改标签政策、不用实例推标签。

**D04 历史路线（钉期语义来源、#47 自有登记、Run 接线）**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_semantic_routes`，登记在 `run_fast_tests_v2.py` 的 source 层（21 个用例，批次占着三个核时实测 204 秒，超时 600）。三组承重：(1) 钉期来源与冻结构建器**逐字节相同**——把冻结的两个"最新年报"读取指向同一份钉期输入，要求输出（含 `semantic_source_id`）完全一致，覆盖更早年份（Marriott 2023）、带 Part III 10-K/A 的前身年份（Paramount 2024，CIK 813828）与范围内的 B13（Enphase 2025）；(2) 登记与加载——默认模式是 LIVE，所以 recorded 登记**永远不会被批次取到**（`NOT_REGISTERED:LIVE`），编辑过输出并重算哈希的已安装副本以 `ACCEPTANCE_DOES_NOT_RE_DERIVE` 拒绝，同一内容自称 LIVE 而不在创建者日志里以 `LIVE_ASSESSMENT_NOT_IN_CREATOR_JOURNAL` 拒绝，#28 的登记（`issue_28_v14`）按名拒绝，缺一个请求的输出集不登记；(3) live 会话按名拒绝两次——先是没有许可，给了许可也因 WB-3 控制器与出口闸门未登记 `issue_47_v1` 而拒绝，后者由控制器自己的拒绝**测出来**而不是写死。**这些用例证明的是管道**：登记的输出是合成的，每条发现都是冻结检查器自己从来源推出的关系，所以它是检查器预期的答案，不说明任何申报的内容。Run 层（安装、`issue_47_v1` 下的原生 Run、冻结、独立进程冷读、公共行）需要注册补丁，在运行树里用 `docs/evidence/issue47_history/semantic-route-wiring/recorded_d04_run.py` 实测。用例写入 `.git/issue47-historical-assessments/RECORDED_TEST_ONLY/`，结束时由会话的 `discard` 删掉自己写的文件与空目录。

**C02 判读**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_c02_board_reading`（source 层，70 秒）。`tools/read_c02_board_statements.py` 经路线自己的文本输入与候选构建器、在当前代码下从已保存代理材料重推十个 C02 值的选择，要求 `docs/evidence/issue47_history/c02-board-read/excerpt-judgements.json` 逐块、逐文本描述它；用例重推整份阅读，并确认少一条判读或判读了另一段文字都按 `JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION` 拒绝，而不是照常出结论。中间两类（构成政策流程、委员会职能）不决定结论的规则也有一条用例：全改成中间类时结论是 `DEPENDS_ON_THE_DEFINITION`，不是 MATCH 也不是 DIFFERS。

**D02 斜体事项标签**：`tests.vnext.test_historical_d02_marks.TheItalicMatterLabelTest` 以"只认下划线"的旧规则为对照（给规则的字节只在 span 带下划线时才交出去），要求 Paramount FY2024 恰好多出 {2877: "Asbestos", 2885: "Other"}、2025 恰好多出 {3249: "Asbestos"}、Lumen 不动，三者 D03 都不动。影响面普查在 `docs/evidence/issue47_history/d02-content-read/italic-note-labels.json`：12 份申报在 Item 3 与被引入附注范围内的所有未取块，以及改动前后逐份的 D02 候选哈希与 D03 集合。该套件现读四份完整 10-K，批次占三核时 162 秒，超时覆盖为 480。

**B06 阅读**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_debt_to_equity_reading`（source 层，不到一秒）。四个位置从申报字节逐项重推；三个融资租赁分支各在其所为的申报上核对；把 Macy's 租赁表改写成"融资租赁列在债务下"后必须不再相加（替换只在那张表内做，并先断言替换已生效——HTML 里的标签文字被标签切开，全文替换会什么都不改）；一份对融资租赁什么都没说的申报不读。

**金融指标适用分支**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_financial_results`（source 层，9 例，批次占三核时 130 秒，超时覆盖 480）。承重的是替换本身：同一份普通准备交给普通解析器与移植后的解析器，六个指标在 JPMorgan 真实最新年报上返回的每个字段都相等，且要求都是 APPLICABLE/EXACT/PUBLISHED（两个相同的拒绝也会相等）。冻结检查器按整份 bundle 的字节作键共享，每个指标只解析一次。钉定准备的形状在可达期间上验：Marriott FY2023（两个解析器逐字段相同）、Paramount FY2025 带修订件（普通解析器按三证明规则拒绝、移植版读同三份并携带第四份）、证明顺序打乱。入口本身用"把银行特征借给 Marriott"打开门来跑，断言只关于读了哪份申报与交出哪份准备。五次注错（按位置取证明、取最新年报、交出重标注准备、门关也回答、删派发）全部被抓。

**读历史块的钉定期间**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_block_inputs`（source 层，4 例）。本仓库唯一"原件已存且选择读历史块"的期间是 JPMorgan FY2025 在刷新链记录根上（索引按已存块自身正文重推，`RECORDED_TEST_ONLY`），它读六个块。用例要求每个被读的块都随钉定输入携带、主文档期间（Marriott FY2023）仍恰好 3 份证明、安装器从运行树读 Requirement；两处注错（丢掉本注册人块、改回从来源根读 Requirement）各被对应用例抓住。运行树端到端用 `docs/evidence/issue47_history/financial-route/recorded_bank_run.py <work> <metric>`：装入、原生 Run、冻结、公共行、另一进程冷读，并与普通路线同一申报上的值比较。

**申报行在历史块里的钉定期间**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_filing_inventory`（source 层，15 例，扫描占两核时 52 秒，超时覆盖 480）。本仓库没有"原件已存且目标行在历史块"的真实期间，所以 `tests/vnext/historical_block_fixture.py` 用 Marriott 的已存材料造一个：2024-06-30 及之前申报的行整体移进新历史块，经录制会话记录（唯一接缝是规划器对主文档"要不要取"答"要"），`RECORDED_TEST_ONLY`、零调用。承重的是答案不变：FY2023 在两个根上公司事实十一个、accession 三个、B01 逐字段相同，修后来源集点名新块；金融路线借银行特征走开门一侧，不带期间选择时按名拒绝。查找本身：行在 `recent` 返回的就是主文档对象（`assertIs`），块正文越界、未声明、另一注册人、两块同列、选择不以主文档开头各有拒绝用例。八个注错（`docs/evidence/issue47_history/block-resident-filings/fault_injections.py`）全部被抓。整期比较用同目录 `measure_block_resident_routes.py <work> <label>`：三期 39 个指标比答案，身份差异单列（FY2023 的 D02 记录了申报行的出处）。

**安装器装入的规则输入**：`tests.vnext.test_historical_sec_session.TheInstallerCarriesTheRuleInputsItClaims`（接线套件的一部分）。一次安装、两个方向：装好的根回答 B13 范围问题与仓库相同；装入集合恰好等于"非代码、非展示"的执行授权输入，且字节与清单一致。恢复旧的目录规则、把代码也装进去，两个注错各被抓（记在 `acquisition-wiring/fault-injections.json`）。改动接线证据文件后照例 `python3 tools/vnext_historical_wiring.py` 重建收据。

**E01 的 8.01 从自己的正文确认**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_event_items`（source 层，17 例，84 秒，超时覆盖 480）。本仓库保存的 40 份带 8.01 的 8-K 逐一唯一定位，其中独立阅读工具（`tools/read_e01_eight_o_ones.py`，不导入路线模块）能找到的 36 份正文逐份相同；Macy's 封面的复选框字母 "o"、句末的条目引用、构造的引号标题/子条目标题/被隔开的重复标题/合并标题/签名收尾；把 `brief` 改成含关键词不改变结论；七个有值窗口的答案（Enphase 0、Ford 2、Lumen 7、Southwest 2 发布，Macy's/Marriott/Pfizer 按名扣留）；只有直接条目的路线（C01、E05）不受影响。九个注错（`docs/evidence/issue47_history/e01-item-text/fault_injections.py`）全部被抓，其中"引号不算引用""两次标题取第一个"只被构造用例抓到。全部 40 份的读法与判断：同目录 `census.py`；原生 Run 与批次逐位置比较：同目录 `compare_runs.py <targeted runs root> <batch runs root>`（C01、E05 的 result_id 与批次相同）。

**B03 折旧摊销的扣留规则（规则本身；2026-09-26 起接入历史路线，路线用例见下一条）**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_da_scope_candidate`（source 层，11 例，10 秒）。九份 B03 申报上八个答案与已批链条相同、只有 Salesforce 按名扣留；读法是冻结事实解析器的子类，用例要求它产出与冻结解析器逐项相同的事实（多记 `decimals`）；构造用例覆盖精度内差异、超精度冲突、构成消解、"不因更大而取"、别的期间/分部/币种、同一概念两个数。八个注错（`docs/evidence/issue47_history/b03-depreciation-scope/fault_injections.py`）全部被抓，其中"任何币种当候选""去掉构成消解"只被构造用例抓到。

**B03 经历史路线**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_da_scope_route`（source 层，6 例，44 秒）。Salesforce FY2026 按名扣留 `B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN` 且仍带 B01；Enphase 与 Marriott 2025 的结果与关掉检查时逐字段相同；四个构造形状（申报自身构成消解冲突、链条取了申报没标的直接总额、标了总额却走构成、数值超出申报精度）替换的是"申报的 inline 事实"并如实标明。七个注错（`docs/evidence/issue47_history/b03-depreciation-scope/route_fault_injections.py`）全部被抓，五个只被构造用例抓到。

**#47 模型调用（仓库侧，补丁未应用）**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_model_calls`（fast 层，21 例，约 5 秒）。许可逐层验证（缺失、别的 Requirement、上限第三项非 0 或服务商≠付费、传输不是固定那一个、只能点名已接线指标与唯一用途、信封宽于授予之并、账本根与 #28 的根/本检出/#47 的 SEC 账本根重叠或嵌套、批准正文摘要不符或比许可窄、批准授权生产、作者不是批准人、GitHub 上的正文与保存的不同）；账本（认领要锁、累计上限、不重抽、无终态的槽位计数并停、每个停止理由都停、改过的槽位被拒、记录账本不能落在已授权根内外或检出里）；以及今天的状态——控制器不造 `issue_47_v1` 授权对象、适配器不把字节交给该请求类型、出口扫描器在本模块在场时通过、封存的离线验证描述的是打了补丁的树而不是这一棵、补丁对当前树仍 `git apply --check` 通过。

**#47 模型出口的离线验证（补丁侧）**：只在带注册补丁的运行树副本里、应用 `docs/evidence/issue47_history/model-egress/egress-registration.patch` 并 mint 之后跑 `python3 docs/evidence/issue47_history/model-egress/verify.py`：确认补丁已应用与快照已铸、出口扫描器通过且只多一个调用方、跑 `tests/vnext/test_historical_model_egress.py`（27 例，约 15 分钟，全程拒绝 DNS/socket/SEC，服务商连接器换成受控的一个）、逐个注错（快类在前、遇错即停，记录首先抓到它的用例与它抛出的那一行）、从各世代清单读出会被补丁移动的世代，全部成立才封存 `offline-verification.json`。仓库里不跑它。注错有两条纪律，都是第一次运行犯过的错换来的：注错后的文本必须能编译（否则套件在任何用例之前就失败，却会被读成抓到）；落在 snapshot 按字节记录的文件上的注错先 mint 再跑、跑完恢复再 mint 并逐字节核对 snapshot（否则抓住它的是字节绑定而不是用例）。运行树必须先同步到当前 HEAD 并逐文件核对等于"HEAD + 两个补丁"——第二次运行就是在一棵落后的树里作废的。2026-09-26 封存的收据：27 例全过（881 秒，收据记的是合并 base 之后那次重跑；合并前那次是 850 秒），17 个注错 16 个由具名用例抓到、1 个在类夹具处被抓，13 个 #28 世代会被移动。

**Part III 修订的说明整段读**：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_historical_amendment_note`（source 层，13 例，94 秒，超时覆盖 480）。三份保存的修订（前身 FY2024、继任 FY2025、Southwest 附件链接更正）与八个在前身自己的字节里改一处的反例：另一个目的、在已批模式留空的中段塞 Item 8、多一句重述、指针指向另一份报告、缺"不变"声明、定义句点名另一家公司、第 15 项附有财务报表、说明超过 8 段。八个注错（`docs/evidence/issue47_history/part-iii-statement-review/fault_injections.py`）全部被抓，其中六个只被一条专门用例抓到。每份修订的报表类证据：同目录 `statement_values_request.py`（跑路线量当前被拒范围，零调用）。

**SEC 许可的授予分项**：`tests.vnext.test_historical_sec_session.TheApprovalIsReadGrantByGrant`（接线套件的一部分）。信封内但不在任何授予里的请求按名拒绝；授予字段、名称重复、信封宽于授予之并、账本根（绝对路径、不与 #28 的根或本检出重叠）各自按名拒绝。改动后照例 `python3 tools/vnext_historical_wiring.py` 重建收据（本轮 101 例、27 类）。
