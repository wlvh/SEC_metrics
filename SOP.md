# SEC_metrics 标准操作流程导航

## 使用原则

每一步只包含动作、权威引用和验收。SOP 不复制会变化的脚本清单、测试命令或指标规范；发生冲突时，以代码、测试、能力契约和被引用的专项文档为准。`config/validation_source_policy.json` 必须把每个权威引用分类为运行/验收 source、snapshot artifact 或非批次治理角色；解释性非权威文档不能作为本表的运行权威。

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
| 2 | 从干净工作区按阶段 00-11 顺序执行完整批次 | `README_RUN.md` 的“从干净目录运行阶段 00-11” | 各阶段完成，预期 evidence 与 outputs 已生成；stage 11 exit 0 只代表报告构建完成 |
| 3 | 单独执行阶段 12 分层验证 | `TESTING.md` 的完整场景、Golden、repair gate 与 provenance 专项 | Golden 与独立最终 gate 满足 full 通过条件，run manifest 已完成，provenance publication/self-check 成功 |
| 4 | 独立重验终态 | `python3 tools/check_validation_snapshot.py` | terminal manifest、source-input tree 与关键 artifact bytes 仍一致 |
| 5 | 交付报告、证据和限制 | `interact.md`；`docs/business_user_guide.md` | reviewer 能从 manifest/provenance 追溯到 report、metrics、evidence 和 request ledger |

## 专项：vNext recorded shadow（不切流）

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
| 1 | 读取 exact Requirement、Decision Register、SU 状态与外部阻塞 | `requirements/ai_first_v3_3_1/IMPLEMENTATION_TODO.md`；`requirements/ai_first_v3_3_1/decision_register.json` | FSD/Issue/baseline hash 可复核；D-01 或其他未完成项没有被默认批准 |
| 2 | 按 recorded 层运行 schema、Reader/Evidence、Review/freeze/replay、Calculator、Projector、publication 和 semantic gates | `TESTING.md` 的“vNext recorded shadow” | 无网络 fixture 测试与双解释器结果按真实状态记录；任何 FAIL/NOT_RUN 不写成 PASS |
| 3 | 需要人工决定时，只复核 run-scoped 完整表格与 rendered ReviewUnit，再通过最小 review CLI 追加不可变 HUMAN decision | `interact.md` 的 vNext review 旅程；`tools/vnext_review.py` | reviewer identity、approved claims、rendered/canonical context 与 supersedes 单链都通过绑定检查 |
| 4 | 对已有 `PASSED`、`FAILED` 或 `NOT_RUN` receipt 的 OPEN Run 执行 freeze，并从 FROZEN Run 做无 AI replay；只有 `PASSED` 可继续检查其他 publication gates | `architecture.md` 的 vNext 状态模型；`TESTING.md` | freeze 前重新读取 Spec/source/review/全部成功 response bytes；任何 AI attempt 必须终态；显式缺失 source role 的 Run 只能保留全 WITHHELD 审计结果；失败或未运行状态禁止 publish；replay 不开 socket |
| 5 | 读取 `outputs/acceptance_receipts/` 中的 recorded receipt 与 SU 清单，确认本次没有改变根目录现行结果或 active publication | `TESTING.md`；`requirements/ai_first_v3_3_1/IMPLEMENTATION_TODO.md` | recorded 状态只能写 `PASSED_RECORDED_ONLY`；live 三轮、staging、Cutover、rollback/full 未实际完成时保持 NOT_RUN/BLOCKED |

该专项不是当前 00–12 批次的替代入口。只有 D-01、有效 SEC 身份、clean committed source closure、第二真实布局、独立 holdout、live 三轮稳定性、完整 staging parity、旧 producer 退出和真实 rollback/full validation 全部产生证据后，才允许另行执行 Cutover；本 SOP 不提供绕过这些 gate 的命令。

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
