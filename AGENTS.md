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

阶段 `00`–`11` 负责采集、计算、repair 与报告构建；阶段 `12` 是独立终态 gate。stage 11 exit 0 只说明报告构建完成，不代表完整批次成功。

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
- `PR_Checklist.md`：仅在用户明确要求发布时使用的 PR 核对流程。
- `.github/pull_request_template.md`：长期 PR body 模板。
- `.gitignore`：本地缓存、环境与临时 PR 草稿的忽略规则。

### 核心配置

- `config/sec_config.json`：SEC User-Agent、请求速率、重试与退避参数。
- `config/company_registry.csv`：逻辑公司、CIK role、行业 profile、财年底与连续性。
- `config/metric_applicability.yaml`：SIC/profile 规则、extractor 路由与行业参数；当前由 JSON parser 读取，内容必须保持 JSON 兼容。

### 核心模块

- `scripts/sec_pipeline.py`：阶段调度、解析、计算、富化、repair、验证、审计与报告的单体内核。
- `scripts/sec_http.py`：精确官方 SEC origin 限制、无隐式 redirect、进程内节流、重试、immutable attempt body/header、request ledger、整表 manifest 与 cooperating-process publication lock。
- `scripts/sec_urls.py`：集中构造 SEC 官方 endpoint。
- `scripts/git_workspace.py`：集中清理 Git 重定向环境，并校验 checkout 与 object/ref 存储边界。
- `scripts/validation_provenance.py`：捕获 source-input tree、发布关键 artifact digest sidecar，并在 postflight 失败时使终态 fail closed。
- `scripts/00_*.py` 至 `scripts/12_*.py`：无参数单阶段 CLI wrapper；stage 11/12 额外负责旧 provenance 失效与终态 publication。
- `tools/check_validation_snapshot.py`：独立复核当前 checkout、manifest、provenance sidecar 与关键 artifact bytes。
- `tools/check_no_company_literals.py`：生产 Python identity literal 的扩展性 gate。
- `tools/check_capability_contract_alignment.py`：能力契约 anchor、文档路径与 `file::symbol` 的机械结构 gate；不证明 claim 语义成立。

### 业务逻辑与运行入口

- `01_SOP_SEC_10公司单年指标计算_直接SEC.md`：业务方法与原始设计说明；其中 M0–M7 是概念阶段，不是当前 `scripts/00_*`–`12_*` 的物理顺序，实际运行以 `README_RUN.md` 为准。
- `02_指标定义_SEC_10公司单年指标.md`：指标定义、候选链、公式、适用性与降级语义。
- `SEC_metrics_Project_Overview_and_Expert_Guide.md`：长篇解释性文档；其中历史数量或历史验收结论不是当前状态源。
- `README_RUN.md`：完整阶段顺序、验收入口、主要输出和 light review 说明。
- `CIK变更应对方案.md`：CIK、successor/predecessor 与实体连续性规则。
- `evidence/requests_log.csv`：按 request attempt 记录的请求 ledger。
- `evidence/requests_log_manifest.json`：绑定 request CSV 的 schema version、row count 与整表 SHA-256；缺失或失配时 request history 不能视为完整证据。
- `evidence/request_attempts/`：content-addressed immutable response body/header attempts。
- `outputs/`：inventory、指标、证据、coverage、Golden、validation 与审计派生产物。
- `outputs/validation_run_manifest.json`：最近一次 repair validation 实际刷新/未刷新的证据清单，不是 runtime checkpoint，也不单独证明当前 checkout。
- `outputs/validation_snapshot_provenance.json`：成功 stage 12 对 source-input tree 与关键 artifact bytes 的绑定。
- `REPORT_十公司财务指标.md`：当前批次的派生中文报告，不独立定义能力、指标口径或成功状态。

测试文件和 fixture 的职责统一由 `TESTING.md` 管理，不在此逐项复制。新增、删除或改变上述核心文件职责时，必须同步更新本节。

## 2. 权威边界

- 架构事实以代码、配置、测试和 `architecture.md` 为准。
- 指标业务口径以 `02_指标定义_SEC_10公司单年指标.md` 和实现/validation 为准。
- 能力边界以 `capability_contract.json` 为准。
- 用户可观察验收以 `interact.md` 为准。
- 业务指南只能派生解释能力契约与用户行为，不能自行承诺功能。
- 测试策略以 `TESTING.md` 为准；SOP 和 PR checklist 只引用，不复制易漂移细节。
- 当前运行状态只能从 validation manifest、snapshot checker 与报告共同判断；长篇 Markdown 中的历史数量或结论不是当前状态源。
- 生成报告和 CSV 是当前代码与输入的 snapshot，不替代源代码、契约、provenance sidecar 或独立 gate。

### Source provenance 与当前 checkout

`manifest.source_commit` 是运行时观察值，不应被孤立解释：

1. exact commit 相同且 source-input closure clean，是最直接的匹配；
2. artifact commit 或 merge commit 改变 SHA 时，只有 `tools/check_validation_snapshot.py` 证明完整 source-input tree 等价，才可继续；
3. closure 内任一 tracked/untracked 改动、文件缺失、symlink、tree digest 变化或关键 artifact hash 变化都使 snapshot 不可验收；
4. `+dirty` 只说明整个工作树含改动，最终判断必须看 source-input closure 和 tree digest。

## 3. 工作规则

1. 先读本文件，再按第 0 节和 `SOP.md` 选择对应流程；不要把规划中的 vNext、Databricks、前端、API、CI、部署或调度写成当前已实现事实。
2. 主分支为 `main`。只有用户明确要求 commit、push 或 PR 时才执行发布；对 `main` 的合并通过 PR。
3. 用户未要求发布时，只保留并报告本地修改，不擅自创建分支、commit、push 或 PR。
4. 工作区可能包含用户已有修改；只处理任务范围，禁止覆盖、重置或混入无关 diff。
5. 修改能力边界时先更新或确认 `capability_contract.json`，再检查 `interact.md` 和 business guide。
6. 修改用户可观察行为时更新 `interact.md`，并判断 business guide 是否需要同步。
7. 修改模块边界、调用链、数据流、状态、错误、依赖、配置、artifact publication 或扩展点时更新 `architecture.md`。
8. 修改测试、fixture、测试副作用或推荐顺序时更新 `TESTING.md`。
9. `PR_BODY.md` 是被忽略的本地发布草稿，只在用户明确要求 PR 时由长期模板生成，永不提交。
10. 修改生成型 README/report 行为时改 generator 或稳定 post-processor；不得只手工编辑生成文件。

## 4. SEC 与数据规则

1. 所有生产网络请求只允许访问官方 SEC 域名，并统一经过 `SecHttpClient`。
2. live 请求前必须确认 `config/sec_config.json` 使用有效 organization/contact email；示例邮箱不是生产合规证明。
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

- 发现 Bug 时遵循 `TESTING.md`：先补稳定复现，再修实现；跨阶段问题同时补场景级证据。
- 不用 quick unittest 替代 Golden、repair gate、snapshot checker 或完整场景，也不用 light review 冒充 full validation。
- 会写 `evidence/`、`outputs/` 或报告的命令优先在干净、隔离的 checkout 运行。
- 用户要求 PR 时，逐项完成 `PR_Checklist.md`；任何豁免、未运行测试、known limitation 和未解决决策写入 PR body。

## 7. SOP 清单

需要执行标准流程时，先读取 `SOP.md` 中对应章节：

- 只读取现有结果
- SEC 阶段 00-12 完整批次运行
- 分层验收与失败定位
- PR 发布（仅用户明确要求时）
