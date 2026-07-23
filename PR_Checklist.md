# SEC_metrics PR 提交检查清单

## 1. 触发条件

只有用户明确要求提交、推送或创建 PR 时才执行本流程。普通分析、测试或本地修改不自动获得发布权限。默认分支是 `main`，向 `main` 合并使用 PR。

## 2. 分支与提交策略

- 发布分支不得是 `main`，PR base 使用 `main`。
- 未有其他约定时，建议一个 PR 保持一个有意义的 commit；连接器限制导致多个机械提交时，PR body 必须如实说明。
- 已发布分支只能使用 `--force-with-lease`，禁止裸 `--force`。
- 不得覆盖、重置或混入用户已有无关工作区修改。
- 默认创建 draft PR；只有用户明确要求 ready，或 maintainer 完成所有发布级验证后，才标记 ready for review。

## 3. PR body 文件

`.github/pull_request_template.md` 是长期模板。`PR_BODY.md` 是被 `.gitignore` 保护的本地草稿，不得提交。PR body 只能记录已完成事实，文件清单来自真实 diff，不包含历史草稿或未落地计划。

## 4. 变更范围核对

- [ ] 用户已明确要求发布。
- [ ] 当前分支不是 `main`，目标 base 是 `main`。
- [ ] 已确认 upstream/base，并运行真实 `git diff --name-status <base>...HEAD`。
- [ ] 已从真实 Git toplevel 运行 `python3 tools/check_capability_contract_alignment.py --base-ref <base>`。
- [ ] PR body 文件清单与 diff 双向一致。
- [ ] `git status --short` 没有混入范围外修改或未跟踪文件。
- [ ] 新增、删除、重命名、历史文档降级和生成 artifact 变化已单独说明。

## 5. 文档影响

### 架构、能力与用户行为

- [ ] 模块、wrapper、调用链、数据流、状态、错误、依赖、配置、source closure、artifact publication 或扩展点变化已更新 `architecture.md`。
- [ ] 能力/行为变化先更新或确认 `capability_contract.json`，再同步 `interact.md` 和 business guide。
- [ ] 新的“必须/不得/能做/不能做”声明使用稳定 anchor；自动化行为登记真实 `file::symbol`。
- [ ] 业务指南只解释契约与用户行为，不独立发明功能。

### 文件地图、SOP 与历史文档

- [ ] 核心文件职责和阅读路由已同步 `AGENTS.md`。
- [ ] 测试层级、fixture、命令、副作用和高价值缺口已同步 `TESTING.md`。
- [ ] `SOP.md` 只保留动作、权威引用和验收。
- [ ] 竞争权威的旧文档已明确标记 active/concept/history，不再保存动态“当前结论”。
- [ ] 生成型 README/report 行为改在 generator 或稳定 post-processor，不只手改生成文件。

## 6. 测试与验证证据

对每条实际执行命令，PR body 记录：原样命令、PASS/FAIL/SKIP/受限结果、证据路径、未运行项及原因。

- [ ] 已按 `TESTING.md` 选择最小且充分层级，没有用 unittest 替代 Golden、repair gate、snapshot checker 或完整场景。
- [ ] 涉及 source/artifact/terminal publication 时运行 `tests/test_validation_provenance.py`。
- [ ] 涉及 capability contract 或 Markdown anchor 时运行 alignment checker。
- [ ] light 的 skipped、NOT_EVALUATED 和 `LIGHT_PACKAGE_NO_GIT` 没有写成 full validation。
- [ ] 会覆盖 `evidence/`、`outputs/`、README 或报告的命令在干净隔离 checkout 中执行。
- [ ] 若运行 stage 11，随后按适用范围单独运行 stage 12。
- [ ] 若 stage 12 返回零，随后运行 `python3 tools/check_validation_snapshot.py`；未运行时不能声称当前 checkout 已完成 full validation。
- [ ] source closure 变更覆盖 clean、dirty、untracked、equivalent-commit 和 tree mismatch。
- [ ] artifact closure 变更覆盖 missing、unexpected、size/hash tamper。
- [ ] 失败未通过改 expected、删除负例、放宽断言、重签旧 artifact 或静默跳过掩盖。

## 7. 用户、数据与 provenance 影响

- [ ] 用户可见入口、status、退出码、manifest/provenance/report 关系已对照 `interact.md`。
- [ ] 指标口径变化已对照指标定义，并核对 evidence 与 Golden。
- [ ] SEC 请求仍统一经过 `SecHttpClient`；request-log manifest 的 key/type/row schema/count/hash 完整。
- [ ] 公司/CIK/profile 扩展没有引入生产 identity branch。
- [ ] 没有把历史绝对路径当跨机器权威地址。
- [ ] 新一轮 stage 11/12 会使旧 provenance 失效，不会留下新报告 + 旧 success proof。
- [ ] full success 绑定 clean source-input tree 和关键 artifact SHA-256/size；commit SHA 变化只在完整 source tree 等价时允许 warning。

## 8. 发布声明约束

当前仓库没有 CI workflow、生产部署或自动调度。除非本 PR 实际增加并验证这些能力，PR body 必须写“不适用/未实现”。流水线 GO、snapshot provenance 和 checker PASS 都不等于外部审计接受或生产发布许可。

## 9. 创建 PR

发布能力可用且已认证时，推送 feature branch 并创建 draft PR。CLI 示例：

```bash
gh pr create --draft --title "<标题>" --body-file PR_BODY.md --head <feature-branch> --base main
```

连接器创建时同样使用真实 repository、head branch、base branch 和 draft 状态。成功后返回真实 PR URL。

## 10. 最终核对

- [ ] Review / 修复记录包含每轮发现、判断、处理与证据。
- [ ] 同类返工记录原验收缺口、当前不变量、反例矩阵和原样命令。
- [ ] 已知限制、未运行测试、回滚方式与当前 patch 一致。
- [ ] PR body 没有未来计划冒充完成事实。
- [ ] `PR_BODY.md` 未进入 diff。
- [ ] branch、base、commit、push 与 PR URL 来自实时结果。
