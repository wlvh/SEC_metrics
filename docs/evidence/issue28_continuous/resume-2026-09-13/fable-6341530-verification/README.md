# Fable 5.1 独立核验记录：PR43 受审提交 6341530c67b5a0aa0ded858a2a60bddc56ee6a12

日期：2026-09-13。来源：用户在 Claude Code 会话中转交。本记录不是 GitHub review，不构成全 PR 批准或生产许可。

## 核验范围
- scripts/vnext/ordinary_update_cycle.py 的 _intent / _terminal / _recover / run_once / run_company，及 tests/vnext/test_ordinary_update_cycle.py。
- CI 运行 34735535954 原日志（ci/）：检出合并提交 9ce88221427e362f461c7625e1df2539d28bccef，其树哈希 98d5c0b47e1969b3d0a73c66df14fc8d58685e2a 与 6341530 相同；
  更新历史方法 935.322s OK；按指标隔离方法 1059.498s OK；十个作业全部 SUCCESS。
- requirements/issue_28_v13 闭包由仓库加载器重算：sha256:e1ac4b08b4b31aa5d7a411ac76b8d29c33075e82da3fe5f939009566194dc1f4，351 个执行文件。
- config/issue28_normal_results_v2.json：36 条 metric_ids，pending B13/D03/D04，provider/sec_fetch/production/freeze 全部 false。

## 本地结果
- local_update_cycle.log：OrdinaryUpdateCycleTest 397.086s OK；material/summary.json 12 项检查；material/metadata-rejections/ 10 项记录反例输入。
- local_fast_suite.log：tools/run_fast_tests_v2.py --jobs 2，97 项 PASSED，80.648s。
- probe_results.json / probe_branch_and_cycle.py：五项 Codex 未测的变造全部被拒绝，恢复后 NO_SOURCE_CONTENT_CHANGE 且无新 Run。

## 副作用
- 本地运行向仓库 .git/ordinary-source-authority/recorded/ 写入 3 条 RECORDED_TEST_ONLY 登记（合计 23 条）；工作树未变。保留其测试身份，不清理，不升级为真实获取证据。
- 本地材料根目录位于会话 scratchpad，不属于仓库。

## 另行发现（非 PR43 回归）
- main 提交 b284a30 改变了 config/provider_model_runtime.json，legacy invocation_control.effective_invocation_policy() 加载 issue_15_v1 时抛出 "Issue #15 runtime authority bytes differ"；只有自带绑定的后继版本（issue_28_v8 模式）可用。
- 生效 D-36：repository_monetary_budget_enforcement=DISABLED，支出权限为外部 API 账户余额，禁止仓库侧金额上限字段。
