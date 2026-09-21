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
