# SEC_metrics 标准操作流程导航

## 使用原则

每一步只包含动作、权威引用和验收。SOP 不复制会变化的脚本清单、测试命令或指标规范；发生冲突时，以代码、测试、能力契约和被引用的专项文档为准。

## SOP 1：SEC M0-M7 完整批次运行

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认公司范围、CIK role、指标适用性和有效 SEC 请求身份 | `config/`；`01_SOP_SEC_10公司单年指标计算_直接SEC.md`；`02_指标定义_SEC_10公司单年指标.md` | 配置结构有效，范围和口径已由运行负责人确认 |
| 2 | 从干净工作区按阶段顺序执行完整批次 | `README_RUN.md` 的“从干净目录运行 M0-M7” | 各阶段退出 0，预期 evidence 与 outputs 已生成 |
| 3 | 执行完整批次的分层验证 | `TESTING.md` 的完整场景、Golden 与 repair gate | Golden 与独立最终 gate 满足对应模式的通过条件 |
| 4 | 交付当前批次的报告、证据和限制 | `interact.md`；`docs/business_user_guide.md` | 报告、矩阵、evidence、coverage、exceptions 与 gate 能互相追溯 |

## SOP 2：分层验收与失败定位

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 按变更类型选择最小且充分的测试层级 | `TESTING.md` 的测试层级与变更决策表 | 每条适用命令、结果和未运行原因已记录 |
| 2 | 定位 unittest、Golden、repair、coverage 或请求失败 | `TESTING.md` 的失败定位；`README_RUN.md` 的验收顺序与 P0 定位 | 失败已对应到具体 test、check_id、company/metric 或请求记录 |
| 3 | 修复真实原因并重跑受影响层及下游 gate | `TESTING.md`；`architecture.md` 的阶段依赖与错误模型 | 没有放宽断言、静默跳过或以 light 结果冒充 full |
| 4 | 核对生成 artifact 与工作区范围 | `TESTING.md` 的写入副作用；`PR_Checklist.md` 的变更范围 | `git status` 只包含预期文件，失败证据与处置可复核 |

## SOP 3：PR 发布（仅用户明确要求时）

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认发布授权、feature branch、base 与 patch 范围 | `PR_Checklist.md` | 用户已要求发布，当前分支不是 `main`，base 为 `main` |
| 2 | 完成文档影响、测试证据、已知限制和 Review 记录 | `PR_Checklist.md`；`.github/pull_request_template.md` | PR body 与真实 diff、测试结果和未解决决策一致 |
| 3 | 按授权执行 commit、push 和 PR 创建 | `PR_Checklist.md` 的分支、提交与创建规则 | 命令成功并返回真实远端分支与 PR URL |
| 4 | 向用户交付发布结果 | `PR_Checklist.md` 的最终核对 | draft/ready 状态、URL、测试与限制均已明确报告 |
