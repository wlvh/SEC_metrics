# SEC_metrics PR 提交检查清单

## 1. 触发条件

只有用户明确要求提交、推送或创建 PR 时，才执行本流程。普通本地修改、分析、测试或工作流文档同步不自动获得 commit、push 或 PR 权限。

本仓库默认分支是 `main`。向 `main` 合并代码时使用 PR；未收到发布请求时保留本地修改并报告状态。

## 2. 分支与提交策略

- 发布分支不得是 `main`，PR base 使用 `main`。
- 未有其他团队约定时，建议一个 PR 保持一个有意义的 commit；这是一项默认建议，不是不可豁免的历史事实。
- 已存在 PR 的修复可在更新 PR body 的 Review / 修复记录后使用 `git commit --amend`。
- 重写已发布分支时只允许 `git push --force-with-lease`，禁止裸 `--force`。
- 不得覆盖或混入用户已有的无关工作区修改。

## 3. PR body 文件

`.github/pull_request_template.md` 是长期模板。`PR_BODY.md` 是由模板生成的本地临时草稿，受 `.gitignore` 保护，不得提交仓库。

仅在发布流程中执行：

```bash
cp .github/pull_request_template.md PR_BODY.md
```

PR body 只能记录本 PR 已完成的事实。变更文件清单必须来自真实 diff，不得包含历史草稿、未落地计划或本地未提交的其他工作。

## 4. 变更范围核对

- [ ] 用户已明确要求发布。
- [ ] 当前分支不是 `main`，目标 base 是 `main`。
- [ ] 已确认 upstream/base，并运行真实的 `git diff --name-only <base>...HEAD`。
- [ ] PR body 的文件清单与 diff 双向一致：不遗漏，也不多写。
- [ ] 已检查 `git status --short`，没有混入本 PR 范围外的修改或未跟踪文件。
- [ ] 删除、重命名和生成 artifact 的变化已单独说明。

## 5. 文档影响

### 5.1 架构

- [ ] 若模块、调用链、数据流、状态、错误、依赖、配置或扩展点变化，已更新 `architecture.md`。
- [ ] 若无需更新，已在 PR body 中说明为什么没有架构影响。

### 5.2 能力契约与用户文档

- [ ] 修改能力边界时，先更新或确认 `capability_contract.json`，再检查 `interact.md` 与 `docs/business_user_guide.md`。
- [ ] 修改用户可观察行为时，先更新或确认 `interact.md`，再检查业务指南。
- [ ] 新增“能做 / 不能做 / 必须 / 不得”的声明时，使用稳定 `anchor_id`；Markdown 不引用 JSON path 或数组位置。
- [ ] 新增 agent 行为承诺时，登记真实 test anchor；未自动化时使用 `test_anchor: null` 并说明原因。
- [ ] 业务指南只教学性解释能力契约和可观察行为，不独立发明功能。

### 5.3 文件地图与测试说明

- [ ] 核心配置、模块、业务逻辑或标准流程变化已同步 `AGENTS.md` 文件简介或 SOP 清单。
- [ ] 测试、fixture、命令、副作用或分层变化已同步 `TESTING.md`。
- [ ] `SOP.md` 只保留动作、权威引用和验收，不复制易漂移的脚本清单或测试细节。

## 6. 测试与验证证据

测试策略以 `TESTING.md` 为唯一权威。对每条实际执行的命令，PR body 必须记录：

- 原样命令。
- PASS / FAIL / SKIP 或受限结果。
- 证据或 artifact 路径。
- 未运行的适用测试及原因。

检查项：

- [ ] 已按变更类型选择测试层级，没有用 unittest 替代 Golden、repair gate 或完整场景。
- [ ] light review 的 skipped 与受限状态没有写成 full validation。
- [ ] 运行会覆盖 `evidence/`、`outputs/` 或报告的命令前使用了干净、隔离的 checkout。
- [ ] 若运行 `scripts/11_build_report.py`，已按适用范围单独运行最终 `scripts/12_validate_repair.py`。
- [ ] 测试失败未通过修改 expected、放宽断言或静默跳过来掩盖。

## 7. 用户与数据影响

- [ ] 用户可见入口、输出字段、status、默认行为、错误提示或排序变化已对照 `interact.md` 验收。
- [ ] 指标口径变化已对照 `02_指标定义_SEC_10公司单年指标.md`，并核对 evidence 与 Golden。
- [ ] SEC 请求变化仍只走 `SecHttpClient`，保留 URL、User-Agent、状态、retry、headers/hash 与请求日志。
- [ ] 公司/CIK/profile 扩展没有引入生产 identity branch，并已运行对应扩展性证据。
- [ ] 没有把历史 absolute `local_path` 当作跨机器权威地址。

## 8. 发布声明约束

当前仓库没有 CI workflow、生产部署或自动调度实现。除非本 PR 的代码、配置和运行证据确实增加并验证了这些能力，否则 PR body 必须写“不适用”或“未实现”，不得声称 CI、部署、调度、前端、API 或 vNext 切换已经完成。

流水线 GO 类自判不等于外部审计接受或生产发布许可。

## 9. 创建 PR

只有 GitHub CLI/发布能力可用且已认证时，才执行发布命令；不可用时报告阻塞，不伪造 URL 或成功状态。

```bash
gh pr create --title "<标题>" --body-file PR_BODY.md --head <feature-branch> --base main
```

成功后返回真实 PR URL，并明确 draft/ready 状态。用户未要求 draft 时，不自行创建 draft；用户未要求 PR 时，本节完全不执行。

## 10. 最终核对

- [ ] Review / 修复记录包含每轮真实发现、判断、处理结果与证据。
- [ ] 已知限制、未解决决策和回滚方式与当前 patch 一致。
- [ ] PR body 没有未执行命令的虚假 PASS，也没有未来计划冒充完成事实。
- [ ] `PR_BODY.md` 未进入 diff。
- [ ] 当前分支、base、commit、push 与 PR URL 均来自实时命令结果。
