# SEC_metrics 标准操作流程导航

## 使用原则

每一步只保留动作、权威引用和验收。发生冲突时，以代码、测试、能力契约和被引用的专项文档为准。

## SOP 1：只读取现有结果

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 先读取 run manifest | `outputs/validation_run_manifest.json` | `result` 不是 `PASSED` / `PASSED_WITH_CAVEATS` 时立即停止验收 |
| 2 | 验证 source 与 artifact binding | `python3 tools/check_validation_snapshot.py`；`docs/validation_snapshot_provenance.md` | provenance 存在；source-input tree clean/等价；关键 artifact SHA-256 与 size 全部匹配 |
| 3 | 阅读报告和具体结果 | `REPORT_十公司财务指标.md`；`outputs/metrics_matrix.csv`；`outputs/metric_evidence.csv` | verdict、value/status、期间、口径和 evidence 能闭合 |
| 4 | 复核限制和人工责任 | `interact.md`；`docs/business_user_guide.md` | 未把 light、caveat、NOT_EVALUATED 或历史快照写成 full PASS |

## SOP 2：SEC 阶段 00–12 完整批次运行

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认公司范围、CIK role、指标适用性和有效 SEC 请求身份 | `config/`；`02_指标定义_SEC_10公司单年指标.md` | 配置结构有效，范围和口径已由运行负责人确认 |
| 2 | 从干净工作区按阶段 00–11 顺序执行 | `README_RUN.md` 的“执行新批次” | 各阶段完成，预期 evidence 与 outputs 已生成；stage 11 exit 0 只代表报告构建完成 |
| 3 | 单独执行阶段 12 | `python3 scripts/12_validate_repair.py`；`TESTING.md` | Golden、repair gate 与 provenance publication 均通过，命令 exit 0 |
| 4 | 独立重验终态 | `python3 tools/check_validation_snapshot.py` | terminal manifest、source-input tree 与关键 artifact bytes 仍一致 |
| 5 | 交付报告、证据与限制 | `interact.md`；`docs/business_user_guide.md` | reviewer 能从 manifest/provenance 追溯到 report、metrics、evidence 和 request ledger |

## SOP 3：分层验收与失败定位

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 按变更类型选择最小且充分的测试层级 | `TESTING.md` | 每条适用命令、结果、证据路径和未运行原因已记录 |
| 2 | 先读 manifest，再运行 snapshot checker | `README_RUN.md`；`docs/validation_snapshot_provenance.md` | stale run、dirty source、tree mismatch 与 artifact tamper 已先排除 |
| 3 | 再定位 unittest、Golden、repair、coverage 或 request failure | `TESTING.md` 的失败定位 | 失败已对应到 test、check_id、company/metric、source path 或 artifact digest |
| 4 | 修复真实原因并重跑受影响层及下游 gate | `TESTING.md`；`architecture.md` | 没有放宽断言、静默跳过、重签旧证据或以 light 冒充 full |
| 5 | 核对生成 artifact 与工作区范围 | `PR_Checklist.md` | `git status` 只包含预期文件，失败证据与处置可复核 |

## SOP 4：PR 发布（仅用户明确要求时）

| 步骤 | 动作 | 权威引用 | 验收 |
|---|---|---|---|
| 1 | 确认发布授权、feature branch、base 与 patch 范围 | `PR_Checklist.md` | 用户已要求发布，当前分支不是 `main`，base 为 `main` |
| 2 | 完成文档影响、测试证据、已知限制和 Review 记录 | `PR_Checklist.md`；`.github/pull_request_template.md` | PR body 与真实 diff、测试结果和未解决决策一致 |
| 3 | 按授权执行 commit、push 和 PR 创建 | `PR_Checklist.md` | 远端分支与 draft PR 已创建 |
| 4 | 向用户交付发布结果 | `PR_Checklist.md` | PR URL、分支、commit、测试与限制均已明确报告 |
