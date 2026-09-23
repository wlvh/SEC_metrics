# SEC_metrics Agent 工作入口

## 开工必读：产品边界与 Issue 级交付（2026-09-11）

先实时读取 [Issue #28](https://github.com/wlvh/SEC_metrics/issues/28)：第1节保存三个最终目标，第3–4节保存当前任务和剩余责任，第5节保存协作原则，第6节区分权限与证据。下文带历史PR编号的阶段状态只解释当时实现，不覆盖实时Issue、最新用户委托及其实际权限；历史规则和证据仍按原绑定读取。

### 只研究指标必需的细节

按公司财报已报告的会计分类和已批准MetricSpec计算，核对数值、单位、期间、主体、账面计量及必要包含关系；不因发现供应商相关项目等线索，自动扩建隐性债务重分类、供应链分析或审计级全面尽调。B06仍遵守已批准的借款、债券、融资租赁及银行/工业范围，不因简化工作擅自删掉应计组成。关键词或标签仅是线索，不能单独证明纳入、排除或完整性；已发现的直接矛盾须在限定范围内处理，无法证明时准确限制该指标。不得临时采用“小额忽略”、猜数、改N/A或把小计当完整总额。需要改变业务口径时按既有修订机制对齐，保留历史语义。

### 日常运行零必需人工操作

资料充分、口径适用的受支持输入，必须自动完成获取、解释、计算、验证和更新；不能依赖逐公司/逐年填写关系、指定单元格、审批数值、修改代码或人工补数队列。限定自动处理后确有披露不足或冲突时，自动形成带来源和具体原因的状态，并继续处理不受影响的指标；历史有效结果只能按原期间显示，不能冒充本期成功。资料足够但程序不会处理属于开发缺口，不能伪装成披露不足。验收同时检查零日常人工依赖与真实正向完成，不能靠大量拒绝或NOT_EXTRACTED过关。开发独立审阅及少数业务/资源/发布决策与常态人工处理分别登记。

### 一次总委托，连续推进，少拆 PR

获得Issue级执行委托后，默认一个主PR、多个可审查提交；在其授权范围内连续完成调查、实现、独立审阅、修复、测试、必要接线、归档和集中交付，不因完成预检、一次测试、commit或子模块而停工回问。内部按风险分解并持续验证，不把所有审阅堆到最后。新增PR须有独立发布、风险隔离或并行协作的实际理由，不能按机械步骤拆分。进度是告知，报告后继续；从Issue、提交及证据恢复上下文，不让用户反复搬运长交接。未获Issue级总委托时，在现有有限委托内采用相同方式，不越过其明确范围和停点。

### 仅在必要决策处对齐

普通代码、解析、接线和测试问题在范围内自行解决；单个坐标的内容失败不阻断无依赖的其他工作。改变指标含义/正确性标准/产品范围、超出资源或权限、执行未授权生产操作，或核心路线经有界尝试仍不成立时，集中给出证据、影响、选项和推荐。来源真实性、权限、调用身份/计数UNKNOWN或共同验证器可能错误接受时，暂停受影响动作，继续仍然安全且获准的离线工作；禁止无限重试。必要对齐不扩展为每步审批。

### 复用能力，用业务增量衡量进度

优先复用定义、来源、Evidence、Calculator、Run和发布链，按交易模式、行业与主体范围、披露结构建立通用规则，不按公司名/CIK/固定原件写通过特例。合法缺失、规则未实现、来源歧义与实现故障分别报告；评估错误接受、误拦截、自动完成和新增维护成本。每次集中交付说明新增正式能力、减少的日常人工操作、退出的旧生产依赖或消除的关键路线不确定性，PR/文件/测试数量不代替进展。按实际差异验证，复用未变部分的有效证据；保留必要正反例和真实材料验收，不重建平行平台、不无限追加局部完善。十家公司×39指标的承诺不暗中扩展为几千家公司全面通过。

### 原则记录与执行授权分开

一次明确授权可覆盖其范围内的分支、commit、push、PR和连续工程步骤，不逐项重复询问；开发授权不自动授予新费用、合并、生产采纳或active切换。用户现已正式采用[Issue #28连续开发与完整交付总委托](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5636808102)，替代PR43旧局部开发范围与机械停点，按十家公司×39指标三个最终目标连续实施。旧关闭额度及原失败不恢复；新增费用集中核实申请，未获批继续合法离线工作。旧生产入口随相应正式采纳退出，不能提前破坏仍在使用的入口。cbede80的原则记录及旧评论保留历史含义；当前可恢复执行状态见`docs/evidence/issue28_continuous/`。

### 2026-09-13 最终恢复批准

[新增总预算与 B13 代登记](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5651558538)来自用户本次对话明确批准；不是代码 APPROVE。provider240/paid240/SEC80 累计，deepseek-flash/Chat Completions/WB-3/SecHttpClient，原资源限制、零自动重试；旧额度不恢复。D-36 保持，无仓库金额预检/预留/上限或账户操作。B13仅 Ford/Enphase 的可比实际产量÷可用产能，以后继 Spec 实现，旧 Spec/Run不改。

新 `continuous_call_policy`、`continuous_call_ledger`、`continuous_semantic_calls`、`continuous_call_wiring` 及 `issue_28_v14/PROFILE_DRIVEN_V15` 负责本轮明确绑定，不能走因模型配置字节变化而失效的 Issue15 默认入口或借用旧v8阶段。固定总账 `/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`；真实调用要求先有绑定的离线接线证据。代码/测试/新批准不授 Ready、合并、采纳、部署或active切换。

ChatGPT review5189571246 与用户转交 Fable5.1 按6341530及明示模块登记；不是全PR批准。Codex独立子任务9月17日前不重试/换模型/重置额度，用户转交模块报告补覆盖。未覆盖模块、安全开发、最终验收责任分别列在当前执行材料中，不再把预算/B13待批或旧340问题索引当成停工原因。

780d9ba 的原生CI因未冻结V14执行字节绑定未同步而失败，当前只更新该草案的执行绑定，原e1ac五文件与失败保存在`docs/evidence/issue28_continuous/runtime-binding-repair-780d9ba/`。V15及其新请求类型延迟到实际选择时导入，旧普通运行包不必加载新调用模块。`capacity_utilization_source.py`、`config/b13_production_capacity_v1.json`和两个B13后继Spec目前只完成来源候选及可比量Calculator开发检查；尚未授予数值来源赋义、原生Review/Run、完整B13或生产信用。

普通Company Facts现复用已批准的REQUIRE_CONTINUOUS守卫，为Paramount B02/B04/B05/B07生成主体不可比的NOT_MEANINGFUL；B08/B09数值保留。Run只对经过完整原件/目录重算的确切该类结果允许无数量输入，不放宽其他守卫。六项原生/两项重签攻击/复制包冷读见`docs/evidence/issue28_continuous/ordinary-continuity-policy/`。这不是数值披露缺失结论，也不是改变指标口径。

`continuous_sec_acquisition.py`与`tools/vnext_continuous_sec.py`为本轮新有限SEC路径：原SecHttpClient/零重试/不可变尝试/日志前缀/同一总账，先验证完整离线接线再发真实请求。创建者登记acquired检查记录，旧recorded测试记录不升级。新获取信用只随实际选中的新请求传播；失败URL不污染其他成功来源。审核材料与可验证复用原件索引在`docs/evidence/issue28_continuous/ordinary-sec-acquisition/`。总预算仍240/240/80，不授生产、长期运行或旧额度复活。

### 2026-09-22 原110受限恢复

170完整离线诊断另见`b13-170-source-audit/`。原111 B1022被确认将制造成本利用率归为产品容量；SUCCEEDED历史保留，当前复用受阻，不能为保留旧成功放宽定义。来源角色检查的两项具体P2在ec311e2d由用户转交外部限定复核结案；原代理发现仍保留历史原义，不扩成全B13批准。后继有含义角色V3仅为显式离线候选，真实申领前阻断；78779bf限定离线独审通过，不证明模型准确或授真实验证，见`b13-meaningful-role-v3/independent-review/`。

本轮a87db7f限定独审及新接线已完成；170紧凑响应完整但重复发现被拒，171 Ford HTTP402使PROVIDER停止。累计122/122/49、余118/118/31；110机会已消费，未获171恢复或113/114/170同摘要重发许可。当前事实以execution-state/continuation和Issue28第3节为准。

后续112—114修复不重开110：原始证据采用无损序列化，历史canonical及业务摘要算法不变；D04纠正特定活动与条件性风险的类别重叠，B13显式紧凑合同保留来源及必评集合。新增差异独审与最终绑定接线分别验收；摘要不变的113/114原样重发仍未授权，D03不调用。当前进度见`failures-112-114-repair/`与执行状态。

用户已采用[110一次恢复授权](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5775635612)，确认充值已处理；不查询账户或发探针。保持原账本/binding/锚点、240/240/80及全部旧失败。`continuous_recovery_110.py`只绑定110的HTTP402、无可用输出、终态和业务摘要；新claim消费一次机会，原件不改。新停止仍生效，D03不调用，至少39基础资源缺口暂缓决定。恢复实现/绑定/限定独审/离线入口检查完成后才能执行原业务请求，不能把授权登记写成已恢复。

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

### 开发、复核 successor vNext Ratchet

当前 PR32 的正常 R4 接线首先读取 `requirements/issue_28_v3/` 与
`docs/r4_minimal_fix/README.md`。标签政策已获 owner 批准；exact-head
激活、implementation merge、新 live plan/grant 仍按既有顺序独立完成。
旧 v2 快照、engine 与证书目录只按原规则解释，不改历史失败。

```text
requirements/issue_28_v1/CONTRACT.md（successor outcome/boundary）
→ requirements/issue_28_v1/decision_register.json（policy-content authority）
→ requirements/issue_28_v1/invariant_profile.json（typed evaluator routing）
→ requirements/issue_28_v1/transfer_manifest.json
→ requirements/issue_28_v1/baseline_manifest.json
→ requirements/issue_15_v1/（immutable R1–R3 compatibility authority）
→ requirements/ai_first_v3_3_1/（immutable inherited foundation）
→ architecture.md「vNext Cutover 实现」
→ TESTING.md「vNext recorded / formal Cutover」
→ SOP.md「vNext operator 与正式 Cutover」
```

Issue #28 / `issue_28_v1` 已经由PR #29合并及独立治理receipt激活；旧被拒head/closure永不恢复为审批候选。当前PR #30的`issue_28_v2`是未激活的离线policy revision：在上述阅读链前先读v2五文件和`docs/r4_offline/README.md`，不得把代码/测试完成当成exact-head activation。版本注册表保留V1/V2/V3 engine，Requirement revision与engine generation是不同编号；同kind可按ratchet拥有多个实例。Decision Register是policy-content authority，transfer按parent叶级义务唯一分类。旧RUN/Publication保留hash-only字节，旧ISSUE_15_RELEASE_PLAN保留原id/closure；三个SUCCESSOR_* subtype强制generation与id/closure/hashes。historical parent只从记录hashes与冻结snapshot重建，不跟随current root漂移。PR22 archive无credit/reuse；两份SEC acquisition已完成且quota耗尽，provider/paid/live/publication仍未授权，PR30不得自动Ready/merge或启动PR-C。

当前lodging authority在owner批准的compact prompt、same-target-table八字段locator、Marriott FY2024 second layout、Marriott FY2023 post-freeze holdout和Marriott FY2025 fresh source上冻结。Occupancy与RevPAR context均由各自provider-reported actual usage证明不超过200000；qualification没有复用measurement response。SECOND_LAYOUT、POST_FREEZE_HOLDOUT和三个FRESH ordinals按ordinal-major顺序形成十个独立provider execution，全部Evidence PASS、D-06 SYSTEM APPROVE、Result PUBLISHED、validation PASSED且usage terminal通过。任何新exact-head push不会重签这些已提交的无关family证据。PR-B的JPM/BAC/Citi已通过同一生产parser、512MiB/no-swap/network-none测量，max_total_cells仅提高至210000；这只解除本地materialization阻断，不授予financial live资格。

代码已具备同一 recorded/live operator、D-06 optional HUMAN/SYSTEM audited Review、固定 DeepSeek/SEC 边界、资格门、legacy migrated producer 退出、PublicationView consumers、正式 publication/rollback primitives 与 new/rollback/restore 终态编排。Issue #15 R1 已只读导入 verified legacy A，以 immutable SEC attempts 冻结十公司 B01/B03 successor B，并真实完成 A→B、rollback→A、restore→B。R2 又以 commit-bound immutable SEC blobs、完整submissions current/history shards和request-ledger绑定的acquisition receipt补集累计加入其余14个DET_ONLY与C01/E01–E05。R3在R2上新增lodging B10/B11：重验十个qualification terminals，为两个APPLICABLE fresh坐标生成模型Result，并为其余18个坐标生成零AI`N_A_STRUCTURAL` Runs。当前active为R3的24指标/240个累计vNext Result keys/327行public matrix，previous精确为R2；发布期间还真实完成R3→R2 rollback→修正版R3。该事实仍不证明financial/text、39指标最终Cutover或full acceptance。

## 1. 文件简介

### PR-B additive offline interfaces

- `scripts/vnext/source_scope.py`: pinned source/window certificate over full
  source/asset/task authority, with native synthetic Evidence replay.
- `scripts/vnext/scoped_reader.py`: separate successor scoped request/attempt
  entrypoints; no legacy Reader semantics or provider opener changes.
- `scripts/vnext/offline_execution_session.py`: process-local exact immutable
  bytes, deterministic operation counters and one final independent disk replay.
- `docs/r4_offline/closure_impact_map.md`: pre-edit A/B/C/D path classification;
  B0 is not freeze/cycle/Stage-A or live authority.
- `scripts/vnext/live_scoped_reader.py`, `r4_live_plan.py`,
  `r4_live_authority.py`, `r4_live_qualification.py`: dormant R4 production
  request/plan/owner-capability/invocation composition. Offline records cannot
  be relabelled live; successor transport policy is Requirement-bound.
  Nine base calls plus three risk-stability ordinals require twelve fresh
  executions; structured positives and four zero-call classes never enter the
  provider set. Prior failed/UNKNOWN/incomplete terminals block later sockets.
- `scripts/vnext/r4_run_store.py`, `r4_structured_run.py`,
  `config/r4_fixture_company_authority_v1.json`: explicit native scoped and
  structured Run/replay with source-bound subject/period authority, original
  wire/marker/reservation closure and no individual qualification/publication
  credit. Large immutable source contexts are process-local, not general caches.
- `tools/vnext_r4_qualification.py`: `draft` is offline-only; `plan`/`execute`
  belong to a separately authorized future PR-C. Current PR-B only runs
  isolated recorded tests and portable replay, not live qualification.
- `scripts/vnext/r4_release.py`, `r4_projection.py`, `r4_publication.py`,
  `config/r4_public_projection_v1.json`: private successor release authority,
  native 6+54 projection and typed immutable R4 bundle. Frozen R3 authority is
  separate from mutable switch state; recorded rehearsal has no live credit.
- `tools/vnext_r4_release.py`: future authorized PR-C stage/validate/publish/
  read-back/rollback/restore/active-terminal. Current PR-B uses only isolated
  private rehearsal and must not activate v2 or change the actual R3 pointer.
- `docs/evidence/issue_28_transition_activation.json`: persisted exact PR #29
  merge-governance receipt, not a provider/SEC execution grant.
- `requirements/issue_28_v2/`, `scripts/vnext/requirement_profile_v3.py`: pending
  A03/A12 composite, A13 international net revenue and bounded parser policy;
  retained v1 snapshot/V1/V2 engines must stay byte-identical.
- `config/r4_fixture_matrix_v1.json`, `catalog/r4_v2/`,
  `scripts/vnext/r4_offline_qualification.py`: exact six-task source-specific
  offline corpus and native structured/Evidence replay, not a live cycle.

### 核心治理与工作流文档

- `AGENTS.md`：agent 入口、文件地图、项目规则与文档关系。
- `architecture.md`：当前 CLI 批处理架构、边界、数据流、状态、错误与扩展点。
- `capability_contract.json`：当前能力、限制、责任和行为承诺的机器可读真相源。
- `interact.md`：CLI 与文件交付中用户可观察行为和验收不变量。
- `docs/business_user_guide.md`：面向首次读取结果的业务人员的派生指南。
- `docs/validation_snapshot_provenance.md`：source-input tree、artifact digest、publication 顺序与 checker 语义。
- `docs/issue_28_requirement_transition_summary.md`：PR-A的一页owner review对象；closure固定，exact head从GitHub PR实时读取以避免自引用。
- `docs/issue_28_pr29_rework_audit.md`：被拒candidate的复现、七项authority返工、fragment语义分类及真实artifact测试命令；不构成activation或live grant。
- `TESTING.md`：测试层级、真实命令、full/light 边界与副作用。
- `SOP.md`：标准流程的一级导航，只保留动作、权威引用与验收。
- `PR_Checklist.md`：仅在用户明确要求发布时使用的发布治理流程，不属于批次 acceptance source。
- `.github/pull_request_template.md`：长期 PR body 发布治理模板，不属于批次 acceptance source。
- `.github/workflows/vnext-fast.yml`：PR fast-suite CI；只运行 `tools/run_fast_tests.py`，不替代integration、live或full acceptance。
- `.gitignore`：本地缓存、环境与临时 PR 草稿的忽略规则。
- `requirements/issue_28_v1/`：Issue #28 successor 的五文件profile-driven snapshot；Decision Register拥有policy content，typed invariant profile、transfer classification、parent/R3/R2/archive与validator binding共同形成新closure。
- `requirements/issue_15_v1/`：Issue #15 的 exact Contract、自包含 Decision Register、post-freeze tips、parent transfer/baseline、legacy producer/matrix/foundation证据；只作为不可变R1–R3历史兼容authority，不再承载successor policy。
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
- `catalog/reference/`：Issue #44 的 SIC × Metrics 映射表与 39 指标中英文定义表（参考数据，不是运行配置）。`source_selection.json` 按明确绑定选取已提交定义版本、不是生产激活指针；`sic_metric_rules.json` 是唯一手工维护的行业关系；`metric_metadata.json` 只保存机器来源没有的中英文说明与代码引用；`generated/` 由 `tools/generate_metrics_reference.py` 生成、`--check` 只读校验，不得手改。现有加载器不扫描该目录。说明见 `catalog/reference/README.md`。
- `catalog/deterministic_metrics.json` / `catalog/event_routes.json` / `catalog/zero_ai_public_projection.json`：R2确定性公式/approved concepts、事件item/keyword路由与22指标完整public-row投影；均被Issue #15 Requirement runtime authority逐byte绑定，approved public delta exact set当前为空。
- `catalog/event_routes.json`：C01/E01–E05 的声明式零 AI item/keyword route authority；冻结 E01 aliases、text normalization、match mode、brief source priority 与 legacy projection。

### 核心模块

- `tools/vnext_normal_candidate.py`、`scripts/vnext/normal_run_v3.py`：V14开发草案将36项普通来源路线接入同一Run，默认OPEN并生成独立公共行；B03保留B01依赖。`normal_run_specs.py`/`normal_run_inputs.py`固定22项来源规格与完整图，`ordinary_projection.py`保留主结果及各项来源证据。V12/V13的`normal_run_v2.py`、旧规则/快照/冻结记录不重写，V14尚不冻结。说明见`docs/normal_candidates.md`。

- `normal_zero_ai_results.py` / `normal_companyfacts_results.py`：旧22项中19项的普通来源原生记录组件，复用既有规格、目录、来源适配与Calculator；上一期来源和依赖指标从原件重建。`normal_accession_results.py`另接A01/A02/B12的源单位/维度/时点，共22项原生组件，已接入V14 OPEN Run；完整更新继续接线，见`docs/normal_source_components.md`。
- `lodging_table_source.py` / `normal_lodging_results.py` / `catalog/ordinary_lodging/`：B10/B11新确定性来源路线，从表前说明、整表及地域脚注重建当前年可比全系统全球统计，沿V14原生Run输出；旧AI规格/资格不改，不授新调用或正式信用。见`docs/ordinary_lodging.md`。
- `annual_amendment_scope.py`：逐份核对普通修订的原件、期间、完整说明及适用输入属性；有限链接更正可接入B01/B03/六事件/Company Facts，Part III不自动批准财务或主体合并范围。
- `b06_combined_borrowings.py` / `b06_financing_inventory.py`：组合附注借款账面数对账与融资披露来源清单。保留原表实际标签、计量调整与舍入说明；小计不是完整B06，缺少单独融资租赁披露不推零，尚未接入Run。说明与实测见`docs/evidence/issue28_continuous/ordinary-borrowing-composition/`及`ordinary-financing-inventory/`。
- `b06_note_carrying.py` / `normal_note_debt_results.py`：新增逐笔债券及明确无融资租赁的有限B06原件路线，核对整表、细分原生事实及独立融资清单，沿V14同一Run输出。旧债务验证器和冻结规则不改，未覆盖关系保留未决；见`docs/note_debt_source.md`。
- `b06_bond_leases.py` / `normal_bond_debt_results.py`：债券本金/费用、单独列报融资租赁、付款条件未变的普通贸易供应商项目及独立融资清单的普通来源路线。新债务集合核对当前加非当前借款；历史模型不改，仍无生产许可。见`docs/note_debt_source.md`。
- `b06_current_input.py`：普通B06先核对全部当前修订件对债务/权益的影响，输入未证明时不进入债务解析或非正权益保护；修订原件和判断进入同一Run。B08/B09旧政策不扩大，债务完整性和当前主体仍另验。见`docs/note_debt_source.md`。
- `b06_inclusive_table.py` / `normal_inclusive_debt_results.py`：逐项证明债务表总额已包含融资租赁，核对当前主体列、同范围权益、原生融资清单和完整续接附注；收购日估值与未来票面额不另加到当前账面债务。复用原`INCLUSIVE_REPORTED_TOTAL`模型及Calculator，新B06v6仅为未冻结开发路线。
- `regulatory_investigation_candidates.py` / `going_concern_source.py` / `fiscal_year_labels.py`：D03事实候选及上下文、D04完整年报/修订原文分组、财年原文/机器标签对照；来源准备不能当成最终调查/持续经营结论或新规则激活。
- `scripts/vnext/historical_metadata_context.py` / `historical_projection.py` 的 `persist`：前者是普通pinned期间的submissions块视图，按既有历史目录读入该期间需要的每个块并要求"读到的块"等于"准入的块"，冻结的recent-only视图字节不改；后者把公共行、证据与收据写到Run旁`row_receipt.json`，收据自带行/证据哈希供只读核对。二者都不改指标口径、不授生产信用。
- `tools/run_fast_tests_v2.py`：当前CI分95个30秒短测试入口和34个240秒完整来源材料入口；先前124项均保留，并新增五个普通来源/输入材料套件。旧`tools/run_fast_tests.py`是V13冻结规则的一部分，保留原字节和历史入口。

- `scripts/vnext/capacity_reference_contract.py`：显式新B13请求把发现放在根层，以原kind/source_index核对归属，局部编号的XML补充对象另带source_unit_index；完整单元审阅和原内容/数量验证保留。旧嵌套响应不重定位、不升级原109失败。接线与边界见`docs/evidence/issue28_continuous/b13-strict-references-20260922/`。

- `scripts/vnext/normal_candidates.py`、`normal_source_authority.py`、`normal_governance_input.py`：从已保存实际来源重建B06/C03/C04/D01候选，外部根与既存获取基线分开验证；V12记录已冻结、未正式激活。后继`normal_text_input_v2.py`为C02/D02保留必要来源和完整选源元数据，`text_results_v2.py`保留严格核验的披露事实与原文，不能推断总诉讼负债。
- `scripts/vnext/text_results.py`、`text_review.py`、`text_run_validation.py`：原有记录中的显式TEXT_V1、完整原文候选/审阅/Run重读，旧数字记录不改。

- `scripts/vnext/financial_duration.py`：从原表头/行脚注重建实际测量期间；季度不能借年报身份变成年均值。`text_coverage.py`重建原件章节/字节定位，查找命中与范围完整分开；二者目前是离线验证组件，后续原生接线仍需验收。
- `scripts/vnext/b06_disclosure_v2.py` / `catalog/r5/B06_new_source_v2.md`：显式后继内容检查，补primary/XML金额一致性、其他债务计量对账及有限当期借款叙述。旧v1保持历史语义，新增组件不自行赋予来源或生产信用。
- `scripts/vnext/normal_annual_input.py` / `tools/vnext_normal_update.py`：从保存清单选择最新普通年报，由原生DEI/context确认实际财年，支持自然年及52/53周年，不使用两样本白名单或旧Result。修订与普通原件分离，来源失败与主体接续实现缺口分别保留；当前只准备输入，不执行指标、不授来源准入或生产信用。旧calendar-only及PR43历史入口不改。
- `scripts/vnext/normal_source_requirements.py`：普通更新的只读来源发现入口；从申报元数据列出本期/上期年报、修订、代理材料及财年8-K原件、头文件、目录和原生XML。新主文件在读取前即可被发现；清单冲突、最后请求失败及尚未知晓的目录子文件分别保留。CLI追加`--discover-sources`，默认十家公司；来源可用不等于最新、不等于39指标来源验收或新获取信用。见`docs/normal_source_discovery.md`。
- `scripts/vnext/instant_balance_amendment.py`：在旧修订范围证明之外，核对完整说明、原生错误更正标志、可见未勾选封面、未附财务报表声明及全文更正语句，只给普通B08/B09的期末余额提供有限输入证明。`normal_companyfacts_results`按原目录允许当前主体/当前时点，不把接续关系一概扩成所有指标阻断；全年、债务和治理范围不获此证明。见`docs/ordinary_instant_balances.md`。
- `scripts/vnext/r6_semantic_source.py` / `r6_semantic_review.py`：D04离线解释输入与保存响应协议，包含全部正文/原生事实及续接关系，嵌套XML按原位置重建，程序定位唯一原文引用并保留响应遗漏/冲突。协议本身不调用模型；后继continuous_semantic_calls已进行有限真实验证并保留首次截断及语义失败，尚无整条语义正确性证明、D04 Run或正式信用。新semantic_review_v2定义类别并列出本单元必评项；不以协议测试代替真实模型验证。见`docs/r6_interpretation_protocol.md`。
- `scripts/vnext/ordinary_source_session.py` / `ordinary_source_authority.py`：测试会话复用SEC原生持久化与追加；实际创建进程在安装目录登记完整来源记录，再通过当前普通验证、外部source_root安装和Run重放读取。原清单不改，调用方JSON不能登记自己；测试类型保留到预览，真实获取/预算/生产仍未启用。见`docs/recorded_source_session.md`。
- `ordinary_remaining_cases.py` / `ordinary_financial_results.py` / `ordinary_text_input.py` / `ordinary_debt_guard.py`：既有十二条金融、治理、文本及债务路线的当前来源入口。复用冻结模块的纯业务函数、Spec及Calculator，不修改旧入口；当前B06修订核对和非正权益保护顺序保持不变。
- `ordinary_update_cycle.py`：普通已准入输入的更新检查，区分最近尝试与完整成功候选，保留失败/中断历史，输入未变时重验并复用Run。使用现有原生链路，零外发、不发布，入口见`docs/ordinary_update_cycle.md`。 正常公司入口按指标保存独立历史，单项失败不阻止其余指标，旧值保留原期间及当前输入匹配标记。 历史意图/终态编号、类型及完整前驱绑定逐项核对，重签哈希不能绕过。

- `scripts/vnext/b06_source_admission.py`：独立于普通输入的受信获取/导入执行记录、
  固定阶段预算及后置离线checkpoint；自洽ledger不授真实SEC信用。
- `scripts/vnext/b06_disclosure.py` / `b06_new_source.py`：两类有限债务披露关系、
  独立遗漏清单、非自然年度身份及原生Run创建/冻结/冷读；新Spec和V11政策
  显式分派，旧B06与年度入口语义不改，任何生产写权限仍不存在。

- `scripts/vnext/annual_adoption_policy.py` / `annual_publication_authority.py`：显式冻结v1/v2
  政策解析、确切候选的待批计划、真实GitHub激活/发布核对及有限发布/回退/恢复；
  V8/issue_28_v7保持新采纳决定待外部批准。共享现有发布核心，schema2切换日志另绑
  plan/action/permission，旧schema1与原Run不改。TEST_ONLY许可不得写实际R3。

- `scripts/vnext/annual_adoption.py` / `annual_projection.py` / `annual_publication.py`：普通候选历史只读采纳、完整结果继承与既有发布原语的隔离演练；原Run不改、无正式信用。CLI为 `tools/vnext_annual_publication.py`，入口说明见 `docs/annual_publication.md`。

- `annual_evidence.py` / `annual_repair_budget.py` / `annual_regression.py`：PR38普通B10同格标签与来源归属修复、固定两次新增修复预算及未改原响应的离线回归；入口见 `docs/annual_label_repair.md`，仍无自动merge或正式发布许可。

- `scripts/vnext/annual_runtime.py` / `tools/vnext_annual_runtime.py`：固定代码与外部输入目录下的Marriott B01/B10阶段候选运行；V6/issue_28_v5独立许可不依赖open PR，复用原生Run与WB-3，总额1/1/0、零重试，成功引用重验两指标，不改变R3。见 `docs/annual_runtime.md`。

- `scripts/vnext/annual_update.py` / `tools/vnext_annual_update.py`：Marriott 年报申报身份检查、显式历史成功/正式对照及受限来源刷新；默认离线，新输入经原有 annual_input 准备，最多可生成未授权普通候选计划。真实 SEC 需另行许可，清单1次、条件式缺少来源至多2次、retry=0；不执行指标、不改变active。入口与示例见 `docs/annual_update.md`。
- `scripts/vnext/annual_input.py`：只读准备连续primary实体、日历财年、current submissions block内唯一未修订10-K的既有Run入口参数；用原始DEI/context核对期间、复用request ledger绑定，不读取旧结果，不提供LIVE授权或发布。
- `scripts/vnext/annual_candidate.py` / `tools/vnext_annual_candidate.py`：普通 B10 的未授权计划、真实 owner comment 核对与原生执行接线；仅隔离候选，无 qualification/publication credit。`requirement_profile_v5.py` 在既有注册表增加该政策类型，`issue_28_v4` 仍未激活。

- `scripts/sec_pipeline.py`：阶段调度、解析、计算、富化、repair、验证、审计与报告的单体内核。
- `scripts/sec_http.py`：集中验证有效 SEC organization/contact email，并负责精确官方 SEC origin、无隐式 redirect、进程内节流、重试、immutable attempt body/header、request ledger、整表 manifest 与 cooperating-process publication lock。
- `scripts/sec_urls.py`：集中构造 SEC 官方 endpoint。
- `scripts/git_workspace.py`：集中清理 Git 重定向环境，并校验 checkout 与 object/ref 存储边界。
- `scripts/validation_provenance.py`：读取 source policy、校验 SOP 权威引用角色、捕获 source-input tree、发布关键 artifact digest sidecar，并在 postflight 失败时使终态 fail closed。
- `scripts/00_*.py` 至 `scripts/12_*.py`：薄单阶段 CLI；04/09 只接受`--workspace-dir <absolute-isolated-root>`，11 无参数时只作active read-back、带该参数时构建legacy candidate，其余wrapper保持无参数。candidate全链统一经`sec_pipeline.py --workspace-dir ... <stage>`；legacy stage 11 mutation使旧provenance失配，stage 12负责终态publication，active stage 11只读。
- `scripts/vnext/`：vNext的canonical/schema/state、source/table-grid、latest verified request-attempt与locator-tier source plan、Spec/constraint、固定DeepSeek OpenAI-compatible Chat Completions adapter、Evidence/Review/Calculator、Run freeze/replay、complete BatchManifest/Projector、固定SEC Stage00/01/02/03/05 acquisition/inventory、资格门、正式Cutover编排、pinned `PublicationView`与publication/rollback transaction实现。recorded可exact验证并闭合legacy working locator，正式live只允许immutable attempt；二者仍受各自Review、staging与publication gates约束。
- `scripts/vnext/requirement_profile.py`：版本注册表与portable authority路径收集；不被旧snapshot绑定为可变共享engine。
- `scripts/vnext/requirement_profile_v1.py` / `requirement_profile_v2.py`：保留的版本化engine。V1拥有strict读取、Decision链、fragment transfer、安全bounds和显式artifact generation；V2依赖不可变V1并只增加typed产品语义Decision扩展。新engine不得覆盖旧engine。
- `scripts/vnext/source_strategy.py`：严格加载39指标registry与Issue #15 ReleasePlan，机械验证exact source-mode mapping、family literal union、迁移状态分离、全部authority hashes及parent→child metric/key/retirement三类no-removal子集门。已发布R1/R2 plan按content ID保留其历史Requirement closure，loader另返回current closure；post-publication D-07 tip不得重签历史plan或active bundle，未来新plan必须显式登记current closure。
- `scripts/vnext/deterministic_router.py`：以统一 `sources[]`/SourceSetManifest 闭合 companyfacts、accession XBRL、ECD XBRL、auditor fact 和 8-K item index 五个 adapter；它生成非模型 DeterministicVerifiedClaim，再投影为 VerifiedObservation/Result/ExecutionTrace。
- `scripts/vnext/invocation_control.py`：绑定 release-input/invocation/execution 三层身份；生产adapter在exact provider envelope形成plan后才进入`O_CREAT|O_EXCL` owner-only socket路径。terminal reservation归档后释放，dead owner的egress marker+缺terminal receipt从磁盘封存为UNKNOWN；plan/request/egress/attempt/execution/response均可重算三种调用计数，不包含仓库金额 cap/preflight。
- `scripts/vnext/table_context_measurement.py`：与qualification隔离的同一one-shot actual-token measurement边界；occupancy与RevPAR authorization均已永久消费。RevPAR exact head `290c1119…`只执行一次，provider usage为160928 prompt、535 completion、161463 total，real model/paid/SEC=`1/1/0`；schema-v2 marker/evidence绑定review/head/task/request且无qualification/publication/reuse credit。latest D-07现在使任何新plan/authorization稳定返回`AUTHORIZATION_CONSUMED`，不得再次运行measurement。
- `scripts/vnext/table_payload.py` / `scope_contract.py` / `table_task_contracts.py` / `table_qualification_freeze.py`：分别实现expanded grid可逆compact transport、多维shared-locator exact-enum scope、单角色catalog task与无网络qualification freeze。schema-v4 freeze按development source×task绑定exact request与各自attestation；当前occupancy/RevPAR两request均以`PROVIDER_REPORTED_EXACT_BINDING`通过，lodging family ready，financial仍仅由`EXPANDED_GRID_RESOURCE_LIMIT`阻断。qualification executor沿同一task plan处理matrix-owned `SECOND_LAYOUT` / `POST_FREEZE_HOLDOUT` / `FRESH_STABILITY`：second layout为Marriott FY2024 immutable SEC fixture，replacement holdout为Marriott FY2023 distinct fiscal-year/accession fixture，fresh为Marriott FY2025，caller不能覆盖source。owner-approved同issuer独立性仍要求source bytes不同并机械证明document table-count与target span geometry等至少两项layout差异；estimated超200000的request只允许exact-head review逐plan/request绑定并由各自新qualification response terminal usage门裁决，usage缺失或超限零重试且停止后续lodging plans，measurement response仍禁止复用。
- `scripts/vnext/table_context_attestation.py` / `table_context_comparison.py` / `stage_c_context_packet.py`：前者保留并机械重验两个exact attestation，qualification-only successor只允许明确authority/consumption文件变化且两个provider request必须逐字段未变；中者保留pre-measurement sibling no-bound历史对象并重验两request bytes；后者同样保持历史packet，不重签为post-RevPAR状态。
- `scripts/vnext/stage_c_packet.py` / `tools/create_stage_c_a_packet.py`：保留Stage C-A answer-first pre-egress packet；严格分开approved/implemented/not-run/unauthorized/blocker，token authorization保持`NOT_ISSUED`，不得在Stage C-B后重签该历史对象。
- `scripts/vnext/stage_c_b_packet.py` / `tools/create_stage_c_b_packet.py`：Stage C-B post-egress terminal packet与current-source overlay；离线重算review-bound plan/cycle/authorization、唯一marker/evidence/raw-response/usage hashes、1/1/0计数、active R2/309-row root与JPM F3 blocker。validator不得构造transport或再次调用provider，并继续要求historical R2仅有source drift。
- `tools/vnext_table_context_measurement.py`：`plan`仅写current RevPAR content-addressed离线plan；`execute`无family/task/source/provider override，必须同时收到exact授权词、当前clean HEAD、review绑定的request SHA、PR top-level review comment URL与UTC时间才可能进入唯一真实provider边界。exact-head独立审核前不得运行`execute`，任一marker后永久禁止再次调用。
- `tools/create_table_qualification_owner_decision_packet.py`：在新freeze与Stage-A overlay均可重验后，生成schema-v4 owner packet；严格分开exact context owner policy、当前task/request/family readiness、已消费measurement/no qualification reuse、sibling evidence decision与financial未决项，并绑定attestation/comparison/unchanged R2 root及三类零egress。旧packet保留，只更新content-addressed pointer。
- `tools/create_table_context_feasibility_attestation.py` / `investigate_sibling_table_context.py` / `create_stage_c_context_attestation_packet.py`：均只离线重建现有bytes；依次生成或验证exact context attestation、sibling full-request decision-neutral comparison与post-attestation Stage-C packet，不构造transport、不请求额外measurement、不开始qualification/publication。
- 2026-08-26 owner在PR #22批准lodging-only frozen prompt修订与重新测量政策：历史occupancy/RevPAR attestation继续immutable但不再给修订request current credit；只允许两个lodging task的`system_prompt`明确必填candidate/scope-evidence/competing字段，schema、MetricSpec、source、serializer、provider/model/API与全表原序均不变。`table_context_measurement.py`复用同一plan/authorization/cycle/marker/evidence边界，为两个新content-addressed task plan各提供最多一次、retry=0、usage-only/no-credit one-shot；具体grant仍须在clean committed head由独立PR评论逐plan/request SHA签发。两份新attestation形成前`live_qualification_authorized=false`。
- 后续schema-v3 Hilton Occupancy response通过结构校验，但目标表supplied caption为空时借用了另一表或邻近正文，机械Evidence以`SCOPE_LABEL_TEXT_MISMATCH`终态拒绝。owner在同一PR再次批准最小scope-binding prompt及两项新one-shot：caption仅在selected target table自身`caption_raw_text`非空时使用并逐字复制；否则cell/header/row/label必须从同一目标表的一格复制完整八字段locator与exact raw text，禁止跨表或借邻近正文。schema仍为v3，其他冻结组件不变；161282/161263 proof降为historical。新Occupancy/RevPAR measurements实际prompt为161433/161422，分别形成`5ee591dd…`/`a5632e90…` exact attestation，均HTTP 200、retry=false、1/1/0且无qualification/publication/reuse credit；same-ID D-07已接受并永久关闭额外measurement，current freeze/Stage-A重建前不得执行qualification。
- Hilton失败终态随后证明其目标表本身缺少same-target-table冻结scope literals。owner批准只更换second-layout fixture/source，保持scope contract、Hyatt holdout、Marriott FY2025 fresh及其他边界不变。替代Marriott FY2024 source由既有`SecHttpClient`exact获取一次、retry=0、无模型调用；offline proof定位唯一`table_000011`，包含全部冻结literals且29x39 geometry/grid hash不同于FY2025 27x39目标表。latest D-07又明确不新增measurement，只把`EXACT_REVIEWED_QUALIFICATION_REQUEST_WITH_TERMINAL_USAGE`扩展到`SECOND_LAYOUT`与`POST_FREEZE_HOLDOUT`；每个rebuilt plan需新execution与exact-head审核，usage缺失或actual prompt>200000即terminal、零重试并停止后续lodging plans。
- Marriott FY2024 Occupancy replacement execution报告159376/550/159926、retry=0并通过context gate，但模型把本地cell exact `"\nWorldwide (2)"` trim为`"Worldwide (2)"`，机械Evidence以`SCOPE_LABEL_TEXT_MISMATCH`终态拒绝，RevPAR未执行。owner批准的最小shared prompt修订只要求首尾whitespace逐字保留并以JSON escapes输出；schema/source/task/serializer/provider/model/API和业务语义均不变，additional measurement与历史response reuse仍禁止。因为prompt由两个lodging task和全部phase共享，161433/161422 attestations降为historical，`SECOND_LAYOUT`、`POST_FREEZE_HOLDOUT`、`FRESH_STABILITY`统一走既有exact-reviewed qualification-response terminal-usage路径；每个plan仍需新exact-head审核与新execution。
- 修订后的FY2024 Occupancy execution实际159479/562/160041并形成Evidence PASS、SYSTEM Review与Result，但Marriott的production registry traits错误覆盖了authorization/fixture traits，finalization以`Run company traits differ from repository`停止，Run保持OPEN且RevPAR未执行。`run_store._run_company_authority`现在仅对`SECOND_LAYOUT`/`POST_FREEZE_HOLDOUT` authorization优先fixture traits；`FRESH_STABILITY`与普通production仍registry-first，无authorization外部fixture仍只在registry miss时fallback。该OPEN success不获qualification credit且不进入新cycle。
- 新cycle的FY2024 Occupancy/RevPAR second-layout均以159479/562/160041与159471/736/160207完成Evidence/Review/PASSED/FROZEN；Hyatt FY2025 holdout Occupancy随后以91588/704/92292通过context但因空caption及source缺失冻结scope literals而`SCHEMA_VIOLATION`，RevPAR未执行。owner据此批准把holdout独立性从`different_issuer_cik`改为同issuer但fiscal year/accession/source bytes均不同，并只获取Marriott FY2023 exact SEC URL。一次HTTP 200/retry=0产生SHA `3e59d9a0…`；production parser离线证明唯一`table_000011`同时含2023 RevPAR 124.70、Occupancy 69.2、`Comparable Systemwide Properties`与`Worldwide`，全文档table count为66（FY2024=67、FY2025=68），且FY2023/FY2024目标表第11/13行span geometry不同。fixture仍是source-only `NOT_RUN`，旧response禁止复用；新freeze/cycle/Stage-A/plans和exact-head review完成前不得调用模型。
- Fresh ordinal 2首次执行在marker前暴露shared WB-3 request-identity碰撞：相同request bytes命中ordinal 1 success path，但acceptance绑定另一task plan，故以`Acceptance receipt binding differs`停止，ledger/marker/attempt/execution均未增加。修复不改变request/prompt/schema/source/serializer/provider或业务口径：同一cycle内每个qualification task plan使用由cycle ID与task-plan ID派生的plan-owned WB-3 namespace；cycle gate跨全部namespace聚合remote terminals并继续与Run/ledger/Evidence exact-set闭合。相同Fresh request必须产生新execution，`REUSED_SUCCESS`不得获得ordinal credit；受保护代码变化后旧semantic freeze/cycle只作历史证据，必须新freeze/cycle/Stage-A与新exact-head计划重新qualification。
- plan-owned修复后的新SECOND_LAYOUT Occupancy plan在exact-head review下只调用一次：HTTP 200、retry=0、usage 159479/560/160039且context通过；模型选中正确`table_000011`、69.8与完整八字段locator，却从serializer-v2 positional tuple复制了normalized `x[6]`而不是带leading LF的exact raw `x[5]`，Evidence以`SCOPE_LABEL_TEXT_MISMATCH`终态拒绝，RevPAR未执行。owner批准的最小shared prompt successor只明示`c=[caption,caption_raw_text]`与`x=[row_index,column_index,rowspan,colspan,header,raw_text,text]`，scope raw text只许`c[1]`/`x[5]`、禁止`c[0]`/`x[6]`；schema/source/serializer/task/provider/model/API与业务口径不变，不新增measurement、不复用失败response，所有lodging phase继续走exact-reviewed qualification terminal usage路径。
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
- `tools/benchmark_jpm_full_materialization.py`：Stage C隔离benchmark入口；只允许child内`max_total_cells=187142`，要求512 MiB硬RSS/address-space、120秒wall与process-tree no-network三重保护，production resource bytes逐byte不变。当前Darwin guard不可可靠安装，故在child启动前记录`NOT_RUN_RSS_GUARD_UNAVAILABLE`；不得把null peak/time/canonical/DerivedAsset写成completed。
- `tools/vnext_qualification.py` / `tools/vnext_cutover.py`：前者保留legacy `prepare` fail-closed，并在同一CLI增加catalog `table-plan/table-execute/table-freeze/table-freeze-status`。plan按phase重建exact source/request；execute仍走唯一WB-3 qualification authorization、provider ledger、Evidence、Review、Run freeze；两个second-layout task FROZEN后，cycle-owned `PRODUCTION_SEMANTIC_FREEZE`绑定semantic tree与ledger prefix，holdout只能在其后运行，fresh stability又要求两个holdout task先FROZEN。其余正式qualification/Cutover继续复用既有validation/publication状态机。
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
- `outputs/active_publication.json`：正式 active identity 的唯一 committed pointer。当前 pointer 指向 Issue #15 R3 successor，覆盖24指标/240个累计vNext Result keys/327行public matrix且previous为R2；不能把partial ratchet写成最终Cutover/full PASS。

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
2. live 请求的 organization 固定为 `axaxl`；自动读取 `config/sec_config.json` 的 `contact_email`，显式 `SEC_CONTACT_EMAIL` 环境变量优先。选中值缺失、畸形或使用 reserved domain 时必须在联网前以稳定错误失败。
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

- Issue #15 的 historical D-26 保留 fast/local 主入口 `python3 tools/run_fast_tests.py --jobs 4`；fast set以`issue_28_v1` smoke同时覆盖successor与其exact historical parent，`.github/workflows/vnext-fast.yml` 在PR上运行同一集合。不把全仓/双解释器、隔离 repository/worktree 或长串行套件列为必跑项。`PASSED_FAST_LOCAL_ONLY` 只界定证据范围；CI green仍不是live、full acceptance或Cutover。
- 发现 Bug 时遵循 `TESTING.md`：先补稳定复现，再修实现；跨阶段问题同时补场景级证据。
- 不用 quick unittest 替代 Golden、repair gate、snapshot checker 或完整场景，也不用 light review 冒充 full validation。
- 真实运营中会写 `evidence/`、`outputs/` 或报告的命令仍须遵循其受控 authority；它们不是 R4 测试。
- 用户要求 PR 时，逐项完成 `PR_Checklist.md`；任何豁免、未运行测试、known limitation 和未解决决策写入 PR body。

## 7. SOP 清单

需要执行标准流程时，先读取 `SOP.md` 中对应章节：

- 只读取现有结果
- SEC 阶段 00-12 完整批次运行
- Issue #28 successor Requirement 与后续 ratchet 开发
- Issue #15 / R1–R3 历史 authority 回读
- vNext operator 与正式 Cutover
- 分层验收与失败定位
- PR 发布（仅用户明确要求时）

- `scripts/vnext/annual_continuity.py`及snapshot/publication/trigger适配：同一受限阶段的年度检查、原生候选、完整前驱接续与有限触发，实际生产只读；新规则V3/issue_28_v8，不改历史v1/v2。入口`tools/vnext_annual_continuity.py`，操作/状态/验收见`docs/annual_update_continuity.md`。`PublicationView.native_result/authority_bytes`拥有有限内部路径解析；不要在调用者伪造旧batch目录。

- `scripts/vnext/r5_b06_structured.py`、`r5_b06_publication.py`、`tools/vnext_r5_b06.py`：B06保存结构化来源→原生结果/阻断→完整只读候选；新Requirement草案无生产激活，来源策略fallback仍未执行。入口见`docs/r5_b06_structured.md`。
- `scripts/vnext/r5_b06_amendments.py` / `r5_b06_measurement.py`：B06完整修订原件影响判断、原生XML账面计量对账及旧v1兼容；新语义见`docs/r5_b06_structured.md`，均无生产权限和业务网络调用。

- `scripts/vnext/r5_b06_scope.py` / `config/r5_b06_debt_sets_v3.json`：B06具名负债组成、原XBRL精度/对账、独立完整性门；现有Calculator/Projector共用。`catalog/r5/history/`保留v1/v2原字节。当前主路径合并不等于B06全部迁移/生产授权。

- `normal_annual_input_v2.py` / `config/normal_fiscal_year_labels_v1.json`：用唯一未处于引语中的注册人原文定义选择财年，保留原始DEI/CF及冲突。每次验证来源字节后才复用进程内的有界解析结果；不缓存来源权限或调用信用。

`ordinary_storage_identity.py`为普通C04增加同一不可变请求的URL文件名视图，原引用/请求/原件不改；`ordinary_source_authority.checkpoint_installation`保留同一响应身份的旧尝试证据，支持相同正文的元数据刷新后冷读。13次真实SEC获取、恢复的10坐标、首次C04/复制失败及修后材料见`docs/evidence/issue28_continuous/ordinary-document-identity/`；模型调用仍需当前进程密钥。

`ordinary_special_debt_scope.py`接入普通B06当前输入/分母守卫之后，按银行行业与原件工业维度/列标题重建已报告融资分项；HTML/XML金额、单位、期间、主体一致才保留小计。JPM融资租赁完整性和Ford工业归母权益仍为明确非数值限制，不依赖旧逐公司范围复核表，不改历史Spec。材料见`ordinary-special-debt-scope/`。

C04的文档身份视图现覆盖当前及历史submissions清单；重建SourceSet仅改变清单引用身份，发现集合/原件顺序/窗口/截止请求保持不变。JPM6事件恢复、C04首次失败与修后双公司原生/冷读，以及未改SEC代码证据的复用核对，见`ordinary-history-identities/`。

普通来源发现现按原事件目录的窗口和已登记主/前身CIK列出完整事件来源依赖；Paramount为2024–2025、4份当前/31份前身申报，缺9份前身8K正文及头文件共18件。来源发现与有限获取准入已离线验证，尚不代表6事件原生接线完成。见ordinary-registered-events材料。

普通normal_zero_ai_results现按原事件目录窗口/已登记主及前身CIK重建6事件；完整来源保留在同一Run。Run的一年坐标与事件实际回溯窗口分开，run_store只对完整原件重建且逐条一致的6事件记录认可差异，通用53周/财务期间不改。18件真实来源补齐后Paramount6事件原生通过，省略前身的相同零值拒绝，见ordinary-registered-event-runs。

ordinary_income_input为接续主体B01/B03增加独立当前收入输入证明：原HTML/XML/CF、实际期间与PartIII收入更正检查。原300–400天Spec守卫自动保留146天报告的NOT_MEANINGFUL，B03复用B01观察；不拼前身，不修改旧余额/债务/修订规则。材料见ordinary-current-income。

D03后继`r6_regulatory_semantics`/`r6_semantic_verification`已接本轮有限真实模型调用，按来源索引恢复原文并分离事件日期/披露状态。上下文选择也进入内容核验；模型内容核验不算独立代码审阅。Pfizer局部修后样本通过，JPM总体当前涉案披露留出仍错误，未取得D03通用或原生验收信用。现行入口和实际调用见`docs/r6_regulatory_semantics.md`及`docs/evidence/issue28_continuous/execution-state.json`。

D04历史控制入口见`docs/historical_semantic_controls.md`：Enphase2016/2017原正文与SEC头文件已实际取得，新的非inline控制身份检查不替换普通DEI规则。v3内容/主体/时间分离保留原响应与失败；控制不代表最新公司状态、整份filing、原生Result或正式信用。

`capacity_semantic_source.py`复用完整年报/修订输入，保留正文/原生事实/续接对象，候选命中不授数值完整性或原生信用。`regulatory_statement_facts.py`以来源别名和当前总体涉入的直接语法关系分开事实与案件明细；D03新请求保存事实并拒绝将其抹为假设/上下文/其他主体，原模型响应和旧调用终态不改。JPM339材料是已见回归；新模块独立审阅和整项验收仍待完成。

2026-09-14 后续开发：`capacity_semantic_review`共享并精确恢复完整来源；`capacity_native_assessment`将新B13请求接入原WB-3 Candidate/Evidence，而不升级旧诊断。`capacity_assessment_input`复用普通来源私有登记边界，真实/测试分开；`capacity_text_results`和`capacity_run`将完整判断后的文字分支接入既有Review/Calculator/普通Run及公共行。当前仅有记录响应的开发验证，真实完整B13、数值/缺失/其余不适用坐标及正常更新仍未完成。说明见`docs/ordinary_capacity_results.md`。来源分组性能修复保留原单元与资源上限，不改变D03内容审阅依赖。

2026-09-15：B13压缩行以原始来源编号作键并保留原顺序。真实68虽然引用正确，仍错误分类税收抵免；原成功终态保留但业务内容拒绝，受影响B13真实调用暂停。`capacity_text_results`新增完整集合/有效Review后的有据不可得分支（仅合成开发验证）；`capacity_run`按已批公司范围为另外八家公司生成零AI不适用Run。数值/适用公司真实完整结果仍未完成。材料见`docs/evidence/issue28_continuous/b13-content-guards/`。

2026-09-15后续：`d04_native_assessment.py`及`catalog/r6/semantic_review_v4.json`接新D04原生请求，复用既有来源登记、Review/Run和公共行。`capacity_*`的共同记录/登记/文本/Run函数现为B13与D04共享；旧诊断不升级。`native_assessment_replay.py`保留原计划/原接受ID，对完全相同来源请求作当前内容复验；归档代码不执行，只读视图无执行权限。D04真实新验证、B13适用数值/完整真实结果及全Issue验收仍未完成，详见`docs/evidence/issue28_continuous/d04-native-integration/`。

PR43 review5205267507修复增量：D04源句关系检查在原生接受、文字结果和未披露公共行共同执行，检查肯定/否定及排除标签，具体未决不成为未披露。B13测试来源补齐metric_id合同；B13完整原生测试独立CI作业避免累计作业超时。限定开发验证与后续独立审阅、真实完整验收仍分别登记。

B13数值接线增量：capacity_utilization_source新增明确年度数量及相同范围的原件检查；capacity_run/run_store/ordinary_projection接入原Calculator、精确记录图与原句证据。合成数值场景明确替代来源准入/登记，不是Ford/Enphase真实利用率，受影响真实调用暂停与独立审阅责任保持。

本轮5207290213恢复材料见`docs/evidence/issue28_continuous/review-5207290213/`。`continuous_request_context.py`负责限定完整Chat Completions计数和显式新分组；原输入加输出预留仍受200000限制，实际usage不匹配暂停provider。D04作用域修复有两轮独立发现及第三轮复核；B13假设数量上下文新增P1尚待修复。旧6e5 D03独立审阅未补齐，不将本轮审阅扩大。


本轮后继接线：`native_unit_index.py`保留完整原单元及原请求，只将长单元ID的返回格式变为严格整数索引；不同请求无旧信用。`capacity_quantity_scope.py`/`capacity_quantity_roles.py`按原HTML断言范围及有限数量角色核验，未知量关系不能被OTHER或遗漏抹成未披露。`capacity_update_input.py`把原生成功收据、当前来源等价和普通逐指标历史接通，`ordinary_refresh_cycle.py`负责有限自动来源获取及新原生请求协调。`ordinary_release_preparation.py`及`ordinary_isolated_publication.py`复用统一发布核心作私有版本准备与恢复；正式生产保持未授权。当前状态以`continuation.md`和累计账本为准；前文阶段性的“未修复/仅准备”记录保留当时身份。

Issue #47历史文本路线边界修复：`scripts/vnext/historical_text_results.py`为`issue_47_v1`第14个规则文件，把编号项的终点收窄到Form 10-K不编号的Part I项（高管信息）。冻结`text_coverage.py`的`_SUCCESSOR["3"]={"4","5"}`允许跳号以容纳省略Item 4的公司，表单又允许把高管章节放在Part I内，两者相遇时Item 3吞掉高管章节。九份已保存年报实测：八家结束于Item 4，只有Pfizer不报Item 4、多抓26块并以`EXACT`发布。修复不能改`text_coverage.py`——其字节被`issue_28_v11`规则集点名并在双根校验，普通路线保留原行为直到能重记该文件的世代携带同一规则。`historical_text_input.py`同时补进规则集（D02 Run每次执行却未被点名，因函数内导入而逃过模块级闭包检查）。冻结Run因closure改变不再冷读，须真实重算而非跳过；矩阵续跑键已含closure。材料见`docs/evidence/issue47_history/d02-section-boundary/`。Pfizer的Item 3唯一句子是77字符超链接，被继承的`_substantive`按导航排除，修复前后同样缺失，作为独立遗留问题记录。

对另外八个D02结果做内容核查（读已通过结果的正文）又发现反向缺陷：被引用附注只在不被其他范围包含时才保留附注身份并整取，落在Item 8内的改按六个关键词过滤，按原文写法点名诉讼的块被丢弃（Pfizer 39块19,918字、Lumen 11块7,689字、Paramount 6块、Salesforce 4块、Marriott 1块）。`referenced_note_candidates`让附注恢复附注身份，去重改为"最内层范围拥有该块"。整取附注是错的：第一版使Marriott由10涨到30，新增20块正是内容核查判定应排除的担保表、信用证与保险赔付，Lumen新增43块里15块是合同承诺段；"只增不减"不是范围正确的证据。`incorporated_scopes`改为按申报点名的标题限定范围，同级判据取自各自文档字节的标题样式（Lumen/Paramount用斜体、Marriott用下划线加缩进），并按"文内重复"排除分页页眉。引用附注自身标题（Salesforce）视为整取该附注；不点名（Ford）不变；`WIDER_PARENT_NOTE`（Pfizer的Note 16A）不整取。实测Marriott 10→11、Salesforce 9→15、Paramount 16→27、Lumen 15→41，其余五家逐字节不变、零块丢失，并逐家按原文读出的必含/必排除块号验证。未做：Pfizer带字母子附注的精确定位；Evidence PASS不等于业务验收。


Issue #47 覆盖汇总去重复执行：`historical_coverage.py`原本为每个已接线位置自建candidate/Evidence/ReviewUnit、加载父Requirement造SYSTEM决定并算结果，两套实现在两个方向都不一致（`native_run_wired`硬编码False而旁边有114个真实冻结Run；B01/B03记为EXACT而历史投影仍拒绝）。现分计划/执行/汇总三层：新增只读`scripts/vnext/historical_run_receipts.py`读取冻结Run的manifest并按其自带三个文件哈希校验records/decisions/validation，再取`METRIC_RESULT`；不重放、不解析财报、不造审阅决定，被编辑的run目录以`RUN_RECEIPT_FILE_CHANGED`拒绝。新增`ROUTE_IMPLEMENTED_NOT_RUN`状态（既非未实现也非披露缺失）；`business_content_accepted`恒False；已确认内容缺陷由`docs/evidence/issue47_history/known_result_defects.json`按result_id或坐标登记，记录的VALUE_EXACT保留原样但退出`verified_outcome`，原件与修复责任不改。同坐标多份收据全部保留计数。实测同390位置260.4秒→4.7秒。验收测试把三个解析器、两个候选工厂与审阅决定工厂全部改为抛异常后报告仍须产出；该测试同时暴露计划层为确定期间仍解析来源字节，属下一项（减少重复解析）范围。CLI新增`--runs-root`；缺收据时报告未运行，不报告未实现。

Issue #47 同一执行内共享解析：按（解析器×源字节×参数）实测，一个D02 Run创建对同一份文档发起80次解析——执行、授权重推、文本上下文重建与开放Run机械重放各自调用`prepare_business_text_sources`共16次。`historical_text_results.shared_source_preparation()`是显式作用域的进程内复用，键含metric、calculation target、全部source reference、source filings与每段原始字节的SHA-256（不信任调用方给的`raw_asset_id`），存取均深拷贝。候选仍独立重推三次，只是不再重复解析不可能改变的字节。作用域可重入——内层若绑新字典会遮蔽外层并丢弃自己，该bug由整Run普查抓到（80→25而非80→5）。实测同一Run同一输入：80次→5次（5次即一次完整准备）、105.9秒→63.7秒（40%）、`result_id`逐字节相同；隔离的候选+Evidence段10→5、7.6→3.8秒。不共享的那次才是独立检查：`load_frozen_run`不在任何作用域内，新进程冷读重新从原始证据解析并返回相同status/quality/条目数（28.1秒）。反例覆盖身份隔离、对象隔离、作用域泄漏与键的字节敏感性。


Issue #47 Pfizer字母子附注已定位，剩余阻断是Spec上限：Item 3点名Note 16A，无同号标题故解析器回退父附注并记`WIDER_PARENT_NOTE`。子节在文档里——Note 16内`A. Legal Proceedings`(块3821)，其后B担保/C承诺/D或有对价/E保险(3937/3947/3950/3952)，故并入范围为[3821,3937)；`A1.`因字母后接数字不匹配子节式，六处重复页眉由同一"文内重复"判据排除。正确定位后Pfizer的D02为**92条41,860字**，对Spec的`max_items=64`/`max_text_chars=64,000`——超条目上限而字符只用65%，`create_deterministic_text_candidate`以`TEXT_V2_COMPLETE_EXCERPT_SET_EXCEEDS_ITEM_BOUND`拒绝，该坐标不产出结果。这是Spec在说话，如实记录不绕过：条目数取决于申报者如何断段而非披露量（Southwest 25条35,545字、Pfizer 92条41,860字），提高上限属于改动已批MetricSpec，按修订机制对齐。未做：提高上限、合并相邻块凑数、收窄范围凑数、退回父附注跳过。其余八家不受影响这一句后来被实测修正：只测过三家。缺陷登记条目现为`D02_PFIZER_2025_EXCEEDS_ITEM_BOUND`（“Spec上限”是当时的错误归因，见下一条）。

Issue #47 D02条目上限：**修订机制已建好，但64不是一个界而是两个，所以还没有接通**。第一层是`specs.py`规定任何`TEXT_V1` Spec最多声明64条——该文件字节被14个已冻结世代（`issue_28_v2`–`v14`及`issue_47_v1`）的execution authority点名，改它实测导致`native_request_construction`对`issue_28_v14`开作用域时抛`NATIVE_REQUEST_CONSTRUCTION_RULE_CHANGED:scripts/vnext/specs.py`，13个测试红、整条continuous语义调用路线起不来。该层已解决：新增第16个规则文件`scripts/vnext/historical_spec_revision.py`承担放宽后的上限，`specs.py`字节不动。它不替换编译——冻结`compile_spec`仍做全部解析校验；本模块把后继前置内容按前驱的界编译一次、要求`compiled`与`prompt_bundle`与前驱完全相等，再放回声明值并用冻结哈希函数重算三个哈希。因此这是机械证明“只动了一个数”：改sections/字符界/allowed_source_roles/name/disclosure_group/quality_rule/metric_id的后继一律被拒，且有用例断言`SPEC_FIELDS`全部24个字段都落在两侧之一（否则相等判断有缝）；另有用例断言空applicability/非法renderer由冻结编译器先拒，以证明后继路径只加检查不减检查。代价比第一版小，但**上一版写的“不再重记任何继承文件、一个数据根可同时满足两者”是错的**——那句是在**未打补丁的仓库树**里跑mint读出来的，而真正执行历史Run的是**已打补丁的运行树**。三棵树逐一核对后（材料见`docs/evidence/issue47_history/authority-divergence/`）：`specs.py`确实在三棵树里都与`issue_28_v13`/`v14`一致了，但`requirement_profile.py`/`run_store.py`/`records.py`仍按补丁后的字节记录，故一棵代码树仍只满足两者之一。第二处纠正：这也**不是本次改动引入的代价**——已安装数据根里14个世代对这三个文件分别有13/11/9个不同哈希，“一棵代码树一次只满足一个世代”是整条ratchet的固有形状。**第二层是协议容量，现已一并接通**：64同时是`ORDERED_NEWLINE_V1`文本结果协议的结构常量，硬编码在`text_results.render_text_payload`第86行，与Spec无关。实测一次D02 Run经过该函数122次、5个调用点（`payload_from_observations`/`build_text_result_and_trace`/`validate_text_record`/`verify_text_trace`/`projector._projection_value`）全部超界，所以只提高编译器上限仍渲染不出第65条。`text_results.py`是`issue_28_v11`的new_rule_file（双根校验），故新增第17个规则文件`scripts/vnext/historical_text_protocol.py`自带该层容量。**只多一个参数、不少一项检查**：五个函数逐字继承，唯一编辑是把条目上限换成参数；保证方式是差分——同一批payload喂给冻结与后继两套实现，冻结上限之内必须返回相同值、抛出相同错误消息，26个变异逐个比对；省略参数时默认就是64。**提高容量只增加验证量**：每个逐项变异在第80项（冻结上限之内到不了的位置）再验一遍，必须同理由被拒；另断言92条渲染出正好92行——“只校验前64条”正是这里会出错却看起来正常的方式。字符上限不变且仍计入渲染器插入的换行（192×332+191恰在64,000内，192×333超）。**容量跟Spec身份走、payload不能自报**：Spec在场处用`policy["max_items"]`（由Run按字节绑定）；Spec不在场处（记录形状/轨迹/投影）用记录已携带的`spec_closure_hash`比对本仓库自己编译的修订Spec，重算而非写死常量（闭包哈希含`execution_semantics_hash()`会随无关代码变动），进程内复用以Spec文件字节为键。伪造记录自报`max_items:192`且身份重建不出时仍拿64并被拒。**真实代价比上一版写的大**：`calculator`/`constraints`/`projector`的字节原由`issue_28_v13`继承记录，补丁一改即对不上（实测`Successor execution authority bytes differ: scripts/vnext/calculator.py`，Run建出但冻结被拒），故三者必须进`RE_RECORDED_FROM_TREE`——重记文件由3个增至**6个**，补丁由三文件九处增至**六文件十三处**，本世代与父代的分歧**变宽**，如实记录不包装成隔离收益。`TEXT_SPEC_PATHS["D02"]`现指向v2，因为路由声明的192已是运行时兑现得了的数；v1字节不变留盘，已冻结Run声明的是它。材料见`docs/evidence/issue47_history/d02-item-bound/`。

Issue #47 六公司×23指标批次（每公司一进程并行，同一只读运行时代码树）：138个坐标中**100个冻结并产出公共行，38个失败且全部是同一条已命名缺口**——目标期间带10-K/A时历史路线以`*_AMENDED_TARGET_NOT_IMPLEMENTED`拒绝（Company Facts 22条、零AI 16条），Southwest与Paramount各只完成4/23。已核实不是本轮改动引入：`git log -S`定位到历史路线最初三个commit，且本轮对`historical_results.py`只动了`TEXT_SPEC_PATHS`及注释，amendments守卫逐字节未变。这是开发缺口按规则如实命名，不是披露不足；`annual_amendment_scope.py`自称未接线、不产出任何Result，所以补它不等于调用现成入口，且“带修订时哪份是target”本身是业务问题。D02容量改动按预期只动了该动的那一个坐标：Pfizer 92条41,860字EXACT并产出公共行，run_id与此前独立端到端跑的完全相同（批次独立复现）；Ford 53、Lumen 41、Paramount 27、Southwest 25、Enphase 18条均EXACT且与改动前一致。**用真实Run跑覆盖表又暴露本轮新代码的两处缺陷并已修**：(1) B03消费B01故B01结果同时记在两个Run里，同一closure下出现两份收据，原判据只数收据数就报`RUN_RECEIPT_AMBIGUOUS`，withdraw掉四个正确结果；实测两份`result_id`相同，改为比对结果——相同即一个结果被记两次，不同才是歧义。(2) 条目上限缺陷条目按坐标匹配且无`result_id`，修好之后仍在withdraw它自己要求的那个修复结果；改为`repair_state`以`_RESULT_RECOMPUTED`结尾的坐标级条目停止withdraw，点名`result_id`的条目不受影响（它指向一个坏结果而非一个坐标）。修后歧义0、verified由93升至98。材料见`docs/evidence/issue47_history/native-run-matrix-capacity-route.json`与`amended-target-gap/`。

Issue #47 修订件缺口：**上一条把它记成“待定业务口径”是错的，口径早已存在且已批准**。读两份修订件自身的Explanatory Note：Southwest只为更正Exhibit 3.2（章程）的超链接，并明写“does not modify or update in any way the disclosures contained in the Original Form 10-K”；Paramount只补Part III Items 10–14，并明写“does not otherwise change, modify or update the disclosures in, or exhibits to”。即38个坐标被拒，是因为两份修订件的存在本身。**但把两份都说成「什么都没改」要收窄**：Southwest那份确实没改任何披露；Paramount那份**改了**——它新增了Part III Items 10–14，只是明写没有另外改动其余披露及附件。政策本身就警告Part III可能影响治理、法律与关联方/债务解释，所以它只清除事件窗口、不清除原始报表数值，并把`original_statement_admission_requires_further_review`置真。把两者写成同一句话，正是这个分类存在的理由被抹掉的方式。`config/annual_amendment_scope_v1.json`逐字匹配这两句及两种purpose，`annual_amendment_scope`按原件字节证明分类；实测Southwest得`EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15`（清除事件窗口+原始报表数值），Paramount得`PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS`（只清除事件窗口，`original_statement_admission_requires_further_review`为真），零issue。这正是既有规则“有限链接更正可接入B01/B03/六事件/Company Facts，Part III不自动批准财务或主体合并范围”。新增第18个规则文件`scripts/vnext/historical_amendment_admission.py`，把Company Facts与零AI两处guard由“见修订即拒”改为“问已批准政策”，按输入类别分别判定：事件指标要`FISCAL_EVENT_WINDOW`，报表类指标要`ORIGINAL_STATEMENT_VALUES`，两类不能合在一次判定里（同一份修订对二者答案不同）；政策的9个`not_covered_metric_ids`一律拒。**目标始终是原始10-K**，修订件只作为“原件输入是否仍成立”的证据，从不作为取值来源。Paramount报表类的拒绝理由为`INPUT_CLASS_NOT_CLEARED:ORIGINAL_STATEMENT_VALUES:PART_III_ADDITION_…`，不再是`NOT_IMPLEMENTED`——把已决政策拒绝报成未实现，正是让已定问题读起来还没定。7个用例跑真实申报，其中`test_the_two_companies_do_not_get_the_same_answer`是承重的：一条无视分类的路线会通过其余全部用例、只挂在这一条。政策自带`production_authorized:false`，issue_47线本身`NOT_ACTIVATED`，故此处只是开发接线，不构成生产采纳。接上后批次立即抓到接线不完整：Southwest的14个坐标由“被修订件挡住”变为`Request-ledger locator evidence is invalid`——准入要读修订件原件，而安装器只复制`prepare_*_input`交出的`source_proofs`，修订件不在其中，装出的数据根里ledger点名了修订件字节而目录没有。修正在`historical_annual_input`：修订件既被读来判定原件输入是否仍成立，就是本次准备的已准入输入，其proof须随其余一同安装。该错误是“单独测函数全绿、接上去才露”的典型形状——`amendment_admission`在仓库树里跑得通，只有装进隔离数据根后才失败。

Issue #47 接续主体事件缺口（`HISTORICAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED`，Paramount的C01/E01–E05共6个坐标）：按前三次的模式核查，**确实是接线不是决定，但不是一行能补完的**。普通路线已按同样条件准入（`registered_event`＝事件指标且模式为`SUCCESSOR_REGISTRANT_ONLY`，用`event_target_period(continuity_status='successor_predecessor')`加宽窗口，跨主体财务合并仍不授权），前身原件也在仓库（CIK 813828共25个accession目录），所以不是来源缺口。**但只移植guard不够，已实测**：过了该guard后以`Run target period exceeds 53 weeks`失败——接续事件窗口为2024-01-01至2025-12-31，而Run坐标不得超过371天。Run的一年坐标与事件回溯窗口本是两回事（AGENTS.md早有此说），但`historical_results`组装Run坐标时`fiscal_year`取自固定期间、`period_start`/`period_end`却取自**primary结果**，于是加宽后的结果期间成了Run坐标；连续主体两者相同，所以此前从未暴露。完整移植还需两件事：(1)让Run坐标留在固定期间而结果保留加宽窗口，且不能一刀切——接续主体的B01本就合法地报短期间；(2)把AGENTS.md所述run_store对“完整原件重建且逐条一致的6事件记录”的差异认可扩到本世代（又一处补丁）。**已移植的guard又撤回**：它不改变任何结果，只是把一条已命名的拒绝换成`Run business coordinates are invalid`这种无法解释的错误——按本轮对修订件接线用过的同一标准，那对读者更糟。材料见`docs/evidence/issue47_history/successor-event-gap/`。

Issue #47 来源需求实测：**本会话反复上报的“1,443/1,950个坐标缺原件，需要有界获取授权”是错的框法**——错在把坐标数当成工作量，而这正是`historical_coverage`自己docstring警告的那件事（“把first blocking reason当成唯一blocker，就会让来源预算看起来等于全部剩余成本”）。39个指标共用同一份申报，所以坐标会坍缩：全十家五年框架下`SOURCE_MISSING_TARGET_ORIGINAL`的**1,170个坐标 = 30份不同文件**（每家每年一份10-K主文件；八家各缺四个往年，Marriott缺两个）。另外`TARGET_PERIOD_NOT_DISCOVERED`273个坐标是7个公司期间、属元数据而非主文件，未按fetch计量；`ROUTE_IMPLEMENTED_NOT_RUN`253、`HISTORICAL_ROUTE_NOT_WIRED`176、`TARGET_PERIOD_METADATA_BLOCKED`78根本不是来源问题。对照已批准预算`config/issue28_continuous_calls_v1.json`的`[240, 240, 80]`：**需要30次SEC获取，累计额度80**，需求落在既有批准之内，不需要新预算。获取路径也已存在：`tools/vnext_continuous_sec.py`（plan/capture）走`continuous_sec_acquisition.live_sec_session`，沿用原SecHttpClient、零自动重试、不可变尝试与同一总账。**仍需owner的只有两件事**：80里已消耗多少（budget_root是host本地路径`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`，本容器读不到，不得假设）；以及这30份历史主文件是否落在已批scope的purposes内——该scope写的是390个当期坐标，不是1,950个历史坐标。材料见`docs/evidence/issue47_history/source-need-quantified.json`。

Issue #47 三处验收边界（外部审阅按注错证明）：(1) `test_historical_protocol_wiring`的轨迹正例写成`except Exception: assertNotIn("TEXT_PAYLOAD_ITEMS_INVALID")`——只要异常不是容量错误就算通过。已复现：把逐项比对换成无条件抛出，旧用例仍绿。改为用生产工厂`_observations`造观察记录、要求**正常返回**，并在**第80条**替换观察记录、要求拒绝理由正好是`TEXT_TRACE_OBSERVATION_VALUE_CHANGED`/`TEXT_TRACE_REVIEW_BINDING_CHANGED`；两种注错（无条件抛出、循环截到前64）都被抓。(2) 收据选择先按result_id去重再取`candidates[0]`，仍由目录读取顺序决定。改为三步且顺序固定：**先定版本→再判各收据的冻结/验证/哈希状态→最后合并同一版本内的同结果重复**。跨版本无选择器报`RUN_RECEIPT_VERSION_AMBIGUOUS`（不因result_id相同而合并）；同版本状态不一致时报最强的一份并置`receipt_status_uniform=false`。(3) 坐标级缺陷靠`repair_state`以`_RESULT_RECOMPUTED`结尾自我释放，改那个字符串就能把未修复结果由withdrawn变verified。改为登记里的`released`块点名**被修复结果的result_id**及其closure，`repair_state`不再释放任何东西；Pfizer那条填的是实测值`a394e0b5…`/closure`1b6d9c87…`。四条新回归在被替换的旧实现下全部失败。顺带修了一个**HEAD上就红**的测试：`test_one_route_s_limitation…`断言Southwest两条路线拒绝带修订件的目标，而已批准的修订政策正确地让它们不再拒绝；已用`git stash`在`3e45533`确认该失败先于本轮。改写到Paramount上（同一期间三条路线三个不同答案），Southwest作正面对照。

Issue #47 共享来源缓存漏验：`_preparation_key`点了冻结`prepare_business_text_sources`五个参数里的四个，漏掉`raw_blobs`；命中在冻结函数之前`deepcopy`返回，于是它的`TEXT_V2_ORIGINAL_SOURCE_MISSING`检查被挡在门后。实测：灌满缓存后清空`raw_blobs`，键不变、冷路径存在性检查为False、请求照样命中。**修的不是那一个参数而是"手工维护的参数子集"本身**：键改为由全部参数导出（字节换摘要），参数集合不等于`PREPARATION_ARGUMENTS`即拒绝，冻结签名将来多一个参数会让键停下来而不是漏掉。四条回归（清空raw_blobs冷热同拒、改坏被点名blob冷热同判、五个参数逐个必须移动键、参数集合不覆盖即拒）在旧键下全部失败。有个小插曲：第一版"改坏blob"冷路径没报错——输入集有三个blob而D02只读source_reference点名的那个，取第一个证明不了任何事；负例本身要先证明它能失败。

Issue #47 历史分片消费者（`scripts/vnext/historical_metadata_context.py`，第19个规则文件）：冻结的`_current_metadata_context`在"任一已声明shard的`filingTo` ≥ 目标期末"时拒绝，然后只扫`filings.recent`。实测覆盖本仓库自己的九个公司期间（Salesforce 2019-01-31–2023-01-31、JPMorgan 2024-12-31、Pfizer 2018-12-31–2020-12-31），其中13个10-K行本身就在shard里、recent-only扫描根本找不到。**这与材料无关且顺序在其后**：`resolve_period_selection`早已读shard并从中选出Salesforce 2023-01-31的真实accession，今天先失败的是`SAVED_SOURCE_MISSING`；所以三个阻断叠在一起，取回文件只解除第一个。后继保持同一不变量（未读的块不得持有filingDate ≥ 目标期末的申报），改为经既有`load_history_for_period`把那些块**读进来**而不是拒绝；调用方自己的`_Sources`传入，所以读到的每个块都经同一请求证明准入，`check_historical_metadata_scope`要求"读到的块"与"准入的块"是同一集合。没有移动任何history行进recent，没有编辑任何submissions正文。实测对照：三个shard驻留期间由拒绝变为解析并点名来源shard；Marriott/Macy's两路一致；JPMorgan仍拒绝，理由换成真实的那个（69个声明shard有57个未保存、11个与声明区间冲突）。**shard驻留的端到端正例仍缺材料**，保留在验收清单上并写明两份最便宜的候选；本轮实跑的正例是Marriott D02 **2023-12-31**（非最新年）走完安装→原生Run→冻结→独立进程冷读→公共行，8条证据、TEXT_QUAL、零新增调用。

Issue #47 交付三层：`verified_outcome`只回答第一层，单独拿出来会被读成交付率。`render_historical_run(persist=True)`把行、证据与收据写到Run旁边的`row_receipt.json`，收据自带行/证据哈希，读取时逐一核对（改过即`ROW_BUNDLE_ROW_CHANGED`）。每个坐标带`delivery`三层——`native_run`（哪个版本产出什么、是否冻结并验证）、`public_row`（Run旁边是否有点名该result的bundle）、`content_acceptance`——**未证明的一层写明理由而不是省略**；`content_acceptance`在本仓库处处为false并说明原因。收据另带坐标键分不开的身份：pinned财年坐标、实际测量窗口、scope_key、value_kind、closure与run_id；不并入键（帧的行就是坐标），而是放在旁边使"合并"可核而非假定。汇总新增`delivery_layer_counts`与`delivery_layer_unproven_reasons`。

Issue #47 获取预算结论撤回：**"30次获取落在#28的80额度内、不需要新授权"作废**，两处都错。授权上——`[240,240,80]`绑定`requirement_id=issue_28_v14`与390个当期坐标，`continuous_call_policy`校验委托正文、scope、budget root与该requirement_id，而#47明文禁止借用#28余量；**获取能力可复用，授权不可移转**。规模上——30只是first blocking reason。实测其后还有：八家公司×四个往年财年窗口的8-K正文**476份一份未存**（当期窗口全存、往年0/476，逐行核对不是抽样），JPMorgan可达2021-01-01的40个submissions shard中28个未保存、11个已保存的与声明区间冲突。加上头文件，包络在高百位到低千位的请求尝试，不是30。另两处纠正：清单的形状是**七家×4 + Marriott 2 = 30**（原文"八家各四份加两份"=34，已改为由清单生成）；`TARGET_PERIOD_METADATA_BLOCKED`的78个坐标被归进"根本不是来源问题"是错的——两个都是JPMorgan的`HISTORY_SNAPSHOT_CONFLICT`，成因是SEC重新分片而本仓库存的是旧分片，解决要刷新索引并重取分片，属来源需求。`TARGET_PERIOD_NOT_DISCOVERED`的273个坐标里JPM三个序位是来源需求、Paramount四个是前身主体范围问题。计划分四类（已知原件30 / 元数据刷新 / 已知其他依赖 / 只能在发现后确定）并给出#47自有scope、累计账与有界上限，见`docs/evidence/issue47_history/acquisition-plan.json`；不问用户查#28的私有账本，授权前不发真实请求。

Issue #47 接续主体事件窗口已接线（第三次尝试，前两次的记录保留原义）：**事件窗口是测量，Run坐标是财年身份**。连续主体两者日期相同，所以一个字段长期兼任；接续主体不同——已批准政策把事件窗口放宽到上一自然年年初，那是两年的申报日期，Run若把它当财年坐标会因超过53周被正确拒绝。两个错误答案都不能选：放宽坐标等于让Run宣称一个它没有的财年，截断来源以适配坐标等于丢掉政策认定属于该测量的申报。`historical_zero_ai_results.event_measurement_window`给出窗口与`registered_event_scope`（已登记CIK、窗口、pinned期间、明确"不授权跨主体财务合并"），事件分支改走普通路线自己的`_registered_event_sources`；`historical_results._run_coordinate`在主结果窗口**落在**pinned期间内时沿用它（六公司批次117个主结果全部落在内，所以既有行为逐个不变），落在外时坐标保持pinned、加宽窗口留在结果上。**不是两处改动**：第三处只有跑起来才发现——Run按pinned坐标建成后在`MetricResult period differs from Run`被拒，因为run_store的共享豁免读的是普通case的形状；`historical_run.replay_case`改为把自己的component以同一字段名暴露，一个检查服务两条路线，而不是在被十四个世代按字节绑定的文件里再加一个hunk。实测Paramount C01：Run FROZEN、坐标2025-01-01..2025-12-31、独立进程冷读114条记录同run_id、公共行fiscal_year=2025而period_start/end=2024-01-01..2025-12-31、零新增调用。**剩余阻断是材料且已点名**：前身CIK 813828在窗口内31份8-K有9份正文未保存（后继CIK 4份全存），终态是`SAVED_SOURCE_MISSING`/`SOURCE_UNAVAILABLE`的WITHHELD结果，不是实现缺口。**同日同仓库跑普通issue_28_v13路线，停在同一份文件、同一个窗口**——两条路线一致，这比"历史路线成功了"是更强的检查，因为悄悄放宽或收窄来源集的移植同样会成功。**对项目记录的一处纠正**：AGENTS.md的"18件真实来源补齐后Paramount6事件原生通过"是按FY2024目标期间量的（窗口2023–2024，前身2024年申报都在）；目标期间已移到FY2025（窗口2024–2025），前身2025年的9份未保存。一条按某个目标期间记录的通过，不会因为目标期间移动而继续成立——这正是历史框架自身的问题形状，所以通过状态必须点名它是为哪个期间通过的。材料见`docs/evidence/issue47_history/successor-event-gap/wired.json`。

Issue #47 source层三处红：本轮source层实测出三个失败，**其中两个在HEAD `3e45533`上就是红的**。**这里我先写错了原因**：我按AGENTS.md里那句「`.github/workflows/vnext-fast.yml`只运行`tools/run_fast_tests.py`」推断CI不跑source层——**那句已经过时**。实际工作流有13个job，其中`vNext saved-source material`就是`run_fast_tests_v2.py --suite source-material --jobs 2`，另有9个原生Run job。真正的原因是**`3e45533`那次工作流运行是`cancelled`**（run 185），所以三处红没人看见；这正是审阅者第I条提醒的事，而我一开始把它的分量估低了。(1) `test_the_route_still_declares_the_bound_the_runtime_can_honour`断言`TEXT_SPEC_PATHS["D02"] == v1`，而容量那轮已把路由改成v2；改为断言性质而非状态：路由指向v2、冻结渲染器仍拒65、后继渲染器对v2身份交付192——即"声明的数是运行时兑现得了的数"。(2) `test_the_located_sub_note_is_built_and_refused_by_the_bound_not_the_scope`在路由上断言拒绝，路由改了就不再拒绝；改为把同一批参数喂给两个Spec身份——旧界按条目数拒绝、新界接受完全相同的集合，这才证明"挡住的是条目数不是范围也不是体积"。(3) `test_normal_zero_ai_results`在240秒超时，与本轮改动无关（并发占用），单独重跑核对。加上此前修好的`test_one_route_s_limitation`，`3e45533`这个commit至少带着三个红测试，而远端fast工作流那次是`cancelled`。

Issue #47 未关闭责任清单（本轮明确保留，不因命名改变而退出分母）：(1) 13个`HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:ORIGINAL_STATEMENT_VALUES`坐标（Paramount报表类）被已批准政策拒绝，**"需进一步审查"不等于"永久不支持"**；它们保留各自的具体依赖与后续责任，仍在目标分母内。政策自带`original_statement_admission_requires_further_review:true`，下一步是就Part III新增对报表类输入的实际影响做有界判定，而不是把这条拒绝当成终点。(2) Paramount六事件已接线但因9份前身2025年8-K正文未保存而WITHHELD，属来源需求，已进获取计划第3类。(3) Pfizer 92条摘录的**内容验收**未做：技术上Run成功与"这92条正是应取的92条"是两回事，必须用独立定位的原文（必含与必排除）核对，不能用同一个选择器生成期望答案。(4) Item 8中未被明确incorporate的内容仍由`_LEGAL`关键词表过滤、`semantic_scope_completeness_asserted=False`；16A定位与容量扩展都没有解决它。(5) 历史路线的两处D02修复尚未带回普通路线——`historical_text_results`仍声明普通路线保留原缺陷直到有兼容世代能携带同一规则；依赖关系在#47跟踪并与#28整合者对齐，不从历史任务改上游、也不假定两边已经一致。

Issue #47 D02 内容核查（按已批准口径读原文，不用选择器生成期望答案）：把四个声明范围内**每一个块**连同序号、强调/链接标志、长度、正文打出来（2712行，见`docs/evidence/issue47_history/d02-content-read/`），逐块对照Spec的`entity_scope: registrant`与定义的来源「Item 3 / legal proceedings / contingencies notes」判断。**结论：Pfizer那92条不是应取的92条**，两个方向都有错。**多取6条**：块1881–1884是**独立审计师的Critical Audit Matter**（1884开头"The following are the primary procedures **we** performed"，这个we是会计师事务所不是注册人）；2240是贸易应收账款信用损失政策，命中词在"written off after all reasonable means to collect the full amount (including litigation, where appropriate) have been exhausted"——说的是催收；2175是关键会计估计，命中在"competition, litigation, legislation"这串风险词里。后两条是`_LEGAL`关键词缺陷的两个实测实例。**漏7条**且**两个不同原因**：`Comirnaty (tozinameran)`在3858/3874各出现一次（一次在"Actions in Which We are the Defendant"下、一次在"Matters Involving…Collaboration/Licensing Partners"下），被"文内重复"判据当页眉丢掉；`Zantac`(6)/`Chantix`(7)/`Paxlovid`(8)/`Asbestos`(8)/`Docetaxel`(9)被冻结`_substantive`的12字符下限丢掉，而`Orgovyx (relugolix)`(19)等因括号里的通用名超过12字符被保留——**一个产品小标题能否活下来取决于它的通用名有多长**。段落本身都在且顺序正确，丢的是"这一段讲哪个事项"的标签。**对的部分**：范围边界[3821,3937)正确（B担保/C承诺/D或有对价/E保险都在3937及之后且一条未混入）、25个页眉块全排除、范围外的2302（或有事项附注引言）与2351（Seagen法律事项）正确纳入。改对后应为92−6+7=93。

修了其中一半，另一半明确留开。`_page_furniture`：重复块只有在**前一块或后一块也重复**时才算页眉——页眉成群出现，每个成员都有重复的邻居；重复的标题夹在两个只出现一次的块之间。无阈值、无已知标题清单。`_note_heading`：在申报自己点名incorporate的附注范围内，带字母的强调未链接块即使不足12字符也是内容；同一批里的纯页码不带字母仍被排除，注册人名按`_substantive`同样的方式排除。实测92→99、七条全部恢复、页眉由22降为20（正好是那两个Comirnaty）、Evidence PASS。**没修的6条**：真正的成因不是"审计报告漏进来"，而是`ITEM_8`（整个财务报表章节）被当作定义所说的「contingencies notes」的代理来扫描；收窄它会改变每一份申报的集合，而我只读了一份。**从一个例子发明"审计报告在哪里结束"的规则，正是这次核查本身要避免的错误**，所以留开、坐标保持撤回，下一步是先按同样方式读第二、第三份再动。

Issue #47 推送前必查Requirement快照：`3817104`的CI fast层红在`test_historical_requirement_snapshot`——`minted snapshot differs from disk: baseline_manifest.json`。成因是我在本地跑完fast套件之后又改了一个规则文件（`historical_projection.py`加`persist`），只在运行树重新mint、**没在仓库树重新mint**就提交了。这个测试正是为这种漂移写的，它工作正常；漏掉的是我的顺序。**动过任何`NEW_RULE_FILES`或`RE_RECORDED_FROM_TREE`里的文件后，提交前必须跑`python3 tools/vnext_mint_historical_requirement.py`（或至少`--check`）**，而且"本地套件绿"只对跑套件那一刻的树成立，不覆盖其后的提交。同一教训的一般形式：本地绿的证据有时间戳，commit也有，两者不对齐时前者不构成后者的证据。

Issue #47 报告层三处读取边界（外部探针给出复现，逐条修复后再复跑探针）：(1) 公共行收据只核对了它自己——行哈希、证据哈希、证据条数——所以一份**行与证据都没动、只把收据里的run_id、Requirement和来源验证状态改掉**的收据照样被读入，该坐标仍计为"已产出公共行"。现在重算收据自身身份，再要求它声称的运行、状态、Requirement就是这个Run的，声称的result也必须是这个Run在它点名的指标下真实记录过的。**但"拒绝"的落点也改了**：原实现直接抛出，一个旁挂文件就能让整张覆盖表建不起来，把其余每个Run各自独立验证过的证据一起丢掉——和"选中一个运行就把所有层都从它上面读"是同一个形状的错。manifest的三个文件哈希才是Run的完整性信封，`row_receipt.json`不在里面，改坏它伪造不了records，也就不该抹掉records；现在按名字记录拒绝理由，JSON读不动是第三种状态（`ROW_BUNDLE_UNREADABLE:`）而不是"没有行"。(2) 同版本、同期间选择、同结果的多份合格运行，原先选中一份就把三层都从它读——B01的结果既记在B01的Run里也记在消费它的B03 Run里，公共行渲染在B01那边，于是**哪个run_id排在前面决定了这个坐标算不算有公共行**。现在先用版本、结果身份和期间选择定下"哪些运行可比"，再让每层各自关联真正承载它的证据，行层自报`rendered_by`。(3) 缺陷释放的`closure is None or 相等`读起来像可选，**漏写或写null就释放了所有版本**；展示层只比对result_id，同一条目能同时出现在`withdrawn_by`和`released_defect_ids`里。现在一个完整判据两边共用，缺失/null/空/非哈希一律不匹配。另补两处**写在旁边却从不参与核验**的字段：主流程重解析的期间选择现在与收据里的`period_selection_id`比对（不一致按名拒绝——它也可能意味着保存的元数据在Run之后移动了、坐标现在选中另一份原件，这值得报告而不是解决掉），渲染器与展示策略摘要现在被读取（渲染器受closure字节绑定，所以同坐标合并的多行必须一致，这是绑定成立而不是第二套策略）；合并重复收据时也真去核对它所依据的那个"result_id能区分测量"的说法，不一致报`RUN_RECEIPT_IDENTITY_CONFLICT`。新增一条用例**从渲染器自己的收据字面量读出读取方该要求的字段集**——这些用例都是手工构造bundle，一个要求了渲染器根本不写的字段的读取方会通过全部用例、却拒绝每一份真实bundle；加一个渲染器不写的字段，该用例失败。

Issue #47 获取计划改用生产规划器重测，**原"30份原件"作废，三个原因都是跑出来的**：它按每个坐标一份文件计，而`plan_historical_sources`声明两份（原件加该accession的`index.json`）；它只数五个目标年，而五年框架还需要最早目标年的前一年（Salesforce的FY2022目标要读crm-20210131.htm）；它记"修订件0份"是在目标期间上量的，而规划器在Marriott的链条里找到一份`prior_amendment_primary`。规划器自己去重后的集合是**142**：40个年度期间身份、33个accession索引、68个JPMorgan分片、1次索引刷新——其中70个是JPMorgan的，它的分片被重新分区过，另外三个期间根本不在这个数里，要等分片到位才可量。Paramount那9份前身8-K从"发现后才知道"移入**已知依赖**：它们是已在范围内的坐标上、已接线路线的具名文件，9份全部经穷举扫描确认不在`evidence/accession_materials`，且`tools/vnext_continuous_sec.py plan`对其中一份的正文与头文件都返回`OFFLINE_SOURCE_PLAN`、calls `[0,0,0]`。事件类**每份两次请求**不是假设：`normal_zero_ai_results.py:96`读取accession的`hdr.sgml`，而186个已存accession目录里151个同时有正文和头文件、没有一个只有头文件。**累计上限给出一个整数：1232**（142+970+120），是执行停止上限，不是估算也不是完成保证——上一版给了993的类上限和"先30份"却始终没给总数。不覆盖的三项（JPMorgan事件窗口、Paramount更早期间、未接线的C02代理）逐项点名，没有可测依据就不该按猜测批准。计数与停止规则写死：失败也计数、零重试、UNKNOWN立即停该类（继续下去会让累计数不可信，而这是上限唯一无法承受的），到上限就停并按类报告剩余。#28的额度不读、不借、也不问用户还剩多少。**离线接线验证发现一处缺口**：获取CLI的准入门读的是当期依赖发现，实测只够回溯一年——Salesforce的FY2025通过、FY2024被拒。所以A类不只是在等许可，声明已经存在于`plan_historical_sources`、只是获取入口不读它；把两者接起来是#47自己的离线工作、不需要授权，且修法是把历史声明交给这个门，不是把门去掉。

Issue #47 D02审计报告边界（读了六份申报才动规则，而这正是必要的）：捷径——把范围收窄到Note 16A——一次就能拿掉全部六条，也会拿掉2302和2351，而同一次内容核查确认这两条属于范围内；为凑数丢掉已确认的披露比缺陷本身更糟。六份实测：审计报告在Pfizer/Lumen/Enphase/Marriott位于Item 8开头，在Southwest位于**结尾**（[1210,2294)里的2250–2290），在Ford**根本不存在**（它整个Item 8就是一个交叉引用块）；每份都有两份报告（财务报表与内控），有些还有非标题的提及（Marriott两行目录、Southwest的1421、Enphase的"(PCAOB ID No. 34)"）。**候选规则"强调标题→事务所`/s/`签名"通过五份、恰恰在Pfizer上失败**：它根本没有`/s/`块，收尾是任期句（且措辞都不一样，写的是无法确定从哪一年开始）。只读第二第三份就会把这条规则发出去。采用的收尾判据是"`/s/`或任期句，且该块不超过400字符"，未闭合则不排除任何东西并如实报告（无界排除可能静默丢掉真实披露，而已登记的多取是两害中较轻的）。**理由是文档部位加内容，不是说话人**：`entity_scope: registrant`回答的是披露涉及哪个主体，而1882读全文正是注册人自己的诉讼敞口；站得住的是"审计报告不是Item 3、不是法律程序章节、也不是或有事项附注"，内容也佐证（1884是1233字的审计程序，1882复述已被整取的Note 16）。实测效果：Pfizer 99→95，其余五份**逐字节不变**（proposal_id与coverage_hash都相同，不只是条数相同）。**只有Pfizer多取**——其余五家的审计报告里一条都没被取走，因为只有Pfizer的审计师点名了诉讼类关键审计事项；所以这个缺陷不常见，但成因是结构性的：任何审计师点名诉讼CAM的申报都暴露在它之下。**条数相同掩盖了我自己引入的一个缺陷**：第一版跳过整个块而不是只跳过D02那一支，于是把同样的块从D03的监管候选集里也拿掉了——D03有自己的已批来源、本轮根本没量过，受影响的正是这条规则本该原样放过的四份申报；六份的候选条数在两种实现下完全一致，是比对记录才抓到的。**"修正后应为93"据此收窄为95**：93假定六条一起离开，实际审计报告规则拿掉四条、关键词缺陷握着另外两条；这正是那个数必须保持为待验证预测而不是目标的原因——一个被调到输出93的实现，必须为错误的理由拿掉两条。剩余未做：2175/2240两条（`_LEGAL`关键词代替"这是不是法律程序披露"的判断）、95条的内容验收、以及其余四个年度（多数公司的往年原件未保存）。

Issue #47 Paramount Part III 修订对报表类输入的有界判定（**做了审查，没有做决定**）：13个坐标（A05/A06/A07/A08/A10/B01–B05/B07/B08/B09）被已批政策以`ORIGINAL_STATEMENT_VALUES`未清除挡住，而政策自己把`original_statement_admission_requires_further_review`置真——那个标志就是在要求做这次审查。三条互相独立的依据：修订自己的说明（第75块「to amend Part III, Items 10, 11, 12, 13 and 14 … to include the information required by such Items」，第76块「does not otherwise change, modify or update the disclosures in, or exhibits to」）；修订内部的明确声明（第1565块「No financial statements or supplemental data are filed with this Amendment」，这句正是政策的`no_financial_statement_pattern`）；以及**数出来而不是推出来的**事实——修订只带7条非DEI原生事实且检查器证明它们属治理分类，原件带2926条，也就是说修订里根本没有报表类指标可读的东西。不覆盖的范围逐项写明：9个`not_covered_metric_ids`（B06/B13/C02–C04/D01–D04）无论分类一律仍拒，这是对的，Item 13关联方与Item 10治理正是其中几项要读的；本结论只针对这一份修订，别的Part III修订可能真的重述了什么；主体接续另算。**决定权不在我这里**——它改变的是一个指标会接受哪些输入，属正确性标准。推荐方案：让Part III新增只在两项机械证明同时成立时清除`ORIGINAL_STATEMENT_VALUES`（无财报声明在场，且修订不带治理分类之外的原生事实），这样「不自动批准」这条既有规则原封不动——仅凭分类仍然什么都不清除——而能自证的个案可以通过；一份真的重述了报表的Part III修订会带上财务事实，照样被拒。代价是按既有修订机制改一份政策与两行清除规则。反方意见也记下来：条件规则仍然是从一份修订写出来的，本仓库只有这一份Part III修订，条件只在一个正例上验过、没有反例。本次审查没有改动任何政策文件或清除规则。

Issue #47 CI没有绿色终态的真正原因：审阅指出run 194没有终态，实际读它的13个作业后结论是**三个作业各自恰好撞上自己的`timeout-minutes`**——`capacity native Runs`上限15分钟跑了15分15秒，`capacity program-role`上限20分钟跑了20分15秒，`saved-source material`上限35分钟跑了35分15秒；另外十个作业全部success。作业超过`timeout-minutes`会被标为`cancelled`而不是`failure`，所以整轮读起来像"被取消"，而没有任何断言失败。前两个已由`0002`补丁覆盖（尚未应用），第三个是新的：`0003-split-saved-source-material-job.patch`把该作业拆成`--shard 1/2`与`--shard 2/2`两个30分钟作业。只抬高单一上限能撑一阵然后再次失效——这一层随Issue增长，现在已有76个用例，而单作业意味着每次推送都要等半小时以上。`--shard i/n`在`tools/run_fast_tests_v2.py`里（本会话可以推送），所以补丁应用之前拆分能力就已存在、不应用时原命令也逐字照旧。分片**按每个用例自己声明的超时预算而不是按个数**平衡（三个长用例不能落在一起），`tests/vnext/test_source_tier_shard.py`断言每个用例恰在一个分片、分片不随运行漂移、且任一分片不超过均分加最重单例。另外把`test_historical_text_boundary`的申报准备与文档派生做成每份申报只做一次的模块级夹具（各用例拿到深拷贝，断言的是选择器对输入做了什么、从不断言准备本身，所以共享输入不会削弱任何一条）；同样16个用例实测297秒→200秒——该作业在本轮新增用例之前就已经超出上限15秒，不能只靠抬上限。

Issue #47 D02剩余一半（`_LEGAL`关键词代理）已量过，结论是**方向反了**：同样六份申报实测，Item 8上靠关键词准入的共17块，其中**14块是对的**——Pfizer的2302/2351、Southwest五块（1428是暴风雪后"could be subject to fines and/or penalties resulting from investigations"，位于基础列报附注里但确实是注册人自己的或有事项；1580/1581/1584/1585是军假集体诉讼与2019年客服代理集体诉讼）、Marriott三块（含"Other Legal Proceedings"标题）、Lumen两块（"We are subject to various claims, legal proceedings and other contingent liabilities"与诉讼计提季度复核）、Enphase两块；**错的只有3块**——Pfizer 2175/2240，外加新发现的Lumen 1670（法律费用政策，命中在"advise us on finance, regulatory, litigation, and other matters"这串顾问事项里，与2175同一形状）。Ford为0，因为它整个Item 8是交叉引用。所以**收窄Item 8会为拿掉3块而丢掉14块**；**按位置判也不行**——Southwest 1428在政策段里却该留，Lumen 1670与Pfizer 2175/2240同样在政策段里却该走，区别不在它坐在哪。观察到的判据是：该留的每一块都在谓述注册人自身（is/are subject to、party to、could be subject to、we review our…accrual）或是标题；该走的每一块，关键词都落在一串逗号枚举或括号里而中心词是别的东西。**没有实现它**：17块里错3块是已登记缺陷，而误删14块中任何一块都是已披露内容的静默丢失，两种错误不对称；一条从六份申报、每份一个期间写出来的语法判据，正是会在第七份上失灵的那种。材料见`docs/evidence/issue47_history/d02-content-read/keyword-proxy-scope.json`。

Issue #47 获取接线缺口已补（`scripts/vnext/historical_source_acquisition.py` + `tools/vnext_historical_sec.py`）：获取CLI原本用当期依赖发现做准入门，实测只够回溯一年（Salesforce的`crm-20250131.htm`通过、`crm-20240131.htm`被拒"URL is not a declared dependency"），而五年框架要四年。**声明本来就存在**——`plan_historical_sources`已经产出去重后的完整依赖集（含URL、accession、角色与保存状态），只是获取入口不读它；现在读它。**不是绕过那道门**：门正是用来阻止任意URL被取走的，修法是把历史声明交给它，未声明的URL按名拒绝。承重用例在同一条里同时问旧门和新门（旧门拒FY2024、新门planFY2024），所以一个"什么都接受"的门会挂在这一条而不是挂在真实请求上。它**不是规则文件**——只做计划与准入、不执行Run，和`historical_coverage.py`同理；旧工具与当期发现逐字节未动，因为二者都被`issue_28_v14`基线与已批调用政策的`rule_paths`点名。**执行部分故意缺席**：`continuous_sec_acquisition.live_sec_session`硬绑`issue_28_v14`，其ledger读的是该Issue的委托、预算根与上限，复用就等于动用#28额度；`capture`在构造任何传输之前先拒，理由点名`config/issue47_historical_calls_v1.json`及它必须携带的六个字段。这把"给一个数1232"变成"给一个可被代码读取的对象"——requirement_id必须是`issue_47_v1`，一份写着`issue_28_v14`的记录会被拒而不是被当作回退。

Issue #47 剩余实现逐项点名（全框架实测、不带runs-root，所以说的是路线不是某次批次）：39个指标中**23个**已有历史路线；**8个**只有结构适用性（A03/A04/A09/A11/A12/A13按financial门控、B10/B11按lodging）——不适用处的`N_A_STRUCTURAL`是真答案而不是缺路线，适用处仍无路线（B10/B11对唯一那家酒店公司占94里的6个）；**8个完全没有路线**：B06、B13、C02、C03、C04、D01、D03、D04，恰好是修订政策九个`not_covered_metric_ids`减去D02——不是巧合，它们是债务构成、产能、依赖代理材料的治理与语义路线，也正是修订政策不自动放行它们的同一原因。1950个坐标分布：缺原件1170、有路线未运行335、期间未发现273、无路线94、元数据阻断78。**94怎么读**：每个未接线指标都是11，因为11就是有原件的期间数；另外39个期间先报缺原件，同一指标在那里同样没路线、只是不进这个计数。所以接完这8条，今天移动88个坐标、原件到位后移动8×50=400个。剩余工作因此是两条互不替代的线：142次获取把11个期间变成50个，8条路线把39个指标变成39个。材料见`docs/evidence/issue47_history/remaining-implementation.json`与`frame-ceiling-today.json`。

Issue #47 那8条未接线路线**不是同一种活**（按各自Spec读出来的，不是数出来的）：**未阻断的确定性**只有C04与B06——C04是`source_mode: structured`，其`auditor_change_dual_source_v1`读`AuditorName`概念加财年8-K item 4.01集合，而这两样都已各有历史路线（Company Facts那条与本轮刚完成窗口分离的已登记事件那条），所以它是组合而不是新建；B06是`structured_first_ai_fallback`，结构路径在先且已有v3–v6多个变体，但守卫最多，便宜不等于容易。**卡在模型额度**的有四条：D01是`ai_text`，B13/D03/D04走语义审阅路径——**这是第二种额度，不是SEC那一种**，获取计划的1232只涵盖SEC请求尝试，把它当成完成框架的代价会漏掉一整类，这与"把first blocking reason当唯一blocker"是同一个错；因为这四条尚未接线、没有东西可计数，所以**不给估数**。**卡在材料**的有两条：C02与C03都读年度股东会DEF 14A，已保存清单列出85份代理材料而只存了10份且全部2026年申报，所以历史C02/C03会解出最近一期、对更早每一期都点名来源缺口——`historical_text_input`对C02早就是这么说的；它们**不在获取计划的上限里**，因为未接线的路线没有依赖可声明，等接线了才进计划。**下一个实现选C04**，但现在不动：给指标接路线要改`historical_results.py`，那是规则文件、会移动Requirement closure，而批次正跑在当前closure上并且是它的证据；在报告底下换掉closure会让那份报告描述一个没有跑过的版本。顺序是：跑完批次、按它自己的closure报告、再接C04。

Issue #47 更早年份的实际交付（Marriott 是唯一有多个期间存着原件的公司，三个年度同一批次同一 closure）：**2025 交付 15 项 EXACT、2024 交付 9 项、2023 交付 7 项**。两种丢失原因不同。六个事件指标在**每一个**非最新年都丢，因为往年财年窗口的 8-K 正文与头文件一份未存（另测八家共 476 份，即计划 B 类）。B02/B03 只在 2023 丢、2024 不丢。**这一条我连错两次，记下来**：第一个解释"上一期原件没存"被 Ford 证伪（它 2025 目标的上一期正文同样缺失，B02/B03 却都是 EXACT）；第二个解释"上一期 accession 的 index.json"被 Marriott 2024 证伪（它上一期的 index 同样缺失而 B02 是 EXACT）。**是 reason code 把我带偏的——它点名 index.json，那只是第一个被尝试的文件，不是需求**；只读那个码会得到第二个错误解释，而且看起来像是测出来的。三种组合实测：Marriott 2023（上一期 index 与正文都缺）失败；Marriott 2024（index 缺、正文在）成功；Ford 2025（index 在、正文缺）成功。所以**需要的是上一期 accession 的材料**，两者都缺才失败；"该路线在两者之间有回退"是从三个结果推的，不是从代码读的，这一点如实标注。对计划的意义：每个目标都要读它前一年，五年框架要**六年**的 accession 材料而不是五年——这正是规划器为 4 个目标年缺口声明 5 份原件的实测形态，也是作废的那个"30"（每目标年一份文件）会让每家最早目标年都落在这个状态的原因。**对上一条结论的纠正**：我说过"142 次获取与 8 条路线是两条互不替代的线"，它们也不是独立的——Marriott 2023 这些路线全部接线，交付 7 而不是 15。获取同时是**已接线路线在它们够得到的期间里能否交付**的前提。同法核过 C04：`auditor_filing` 要读每个 accession 的 index.json，Marriott 2023 的目标件与上一期件都缺，2025 的都在，所以历史 C04 今天接上只在最新期间交付、对更早期间点名来源缺口。

Issue #47 分片驻留端到端正例**今天根本跑不了**，这是测出来的不是推的：对十一个有原件的目标期间逐个读它 10-K 行自带的 `metadata_origin`，**十一个全部在 `filings.recent`、零个分片驻留**。所以这条待办是卡在获取上，不是卡在实现、也不是我选择推迟——本仓库里没有任何一个期间同时满足"有原件"和"分片驻留"。覆盖边界要说清：`historical_metadata_context` 的读分片路径有三个分片驻留公司期间的单元覆盖（能解析并点名来源分片），但**从未有任何一个分片驻留期间建过 Run**，所以从该元数据视图往下的安装→原生Run→冻结→冷读→公共行整条路没有端到端验过；单元覆盖说的是"视图解得出来"，没说下游处理得了从分片选出的期间，而本仓库的历史恰恰是一连串"接起来才失败"的事。最便宜的解锁是 Salesforce 的 2023-01-31 与 2022-01-31（行在分片里、原件属计划 A 类），已在计划内。材料见 `docs/evidence/issue47_history/history-shard-wiring/blocked-positive.json`。

Issue #47 C04 历史路线已接通（`historical_governance_input.py` 第21、`historical_governance_results.py` 第22个规则文件）：**先撤回我自己几条提交前写的"接上去也没有新东西"**——那句把两个帧换掉了，历史帧里 C04 对每个期间报的都是 `HISTORICAL_ROUTE_NOT_WIRED`，在那里出一个值就是新的，普通路线覆盖最新期间是另一条路、不能抵消。**只换了一条规则**：冻结的 `select_governance_metadata` 用"所有已载行 reportDate 的最大值"判定当期，只对最新年正确；读分片的 cutoff 循环本来就按期间写、不需要后继，`resolve_c04` 的比较一行未动。实测端到端（closure `sha256:6d6feef5…`）：Marriott 2025 Run FROZEN、值 0、EXACT、PUBLISHED、公共行 OK、1 条证据点名原件、零新增调用；2023/2024 同样 FROZEN 但 WITHHELD、0 条证据、理由 `HISTORICAL_GOVERNANCE_SOURCE_ROUTE_UNRESOLVED` 并点名缺失的上一期 `index.json`——**来源缺口按来源缺口报**。整帧 `HISTORICAL_ROUTE_NOT_WIRED` 94→83、`ROUTE_IMPLEMENTED_NOT_RUN` 335→346、`historical_route_implemented` 1472→1522、已接线指标 23→24。**注错验证第一轮不算数**：把撤回分支换成"确认无变更 0"确实挂了三条，但挂在记录校验器的 `Observation source binding is incomplete` 上——那是校验器抓伪造绑定，不是用例抓语义；第二轮用选择器真正选中那份申报补全绑定后，才由用例以 `('NONE','WITHHELD')` vs `('EXACT','PUBLISHED')` 抓住，而这正是 C04 最暴露的失败形态。**还有一处顺序我先做错**：第一次端到端跑在加规则文件之前的 closure `7588e4ff…` 上，加了两个规则文件后 closure 变了，那次就成了仓库不再 mint 的版本的证据；重 mint 后重跑结果相同。这就是 AGENTS.md 已记的"本地绿有时间戳"，只不过这次对象是 closure 而不是测试套件。**不交付的部分**：C04 的五年。最新期间以外全部 WITHHELD，因为比较要读的 accession 索引与实例属获取计划 A 类；接线与交付是两件事，这是第一件。

Issue #47 B06 **不是一条路线，是一条六级级联**——**撤回我上一条按 Spec 读出来的判断**。上一条写"B06 是 `structured_first_ai_fallback`，结构路径在先且已有 v3–v6 多个变体，守卫最多但便宜不等于容易"，那是读 `source_mode` 和 `catalog/r5` 里四个 Spec 变体得出的，**没有读普通 Run 实际从哪个入口产出 B06**。读 `normal_run_v3.py` 的 B06 分支后：① `b06_current_input.prepare_current_debt_input` 证明本期修订未改变债务/权益输入，未证明即 `withheld_current_debt_case` 且后面全不跑；② `ordinary_debt_guard` 的非正权益守卫——`NOT_MEANINGFUL` 是**终答案不是拒绝**，权益非正时这个比率本就无意义；③④⑤⑥ 依次尝试 `ordinary_special_debt_scope`（守卫说 `EXISTING_SPECIAL_SCOPE_REQUIRED` 时）、`normal_note_debt_results`、`normal_bond_debt_results`、`normal_inclusive_debt_results`；⑦ 全部谢绝后才落到经 `ordinary_remaining_cases` 的 `b06_disclosure_v2`。**四个 Spec 变体是同一条级联的四种语法，不是可挑一个的备选**，而我接的那个是最后的兜底。已写出的 `historical_debt_results.py`（兜底语法的定期形态）**已删除**：它确实能跑、且与普通兜底逐字一致（Marriott 2025 两边同为 `DISCLOSURE_NOTE_MISSING_OR_AMBIGUOUS:us-gaap:DebtDisclosureTextBlock`），但**复现兜底不等于复现 B06**——实测普通链路对 Marriott 的答案是守卫给出的 `NOT_MEANINGFUL/DENOMINATOR_NONPOSITIVE`，是关于这家公司的真实结论；只接兜底会在历史帧里报 `B06_SOURCE_RELATIONSHIP_UNRESOLVED`，那是另一句话，**把错答案放进帧比诚实的"未接线"更糟**。拦下它的检查是"接线之前先拿同一问题问普通链路"，和接续事件窗口用的是同一条。四家实测到达三个不同阶段（Marriott 守卫终止、Ford 特殊范围、Enphase/Southwest 继续债务语法），所以没有单一语法能代表这条路线。历史 B06 需要每个**可达阶段**各自的定期形态，而不是其中一个；把它和 C04 一起叫"未阻断的确定性"，是把两件不同体量的事放进了同一个桶。材料见 `docs/evidence/issue47_history/b06-is-not-one-route.json`。

Issue #47 B06 历史路线已接通（`historical_debt_results.py` 第23个规则文件）：**先撤回我上一轮自己写的"B06 体量更大"**——那句是没调查就下的结论，查完两处都错。**第一，不是六级是七级**：`normal_run_v3` 的 else 分支落到 `ordinary_remaining_cases`，那里又调一次守卫，NOT_MEANINGFUL 时直接用守卫自己的记录建结果，否则才走 `_b06_resolution`；我上一轮写完又删掉的模块实现的恰好是这最后一级，所以 Marriott 答案对不上不是巧合而是必然。**第二，七级是同一个替换做七遍**：每级唯一的期间依赖都是那两个"取最新年报"的准备动作，其余全在读该份申报自己的字节。**为什么七级必须一起接是实测不是论证**：Marriott 停在分母守卫（`B06_guarded_v3.md`）、Ford 停在特殊范围（`B06_new_source_v2.md`）、Enphase 停在票据账面（`B06_note_carrying_v4.md`）、Macy's 停在债券（`B06_bond_leases_v5.md`）、Southwest/Pfizer/Salesforce 走兜底解析器——五家五级四个 Spec，只接一级会让另外四家拿到那一级的答案，有证据、有把握、且是错的。

**差分测试抓到一个真 bug，而它正是差分存在的理由**：普通级联读的是**两个**年报准备而不是一个。`normal_annual_input` 按报告期末推财年，`normal_annual_input_v2` 调用它之后用发行人自己的 DEI 标签覆盖那个字段；来源走查（`_prepare_b06`）与修订范围（`prepare_saved_amendment_scopes`）读第一个，Run 坐标与各语法的 `annual_label_input` 取第二个。我第一版把一个 pinned 输入喂给了两处，**十家里九家照样通过**——日历年公司两者相同；只有 Salesforce 截至 2026-01-31 的年度前者叫 2025、后者叫 2026，而 `_rebuild_equity` 会从申报字节重算整个 period 字典并整体比对，于是恰好在那一家以 `B06_GUARD_ANNUAL_SOURCE_IDENTITY_CONFLICT` 失败。修法不是绕过守卫而是把 `prepared["original_input"]`（pinned 输入自带的原始档）交给该读它的两处。**一个副产品结论**：同样的 `annual_period(...) == period` 整体比对也出现在 `ordinary_special_debt_scope.native()`，但已发布的其他历史路线只比日期与相邻性、不比 fiscal_year，所以没有同类潜伏缺陷（逐处核对过，不是推断）。

**bond 与 inclusive 是同一个算法**：归一化六个名字后两个冻结函数体只差"策略如何列概念"和范围拒绝消息一句，故本模块一份实现服务两者；担保方式是每次运行重新归约两个冻结体并要求 diff 为空——它们将来若不再互相归约，这份共用实现就不再对两者都忠实，而这正是会被发现的地方。**未被真实材料跑过的两级如实登记**：本仓库没有任何当期申报命中 inclusive 语法，也没有任何当期修订改动了债务/权益，所以第 6、第 7 级（`INCLUSIVE`、`CURRENT_INPUT_UNRESOLVED`）是"实现了但没有 Run 跑过"，支撑 inclusive 的是上述归约回归而不是一次 Run。**两处不一致都是既有阻断**：JPMorgan 在期间选择就以 `SAVED_HISTORY_INCOHERENT` 拒绝（分片被 SEC 重新分区，已在获取计划里），Paramount 是每条历史路线共有的接续主体缺口，都不是本路线引入的。覆盖表 wired 由 24 升至 25。材料见 `docs/evidence/issue47_history/b06-cascade/differential.json`。

Issue #47 25指标×11期间批次（一个期间一进程、同一只读运行时树、closure `sha256:95a0f340…`、零新增调用）：**357个坐标全部尝试，正好等于批次前帧里`ROUTE_IMPLEMENTED_NOT_RUN`的357**——有路线没跑过的那批被完整消化。**343产出冻结Run与公共行、14失败**。**但343不是交付数，把行当交付就是把三件事数成一件**：其中**139带数值**（137 EXACT＋2 APPROX）、**164是结构不适用**（`TRAIT_NOT_APPLICABLE`，该指标对该公司本就不适用，这是真答案不是缺口）、**40跑了没有值**。那40里**5个也是答案**（3个`DENOMINATOR_NONPOSITIVE`、2个`RATIO_NUMERATOR_NOT_POSITIVE`，即比率对该公司无意义），另外35个点名缺的材料：24个零AI来源未解（往年财年窗口8-K正文，计划B类）、5个治理来源未解（C04要读的上一期accession索引）、3+1个B06来源未解、1个Company Facts路线未解、1个全分支拒绝。**14个失败全在Paramount且都是已命名的既有阻断**：13个是已批修订政策对报表类输入的`ORIGINAL_STATEMENT_VALUES`未清除（已做有界审查并记录，但该决定改变一个指标接受哪些输入、属正确性标准，权不在此处），1个是B06接续主体范围未实现。

**帧怎么读（三层，不能压成一个率）**：1950是五年目标；其中**1521在等获取**（1170缺原件、273期间未发现、78元数据阻断），任何实现量都不移动它；**今天够得到的是429**（11个有原件的期间×39指标）；429里**357有路线**（72没有：6个未接线指标加唯一那家酒店公司的B10/B11）、**343产出Run**、**139带数值**。`verified_outcome`为302（139＋164−1个已登记内容缺陷），`content_acceptance`**全帧为0并写明理由**——冻结Run加公共行只说明路线算出了东西且字节已绑定，没说那个值是对的值。材料见`docs/evidence/issue47_history/native-run-batch-25-metrics.json`。

**一处操作教训**：批次第一次跑到一半（13:51）被我自己杀掉——它用`setsid nohup`启动，但父进程链上仍挂着启动它的那个harness shell，我按ID清理僵死等待器时把它一并带走了。`setsid`挡不住harness的task记账。**detach出去的东西不在task列表里，而不在列表里的东西会被当成已完成或垃圾**；重跑时改用harness自己的后台任务，可见即可控。同源的坑本轮共三次：两次`pkill -f <pattern>`杀掉自己的shell（shell命令行含该pattern），一次`until ! pgrep -f <pattern>`等待器等自己退出而永不结束——判据只要出现在自己的命令行里就会自匹配，改用按文件存在判定即可避免。

Issue #47 外部审阅（GPT-6 Pro，对 `3e88680`）三处必办已关闭，另三处结论撤回。**先说最要紧的：`3e88680` 的 CI 是红的，而我上一轮报告时没看。** 红在 `test_historical_requirement_snapshot`——`minted snapshot differs from disk: baseline_manifest.json`。本地复现并逐字节定位：仓库树的 manifest 把 `historical_debt_results.py` 记成 **48,388 字节**，而该文件当前是 **52,311 字节**。成因是顺序，不是内容：加完 `_withheld_source_case` 之后我只在**运行树**重新 mint，没在**仓库树** mint。**不是覆盖旧 Run 身份来制造通过**——两棵树都是 52,311 且同一 SHA，运行树的 manifest 也早已记录 52,311，即批次本来就是对着当前字节跑的；重 mint 是让仓库追上真正执行过的那份，而不是反过来。三个重记文件（`calculator`/`run_store`/`records`）两棵树仍不同，那是注册补丁，属已记录的"一棵代码树一次只满足一个世代"。这是 AGENTS.md 已写过的同一条教训第二次发作，第一次是"本地套件绿之后又改了规则文件"，这次是"重 mint 去了另一棵树"。

**Lumen 的已知错误此前只写在散文里，没有进入登记，所以报告仍只扣 Pfizer 一项。** 已按实际结果对账：读本批次 Lumen D02 的 Run 记录（result `cb34c981…`、run `81223cbf…`、closure `95a0f340…`、41 条），块 1670 确实在里面，正文就是那段"外聘法律顾问费用"的政策段。同时把三个普查判错的块对全部 11 份批次 D02 结果做了穷举扫描：Pfizer 2175/2240 在（已被坐标级条目撤回）、Lumen 1670 在（现已登记）、其余九份一个都没有。新条目是坐标级、`same_cause_as` 指向 Pfizer 那条并点名共同根因（`_LEGAL` 关键词代理），`confirmed_in` 记的是从 Run 读出来的身份而不是普查的预测。**`known_content_defect` 1→2、`verified_outcome` 302→301。** 教训一句：**发现错误和撤回错误是两件事，只有第二件会移动数字**；`content_acceptance` 全帧为 0 不能替它兜底，"尚未验收"与"已验出错误"必须分开计。

**14 个已失败的坐标此前在覆盖表里读作"从未运行"。** 修法不是记住那次尝试，而是**现在去问路线**：一条今天拒绝某坐标的路线，对任何人都拒绝，所以拒绝是可从仓库重新导出的测量，比一份可被编辑的尝试日志更强。新增只读 `scripts/vnext/historical_route_refusal.py`（只问、不建 Run、零调用，非规则文件），`historical_coverage` 增 `explain_not_run`、`tools/vnext_history_coverage.py` 增 `--explain-not-run`；问了就给 `ROUTE_IMPLEMENTED_REFUSED` 并带路线自己的原话，没问就在 detail 里写明"该区分未计算"而不是暗示没跑过。实测 14 个全部变为 REFUSED：13 个 `HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED:ORIGINAL_STATEMENT_VALUES`、1 个 `HISTORICAL_B06_SUCCESSOR_SCOPE_NOT_IMPLEMENTED`。承重用例问同一公司同一期间的两个指标并要求两个不同答案（Paramount 的 B01 被拒、D02 可准备），一个"对什么都给同一答案"的探针会通过其余全部用例、只挂在这一条。

**位置级索引已出，且计划集与终态集是按集合比对不是按总数。** `docs/evidence/issue47_history/batch-position-index.json`：计划集由"已接线指标并上各公司结构不适用指标"**重新导出**（不读批次自报的 attempted），终态集经 `collect_run_receipts` 读取并先校验每份 manifest 的三个文件哈希。结果：**计划 357 = 终态 357**，343 份 `RUN_FROZEN_WITH_PUBLIC_ROW` 全部收据已验证且公共行被接受，14 份 `ATTEMPT_FAILED`；零不可读 run 目录、零"声称有 Run 而无已验证收据"、零跨 closure 收据、零同坐标结果不一致。

**"1521 个坐标全在等获取、任何实现都不移动它"撤回，错得可量化。** 273 个未发现期间里 JPMorgan 117 个确属来源（68 条目录限制：57 个分片未存＋11 个快照不连贯），**Paramount 156 个不是**：它零条目录限制，后继 CIK 2041610 只有一份 10-K（2025-12-31），前身 CIK 813828 有六份（2024 回溯到 2019）且全部已在已保存申报清单里，期间目录只是不跨主体过渡。更锋利的一点是**前身 FY2024 的原件 `para-20241231.htm` 就在盘上**——那 39 个坐标一次下载也不需要，纯卡实现。修正读法：只卡获取 1365、只卡实现 39、两者都卡 117。

**"35 项点名了缺的材料"也撤回，6 项不是材料。** 逐项重新导出而不是按错误码归类：22 项 `MATERIAL_NOT_SAVED`（点名 URL）、7 项 `MATERIAL_REQUEST_RECORDED_AS_FAILED`（Salesforce 六个事件加 C04，账本里只有两条失败 GET，都是 2026-07-09 的 `.hdr.sgml` 且带 `<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>`；`annual_update.saved_source` 按设计拒绝把"最近一次尝试失败"的 URL 当已保存，所以早先的成功不能顶上——**这不是本进程发的请求，账本未变、最后一行是 2026-09-08**）、5 项是"比率对该公司无意义"的**真答案**、3 项 `SOURCE_RELATIONSHIP_NOT_PROVEN`（Ford/Pfizer/Southwest 的 B06，申报在盘上而债务关系证不出，任何下载都不解决）、2 项 `ROUTE_ORDERING_CONDITION_NOT_MET`（Paramount/Southwest 的 C04，`C04_FILED_TARGET_MUST_BE_FIRST`，实现条件）、1 项由缺失输入派生（Marriott-2023 B03 消费 B01）。

**Paramount 那 13 项：政策放行也产不出结果，这是量出来的。** 在探针进程内把准入入口整体站下（不改任何政策文件或清除规则，且返回的记录自带 `PROBE_ONLY_...` 标记），13 项**全部再次被拒**——11 个 `HISTORICAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED`、2 个 `HISTORICAL_ZERO_AI_SUCCESSOR_SCOPE_NOT_IMPLEMENTED`。所以"政策决定"和"接续主体实现"是两件独立的活，把前者报成 13 项的阻断会盖掉后者。材料见 `docs/evidence/issue47_history/review-gpt6pro-3e88680/`。

**"已经没有不被材料或额度卡住的接线工作"撤回。** 最直接的反例是获取入口自己：`tools/vnext_historical_sec.py` 的 capture 分支在**许可存在时仍报 `ISSUE_47_SEC_EXECUTION_NOT_WIRED`**——执行路径没实现。#47 自己的许可核验、累计计数、请求执行、不可变保存与来源安装之间的连接，是不需要任何授权的离线工程，可以用明确的测试许可与受控响应先验证，生产入口继续拒绝未授权真实请求。`SecAcquisitionSession` 不能直接复用：它的 `_check` 按 `requirement_id == issue_28_v14`、`limits == [240,240,80]`、#28 的 budget_root 与 #28 自己的离线接线收据逐项断言，而它是 #28 的冻结规则文件——所以 #47 需要自己的后继会话，复用 `SecHttpClient`、`initialize_source_inputs`、`validate_acquisition_checkpoint` 与本 Issue 已有的依赖准入门。这条尚未开始。

Issue #47 外部审阅第三项重做（前两项按裁定关闭，不重跑357个位置去修报告）：`probe_route_refusal`确实调用完整准备入口、会进入生成指标结果的路线，而覆盖表同一份记录里声明未执行业务——已复现，探针一次跑出6次calculator调用，并且它的`except Exception`把`AssertionError`一起吞了。修法不是把诊断藏进覆盖表，而是**把两个问题分开**，因为它们本来就不是同一个问题：**"过去有没有尝试过"**只能由过去的记录回答，新增只读`historical_attempt_records.py`读批次自己的`native-run-matrix.json`，只读不执行；**"今天这条路线会怎么答"**由独立诊断回答，`historical_route_refusal.py`改成`diagnose_route`，自报`business_execution_invoked: True`、携带执行身份（世代、引擎是否在本树注册、baseline哈希），并把结果分成三类——`ROUTE_DECLINED`（九个已命名路线异常类之一）、`ROUTE_PREPARED_THE_POSITION`、`PROGRAM_FAULT`，`AssertionError`原样抛出。**"任意程序异常都算准入拒绝"正是把实现缺陷读成业务结论的方式**，所以第三类必须单独存在并写明它不是拒绝。入口是新CLI `tools/vnext_history_diagnose.py`；覆盖表不再引用诊断，14个失败位置改为`ROUTE_IMPLEMENTED_ATTEMPT_FAILED`并点名产物路径、错误、停在哪一层，没有记录的位置写`historical_attempt: UNPROVEN`而不是暗示没跑过。

**零调用测试第一版是空的，这比没有测试更糟**：我在`vnext.calculator`模块属性上打桩，而调用方早已`from X import name`绑好名字，于是一段真的在计算的代码读出零次调用。改为遍历全部已加载`vnext`模块的绑定逐个打桩，并在某个名字**没有任何绑定**时直接拒绝——否则名字一改，测试会静默变回空的。修好的仪器立刻抓到一件事：`parse_accession_xbrl_source`在**每一种模式**下每个已确定期间都被调用一次，来自`normal_history_plan._native_instance_alternative` → `annual_period`。所以原来那个裸的`business_execution_invoked: False`本身就不准确；现在改成结构化声明：指标未评估、calculator零次、但来源规划器对每个已确定期间解析一份accession，并说明为什么那不是评估（读的是pinned申报自己的DEI上下文以确认财年，不进入任何指标）。**"没有执行业务"必须说清是哪一层没有执行**，而这一句只有仪器修对了才问得出来。

来源分类收窄（按裁定"限定在实际核验层"），**`implementation_only: 39`撤回，而且是量出来的不是让步**：Paramount前身2024-12-31的目标原件`para-20241231.htm`确实在盘上，但同一位置往下还缺两样——上一期`para-20231231.htm`没有accession材料目录，而B02/B03要读上一期accession材料（Marriott三个年度实测过）；接续主体事件窗口2023-01-01..2024-12-31内前身15份8-K**一份都没有材料目录**（2024年的22份全有）。所以那39个位置"只卡实现"是错的：期间目录确实是先答的那一层、也确实属实现，但六个事件指标和B02/B03在同一位置还缺材料。**反方向同样收窄**：`SOURCE_MISSING_TARGET_ORIGINAL`只是first blocking reason，不证明路线存在——8个指标根本没有历史路线，材料到了照样算不出来（Marriott 2023目标原件在盘上、25条已接线路线只交付7条，是从另一端读出的同一个不对称）。两端的"only"都不成立，`acquisition_only/implementation_only`这个切分本身作废；保留的只有各层"哪一层先答"的计数，它不能用来给获取授权或实现计划定规模。

CI没有绿色终态的原因第二次确认：run 213在`fc95cca`是`cancelled`而不是`failure`，13个作业10个成功、3个各自撞上自己的`timeout-minutes`（capacity 15分钟跑15m04s、program-role 20分钟跑20m17s、saved-source 35分钟跑35m22s），**没有任何断言失败**。这是run 194同样那三个作业的第二次，所以不是抽到慢runner。三个补丁都重新`git apply --check`过、单独与连续都能应用，但本会话的GitHub App没有`workflows`权限、推不上去；在有该权限的人应用之前这个PR拿不到绿色终态，且`cancelled`两个方向都不能读成通过。`test_historical_coverage`的超时由900降到480——原注释描述的是被我删掉的那五个"问路线"用例（343秒），现在42个用例实测144秒；两个来源分片按各用例自己的预算重新平衡为10500/10440秒。

Issue #47 获取执行链已离线接通（`scripts/vnext/historical_sec_session.py`，非规则文件）：`capture`原本在**许可存在时仍报**`ISSUE_47_SEC_EXECUTION_NOT_WIRED`，那是上一轮被撤回那句"没有不被材料或额度卡住的接线工作"最直接的反例。现在它按另一个理由拒绝——`ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED`并点名所缺文件与七个字段。**"缺许可"和"缺实现"是两句不同的话，今天只有第一句是真的。**不能复用`SecAcquisitionSession`：它的`_check`逐项断言`issue_28_v14`、`[240,240,80]`、#28的预算根与#28自己的离线接线收据，`live_ledger`又经`load_delegation`按名字拒绝其他requirement；而`continuous_call_ledger.py`/`continuous_sec_acquisition.py`/`continuous_call_policy.py`全在已批调用政策的`rule_paths`里，也不能放宽。**能力可复用，授权不可移转**：传输（`SecHttpClient`）、尝试原语、来源安装形状与来源验证器都用现成的，许可、累计计数与总账是新的。

**这个模块凭什么不是规则文件**：它写出的checkpoint由`continuous_sec_acquisition.validate_acquisition_checkpoint`重放，而那个函数被`issue_28_v14`按字节冻结、本Issue改不动；它重读总账前缀、每次获取的行绑定与每次成功获取的不可变尝试。所以来源凭据不落在本模块的字节上。实测端到端：未经修改的下游（`checkpoint_installation`与`verify_ordinary_source_proofs`）找到该checkpoint、点名两个要随行的依赖路径并接受proof。**共享checkpoint不说的那件事**是哪个Issue的额度付的账——它只带mode和captures、不带Issue，所以共享journal里的一条记录本身不构成#47信用；归属在本Issue自己的总账slot（逐个写`issue_47_v1`）和旁边的attribution记录里。

**四次注错，两次找到真缺口**。(1)只数成功的slot→失败用例抓住。(2)去掉capture开头的`require_unblocked()`→用例抓住，而这个检查**本来就是写用例时发现的真bug**：已保存短路在claim之前返回，于是上一个slot缺terminal的会话仍会答"已保存、不需要调用"——**看起来最无害的那个答案正是漏过去的那个**。(3)把`register_checkpoint`里的验证器换成`pass`→**16个用例全绿**：它们都直接调验证器，"验证器管用"不等于"这个会话调了它"，模块的核心主张当时没有任何用例守着。新增`TheSessionActuallyRoutesThroughTheFrozenValidator`包住真验证器，要求对本会话自己的安装根恰好调用一次、且返回的就是被重放的那条记录；另一条要求被拒绝的重放**什么都不入账**。(4)先入账后验证→由(3)新增的第二条抓住。

**真实许可必须绑定离线接线收据**：`REQUIRED_POLICY_FIELDS`新增`sec_wiring_receipt_path`（与#28同形），`live_historical_session`在构造任何传输之前核验该收据并逐个重算它点名的四个文件哈希。收据由`tools/vnext_historical_sec.py wiring-receipt`**跑一遍链路**产生而不是描述出来。**改了那四个文件中任何一个都要重新生成**——包括测试文件，因为收据的`fault_injections_caught`正是靠那些用例成立，削弱它们就必须让收据失效。这与`vnext_mint_historical_requirement.py`是同一条纪律，跳过它也是同一种失效形态。零SEC请求，全部记录`RECORDED_TEST_ONLY`/`real_sec_credit:false`，recorded构造器拒绝任何已配置预算根；获取计划的范围、上限与计数规则不变，#28额度不读不借。材料见`docs/evidence/issue47_history/acquisition-wiring/`。

Issue #47 外部审阅(GPT-6 Pro,对`2293330`)点名获取链四处缺陷,**四条全部先复现再修**——审阅是线索,复现才是事实。**"只缺许可、执行链已完成"这句撤回。**

**(1) 许可只验字段存在,不验授权成立。** `live_historical_session`只检查`delegation_url`与`delegation_body_sha256`非空,没有任何代码读取这两个字段所描述的正文,也没有把请求与获批范围逐项核对。实测:一份`delegation_url="NOT-A-URL-AT-ALL"`、`delegation_body_sha256="NOT-A-DIGEST"`的配置**构造出了LIVE会话并通过请求前检查**。**没有东西去哈希的摘要只是装饰。**现在:字段逐个定型(64位十六进制、issue-comment 形状的URL、三个非负上限、带公司/依赖类/期间窗口的scope);按`delegation_record_path`读出获批正文并重算哈希与声明摘要比对;并要求正文本身复述上限、账本根与scope——**政策文件是指向一次批准的指针,不是批准可以第二次被写下的地方**。每次capture再经`request_is_in_scope`按公司、依赖类与该依赖服务的目标期间核对。

**(2) 终态文件存在被当成结果已知。** `snapshot()`只问`terminal.json`在不在,而`capture`对未知结果**同样**写终态,于是这条规则唯一存在理由的那种情况正是它不再拦截的。实测四种:无文件→拦(符合预期);已知失败→放行(符合"失败计数后继续");**已封存的`UNKNOWN_REMOTE_OUTCOME`→放行**;**内容只有`{}`→放行**。现在分四种状态并在拒绝里点名:`TERMINAL_ABSENT`/`TERMINAL_RECORD_DAMAGED`/`TERMINAL_BOUND_TO_ANOTHER_INTENT`/`OUTCOME_NOT_KNOWN:<status>`,只有"格式正确、绑定本intent、记录已知结果"的终态才解除阻塞。

**(3) "属于任务"与"现在要不要取"是同一个字段。** 两个方向都实测到:已保存的声明依赖被判成**"非声明依赖"**(准入只搜未决行,所以门后那条复用分支根本到不了);而规划器标记`SNAPSHOT_REFRESH`的行同时带`VERIFIED_SAVED_SOURCE`和`new_acquisition_required`(字节完整但与所属索引不一致),`capture`只读第一个字段就返回复用,**刷新永远到不了请求**。现在`declared_dependencies`回答前者、`new_acquisition_required`回答后者,分开问。

**(4) 接线收据能靠自报标志通过,删光证据反而不检查。** `verify_offline_wiring`遍历收据自己列出的证据,所以`evidence:{}`**被接受**——循环跑零次。生成器又把`frozen_validator_routing_verified`与`fault_injections_caught`无条件写成真,而它两样都没跑:**文件哈希证明测试文件是哪个版本,不证明那个版本被执行过并通过**。现在证据集必须逐项等于`REQUIRED_WIRING_EVIDENCE`(删一个文件是删掉资格而不是删掉检查);收据带`verification_run`块,是子进程实跑套件的实测结果;故障注入要改源码重跑、任何单进程都做不到,所以移入收据所哈希的`fault-injections.json`而不是写成布尔值。生成器**明确排除**验证本收据的那个类并把排除写进收据——否则证据自循环。

**对"冻结验证器"的推论收窄**:复用`validate_acquisition_checkpoint`是对的,要求本会话真正调用它的两条用例保留。但它证明的是"保存原件、请求行、不可变尝试与来源凭据彼此相符",**不证明**授权有效、请求在范围内、累计计数完整、未知结果会停机、或陈旧快照会被刷新——上面四条缺陷恰好全部落在这个缝里。所以"来源校验落在冻结代码上"从来不意味着本模块自己的字节不需要纪律。

**尝试记录区分"记录的"与"推断的"**:批次写了case/error/error_type,没写停止阶段也没写执行版本。现在`failed_records`分`recorded`与`inferred`两块(后者自带`recorded_by_the_batch:False`),`execution_version_recorded_by_the_batch`恒为null并说明不可从这些记录恢复,报表closure移到`report_context`并写明"这是读这条记录的上下文,不是记录对当时尝试的断言"。CLI的失败输出也不再一律写零调用——请求之后的收据检查也会失败,届时按实际账本读取并标明来源。

**仍未做且已点名**:`plan_historical_sources`声明的四个依赖类里**没有事件窗口的8-K正文与头文件**(获取计划量到485份申报/970次尝试),所以这里那个Marriott年度索引的成功例子**不能证明事件类已接通——它没有**。该文件是`issue_47_v1`的`NEW_RULE_FILE`,扩展它会移动closure、让上一批343个冻结Run不再是"届时会运行的版本"的证据;正确修法是在非closure绑定的文件里写后继声明、与规划器的行取并集,尚未动手。材料见`docs/evidence/issue47_history/acquisition-wiring/`。

Issue #47 外部审阅(GPT-6 Pro,对`416ab14`)：**上一轮"四条全部关闭"不成立,而最要紧的一条是我修一个缺陷时破坏了真实功能。**

**范围门拒掉了大半个真实声明。** 上一轮为许可加的`request_is_in_scope`要求每个依赖都带`period:`消费者,而规划器根本不是这么声明的:年度主件与accession索引带`period:2025-12-31`,**submissions索引与历史分片带`historical_catalog`,Company Facts带指标名**。实测JPMorgan **75行里71行被拒,包括全部69个历史分片和全部12个`SNAPSHOT_REFRESH`行**——恰好是上一轮"刷新已修好"那件事的对象。**所以那句话对分支成立、对系统不成立。**我自己的刷新用例没抓到,因为它取了一条Marriott待获取行**手工改成**刷新,保留了年度行的期间标签——**一条手造的行证明不了真实的行能过**。修法不是去掉窗口检查而是点名正确的窗口:带期间消费者的按那些期间核,让目标期间可被发现的(索引/分片/Company Facts)按**帧自己的目标窗口**核,准入记录写明用了哪一种。两家共91行真实依赖现在全部通过,错公司/错类别/错窗口/错用途仍然拒绝。新用例遍历规划器**实时输出**而不是夹具。

**授权仍只是两份本地文件互相自洽。** 读正文并重算哈希挡住了"只改一份",但两份都来自同一棵树,于是批准可以由执行者写、再由执行者的另一份文件确认;URL检查也只认"某个GitHub议题评论"、不限仓库。现在政策声明`repository`与`approver_login`,URL必须是**本仓库议题47**的评论,comment的`id`/`issue_url`/作者都要对上,且**真实路径提供reader从GitHub取回该评论**并要求本地记录与之逐字节相同;离线读取返回`provenance_verified_against_github: false`而不是看起来一样。

**终态点名了一份收据,而没有任何代码读它。** 已封存但点名缺失收据、或点名属于另一次请求的收据,都不阻塞、下一次claim照样成功。冻结来源验证器会拒绝这样的账本,但那是**下一次请求发出之后**,而这个检查存在的意义就是在它之前。新增五种状态:`RECEIPT_ABSENT`/`RECEIPT_RECORD_DAMAGED`/`TERMINAL_NAMES_ANOTHER_RECEIPT`/`RECEIPT_BOUND_TO_ANOTHER_INTENT`/`RECEIPT_AND_TERMINAL_DISAGREE`。

**收据实跑的选择器漏掉了产生它那一轮的全部回归。** 选择器写了八个类、新增十六个用例时从未回看,其中十三个根本不读收据。现在十五个类,两个读收据的按原因点名,`unclassified_verification_cases()`让"归属两边都不在"的类直接失败——它立刻抓到我自己本轮新增的四个类。收据由**18项/8类升到48项/15类**。CLI原本把账本累计数放进成功分支表示单次调用的同一个`calls`字段,现分为`calls`与`cumulative_calls`。

**四次注错全部被抓**:恢复"每行都要period:"→5条范围用例挂4条;去掉取回正文比对→本地自造那条挂;终态不读收据→三条绑定用例全挂;新类不归类→分类用例挂。

**一处测试卫生缺陷伪装成21个代码失败**:套件在未改动的树上报21个error,真因是`No space left on device`——每个recorded会话都要安装整份基线语料(实测单份468M),而共享夹具从不清理自己的临时根。夹具现在自行注册清理。记下来是因为**它看起来完全像代码回归而不是**,而且一个会泄漏的夹具早晚会为一个不是它造成的缺陷背锅。

**仍未做**:事件窗口8-K正文与头文件仍不在声明里(规划器四个依赖类没有事件类),该文件是规则文件、扩展会移动closure;按审阅裁定,旧343个Run不因产生新版本而作废,也不必为接获取声明重跑整批,但新声明模块仍须进入范围检查与证据、不能因为放在未绑定文件里就免于验证。材料见`docs/evidence/issue47_history/acquisition-wiring/`。

Issue #47 验收机制搬出业务模块，产物改为一次操作：本Issue里收据已经过期**六次**，每次都是同一个形状——产出它是一串人要记住的步骤。两份手写选择器清单住在`scripts/vnext/historical_sec_session.py`里（套件每加一个类就要改业务代码），构建要经获取CLI写到checkout之外、再手工复制到提交路径，还要按顺序提交让复制落在最后一次改动之后；894行里200行是`importlib`/`inspect`/`unittest`/`subprocess`，于是那个签发实时授权的门与跑测试的机器住在同一个文件里。三条验收各自是**断言出来的而不是描述出来的**。**(1) 业务模块在没有测试包的运行时里能加载**：它现在只留`execute_recorded_chain`（链路）、`seal_wiring_receipt`（记录）与`verify_offline_wiring`（门），且不import `unittest`/`importlib`/`inspect`/`subprocess`——按整棵解析树断言、含函数内import，不是搜词（模块仍点名套件文件，因为它哈希它）。`TheBusinessModuleLoadsWhereNoTestPackageExists`起一个把仓库根从`sys.path`去掉、只加`scripts/`的子进程，要求`import tests`在那里失败，然后仍要求那道门验过已提交的收据。第一版把`sys.path`整个换掉、连标准库一起抹了，子进程挂在`No module named 'json'`——**与要问的问题无关的失败不是证据**。**(2) 普通新增用例不需要改任何清单**：`tools/vnext_historical_wiring.py`的`declared_cases()`读套件模块、返回它自己声明的`TestCase`子类（继承来的不算，否则收据里的账与实际跑的对不上）。只剩一份手写清单`RECEIPT_DEPENDENT`，而它按"类做了什么"核对——一个类被排除当且仅当其源码点名已安装的收据。这条判据两个方向都会失败：塞进排除集却不读收据的类停跑而无人察觉；真读收据却留在第一阶段的类会让树一改就再也重建不出产物，因为**第一阶段跑在新收据安装之前**。这不是推理：那个子进程用例第一版就留在第一阶段，第一次真实构建即在第二阶段挂掉。**(3) 从固定候选到可用产物是一次确定操作**：`python3 tools/vnext_historical_wiring.py`驱动链路→读套件→跑所有不读收据的类→封存→安装到提交路径→拿已安装的文件跑读收据的类；任一步失败就把先前安装的字节原样放回并以2退出。这不只有三条用例断言，**它在本工具第一次真实运行时就被观察到**——第二阶段因新用例里的一个缺陷失败，已提交收据与`HEAD`逐字节相同。`--check`回答更便宜的那个问题（已安装产物对这棵树是否仍成立、是否仍覆盖当前套件）而不重建。**验证器是增强不是削弱**：它原本拿收据里的选择器与同一模块的字面清单比对（这既是"普通用例要改业务代码"的成因，也是没有测试包时根本做不到的事），现在按记录自身的性质检查——`classes_run`与`classes_excluded`必须**划分**`classes_declared`，不重叠、跑的那份非空；一次绿色但只覆盖21个类中9个的运行（上一版实际出过的缺陷）按名拒绝。产出这三个集合的收集器自己也在`REQUIRED_WIRING_EVIDENCE`里，被削弱就改变自己的字节、授权随之作废；套件另有一条用**解析测试文件**（而非内省已导入模块）的独立第二推导交叉核对它。**代价如实记**：业务模块894→854行（净减40，因为三个新函数带完整docstring），新工具250行、用例净增约300行，所以**总行数是增加的**；减少的是手写清单2→1（且剩下那份被核对）、人工步骤5→1、业务模块对测试框架的import 4→0。**没有解决的**：收据终究是一次运行的记录，被改坏又重跑的构建器会产出更小但自洽的收据；哈希建立的是"盘上产物对应这个构建器和这个套件"，与`mint`同一性质。候选身份检查没有放宽——改任何被哈希的文件仍让收据失效，变的只是恢复它从五步变成一条命令。**五次注错全部被抓**（第9项由整个构建器跑出来，因为它的捕获用例在第二阶段）：截断收集器、去掉失败恢复、把收据读取者放回第一阶段、在业务模块里重新import `unittest`、让验证器只信pass标志。材料见`docs/evidence/issue47_history/acquisition-wiring/`。

Issue #47 验收产物改为"先验候选再安装"（外部审阅对`3ff7616`的实测，**上一条"失败即逐字节恢复"要收窄**）：上一版的顺序是先把新收据写到**安装路径**、再跑第二阶段、失败才恢复旧字节。恢复本身是有效的，第一次真实运行也确实留下了与`HEAD`逐字节相同的收据——**但"失败能安全收场"不等于"从未把未验完的东西放出去"**。审阅实测三态：两阶段都过→正常；第二阶段返回失败→**在失败返回之前，门禁与`--check`已经接受了新收据**，之后才恢复；第二阶段进程被杀来不及执行恢复→**未验完的收据留在安装路径，门禁接受、`--check`仍报`OFFLINE_WIRING_CURRENT`**。`verify_offline_wiring`看的是文件哈希与已记录的第一阶段结果，它无从知道还有一个第二阶段在飞。**为这个恢复写的三条用例一条也看不见这些**——它们都在运行之后看安装文件，而恢复让两种顺序的终态完全相同。**修法是改顺序，而且是删代码不是加代码**：收据先写到安装路径旁边的候选路径，第二阶段**按名字**被告知去验这份候选，只有通过才经仓库既有的`atomic_write_bytes`落到安装路径；不再有备份与恢复，因为没有东西需要撤销——失败或被杀都天然留下旧字节（或本来就没有文件），不需要任何代码跑起来才成立。候选在`finally`里删除，残留的候选是惰性的（许可只点名安装路径）。随之两处改动：读收据的用例不再写死安装路径，改问`_receipt_under_check()`（读`ISSUE_47_WIRING_RECEIPT_PATH`，单独跑时回落到安装路径），所以第二阶段验的是**本次产出的那份**而不是上次留下的那份；判定"哪些类读收据"的判据改为两种写法都算（问候选、或直接点名安装文件），且其token在**任何类体之外**组装——第一版把token写在做扫描的那个类里，于是它把自己也标成了读收据的类。**第10次注错**`INSTALL_FIRST_AND_RESTORE_AFTERWARDS`（把顺序改回去）**只被一条用例抓到**：`test_the_second_phase_checks_the_candidate_while_the_old_one_is_installed`（在第二阶段运行**当时**要求拿到的路径不是安装路径、候选存在、安装路径仍是旧字节）；另外三条在注错下照样通过，**这三条通不过才是要点**——已按名登记"哪几条分不出来、为什么分不出来"。**"无测试包"结论同时收窄**：用例证明的是`tests`不可导入、测试框架不运行时模块仍能加载并答复；它**不证明**不依赖磁盘上的测试源码——`REQUIRED_WIRING_EVIDENCE`点名套件文件、构建器与注错记录，缺任一即拒。准确说法是：**对"可导入的测试包与可执行的测试框架"的依赖已去掉，对"作为只读证据的测试源码"的依赖保留且是故意的**——正是它把许可绑到一份具体套件上；为了瘦身把测试文件从交付包里拿掉是去掉绑定而不是改进，不做。CI工作流补丁按用户决定搁置，不再作为阻塞或待办复述。

Issue #47 事件来源声明已接上（`scripts/vnext/historical_event_sources.py`，非规则文件）：`plan_historical_sources`只声明四类依赖——submissions索引、其历史分片、Company Facts、每份年度accession的两个文件——**没有事件类**，所以零AI路线为C01/E01–E05读取的所有财年8-K正文与头文件，在获取门上一律以`HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY`按名拒绝；这条成立时，任何许可都解不开那六个坐标。新模块声明它们，`declared_frame`取并集。**之所以另起一个模块**：规划器是`issue_47_v1`的`NEW_RULE_FILE`，改它的字节会移动Requirement closure，而上一批343个冻结Run是"当时那个版本"的证据。**在closure之外不等于在检查之外**：这些行带规划器的字段、由规划器自己的`_saved_state`分类、走同一道范围门，模块字节进`REQUIRED_WIRING_EVIDENCE`。**验收不是"依赖清单里多了一个类名"**——清单两个方向都可能错：短了，门会拒掉路线需要的文件；长了，许可被花在没人读的文件上。所以用例拿**冻结路线自己的来源发现**（`_event_sources`）在已保存语料上跑一遍、用记录型reader收下它请求的每一个URL，要求该期间的声明**恰好等于**这个集合；Marriott最新期间实测读20个、声明20个、两个方向都为0。十家实测：**354行/177个accession，其中60行仍需获取**；每个accession两次请求是量出来的不是假设（186个已存accession目录里151个同时有正文和头文件、没有一个只有头文件）。**Paramount是值得点名的互证**：它那18行正是9份前身8-K正文加9份头文件，而本仓库在接续事件那一轮由**另一条路径**独立记录过同样的9份（窗口内31份前身申报、9份无正文）；两条推导落在同样的九份上，比任何一条单独成立都强。**为什么比计划里的970小、而这不是"下修"**：事件窗口来自目标年自己的文件——财年起始日在它的DEI上下文里、不在submissions行里——所以年报正文未保存的年份**没有可导出的窗口**，模块对它**什么都不声明**而不是声明零份（这两者在计划里读起来一样、意思相反）；50个期间里31个处于该状态，每个都带具名限制并点名能解锁它的那份年报正文。所以这份声明是**随A类落地而增长的下界**，不是替代计划估算的上界；用别的方式推导窗口等于把路线已经拥有的规则再抄一遍，而那正是本模块要避免的漂移。两次注错全部被抓（只声明正文不声明头文件；窗口不可导出时静默跳过而不记限制）。**本轮另外自查出一处**：`recorded_historical_session`默认范围列了四个依赖类而声明实际产出五个，于是"用recorded路径获取一个history shard"根本不可能、且无人察觉——它是因为加第六个类弄挂了一条不相干用例才浮出来的，现在该默认值按"声明实际产出的类"核对。**授权没有任何变化**：`FISCAL_EVENT_FILING`不在任何已批scope里，`config/issue47_historical_calls_v1.json`仍不存在，`capture`仍以`ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED`拒绝。材料见`docs/evidence/issue47_history/event-source-declaration/measured.json`。

Issue #47 元数据刷新链完整正例（`ARefreshIsFinishedWhenThePlanStopsAskingForIt`）：此前唯一有用例的只是"`SNAPSHOT_REFRESH`行能到达请求"，它后面的保存、账本行、收据、终态、冻结checkpoint重放、安装、以及**在刷新作用过的那个根上重新规划**一个用例都没有，于是"门接受了刷新请求"一直在冒充"刷新完成了"。**先把冲突量出来，结论比记录里的更锋利**：JPMorgan 12份已保存分片**每一份的正文都整个落在自己声明区间之外**，且各自落在后两个分片声明区间之间——SEC重新分区过，已保存正文早于那次分区；最新已保存申报是2025-07-02，而最新声明区间要到2025-07-15才开始。**顺带纠正一个数**：计划里分片001写的是`out_of_range_filing_count: 2`，读起来像"漂了两条"，那个计数只算读取器保留的表单种类，而001只含两条这类表单；2079条原始行**全部**在区间外。冲突是整体的不是边缘的。**因此正文侧的刷新无法从已保存字节导出**（当前分片该含的申报本仓库从未保存），所以本次刷新的文档是**索引**，其字节是**导出的不是编造的**：每个已保存分片的声明区间改为该分片正文自己的最早/最晚申报日；从未保存的分片条目原样不动，所以"57个分片未保存"这条限制既没被掩盖也没被改动。**这证明的是机制不是SEC当前元数据**——这家公司真正的修复是一次获取，并按获取如实命名。实测链路：安装→`before`（12行`SNAPSHOT_REFRESH`＝11个分片＋索引、11个冲突分片）→**一次capture**（`SUCCEEDED`、零调用）→checkpoint登记、下游安装接受并点名2条依赖→`after`：**0行刷新、0个冲突分片**，且帧声明的行数前后都是115（刷新不得改变帧声明什么）。**一份文档清掉十二行**，正是规划器自己那句"连贯性是索引与分片共同的性质"被做成可核的样子。**承重的是反例**：`test_capturing_the_same_bytes_again_does_not_clear_the_conflict`——同一条链、同一道门、同一个checkpoint、同样的安装，只把正文换成**未经导出的原索引**，冲突必须原样还在；没有它，一条"因为重存/重登记/重安装才清掉冲突"的链会通过其余每一条用例。**为此改了录制会话**：`recorded_response`现在可以是bytes（原样，每个URL同一份正文）或dict（每个URL各自的正文）——多文档的链正是要让索引与分片**互相不一致**，单一正文做不到；缺失URL按名拒绝而不是回退到任意一份（回退会把A的字节交给B的请求、并且看起来像通过）。第13次注错（缺失URL时回退取map里第一份）**只被专门那条用例抓到**，刷新链六条一条也没挂——因为它只需要一个文档、map只有一条、回退根本到不了；**守卫的用例要写在守卫会咬的地方，而不是写在功能恰好被用到的地方**，已按名登记。**没有解决的**：JPMorgan的元数据仍与SEC不一致（已保存正文仍是陈旧的那一侧、仍需获取）；57个未保存分片原样保留。零SEC调用、全程`RECORDED_TEST_ONLY`，live capture仍以`ISSUE_47_SEC_ALLOWANCE_NOT_GRANTED`拒绝。材料见`docs/evidence/issue47_history/metadata-refresh-chain/measured.json`。

Issue #47 接续主体Company Facts已接通（改`historical_results.py`，第24次移动closure），**并纠正本文件先前一条记录**：此前写"政策放行也产不出结果——13项全部再次被拒，11个`HISTORICAL_COMPANYFACTS_SUCCESSOR_SCOPE_NOT_IMPLEMENTED`"，那在当时为真，它也正是"政策决定"与"接续实现"是两件独立活的证据；**第二件现已完成**，同样的站下探针今天返回全部十一个答案。**三处改动**：(1) **结构适用性先于修订问题**——traits排除的指标根本不读任何输入，任何输入类别对它都无从存疑；十一个里有五个此前被一条够不到它们的修订分类挡住。(2) 已批修订拒绝改为**逐指标携带**而不是终止整次解析，并带自己的reason code与category（`HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED` / `APPROVED_AMENDMENT_POLICY_REFUSAL`），**已决问题不再读成未解实现**。(3) 把普通路线一直在跑的已批准连续性处理搬过来：`REQUIRE_CONTINUOUS`路线报`ENTITY_CONTINUITY_NOT_COMPARABLE`、current-instant的`ALLOW`路线读本注册人自己的事实、其余接续情形照旧拒绝。**今天实际移动5个坐标**（A05/A06/A07/A08/A10由拒绝变为`N_A_STRUCTURAL/TRAIT_NOT_APPLICABLE`，与普通路线逐字段相同），另外6个仍被修订政策挡住——那是**已决的政策问题、答案是"未清除"**，其归属不在本任务。**承重检查是差分**：在一个探针进程内站下修订门（返回带`PROBE_ONLY`标记的记录、不碰任何政策文件），把十一个答案与普通链路**逐字段**比对，**差异为0**，包含B08=1.256722332295499575431644495与B09=3274000000两个精确值。两次注错都被抓：恢复"整族按修订拒绝"（解析重新抛出、类连setUpClass都起不来，属钝的捕获，如实记为钝）、去掉已批准连续性处理（**只被那条差分用例抓到**，另外三条照样通过，因为它们问的是修订顺序而不是接续处理——一条自己发明接续答案的移植只会挂在差分上）。**不成立的部分**：那6个指标在Part III修订问题被回答前不会解出；Paramount更早期间仍因期间目录不跨主体过渡而未发现；两个数值的内容验收未做。材料见`docs/evidence/issue47_history/successor-companyfacts-scope/measured.json`。

Issue #47 接续主体B01/B03已接通（`historical_zero_ai_results.py`）：历史零AI路线原本对接续注册人的B01/B03整体拒绝，而普通路线一直在答——它用当前收入输入（注册人自己的HTML/XML/Company Facts、其利润表**实际覆盖的期间**、以及Part III收入更正检查）。该输入**点名了它所证明的那份申报**，所以这里把它取来、且**仅当那份申报就是本次目标时才生效**；否则保留原具名缺口——一份关于A报告的证明用来准入B报告的数值，正是整条路线存在的理由所要避免的。**第一版是错的，而且是跑出来才知道的**：只放过守卫、不接期间，路线就按pinned财年2025-01-01..2025-12-31去问Company Facts——这家注册人从未报过那个年度——B01得`MISSING_CANDIDATE`、B03得`REUSE_CARDINALITY_FAILED`。**关于一个没人申报过的期间的答案，比它替换掉的那条具名缺口更糟**；测量期间必须来自那份证明，Run坐标仍保持pinned，与事件窗口用的是同一条分离。接完后两项与普通链路**逐字段相同**（applicability/quality/reason_code/value/period_start/period_end，差异0）：`APPLICABLE / NOT_MEANINGFUL / ANNUAL_DURATION_OUT_OF_RANGE`、期间2025-08-08..2025-12-31。**NOT_MEANINGFUL是答案不是拒绝**——接续注册人第一个期间只有146天，Spec的年度时长守卫说146天不是年度测量。两次注错都被抓：让关于另一份申报的证明也能转移（只被那条专门用例抓到）、把pinned年度当作测量期间（被差分与窗口两条抓到，而它正是第一版的真实缺陷，已留作用例）。**十三项里现已答出七项**（五个结构性Company Facts加这两个），其余六项仍被已决的Part III修订问题挡住。材料见`docs/evidence/issue47_history/successor-companyfacts-scope/zero-ai.json`。

Issue #47 C03历史路线已接通（改`historical_governance_input.py`与`historical_governance_results.py`，覆盖表wired 25→26）：**先按B06那次的纪律量，再动手**——普通路线对十家公司的C03答案实测为**九家走代理的薪酬对业绩（ECD）事实、一家（Paramount）走年报自己的薪酬表**，所以这同样是"级联不是一条路线"，只接第一级会让Paramount拿到第一级的答案、有证据且是错的。两级一起接。**代理按期间钉住而不是取最新**：冻结选择器取最新DEF 14A，那在pinned期间就是当期时是对的同一份；后继取**pinned期末之后最早的那份**——当期二者相同（这一点是**对着普通路线断言出来的**，不是假定），更早期间则不同；取最新等于把后来那份代理的重述当成更早年度的首次报告。实测当期十家里**九家逐项相同（quality/reason_code/value**并且**同一级**），JPMorgan在期间选择就以`SAVED_HISTORY_INCOHERENT`拒绝（分片重分区，已在获取计划里，非本轮引入）。**更早期间只能报来源缺口**：本仓库每家只存一份代理且全部2026年申报，所以Marriott FY2024选中的是**首次报告该年度的2025年代理**（清单里有、未保存），失败按名点出那个URL，而**不是**回落到已保存的2026年那份；终态`C03_SUPPORTED_CURRENT_SOURCE_NOT_FOUND`。接线与交付是两件事，这是第一件，四个往年需要那些代理（获取计划A类）。两次注错都被抓：取最新代理（更早期间会产出一个来自另一年度代理的数值）、只接代理那一级（Paramount的级与值都对不上）。**本轮改写了两类既有断言**：`test_an_unwired_governance_metric_is_refused_by_name`原来拿C03当例子，现改用C02（`ai_text`、确实未接线）；`test_historical_coverage`的两条在**上一次提交后就已经红**（接续端口把它们断言的拒绝换掉了），改写为这些路线现在真正产出的状态——同一期间由三个答案变成四个（逐指标政策拒绝＋结构性不适用、经已批收入证明的NOT_MEANINGFUL、事件来源缺口、一个数值）。**教训**：上一次提交我跑了相邻历史模块却没跑`test_historical_coverage`，红是我推上去之后才发现的。材料见`docs/evidence/issue47_history/c03-compensation/measured.json`。

Issue #47 D02内容验收（Pfizer 2025，两个方向都读）：此前每一轮都只问"取到的这些该不该取"，那只是一个方向——选择器可以对取到的每一块都判断正确，同时丢掉一份披露，而只看取到的集合永远看不见它。补上另一个方向后，声明范围内每一块**未取**的都读了。**note范围干净**：[3821,3937)共116块，取91未取25，那25块正好是五组连续五块的页眉（注册人名×117、表单名×116、附注标题×46、子公司行×52，每组外加一个页码）；重复次数是从文档自己的块文本数出来的、不是问那条排除规则，所以"页眉"这个判断来自申报而不是来自规则。**另一个方向抓到一件事**：Item 3——已批定义点名的第一个来源——范围内有一块，选择器取零块。Pfizer整个Item 3就是一句77字符的超链接句子，而冻结的`_substantive`丢弃任何不足120字符的带链接块。**Lumen是对照**：它的Item 3同样是单块、同样是"按引用并入某附注"的句子，226字符、不带链接，于是被取。同一种内容两个相反答案，差别只在注册人有没有把句子包进锚点里。**这条此前被声称"已登记"而实际没有**：它写在两份README和AGENTS.md的散文里，`finding.json`还断言它"已作为独立缺陷登记"，而`known_result_defects.json`——真正撤回结果的那份——里从来没有。散文撤回不了任何东西，而"已登记"这句话恰恰让人不再去查；已更正并正式登记。**修法是问冻结规则而不是发明新判据**：把锚点摘掉再问一次`_substantive`。那条子句在六份申报的声明范围内共挡住365块，能进D02的只有14块，其中13块是同一个字符串`Table of Contents`，而冻结规则自己的navigation-header模式在链接标志不再抢答之后已经把它们全部拒绝。第一版还写了"重复即导航"的第二判据，**实测删掉它六份申报一块不差**，于是删掉而不是留成一条没有任何例子检验的守卫；长度判据同理删掉（该分支只在`_substantive`已经拒绝之后才问，带链接块被拒就意味着不足120字符）。实测Pfizer 95→96只加块937不减，其余五份申报的proposal记录**逐字节相同**（是proposal_id相同，不只是条数相同），六份的D03候选集全部未变。**接在D02那一支而不是共享门**：本语料区分不了这两种接法——接到共享门上D03同样逐字节不变——所以它是对"这次改动能碰到什么"的约束，如实记录，不冒充被测过。`_d02_section`现在是两条路共用的同一个表达式，抄两份正是它们分开的方式。四次注错（任意链接块全收、保留链接子句、去掉章节规则、把章节规则里Item 8的关键词删掉）全部被抓。**验收状态**：96条里94条被这次阅读接受，2条（2175/2240）是已登记的`_LEGAL`关键词代理缺陷，所以该坐标**仍然撤回**、`business_content_accepted`仍为false。**没有覆盖的**：Item 8里附注之外的2226块未取块属于关键词代理那个问题（六份申报17块准入、3块错、收窄会丢掉14块该留的），本次不结论；Item 1A的142块是D03的分支不是D02的；另外四个目标年原件未保存；以及写规则的和读申报的是同一双手，这不是独立验收。材料见`docs/evidence/issue47_history/d02-content-read/pfizer-2025-both-directions.json`与`hyperlinked-item-three.json`。

Issue #47 B10/B11历史路线已接通（`historical_lodging_results.py`第24个规则文件，覆盖表wired 26→28）：**为什么是现在这两个**——八个指标带特征门，此前只答得出关闭的那一侧；六个门在`financial`上，而唯一打开那扇门的公司没有可达期间，开着的那一侧无处可写；B10/B11的门在`lodging`上，而本仓库唯一那家酒店存着三份年报原件。且普通路线是确定性的：`lodging_table_source`重建整份表集合、按表自己的表头与几何匹配范围合同，零模型调用，接线不需要任何额度。**只换了一条规则**：普通的来源准备调用`prepare_saved_annual_input`，即"最新那份年报"；其下游全都已经把申报和期间当参数收——`inspect_lodging_table_source`从字节里重新推出该来源自己的年度区间，与传入期间不一致就拒——所以指到一份pinned申报是替换而不是重写。**先量后写**：普通链路对Marriott FY2025给B10=0.693、B11=128.8 USD，都是EXACT/PUBLISHED、都来自`table_000011`、`ai_response_used`为假；历史路线同期间逐字段相同。**往年实际交付**：FY2024给0.698/128.23、FY2023给0.692/124.7，全部EXACT/PUBLISHED。FY2023那两个数与当初表资格那一轮用**另一条路**从同一份申报读出并记进本文件的124.70与69.2一致——那是为别的目的量的，不是这条路线自己的输出。**差分暴露了一个此前没人注意的事实**：观察记录`source_binding`的十七个字段里十六个逐字段相同（含`raw_asset_id`、`source_reference_id`、`derived_asset_id`、`table_locator`、`reported_raw_text`与全部witnesses），唯一不同的是`source_component_id`——它把申报记录一起哈希，而pinned选择器把申报投影到五个标识字段（form/reportDate/filingDate/accessionNumber/primaryDocument），最新期准备却携带整行submissions（多出`filmNumber`、`size`等十个SEC簿记字段）。**同样的字节读出两个组件身份**；窄的那个才是业务身份该用的，所以用例断言这个差异而不是抹掉它——第二个字段加入差异集就会挂。**计数也改了**：`STRUCTURAL_APPLICABILITY_METRICS`改为从结构集**减去**已接线集导出而不是手工列——两个家族相加才是"有路线的指标数"，B10/B11现在两侧都有路线，留在两边会被数两次；减法还意味着下一个拿到开侧路线的指标自己离开该元组，不用等人记得。派发不变：`historical_structural_results`自己的支持集仍带着它们，非酒店公司照样拿到结构性不适用。现在wired 28、仅结构6、有路线34、未接线5（B13/C02/D01/D03/D04）。**没做的**：五年。B10/B11只读目标申报（不读上一期、不读accession索引），是这批里最便宜的历史指标，但原件没存的期间照样只能给具名来源缺口——Marriott五个目标年里三个有原件；其余九家没有——八家不是酒店，第九家JPMorgan是银行且期间选择因保存的历史不自洽而拒绝。数值与普通路线一致、也与一次独立阅读一致，但两者都不是业务内容验收。材料见`docs/evidence/issue47_history/lodging-route/measured.json`。
**四次注错，第四次没被抓，如实处理**：`TAKE_THE_LATEST_FILING`挂4条、`COMPILE_THE_AI_SPEC`挂4条、`ANSWER_THE_CLOSED_GATE_TOO`挂2条；`DROP_THE_SCOPE_AND_PERIOD_CHECK`**六份申报一条都不挂**——`inspect_lodging_table_source`已经从字节里重推该来源自己的年度区间并拒绝不符，范围又来自同一份编译Spec，所以这条检查在本语料上处处冗余。**没有删它**：普通路线做这个检查，一条比它所镜像的路线查得更少的pinned路线是削弱；改为**构造它所防的那种分歧**来行使它——让检查器返回一个关于另一期间的事实，断言不得产出数值（输入是构造的，用例里写明）。复跑同一注错：**八条里正好挂一条**，就是那条构造的；其余七条仍分不出来——这是对的结果，它们读的是真实申报，那里检查器自己的期间校验让这条冗余。这与D02那轮删掉"重复即导航"是同一条纪律的两个方向：**我自己新发明而无例检验的判据删掉，继承自既有路线的检查保留并设法行使**。

Issue #47 批次跑出两处单元层面全绿的缺陷，**两条都是对本文件上一条记录的纠正**。**(1) B10/B11"往年交付"当时只在组件层为真**：上一条写"FY2024给0.698/128.23、FY2023给0.692/124.7，全部EXACT/PUBLISHED"，我量的是`resolve_historical_lodging_metric`与`prepare_historical_run_input`，**从没走过`create_historical_run`**。批次一跑六个位置全部`FAILED`：`Reviewed observation lacks an approval effect`——`run_store`那条确定性表格豁免按世代写死为`issue_28_v13`，而B10/B11的观察记录带`derived_asset_id`（表格网格），冻结时要么有审阅批准效力、要么属已认可的确定性路线，`issue_47_v1`不在集合里，于是**组件算得出值、Run建不出来**。运行树注册补丁加两个窄hunk（豁免按世代扩到`issue_47_v1`、其余四个条件不变；重建对照观察记录同样走各自case的重放）。修后全链路实测：六个位置FROZEN→公共行→**独立进程冷读读出同一个值**，1条证据、零调用。**"单独测函数全绿、接上去才露"这条纪律我刚写完就自己犯了一次**，记在这里。**(2) 收据写在run目录内部，使每一个持久化过公共行的历史Run冷读失败**——这条不是lodging的，影响**上一批已提交的343个Run**。`render_historical_run(persist=True)`把`row_receipt.json`写进run目录；不改manifest三个哈希文件是**必要条件不是充分条件**，冻结Run的目录必须恰好只含其记录点名的产物，而这份收据是**故意不被manifest哈希的**，所以目录内部正是它唯一不能待的地方。那条exact-set检查拒得对：`Run validation artifact exact set differs`；删掉这一个文件，同一个Run立刻读通（FROZEN、10条记录、同值）。我那段注释写的是"写在Run旁边"，代码写的是`run_dir / name`。**批次驱动本来每期间抽一次冷读并存了结果，汇总没有读它**——记录了但没人看的失败，和没记录一样。已改写到run目录同级（`<run名>.row_receipt.json`），写方读方共用**同一个函数对象**而不是两份路径拷贝（路径抄两份两个方向都会静默出错：读方找错地方报"没有行"，写方写错地方让整个Run读不出来）。三条回归断言该性质；端到端那一半仓库树跑不了（建不出历史Run、缺注册补丁），在运行树实测。

Issue #47 28指标×11期间批次（一期间一进程、同一只读运行时树、零调用）：**374个位置全部尝试，372个冻结Run与公共行、2个失败**。三层拆开（把行当交付就是把三件事数成一件）：**153带数值**（151 EXACT＋2 APPROX，上一批139）、**169结构性不适用**（真答案）、**50跑了没有值**——其中5个也是答案（分母非正3、分子非正2），另外45个点名缺的材料或已决政策。`verified_outcome` 320（153＋169−2条已登记内容缺陷），`content_acceptance`**全帧为0并写明理由**。帧的另外三层不变：1950个目标位置里**1521仍在等获取**（缺原件1170、期间未发现273、元数据阻断78），55个无路线。**与上一批的差额正好是新接的三条**：Marriott 2023由7升到9、2024由9升到11、2025由16升到19（B10/B11三年都在、C03只在最新年；更早年份点名读不到的那份代理而不是借用最新的）；**Paramount失败由14降到2**——接续主体Company Facts与B01/B03接通后，它的A系列走结构性不适用、B01/B03给出`ANNUAL_DURATION_OUT_OF_RANGE`（接续注册人146天首期，与普通路线同一答案）。**两个失败**：B06接续主体范围未实现（已命名实现缺口）；C03 `Observation DerivedAsset is absent`——**本Issue自己的接线缺陷，由本批次发现并在其后修复**，所以这批是它所跑那个closure的证据、不是当前的。**按路线族冷读16/16通过、九族全覆盖**（Company Facts／零AI报表／零AI事件／accession／文本／治理／债务／lodging／结构）：驱动本来每期间抽一次，那是任意的——十一次读可能全落在同一条路线上；真正的问题是"**这一类**Run能不能被一个没创建它的进程从自己的字节读回来"。**冷读检查自己先有个缺陷**：首轮把B03报成不一致，而读是对的——比对取了`results[0]`，B03的Run里同时带着它消费的B01结果；"取第一个"两个方向都会错，现改为按Run自己的主指标选并断言恰好一条。**还有一个看起来完全正常的错帧**：本批次第一次建帧报告374个位置全是`ROUTE_IMPLEMENTED_NOT_RUN`、零份已验证收据——批次写在`<根>/<期间>/run-<期间>-<指标>`，而收据收集器只扫一层，于是**什么都没找到，并把这个"没找到"当成事实报了出来**。收集器现在对"根里有目录却没有任何一个带manifest"按名拒绝（`RUN_RECEIPT_ROOT_HOLDS_NO_RUNS`），空根仍是空根。**看错地方不是不存在**，而这正是本轮反复出现的同一形状。材料见`docs/evidence/issue47_history/native-run-batch-28-metrics/`。

Issue #47 B06 接续主体已接通（改 `historical_debt_results.py`）：**先撤回两条我自己写进本文件的记录，两条都是量出来的**。(1)「本仓库没有任何当期申报命中 inclusive 语法，所以第6级是实现了但没有 Run 跑过」——**错**，Paramount 的当期 10-K 正是命中它的那一份。(2)「Paramount 是每条历史路线共有的接续主体缺口，不是本路线引入的」——**也错**，`git log -S` 把那条拒绝定位在 `ae12a83`，就是本 Issue 自己接 B06 级联的那次提交；另外四条历史路线的接续拒绝在普通链路里**各自都有对应**（`normal_accession_results`、`lodging_table_source`、`normal_companyfacts_results`、`normal_zero_ai_results`），只有 B06 这条是多出来的。**成因是调查顺序**：写那份差分时循环**先问副本再问原件**，副本拒绝的坐标记成 `not_measurable`，于是「没有申报命中 inclusive」是从一个有洞的普查里推出来的，而那个洞恰好就是唯一命中它的那家公司。**副本拒绝时先去问原件，再记录"不存在"**；这是本轮第三次同一形状（B10/B11「往年已交付」只在组件层为真、覆盖表扫错目录把 372 个 Run 报成零）。

**实测**：普通链路给 Paramount 的 B06 是 `1.168049260241169930727785855`，EXACT/PASS/PUBLISHED，走 `catalog/r5/B06_inclusive_table_v6.md`，坐标 2025-12-31 瞬时；只把那条守卫按名字站下，历史级联到达 **INCLUSIVE** 并与普通链路逐字段相同。**改动是删掉笼统拒绝、换成它所依赖的前提**：B06 只读一份申报，主体义务由看得见它的那一级各自履行——两条链路共用的冻结 `bind_current_debt_input` 要求已发布结果的计算对象就是这位注册人自己的 entity 与 accession（`RESULT_CURRENT_REGISTRANT_SCOPE_UNPROVEN`），inclusive 语法要求当期列带接续标签（`CURRENT_SUCCESSOR_COLUMN_UNPROVEN`）；本路线只检查主体政策是本级联有答案的两种之一（第三种按名停下）与未授权跨主体合并。端到端：Run FROZEN、公共行（2 条证据、`row_hash` `sha256:4a026db2…`）、独立进程冷读 17 条记录同 run_id 同值、零调用。

**四次注错，第二次自己是坏的，这件事比结果重要**。`RESTORE_THE_BLANKET_REFUSAL` 四条全挂；`DROP_THE_MODE_CHECK`、`DROP_THE_CROSS_ENTITY_CHECK` 各只挂那一条专门用例（如实记为只被一条看见）。`RELABEL_THE_SUBJECT`——"为绕过自己的拒绝把主体改标成连续"——**第一版返回全绿，我差点把它记成"套件抓不住"**。真因是注错没打中：它只改 `prepared["subject_policy"]`，而各级读的是 `prepared["original_input"]` 里另一份副本，被改的字段没有任何代码读，所以那次全绿对套件什么都没说。**够不到目标代码的注错，不是"没人抓得住"的证据**。第二版同时改两份副本，并先用探针在注错后的树里打印语法实际收到的主体政策（`GRAMMAR_SAW ['CONTINUOUS_PRIMARY']`）——没有这一行，那次运行两个方向都读不出来；修好后**由且仅由** `test_the_grammar_is_told_the_real_subject_policy` 抓到。另一处实测：把接续列证明整个跳过，这份申报上**值不变**（选择器本来就选那一列），所以担保它的是"语法有没有被告知真实主体政策"，不是"结果会不会变"。

**同时确认的两件事**。C03 的 `e40d502` 修复此前只在仓库树里经 `prepare_historical_run_input` 量过，现已跑完整工厂：Paramount 2025 C03 FROZEN、公共行、独立进程冷读同 run_id 同值 `63211569`、零调用——28指标批次说它"其后已修复"，那句话现在有一个 Run 撑着。批次的一处计数也纠正：`ANNUAL_DURATION_OUT_OF_RANGE` 的两个坐标（Paramount B01/B03，接续注册人首期 146 天）是 Spec 的答案，与 `DENOMINATOR_NONPOSITIVE` 同类，不该计进"点名缺材料或已决政策"的那 45，应为**答案 7 / 缺口 43**。**未做**：五年（这家公司只有一份已保存原件）；内容验收（冻结 Run 加公共行只说级联算出了东西且字节已绑定，没说 1.168… 是对的比率）；第 7 级 `CURRENT_INPUT_UNRESOLVED` 仍无任何申报到达。

Issue #47 第三层交付首次非零（`historical_coverage` 加接受登记，均非规则文件，不移动 closure）：此前每个批次 `content_acceptance` 对每个坐标恒为 `NOT_PROVEN`，理由写得诚实但也**永久**——没有任何机制能表达"这个数被独立读过"。现在由 `docs/evidence/issue47_history/accepted_result_content.json` 表达，**方向与缺陷登记相反**：缺陷一直撤回到被显式释放为止；接受**只在它点名的那个值仍是该坐标当前的值时成立**，因为接受说的是"一个数被对着申报读过"，另一个数没被读过，按坐标继承正是这一层开始报告没人读过的数字的方式。两者冲突时撤回胜出。两次注错（只按坐标匹配、让接受盖过撤回）各由且仅由对应那一条用例抓到，52项套件全绿。

**读法是跨来源的**：路线从 Company Facts API 解析，这次读申报主文件自己的 inline XBRL——按期间/瞬时/维度解析上下文，按 scale 与 sign 读 `ix:nonFraction`，只取无维度事实，按**已批定义**的候选链（不是按路线代码）走，Decimal 用计算器自己的精度。十个公司期间×八个报表指标共80个位置：**73 MATCH、0 DIFFERS**。

**但这一轮真正的收获是我自己的读法有三处缺陷，而且是它先报出"差异"的**。(1) 瞬时上下文没有起始日，事实存在 `(None, end, True)` 下，我按 `(end, end, True)` 查——**每一家**的 B08/B09 都读成 NOT_READ；**读不到和申报没写，长得一模一样**。(2) 文档路径按 `company_id` 拼，而 `macys` 在盘上是 `macy_s`，十家里九家能跑，第十家被报成"原件未保存"；改为读输入自带的 `source_repo_relative_path`。(3) Ford 的 B03 先报 DIFFERS，只因为 Decimal 多留一个尾零而我在比字符串。**最有用的是第四处**：Salesforce 的 B03 读出 0.288、发布 0.230，长得就像一个错数——**不是**。主文件的 inline XBRL 是该 accession 事实的**子集**：它标了 `DepreciationAndAmortization`(3,631,000,000) 而没标链上更靠前的 `DepreciationDepletionAndAmortization`，后者在 accession 自己的事实里是 1,200,000,000，正是路线用的那个。**路线是对的，我的读法够不到**。现在在报告"差异"之前先查 accession 里有没有更靠前的候选——**读法的局限和路线的缺陷是两种发现，只有一种是关于这个仓库的**。它还顺带质疑了我自己第一条登记：Marriott 的 B03 写"本申报里没有合并 D&A 事实"，那是只按主文件量的；按 accession 事实复核，三个合并候选一个都没有，所以组合回退是对的、条目成立——但在跑这一次之前，它站在错误的全集上。

**同轮另外三件**。(1) 把 B06 那个问题问遍其余四条历史路线的拒绝：各自在普通链路里都有对应，B06 是唯一多出来的。顺带量出两处**任何材料都够不到**的修订分歧——lodging 更松（问已批政策，而普通入口见修订即拒；唯一那家酒店三个目标期间零修订），accession 更严（见修订即拒，而另三条问政策；每个带修订的期间都先被它自己的适用性门答掉）。后者接线会移动零个坐标、且只能用构造用例行使，**点名不建**。(2) D02 关键词代理普查从六份扩到十一份（24个Item 8准入、19个正确）：Marriott 三个期间同一块同一判断；**Macy's 1065 证伪了那条候选判据**——它既谓述注册人又把关键词放在枚举里，两半同时成立，所以按枚举收窄会丢掉一条或有事项披露。Paramount 的 D02 登记为第三个实例并撤回（28条里两条是交易成本与债务契约）。(3) 获取许可的"1232次上限"写成了**门禁能接受的对象**：九字段政策加一条须复述其中三项的批准评论，在临时树里跑真验证器——接受、上限读回 [0,0,1232]、而一份声称超过其评论的政策按名被拒。依赖类别是十家公司声明实际产出的六类（554行），窗口是帧自己的14个目标期末（上一期材料要往回一年，但那些行带的是**目标**期间，所以窗口不必多一年）。它是提案不是授权：写在证据树而不是门禁读的路径，`budget_root` 仍由 owner 选，这次算出的摘要是占位文本的摘要——政策文件从已发布的评论写出来，反过来不行。

Issue #47 内容接受扩到124条，而**本轮最该记的是我自己的读取器错了六次，每次都长得像路线的缺陷**。清单：(1) 瞬时上下文键写错→每家的B08/B09都读成"没读到"；(2) 文档路径按`company_id`拼→`macys`在盘上是`macy_s`，第十家被报成"原件未保存"；(3) 比字符串而不是比数→Ford的B03因Decimal多一个尾零报DIFFERS；(4) 8-K过滤写成`form == "8-K"`→漏掉带item 5.02的8-K/A，Marriott的C01/E03读2对发布3；(5) 上下文正则只认`xbrli:`前缀、再改又只认`id`是第一个属性→代理文件返回空上下文表，**空表和"这份文件什么都没写"长得一模一样**，六个C03位置因此读不出来；(6) "40个块内没被取到就算漏"这个阈值→把Enphase的或有事项附注报成漏掉，而选择器在第57块处取了。**够不到目标代码的注错不是"没人抓得住"的证据，读不到也不是"它不存在"**——六次里有五次的表现形式就是这两句的变体。**零个真差异幸存**。

**四份读取产物**（`docs/evidence/issue47_history/content-acceptance/`，登记由`tools/build_acceptance_register.py`生成不手写）：报表八项走申报自己的inline XBRL（路线读Company Facts，所以是跨来源）73条；住宿表不经生产网格构建器6条；8-K事件从各申报自己的SEC头计数、且在"按申报日"与"按报告日"两种窗口读法下同值36条；治理5条；D02四份小集合整读4条。Marriott 2025的19个值里18个已读。

**三处读不了，各有具体理由而不是沉默**。**B06**：三个位置都能从申报字节重现，但其中两个是**从发布值反解出组成再去找概念**——那是拟合不是核对；而规则也无法只从申报陈述：Salesforce的申报同时带两个已批债务模型的输入，给出14,974,000,000与14,439,000,000两个不同答案，选哪个由级联读的附注结构决定，正是第二实现要重写的那部分。**E01**：唯一带关键词分支的路线，按整个accession扫描会在几乎任何附件里命中"transaction"；七个窗口有六个含8.01申报，所以只接受那个没有的。**D02其余七份**：Pfizer那份整读过并抓出两块错的，所以不能凭读过的四份去接受没读的七份。

**没人量过的那个方向已量**：此前每次D02核查都只判"取到的这些该不该取"，被丢掉的披露对它不可见。整读一个声明范围十一次不可行（Macy's一份就1208块），所以改问一个能机械回答、且不复用选择器自身信号的窄问题——**有没有哪份申报的或有事项/法律程序附注标题，是摘录集从未到达的**。二十一个标题：**每一份的"Commitments and Contingencies"附注都被到达**（间距1到57块）；三个从未到达的都对（Macy's的"14. Commitments"是商品采购义务，Lumen两个是Note 17法律部分之后的承诺小节）；四个在Item 1A的是风险因素标题、属D03范围。这**不证明没丢东西**——它本身也是代理，只找带那四个词的标题形状块——但它证明了一件此前未知的事。

**接受登记与缺陷登记方向相反**这条现在还多一层：文本值可按`sha256:`摘要点名（D02一条5098字符），绑定不变——不同的正文不同的摘要，接受即失效；对应用例两头都断言（拿摘要串去比原值会一条都不接受，只看前缀会什么都接受）。

Issue #47 28指标×11期间批次（同一只读运行时树、closure `sha256:ecacd7f2…`、零调用）：**374个位置全部尝试、374个冻结Run与公共行、零失败**——本Issue第一次没有失败位置。上一批那两个失败都已在其后修好并在这一批交出数值：Paramount的B06走INCLUSIVE语法给`1.168049260241169930727785855`，C03给`63211569`。三层照旧分开数：**155带数值**（153 EXACT＋2 APPROX，上一批153）、**169结构性不适用**、**50跑了没有值**。

**那50不是一个数而是三件事，并且这里纠正我自己上一条记录**：上一批我把它写成"答案7／缺口43"，那43里其实含**6个已决政策拒绝**（Paramount报表类的`HISTORICAL_AMENDMENT_INPUT_CLASS_NOT_CLEARED`）——已批准政策说"未清除"是一个有答案的问题，和"这份材料本仓库没有"是两回事，混在一起正是让已定问题读起来还没定的方式。本批实际为**答案7**（分母非正3、分子非正2、接续注册人146天首期的`ANNUAL_DURATION_OUT_OF_RANGE`2）／**已决政策6**／**缺口37**（事件8-K正文24、C04上一期accession索引5、B06来源关系4、代理未保存2、Company Facts 1、全分支拒绝1）。

**第三层首次非零**：`content_acceptance` 125（上一批0）。155个数值里125个被独立读过、3个被已登记内容缺陷撤回（三份D02）、27个没人读过。`verified_outcome` 321。帧的另外三层不变：1950个目标位置里1521仍在等获取。

**冷读又是同一个形状，这次出在我自己的检查器上**：按路线族的冷读脚本第一次指向了扁平化后的runs根，那里有Run目录但没有逐期间的matrix，于是它glob到零个文件、读了零个Run、打印`all_passed: True`——`all()`对空列表恒真。这是本Issue第八次"**把我没看见当成它不存在**"。已加三道拒绝（根里没有期间matrix、没有任何PUBLIC_ROW位置、批次里出现过的族却没被覆盖），并先把它指回扁平根确认会拒。修后**16次读、九族全覆盖、全部通过**，包括accession/companyfacts/zero_ai_statement/zero_ai_event/text/governance/debt/lodging/structural。

**两棵树的差异这次量了**：逐叶比对两份minted `baseline_manifest.json`，**12个叶子不同，全部落在6个注册补丁文件的`execution_authority`条目上；`new_rule_files`的哈希一个都不差**。所以这批跑的是仓库自己的路线字节，不同的只有继承下来的注册补丁——"一棵代码树一次只满足一个世代"是ratchet的固有形状，不是这批引入的。材料见`docs/evidence/issue47_history/native-run-batch-28-metrics-zero-failures/`。

Issue #47 内容验收三处进展，其中两处是**我自己的读取器错了，而不是路线错了**。(1) **Pfizer的B03/B07此前记作"读不到"**，原因在读取器不在申报：两者都要营业利润，而Pfizer整份5.2MB主文件**零次**标记`OperatingIncomeLoss`；我的读取停在候选链第一项，**已批定义不停**——它允许"税前持续经营利润 − 合计非经营项"重建，且只许用合计桥接（不得用利息/投资收益/其他碎片拼），并在申报标了`CostsAndExpenses`时用`Revenues − CostsAndExpenses`交叉核对。实测Pfizer：税前7,520,000,000、`OtherNonoperatingIncomeExpense` −6,724,000,000（`NonoperatingIncomeExpense`未标）、重建营业利润14,244,000,000，于是B03=0.3329551446971028619824541779、B07=5.332834144515162860351928117，与发布值逐位相同。**"只增不移"是断言出来的**：十家重跑，此前MATCH的**零个移动**、恰好两个新增、且只有Pfizer用到重建。三次注错（桥接符号相反、用利息当桥接、直接拿税前当营业利润）全部被抓。`CostsAndExpenses`交叉核对分支**本语料无一例触发**，如实登记。跨来源读取现为80个位置**75 MATCH、0 DIFFERS、0 读不到**。

(2) **D02的四个未读集合已两向读完，读出一个新缺陷族：摘录集里有页眉页脚**。Salesforce 15条、Southwest 25条全对并接受；**Enphase 18条里第755块是页脚**"Enphase Energy, Inc. | 2025 Form 10-K | 46"；**Ford 53条里8条是连续附注的running head**（"FORD MOTOR COMPANY AND SUBSIDIARIES"、"NOTES TO THE FINANCIAL STATEMENTS"、"NOTE 24. …(Continued)"，三个分页各一组）。成因同一处：页眉判据只挂在本世代自己构造的scope上，`ITEM_3`与整取附注没有它——代码注释里早写着"整取附注保留继承行为，它已经带着Ford的running header"，也就是知道而留着。**修的是覆盖面不是判据**：同一条"重复且邻块也重复"现在每个scope都用。十一份实测：**Ford 53→45，丢掉的正是那8块；其余十份的D02候选、proposal与coverage哈希逐字节不变**。Enphase那一条**修不了也不修**——页脚带页码，任何两次出现都不是同一串文本，重复判据无从比较；要抓它得发明第二条判据，而本语料只有一个例子，这正是本Issue反复记录的那种错误，故按缺陷登记（第7条）并撤回该坐标。

(3) **这次改动我又犯了已经记过的那个错，并被量出来**：第一版直接`continue`跳过该块，而**同一个循环同时在建D03的监管候选集**，于是Macy's的D03由42降到40——丢的是1566/1573两块"Settlement(189)(123)— —"，养老金附注里重复出现的表格行，带`ACTION_LANGUAGE_PRESENT`。**Macy's的D02一条都没动**，所以从正在处理的那个指标上完全看不见。现在跳过只加在D02那一支；十一份实测D03全部未变。顺带量出一件关于这条判据本身的事：**它会把重复的表格行看成页眉**，本语料里没有D02 scope含这种行所以无代价，但这就是它不能无限外推的理由。四次注错三次被抓（不扩覆盖面→Ford那条挂；让跳过也作用于D03→两条挂；把页眉写回scope对象→同两条挂，因为写回去就等于让跳过作用于D03）。**第四次`RECOMPUTE_EVERY_SCOPE_INCLUDING_THE_SUB_NOTE`没被抓**：子附注scope按父附注范围计重复，与按自身范围计在原理上不同，但四份实测（含Pfizer这唯一有子附注scope的）两种算法结果完全一致——**本语料区分不了**，守卫保留是因为它维持各scope被测量时的语义，如实记为"无例检验"。

**还有一处顺序上的提醒**：页眉改动写进scope对象时，Macy's的candidate不再与冻结实现逐字节相同（三个哈希变了，可见内容一个字没变），而那条比对用例正是为此存在。**一个只移动一份申报里8个块的改动，就该只改一份申报的字节**；现在页眉表放在scope旁边而不是写进去，代价是这些scope的记录不再自报把什么当成了页眉（caption scope会自报），如实记下。
