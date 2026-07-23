# SEC_metrics Agent 工作入口

## 0. 按任务选择阅读路径

首次进入仓库时，不要先把全部文档顺序读完。先按当前任务走一条路径，再按引用深入。

### 只读取当前结果

```text
docs/business_user_guide.md
→ outputs/validation_run_manifest.json
→ python3 tools/check_validation_snapshot.py
→ REPORT_十公司财务指标.md
→ outputs/metrics_matrix.csv / outputs/metric_evidence.csv
```

manifest 不是成功证明本身。`result` 必须是 `PASSED` 或 `PASSED_WITH_CAVEATS`，且 snapshot checker 必须证明当前 source-input tree 与关键 artifact bytes 仍和该 run 绑定。缺少 provenance、源文件有未提交改动、tree digest 变化或 artifact hash 失配时停止验收。

### 执行完整批次

```text
README_RUN.md
→ TESTING.md
→ SOP.md
```

阶段 `00`–`11` 负责采集、计算、repair 与报告构建；阶段 `12` 是独立终态 gate。stage 11 exit 0 只说明报告构建完成，不代表完整批次成功。

### 修改代码或 review PR

```text
architecture.md
→ capability_contract.json
→ interact.md
→ TESTING.md
→ PR_Checklist.md
```

涉及 SEC 访问、证据、manifest、verdict、source provenance 或 artifact publication 的改动，必须同时核对用户可观察后果和负例测试，不能只证明 happy path。

## 1. 核心文件地图

### 治理与工作流

- `AGENTS.md`：agent 入口、按任务阅读路由、项目规则与文件地图。
- `architecture.md`：当前 CLI 批处理架构、边界、数据流、状态、错误与债务。
- `capability_contract.json`：当前能力、限制、责任和行为承诺的机器可读真相源。
- `interact.md`：CLI 与文件交付中的用户可观察行为和验收不变量。
- `docs/business_user_guide.md`：面向首次读取结果的业务教学主路径。
- `docs/validation_snapshot_provenance.md`：source-input tree、artifact digest 与 checker 语义。
- `TESTING.md`：测试层级、真实命令、full/light 边界、provenance 负例与副作用。
- `SOP.md`：标准流程导航，只保留动作、权威引用与验收。
- `PR_Checklist.md`：仅在用户明确要求发布时使用的 PR 核对流程。
- `.github/pull_request_template.md`：长期 PR body 模板。
- `.gitignore`：本地缓存、环境与临时 PR 草稿的忽略规则。

### 核心配置

- `config/sec_config.json`：SEC User-Agent、请求速率、重试与退避参数。
- `config/company_registry.csv`：逻辑公司、CIK role、行业 profile、财年底与连续性。
- `config/metric_applicability.yaml`：SIC/profile 规则、extractor 路由与行业参数；当前由 JSON parser 读取，内容必须保持 JSON 兼容。

### 核心模块与工具

- `scripts/sec_pipeline.py`：阶段调度、解析、计算、富化、repair、验证、审计与报告的单体内核。
- `scripts/sec_http.py`：精确官方 SEC origin 限制、无隐式 redirect、进程内 pacing、重试、immutable attempt body/header、request ledger、整表 manifest 与 cooperating-process publication lock。
- `scripts/sec_urls.py`：集中构造 SEC 官方 endpoint。
- `scripts/git_workspace.py`：清理 Git 重定向环境，并校验 checkout、object store 与 ref 边界。
- `scripts/validation_provenance.py`：捕获 clean source-input tree、发布关键 artifact digest sidecar、验证等价 source tree，并在 postflight 失败时把终态降为 FAILED/NO-GO。
- `scripts/00_*.py` 至 `scripts/12_*.py`：无参数单阶段 CLI wrapper；stage 11/12 wrapper 还承担 stale provenance invalidation 与终态 publication。
- `tools/check_validation_snapshot.py`：独立验证当前 checkout、manifest、provenance sidecar 与关键 artifact bytes。
- `tools/check_no_company_literals.py`：生产 Python identity literal 的扩展性 gate。
- `tools/check_capability_contract_alignment.py`：能力契约 anchor、文档路径与 `file::symbol` 的机械结构 gate；不证明 claim 语义成立。

