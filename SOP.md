# SEC_metrics 标准操作流程导航

## 使用原则

每一步只包含动作、权威引用和验收。SOP 不复制会变化的脚本清单、测试命令或指标规范；发生冲突时，以代码、测试、能力契约和被引用的专项文档为准。`config/validation_source_policy.json` 必须把每个权威引用分类为运行/验收 source、snapshot artifact 或非批次治理角色；解释性非权威文档不能作为本表的运行权威。

## Issue #15 D-26 测试执行边界

`requirements/issue_15_v1/decision_register.json` 的 historical D-26 保留 `python3 tools/run_fast_tests.py --jobs 4` 与 fast/local 证据层级；该集合现在以successor smoke同时加载`issue_28_v1`和exact `issue_15_v1` parent。它继续排除全仓/双解释器、隔离 repository/worktree 和长串行套件，并保留single-flight、HTTP 402停批、UNKNOWN no-retry、零网络replay/rollback/restore等短小确定性测试。`.github/workflows/vnext-fast.yml` 在 PR 上运行同一命令；本地receipt与CI fast check都不是live、full acceptance或active Cutover。

## Issue #28 successor Requirement transition

PR-A has merged; its exact activation receipt is separately persisted as
governance evidence. PR-B first tests and commits the additive SourceScopeManifest,
scoped Reader and offline-session B0 interfaces. Source-specific audit, transport
tamper and real performance work follow that interface baseline. B0 is never a
production semantic freeze, cycle, Stage-A or live execution authority.

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 加载五文件snapshot、固定版本engine与记录parent | `requirements/issue_28_v1/`；`scripts/vnext/requirement_profile.py` | exact files/hash/size、engine及其dependencies、parent recorded hashes/snapshot bytes一致；parent不读取current root authority |
| 2 | 执行fragment transfer和typed safety bounds | `transfer_manifest.json`；`decision_register.json`；`invariant_profile.json` | 每个parent叶级义务唯一分类；D-01/D-24/D-26语义不可错配；同kind按ratchet独立；未知kind/fork/detached/tamper失败 |
| 3 | 重验真实artifact与历史兼容 | `tests/vnext/test_issue28_rework.py`；`tests/vnext/test_issue28_requirement_transition.py` | successor三个subtype的generation和完整identity均必填；真实round-trip及删字段负例通过；root drift不破坏R1–R3；0/0/0 egress |
| 4 | 保持Draft并提交返工证据 | PR-A一页summary与rework audit | 被拒head/closure不再请求批准；policy-content evidence不是activation。后续有效exact-head approval才可形成单独activation receipt；合并前不开始R4、不关闭#15/#24 |

## Issue #15 D-36/D-35 金额与资源安全边界

effective D-36 禁用仓库金额预算执法，花费权威是 `EXTERNAL_API_ACCOUNT_BALANCE`；仓库不定义 per-call、batch、owner 或 remaining monetary cap，也不在 provider egress 前以 estimated/actual cost 阻断调用。pricing、token、usage、cache 与 cost 只作非阻断审计。effective D-35 不含金额 `BUDGET_EXCEEDED`；`HTTP_402` 仍零自动重试并立即终止 execution 与 batch。payload/context/resource limit 仍是独立 terminal 安全类，不得重命名为金额门禁。
<!-- capability-anchor: BEHAVIOR.issue_15_repository_monetary_budget_disabled -->

## R5 live 与 review 边界

