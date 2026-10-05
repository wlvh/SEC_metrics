# 原VAR入口材料分类增量独立审阅

本次新增差异通过，未发现阻断问题。候选只把已在原119个入口中的完整VAR测试移入材料层；现在为94项短测试、25项材料测试，完整119集合及原断言保留。结论 **PASS_FOR_ORIGINAL_VAR_CLASSIFICATION_INCREMENT_ONLY_NOT_FULL_ACCEPTANCE**，仅覆盖这一分类补齐及两条成员断言。

- 精确候选 `bee3b0fef6390553e980d4f5f208e3677106472a`；增量基线 `8f6640bcdfddbbaa5fca42619f1bbb69ec7a50b9`；工作树 `/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics`。
- 范围：`tools/run_foundation_ci.py:19`–`:20` 额外接受 `s == v2.REPLACED`；`tests/test_foundation_ci.py:26`、`:27` 分别断言原完整入口在材料层、不在短测试层。两项当前文件字节均与指定Git对象一致。
- 继承8f的分层、旧runner/失败传播/工作流限定审阅，不重复审整个CI、main源码或业务实现。原8f报告、verdict、30次计数均保持原义；本次终态追加在同一任务的increments中。

独立确认新adapter去掉新增的这一条件后，与8f版本完全相同，`main()`的AST也相同，因此分发函数、30/240秒单项执行限制、并发、失败码处理均没有随此补丁改变。额外条件使用既有v2.REPLACED明确指向的原完整测试：

```text
tests.vnext.test_financial_balance_scope.FinancialBalanceScopeTest.test_var_reported_estimate_is_distinct_from_an_illustrative_table
```

它没有借用v2的替代测试集合。独立核对新旧集合，唯一变化正是这一个入口从短测试移到材料测试；没有增加、删除、重命名或重复任何入口，119项并集和各层互斥性继续成立。原VAR入口恰好出现一次，仍运行原整表测试及其原断言。它通过既有材料worker使用240秒；源码没有修改worker或新增timeout override。

本审阅者只执行以下获准命令，三项均退出0：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_foundation_ci -v
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_foundation_ci.py --suite fast --list
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_foundation_ci.py --suite source-material --list
```

**3项结构测试通过，unittest耗时0.001秒，完整进程0.053329秒**；列表分别为94/25项，进程耗时0.038067/0.037140秒。指定列表的完整输出与静态单入口差异证明在 `independent-foundation-ci-var-increment.log`。未实际运行VAR、119项或父执行者的材料验证。

父输入所述3dbe远端24材料成功、短测试只剩原VAR的30秒/124，是本次有界修补的背景；此次没有HTTP调用，未重新认证远端结果。该背景和父实际VAR材料worker验证不计作本审阅者新执行。此独审确认分类和合同保留，不替实际最终head的CI终态判绿，也不扩成main验收、合并或生产许可。

登记增量开始 `2026-10-04T15:55:07.025049+00:00`，结束 `2026-10-04T15:58:15.956015+00:00`；本次 **188.931秒**。工具增量含写入及随后回读 **10次**（4次functions.exec、6次exec_command），累计 **40次**（11次functions.exec、28次exec_command、1次clock）；普通消息本次仅最终1条、累计3条，问题0条。累计实际审阅段耗时 **462.728秒**，从原首次读取到本次结束墙钟 **1135.956秒**，均未触及80工具/90分钟限制。

只写本增量报告、同名日志及原登记中本SHA的increment终态。原8f报告/verdict未覆盖；没有代码/快照/其他root修改、commit/push、spawn、HTTP/SEC/model调用或后台任务操作。最终回读在随后数秒完成。