### 业务、证据与运行入口

- `02_指标定义_SEC_10公司单年指标.md`：当前指标定义、候选链、公式、适用性与降级语义。
- `README_RUN.md`：角色化读取入口、完整阶段顺序、验收入口、主要输出与 light review 说明。
- `CIK变更应对方案.md`：CIK、successor/predecessor 与实体连续性规则。
- `evidence/requests_log.csv`：按 attempt 记录的请求 ledger。
- `evidence/requests_log_manifest.json`：绑定 request CSV 的 schema version、row count 与整表 SHA-256；缺失或失配时 request history 不能视为完整证据。
- `evidence/request_attempts/`：content-addressed immutable response body/header attempts。
- `outputs/validation_run_manifest.json`：最近一次 repair validation 的 run、mode、result 与 refreshed/not-refreshed 清单；不是 runtime checkpoint，也不单独证明当前 checkout。
- `outputs/validation_snapshot_provenance.json`：成功 stage 12 对 source-input tree 与关键 artifact bytes 的绑定；stage 11 开始时会删除可安全识别的旧 regular sidecar；alias 或非 regular 目标会在修改新 artifact 前失败。
- `REPORT_十公司财务指标.md`：当前批次派生报告，不独立定义能力、指标口径或成功状态。

### 历史与解释性文档

- `01_SOP_SEC_10公司单年指标计算_直接SEC.md`：历史设计入口的兼容重定向，不是当前物理执行顺序；当前运行顺序以 `README_RUN.md` 为准。
- `SEC_metrics_Project_Overview_and_Expert_Guide.md`：概念、当前状态与历史快照的导航页，不保存“当前数量”或“当前 verdict”。
- `docs/concepts/sec_xbrl_and_evidence_model.md`：稳定的 SEC/XBRL/证据模型，不含动态 run 数量。
- `docs/history/`：固定 commit/date 的历史设计与测量记录，不得冒充当前状态源。

测试文件和 fixture 的职责统一由 `TESTING.md` 管理。新增、删除或改变上述核心职责时，必须同步更新本节。

## 2. 权威边界

- 架构事实以代码、配置、测试和 `architecture.md` 为准。
- 指标业务口径以 `02_指标定义_SEC_10公司单年指标.md`、实现和 validation 为准。
- 能力边界以 `capability_contract.json` 为准。
- 用户可观察验收以 `interact.md` 为准。
- 业务指南只能派生解释能力契约与用户行为，不能自行承诺功能。
- 测试策略以 `TESTING.md` 为准；SOP 和 PR checklist 只引用，不复制易漂移细节。
- 当前运行状态先读 validation manifest，再运行 snapshot checker，最后读报告；任何 Markdown 中的历史计数或结论都不是当前状态源。
- 生成报告和 CSV 是当前代码与输入的 snapshot，不替代源代码、契约、provenance sidecar 或独立 gate。

## 3. Source provenance 与当前 checkout

`manifest.source_commit` 是运行时记录，不应被孤立解释：

1. exact commit 相同且 source-input tree clean，是最直接的匹配；
2. commit SHA 因 artifact commit 或 merge commit 改变时，只有 `tools/check_validation_snapshot.py` 证明完整 source-input tree digest 等价，才可继续；
3. source-input closure 内任一 tracked/untracked 改动、文件缺失、symlink、tree digest 变化或关键 artifact hash 变化都使 snapshot 不可验收；
4. `+dirty` 只说明整个工作树含改动，不能区分生成 outputs 与源代码。最终判断必须看 source-input dirty paths 和 tree digest，不能只比较字符串后缀。

当前 source-input closure 包含 `scripts/`、`tools/`、`config/`、`tests/`、能力契约、指标定义以及核心治理/用户行为文档；生成 evidence/outputs 由 artifact digest 单独绑定。

## 4. 工作规则