按 [Issue #12 R5 用户授权](https://github.com/wlvh/SEC_metrics/issues/12#issuecomment-5314176033)，live Reader 使用 `DEEPSEEK_API_KEY` 对应的官方 `deepseek-v4-flash` Chat Completions；HUMAN review 可选，缺失时 D-06 只允许明确标注的 SYSTEM approval。Issue #12 的历史 Hilton/Hyatt 样本说明不能替代 Issue #15 当前 matrix：当前 lodging 顺序为 Marriott FY2024 second layout → production semantic freeze → Marriott FY2023 post-freeze holdout → Marriott FY2025 fresh stability。FY2023 holdout只在同issuer、fiscal year/accession/source bytes均不同且至少两项material layout差异机械通过时成立；旧cycle response一律不能给新cycle qualification ordinal。首次 Cutover 不需要预先存在 active/previous pointer，而是导入 legacy A 后原子创建 B→A chain。

## Issue #15 R1–R3 历史 Requirement authority

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 读取冻结 Contract 与 transfer/baseline | `requirements/issue_15_v1/CONTRACT.md`；`requirements/issue_15_v1/transfer_manifest.json`；`requirements/issue_15_v1/baseline_manifest.json` | Contract SHA-256 为 `9a368d3cf7381d29adb0a1b041e882f74c1137b6e16d266300ef4ec21b9e19ec`；parent closure 与 foundation commit/tag/merge binding 一致 |
| 2 | 加载自包含 Decision 和 WB-1 receipts | `requirements/issue_15_v1/decision_register.json`；`requirements/issue_15_v1/legacy_semantic_producer_inventory.json`；`requirements/issue_15_v1/source_strategy_baseline_receipt.json`；`requirements/issue_15_v1/foundation_verification_receipt.json` | `load_requirement_snapshot(issue_15_v1)` 通过；D-01 与 post-freeze D-36、D-35、D-26、D-07 effective tips 精确。D-07 same-ID chain保留全表/原序/无selector、200000 inclusive普通门与family-scoped failure domain；Occupancy/RevPAR measurement authorization均已消费且response不可qualification复用。latest additive tip只把holdout fixture收窄到Marriott FY2023，并允许同issuer但fiscal year/accession/source bytes均不同且material layout差异机械通过；每个new-cycle plan仍需exact-head审核、新execution、provider usage存在且actual prompt<=200000。39 指标 producer/matrix exact set闭合；最高 foundation 证据仅为`FAST_LOCAL_ONLY`。 |
| 3 | 读取 inherited foundation | `requirements/ai_first_v3_3_1/` | 父目录 exact bytes 不变；其实现、evidence/publication/fail-closed invariants 被继承而不是重写 |
| 4 | 加载 WB-2 target routing 与 ratchet state | `config/source_strategy_registry.json`；`config/issue_15_release_plan.json`；`config/release_plans/`；`scripts/vnext/source_strategy.py` | 39 metric ID 恰好各有一条；source mode只有四种；index active tip与不可变R1→R2 parent/content chain一致；parent metrics/keys/retired producers分别为child子集，removed/unretired exact set为空；已发布R1/R2保留各自historical Requirement closure且current closure单独返回，不因post-publication D-07 tip重签；family literal不含通用词 |
| 5 | 验证 WB-2B deterministic source routing | `catalog/deterministic_metrics.json`；`catalog/event_routes.json`；`catalog/zero_ai_public_projection.json`；`scripts/vnext/deterministic_router.py`；`scripts/vnext/zero_ai_r2.py`；`scripts/vnext/public_projection.py` | 五个adapter只消费exact SourceReference/raw bytes；14财务与事件Result/Trace producer无legacy semantic input；8-K set由submissions shards和immutable acquisition receipt补集闭合；220 rows先独立渲染，legacy随后只作141×20字段oracle；C01/E03共用claim、E01事后parity、projection-independence gate及provider socket=0通过 |
| 6 | 验证 WB-3 invocation control | `scripts/vnext/invocation_control.py`；`scripts/vnext/ai_adapter.py`；`config/provider_model_runtime.json`；`tools/check_provider_egress.py`；Issue #15 effective D-35 与 D-36 | Cutover/CLI exact envelope经过AIInvocationPlan与owner-only reservation后才可进入唯一opener；无context factory和qualification capture fail closed；terminal reservation归档释放；402停批；429/timeout/recoverable 5xx同execution最多一次重试；dead-owner egress从磁盘恢复UNKNOWN且零重试；cost只观测；payload/context fail closed；UTF-8 byte上界不冒充exact token；paid count按billing class×真实egress marker推导；structured-only计数由空namespace与route closure推导 |
| 7 | 冻结 table transport / scope / task/request context authority | `scripts/vnext/table_payload.py`；`scripts/vnext/scope_contract.py`；`catalog/table_task_contracts.json`；`config/table_qualification_matrix.json`；`scripts/vnext/table_qualification_freeze.py`；`tools/freeze_table_qualification.py`；`tools/create_stage_a_validation_snapshot.py` | 继续验证全表可逆compact transport、scope/task/MetricSpec与shared/family-local closure。schema-v4 freeze必须为每个development source×task重建完整SourceReference与exact provider request SHA，并持久化`readiness_by_task_request`；普通`estimated<=200000`走`ESTIMATED_BOUND`，超限只允许有效exact attestation或`EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE`在各自冻结范围内裁决。当前new-cycle lodging task/request均ready；financial仍为`EXPANDED_GRID_RESOURCE_LIMIT`。qualification仍需独立exact-head授权和新execution，response usage缺失或超限必须terminal/no retry/stop later plan；旧response不得复用，active/root不变。 |
| 7 | 只实施当前获准的 WB/ratchet | Issue #15 对应章节；`architecture.md`；`TESTING.md` | 不提前实现后续 WB；未获授权不得发起真实模型调用 |
| 8 | 对未决的lossless context minimization只生成离线可复算证据 | `tools/investigate_table_context_minimization.py` | exact source×task/provider-envelope分解与五候选逐字段round-trip闭合；连续运行receipt ID相同；不改production serializer/task contract，不把机器可逆写成模型准确率已验证，三类egress为0 |
| 9 | 对JPM expanded-grid策略只生成完整流式census与option matrix | `tools/investigate_jpm_financial_grid.py` | exact HTML/table/source/expanded/blank/span/nesting/size与100000首次触发点闭合；连续运行receipt ID相同；A/B/C均未选择，不改resource limits、不筛表/分片/换source，三类egress为0 |
| 10 | authority/matrix/readiness变化后重建freeze、Stage-A overlay与owner packet | `tools/freeze_table_qualification.py`；`tools/create_stage_a_validation_snapshot.py`；`tools/create_table_qualification_owner_decision_packet.py` | source commit先冻结；旧objects保留；pointer只指向新content-addressed objects；packet分开OWNER_APPROVED/STILL_UNDECIDED并绑定两份调查receipt、空live-ready set、NOT_RUN actual tokens、R2 root equality与0/0/0 egress |
| 11 | Stage C-A只实现并离线验证one-shot lodging token measurement与JPM guarded benchmark | `scripts/vnext/table_context_measurement.py`；`tools/vnext_table_context_measurement.py plan`；`tools/benchmark_jpm_full_materialization.py`；latest same-ID D-07 tip | measurement plan exact绑定Marriott immutable attempt、lodging occupancy task、serializer v2、prompt/schema/provider request及protected closure；mock证明marker前不消费、marker后永久消费、最多一次且零重试、evidence无qualification/publication credit，普通200000门不变。JPM只在512 MiB hard RSS/address-space、120秒wall、no-network全部可用时以child-only 187142 materialize；不可可靠实施时必须在child前停止并记录`NOT_RUN_RSS_GUARD_UNAVAILABLE`。不得运行token `execute`，real model/paid/SEC=0/0/0 |
| 12 | Stage C-B仅在独立exact-head授权后执行一次并永久停止 | `tools/vnext_table_context_measurement.py execute`；review 5014622571的`AUTHORIZE_ONE_TOKEN_MEASUREMENT` | exact head `451dd693175bea6c1196a09989c60017e96d63e7`只执行一次：HTTP 200，provider usage为160937 prompt、576 completion、161513 total，real model/paid/SEC=1/1/0。marker已永久消费authorization，不得第二次执行；结果只有usage-measurement语义，不进入qualification/publication |
| 13 | 保留Stage C-A历史packet并生成Stage C-B terminal overlay后停止 | `tools/create_stage_c_a_packet.py`；`tools/create_stage_c_b_packet.py --validate`；`tools/check_validation_snapshot.py` | Stage C-A packet继续原样保存pre-egress 0/0/0事实，不得重签；Stage C-B packet逐byte绑定review、plan/cycle/authorization、marker、raw response、usage evidence、active/root与1/1/0计数。JPM仍为NOT_RUN/null与`F3_NEED_MORE_EVIDENCE`，historical R2只允许source drift；不得开始qualification、R3/R4或publication |
| 14 | 实现exact-binding context attestation并重建当前离线authority后停止 | `scripts/vnext/table_context_attestation.py`；`scripts/vnext/table_context_comparison.py`；`scripts/vnext/stage_c_context_packet.py`；`tools/create_table_context_feasibility_attestation.py --validate`；`tools/investigate_sibling_table_context.py --validate`；`tools/create_stage_c_context_attestation_packet.py --validate` | same-ID D-07 successor、attestation与当前request binding exact；attested task context feasible但measurement response不可qualification reuse；sibling状态=`EXACT_CONTEXT_EVIDENCE_REQUIRED`、reason=`NO_SOUND_CROSS_TASK_TOKEN_BOUND`；schema-v4 freeze/Stage-A/schema-v4 owner packet/Stage-C packet均content-addressed且旧对象保留；lodging family overall=false、financial=`F3_NEED_MORE_EVIDENCE`、`live_ready_family_ids=[]`、active/root不变，本PR real model/paid/SEC=`0/0/0`。不得请求新measurement、执行qualification、修改financial resource policy、开始R3或publication。 |
| 15 | 验证已消费RevPAR one-shot terminal与双context proof | `tests/vnext/test_table_context_measurement.py::TableContextMeasurementTerminalTest`；`tools/create_table_context_feasibility_attestation.py --validate --task-contract-id ...` | reviewed head `290c1119…`唯一执行为HTTP 200，usage 160928/535/161463、1/1/0、retry=false；attestation `d3824ed2…`与occupancy `dc8cb1d1…`均exact通过且无qualification/reuse credit。两个旧authorization均永久消费，禁止再运行旧measurement plan或execute。 |
| 16 | 按matrix phase完成lodging qualification并形成R3前置证据 | `tools/vnext_qualification.py` 的 table-plan、table-execute、table-freeze、table-freeze-status；latest D-07 live qualification scope | 两个task依次完成Marriott FY2024 second-layout新execution→FROZEN、production semantic tree/ledger-prefix freeze、Marriott FY2023 post-freeze holdout新execution→FROZEN、每task三个Marriott FY2025 fresh ordinals。FY2023必须同时满足same issuer、different fiscal year/accession/source bytes及至少两项机械layout差异；所有plan绑定source/request SHA/context basis并经exact-head review。每个sample必须有new WB-3 execution、provider ledger、Evidence、Review、Result、PASSED/FROZEN closure；usage缺失或actual prompt>200000即terminal、零重试并停止后续plan；measurement或旧qualification response禁止复用。financial仍未授权。 |
| 17 | 验证已完成的prompt/schema-v3 context历史闭包 | latest same-ID D-07；`tools/create_table_context_feasibility_attestation.py --task-contract-id ... --validate` | caption必须来自selected target table自身非空caption raw text，否则从同一目标表的一格复制八字段locator与exact raw text，禁止跨表或借邻近正文；复制值首尾空白与JSON转义必须逐字保持。Occupancy与RevPAR one-shot measurement均已消费、retry=0、usage-only/no-credit，禁止新增measurement或复用response。当前qualification只可走步骤16的new-cycle exact-head-reviewed execution。 |

Fresh stability必须按Occupancy 1 → RevPAR 1 → Occupancy 2 → RevPAR 2 → Occupancy 3 → RevPAR 3推进；每个ordinal的两个task均FROZEN前不得进入下一ordinal。相同task的三轮provider request bytes可以相同，但每个qualification task plan使用独立plan-owned WB-3 namespace并必须产生新的provider execution；`REUSED_SUCCESS`没有fresh credit。任一usage/terminal失败停止剩余序列。

## 快速入口：只读取现有结果

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 先读取 run manifest | `outputs/validation_run_manifest.json` | `result` 不是 `PASSED` / `PASSED_WITH_CAVEATS` 时立即停止验收 |
| 2 | 独立验证 source 与 artifact binding | `python3 tools/check_validation_snapshot.py`；`docs/validation_snapshot_provenance.md` | provenance 存在；source-input tree clean/等价；关键 artifact SHA-256 与 size 全部匹配 |
| 3 | 阅读报告和具体结果 | `REPORT_十公司财务指标.md`；`outputs/metrics_matrix.csv`；`outputs/metric_evidence.csv` | verdict、value/status、期间、口径和 evidence 能闭合 |
| 4 | 复核限制和人工责任 | `interact.md`；`docs/business_user_guide.md` | 未把 light、caveat、NOT_EVALUATED 或历史快照写成 full PASS |

## SOP 1：SEC 阶段 00-12 完整批次运行

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认公司范围、CIK role、指标适用性和有效 SEC 请求身份 | `config/`；`01_SOP_SEC_10公司单年指标计算_直接SEC.md`；`02_指标定义_SEC_10公司单年指标.md`；`CIK变更应对方案.md` | 配置结构有效，范围、身份连续性和口径已由运行负责人确认；`01_SOP...` 的 M0–M7 仅作业务概念说明 |
| 2 | 以`sec_pipeline.py --workspace-dir <absolute-isolated-root> <stage>`在干净candidate数据根按需执行SEC采集与legacy非迁移阶段 | `README_RUN.md`；`TESTING.md` | 源码repository root与含active pointer的workspace不运行legacy Stage04/09/11；migrated写入全部fail closed；candidate evidence/outputs不冒充active |
| 3 | 通过vNext operator形成complete staging并准备formal publication；full live path在release planning前固定执行SEC Stage00/01/02/03/05 acquisition/inventory | 本文件“vNext operator与正式Cutover”；`README_RUN.md` | acquisition原样命令、ledger合法tail与inventory receipt已持久化；qualification、live有效 review、strict parity、old-path migration与publication gates全部满足 |
| 4 | commit后对new/rollback/restore分别执行一次公开terminal cycle | `python3 tools/run_acceptance.py --scope full --execute-live`；`tools/vnext_terminal_cycle.py`；`TESTING.md` | 每轮只启动一个进程并pin一次PublicationView transaction，依序完成Stage10 Golden、Stage11 report、Stage12 active validation、snapshot publish/verify；三轮均通过，最终恢复new publication并生成full receipt |
| 5 | 交付root mirrors、报告、证据和限制 | `interact.md`；`docs/business_user_guide.md` | reviewer能从active pointer/provenance追溯到bundle、report、metrics、evidence和request ledger；latest失败不覆盖active |

## 专项：vNext operator 与正式 Cutover

<!-- capability-anchor: BEHAVIOR.vnext_freeze_accepts_audit_validation_states -->
<!-- capability-anchor: BEHAVIOR.vnext_publication_requires_passed_validation -->
<!-- vnext-validation-state-contract:start -->
| Validation 状态 | OPEN Run 可 freeze | Candidate publication 状态门 |
|---|---|---|
| `PASSED` | 允许 | 满足本状态门 |
| `FAILED` | 允许 | 禁止 |
| `NOT_RUN` | 允许 | 禁止 |
<!-- vnext-validation-state-contract:end -->

Freeze 保存不可变审计与 replay 事实，不代表 validation 通过；publication 仍须同时满足 `PASSED` 和其他全部发布门。

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 对现有 inherited operator 读取父 FSD/R2/R3 与历史实现闭包；对任何后续开发先读取 Issue #15 authority | `requirements/issue_15_v1/`；`requirements/ai_first_v3_3_1/` | 新开发只以 Issue #15 / `issue_15_v1` 为入口；WB-1 未把新 D-01/D-26 语义提前接入现有 Reader/Cutover runtime |
| 2 | 用同一 operator 创建、查看并推进 Run；recorded 只替换 transport/source acquisition | `python3 tools/vnext_operator.py --help`；`interact.md` | recorded 时 socket=0、root/active 不变；live 必须显式 `--execute-live`，key 只读 `DEEPSEEK_API_KEY`；SEC organization 固定 `axaxl`，email 自动读 `config/sec_config.json.contact_email`，`SEC_CONTACT_EMAIL` 可显式覆盖 |
| 3 | HUMAN 可选地复核 `review.md` 和完整 ReviewUnit，并通过 `review list/show/decide` 追加单链决定 | `tools/vnext_operator.py review`；`tools/vnext_review.py` | 已有 HUMAN 决定优先；缺决定时 D-06 写入可审计 SYSTEM approval，SYSTEM 不得伪装为 HUMAN，Evidence/compatibility publication gates不放宽 |
| 4 | release input plan先绑定exact source的latest verified request attempt及locator class；finalize/freeze 后做无网络 replay，再由 complete BatchManifest 与 Projector 形成 strict-compatible staging | `architecture.md`；`TESTING.md` | recorded legacy locator必须逐path/hash/headers/size验证并在closure显式绑定tier/class；formal live只允许immutable attempt并拒绝legacy。所有 Run 都是 `PASSED/FROZEN`；十公司×四指标 exact set、N/A、期间、字段/evidence/reconciliation parity 全部通过；WITHHELD 阻止整批发布 |
| 5 | WB-4+获准后才可恢复受控capture、第二布局与holdout资格顺序；PR-2保持入口关闭 | `tools/vnext_capture_qualification_fixture.py`；`tools/vnext_qualification.py` | 当前capture在SEC/provider构造前稳定返回`AI_QUALIFICATION_EGRESS_NOT_ENABLED`；未来恢复时必须接入完整WB-3 plan/execution/reservation/acceptance，且仍满足second→freeze→holdout顺序与独立company/CIK/accession/source |
| 6 | 只在全部资格和凭据满足后执行 live Cutover；同一命令先执行固定SEC acquisition/inventory，再依次验证 new→rollback→restore | `python3 tools/run_acceptance.py --scope full --execute-live` | 三次live attempt的portable audit closure、十公司staging、verified legacy A→formal B commit，以及每轮单次调用`tools/vnext_terminal_cycle.py`、共用同一pinned view完成五项gate均真实产生并返回0 |

### Cold-start recorded fixture 与 sandbox publication

运行负责人可先执行 `python3 tools/vnext_operator.py --json fixture list`，再用 `fixture show --fixture-id <id>` 核对 catalog/source/provenance binding。随后以同一组显式 UTC 值运行：

```bash
python3 tools/vnext_cutover.py --json --fixture-id <id> \
  --workspace-dir artifacts/vnext/recorded-<workspace> \
  --legacy-snapshot-dir outputs \
  --validated-at-utc <UTC> --committed-at-utc <UTC>
```

HUMAN review 是可选停点：若具名 HUMAN 在最终化前写入 decision，系统使用该决定；否则 D-06 写入固定身份的 SYSTEM approval 并继续 finalization/freeze/replay、complete Batch/Projector，随后在 `<workspace>/recorded-publication` 内 prepare、CAS commit 和 PublicationView read-back。recorded workspace第一层固定为`recorded-*`，默认`recorded-cutover`；live固定使用repository-owned `artifacts/vnext/cutover`，不得传`--workspace-dir`，否则在load/write前以`LIVE_WORKSPACE_OVERRIDE_FORBIDDEN`失败。live core同时exact固定module-owned repository、`outputs` legacy snapshot与publication root；每次有效live调用（包括 HUMAN 或 SYSTEM resume）都fresh执行SEC acquisition，再复用exact pinned semantic plan，本次receipt必须进入current audit/full binding。整个 recorded flow socket=0，正式 active pointer/root mirrors、formal namespace与SEC ledger前后 exact 不变。测试使用的 `TEST_ONLY_EXPLICIT_REVIEW` 不能作为正式 review 或 full evidence；generic `publish --commit` 仍是 fail-closed tombstone。

sandbox publication 的 request closure按证据层级验证：recorded 可接受历史ledger row明确声明、且body/headers的repository path、hash、size全部匹配的唯一`LEGACY_WORKING_LOCATOR`，portable closure必须保留locator tier/class；缺失、歧义或bytes漂移均失败。formal/live仍只允许`IMMUTABLE_ATTEMPT`，legacy class稳定返回`LIVE_SOURCE_ATTEMPT_INCOMPLETE`，不得因recorded可重放就升级为formal证据。

`python3 tools/run_acceptance.py --scope recorded` 的最高状态是 `PASSED_FAST_LOCAL_ONLY`，且不得修改正式 pointer、root mirrors、formal namespace或SEC ledger。generic operator `publish`只能准备inactive recorded bundle；public generic formal receipt/commit API会fail closed。Issue #15 R1 由 `python3 tools/vnext_zero_ai_release.py r1 --committed-at-utc <UTC>` 唯一执行A→B→A→B。R2只在exact R1 active上运行 `python3 tools/vnext_zero_ai_release.py r2 --committed-at-utc <UTC>`：以submissions current/history shards和immutable acquisition receipt补集闭合完整8-K集合，先独立生成22指标/220坐标与完整public rows，再以legacy作141×20字段oracle，验证79个structural additions、309-key matrix、事后event-key parity、projection independence与retirement后CAS提交。R3只在exact R2 active上运行 `python3 tools/vnext_zero_ai_release.py r3 --committed-at-utc <UTC>`：重验十个committed lodging qualification terminals，重新执行DerivedAsset/Evidence/Review/Calculator，为B10/B11生成20-coordinate Batch，并以18个零AIstructural Runs形成24指标/240累计vNext keys/327-row matrix；CAS bundle还必须重验qualification binding、portable closure与root mirror read-back。当前active为修正版R3、previous精确为R2；发布期间的R3→R2 rollback→修正版R3 switch chain已持久化。R1/R2两档real model egress和paid call为0；R3包含其十个qualification真实模型execution。当前active仍只是partial ratchet，不能替代financial/text qualification、39指标最终Cutover或full acceptance。

recorded acceptance 当前要求 macOS `/usr/bin/sandbox-exec` 对整个子进程树拒绝网络，以literal保护正式pointer/mirrors/sidecar/ledger、pointer lock与latest run status，以subpath保护live Cutover、qualification、request attempts、publication、publication switch intent/receipt、fault与live audit tree；缺失时稳定返回 `OFFLINE_PROCESS_SANDBOX_REQUIRED`，不得降级。runner 还会从 recorded 与 terminal-validation 子进程剥离 live secrets，绑定 clean source/Requirement、本次隔离 semantic/scalability exact artifacts，并在前后重验formal namespace exact tree与pointer lock/latest status bytes。持久receipt用`$REPO_ROOT`、`$ACCEPTANCE_OUTPUT`、`$PYTHON_CURRENT`、`$PYTHON39`、`$SANDBOX_EXEC`等portable token替换host路径，并对实际runtime binary保存SHA-256；本机绝对路径不落盘。每个new/rollback/restore terminal cycle只启动一次`tools/vnext_terminal_cycle.py`，在单进程、单次pin中完成Stage10→Stage11→Stage12→snapshot publish→verify。若 recorded 仍产生 root drift，会先恢复原 bytes 但本次 receipt 保持失败；namespace/ledger漂移fail closed且不删除可能的并发合法append。full Cutover 子进程若在非零、`HUMAN_REVIEW_REQUIRED` 或非法返回时意外 commit，会恢复调用前 predecessor（首次无 pointer 时恢复原 root bytes）并保留原 blocker。默认 7200 秒只是单 command timeout 上限，超时仍为 `FAILED`。

publication switch在修改mirror前于独占锁内写`outputs/publication_switch_intents/<sha256>.json`，绑定previous/proposed pointer、上一switch tip、模式及每个mirror的存在性/hash/size。共享锁reader遇pending、多份或tampered intent只会fail closed，不做恢复或清理；独占锁writer/recovery若pointer已是proposed则补齐switch receipt并从proposed bundle重建mirrors，若仍是previous则移除本事务receipt、恢复previous状态，再删除exact intent；其他pointer状态失败。hard crash恢复不运行旧parser，也不改变request ledger。

## SOP 2：分层验收与失败定位

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 按变更类型选择最小且充分的测试层级 | `TESTING.md` 的测试层级与变更决策表 | 每条适用命令、结果和未运行原因已记录 |
| 2 | 先读 validation run manifest，再运行 snapshot checker | `README_RUN.md` 的验收顺序；`docs/validation_snapshot_provenance.md` | stale run、dirty source、tree mismatch 与 artifact tamper 已先排除 |
| 3 | 再定位 unittest、Golden、repair、coverage 或请求失败 | `TESTING.md` 的失败定位 | 失败已对应到具体 test、check_id、company/metric、source path、artifact digest 或请求记录 |
| 4 | 修复真实原因并重跑受影响层及下游 gate | `TESTING.md`；`architecture.md` 的阶段依赖与错误模型 | 没有放宽断言、静默跳过、重签旧证据或以 light 结果冒充 full |
| 5 | 核对生成 artifact 与工作区范围 | `TESTING.md` 的写入副作用；`PR_Checklist.md` 的变更范围 | `git status` 只包含预期文件，失败证据与处置可复核 |

## SOP 3：PR 发布（仅用户明确要求时）

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认发布授权、feature branch、base 与 patch 范围 | `PR_Checklist.md` | 用户已要求发布，当前分支不是 `main`，base 为 `main` |
| 2 | 完成文档影响、测试证据、已知限制和 Review 记录 | `PR_Checklist.md`；`.github/pull_request_template.md` | PR body 与真实 diff、测试结果和未解决决策一致 |
| 3 | 按授权执行 commit、push 和 PR 创建 | `PR_Checklist.md` 的分支、提交与创建规则 | 命令成功并返回真实远端分支与 PR URL |
| 4 | 向用户交付发布结果 | `PR_Checklist.md` 的最终核对 | draft/ready 状态、URL、测试与限制均已明确报告 |