1. 先按第 0 节选择阅读路径；不要把规划中的 vNext、Databricks、前端、API、CI、部署或调度写成当前已实现事实。
2. 主分支为 `main`。只有用户明确要求 commit、push 或 PR 时才执行发布；对 `main` 的合并通过 PR。
3. 用户未要求发布时，只保留并报告本地修改，不擅自创建分支、commit、push 或 PR。
4. 工作区可能包含用户已有修改；只处理任务范围，禁止覆盖、重置或混入无关 diff。
5. 修改能力边界时先更新或确认 `capability_contract.json`，再检查 `interact.md` 和 business guide。
6. 修改用户可观察行为时更新 `interact.md`，并判断 business guide 是否需要同步。
7. 修改模块边界、调用链、数据流、状态、错误、依赖、配置、artifact publication 或扩展点时更新 `architecture.md`。
8. 修改测试、fixture、测试副作用或推荐顺序时更新 `TESTING.md`。
9. `PR_BODY.md` 是被忽略的本地发布草稿，只在用户明确要求 PR 时由长期模板生成，永不提交。
10. 修改生成型 README/report 行为时改 generator 或稳定 post-processor；不得只手工编辑生成文件。

## 5. SEC 与数据规则

1. 所有生产网络请求只允许访问精确官方 SEC HTTPS origin，并统一经过 `SecHttpClient`。
2. live 请求前必须确认 `config/sec_config.json` 使用有效 organization/contact email；示例邮箱不是生产合规证明。
3. 每个已发请求 attempt 必须保留 UTC observation；有响应体时保存 immutable raw bytes、headers 与 SHA-256。HTTP redirect 不自动跟随，下一跳必须重新显式校验。
4. `requests_log.csv` 与 `requests_log_manifest.json` 共同构成 ledger publication；row count/hash、CSV schema、HEAD/base 有序前缀、下游 locator 与 sidecar 任一失配都不能 PASS。
5. 禁止使用第三方数据、新闻、搜索结果或模型记忆为 SEC 指标补数。
6. 可采信的非空数值必须有 matching metric evidence；证据不足时使用明确 status 和 notes，不得猜数。
7. 公司身份、CIK role、行业 profile 与适用性来自 `config/`；生产代码不得按公司名、CIK、ticker、固定 accession 或固定财年日期写业务分支。
8. 新 artifact 使用 `source_url`、`repo_relative_path`、`content_sha256`、`accession` 与 `document_name`；历史绝对 `local_path` / `source_path` 只作 relocation hint。

## 6. 代码规范

1. 与用户沟通使用中文；代码、文档和数据文件使用 UTF-8，时间使用 UTC。
2. Python 遵循 PEP 8；函数调用优先显式关键字参数，公共函数和类保持有意义的 docstring。
3. 必需字段通过显式检查 fail fast；不得用隐式 `None` 或宽泛异常吞掉预期外错误。
4. `try/except` 只捕获可处理的具体异常，并保留足够诊断；无法处理的错误在当前边界失败。
5. 输入、输出和阶段 handoff 通过明确数据契约表达，避免隐藏全局状态与不可见副作用。
6. 重复规则抽成共享函数或配置；优先减少代码量，但不得牺牲证据、状态语义和可维护性。
7. 修改生成逻辑时改源代码并重跑适用验证，不把手工编辑生成 CSV/报告当作实现修复。
8. 完整性修复必须覆盖字段值、行形状、集合、顺序、版本、路径别名、publication failure 与 post-run tamper，不以单个正例替代不变量证明。

## 7. Review 与测试

- 发现 Bug 时遵循 `TESTING.md`：先补稳定复现，再修实现；跨阶段问题同时补场景级证据。
- 不用 quick unittest 替代 Golden、repair gate、snapshot checker 或完整场景，也不用 light review 冒充 full validation。
- 会写 `evidence/`、`outputs/` 或报告的命令优先在干净、隔离的 checkout 运行。
- 用户要求 PR 时，逐项完成 `PR_Checklist.md`；任何豁免、未运行测试、known limitation 和未解决决策写入 PR body。
