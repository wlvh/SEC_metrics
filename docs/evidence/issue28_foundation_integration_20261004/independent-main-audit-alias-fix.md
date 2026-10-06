# main 审计悬空链接修补增量独立审阅

结论：本次限定修补通过，原报告 P2_MAIN_SELECTOR_DANGLING_ALIAS_FALLBACK 在此精确候选中已关闭；没有发现新的阻断问题。结论仅覆盖新增存在性判断、其两项指定反例与相应当前绑定同步，不构成整个 PR、业务验收、GitHub CI、合并或生产批准。

## 身份、范围与计数

- 精确候选：`9a51b24b95373ad4f41076e01fab55a591b193fd`；增量基线：`d1648880e7518f019f734a00e0a3444dab45a9bc`。
- 工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics`。五项被审源码/测试/绑定文件的当前字节均与候选 Git 对象匹配，HEAD 一致。
- 先读取 `independent-main-audit-increment.md`，继承其中未变范围的结论与未覆盖边界，只复核先前尚未覆盖的最小修补。
- 本次审阅路径：`scripts/vnext/publication.py` 的 exists/is_symlink 判断；`tests/vnext/test_main_scalability_audit.py` 的新增悬空反例及指定原有部分/别名反例；V13 baseline、V14 baseline 和 V14 transfer 的本次绑定差异。
- 保守工具计数 **20次**：8次 functions.exec、11次内部 exec_command、1次内部 clock；包括本次写入和随后最终回读。普通消息 **2条**：开工说明和最终报告；问题0条。登记开始 `2026-10-04T12:46:02.343323+00:00`，结束 `2026-10-04T12:50:33.322805+00:00`，写入时耗时 **271秒**；最终回读在随后数秒内完成。
- 仅写本报告、同名日志和 execution-state.json 本子任务终态。没有源码/快照改写、commit/push、spawn、HTTP/SEC/model 请求、其他工作树写入、长测试或后台任务操作。没有重复父执行者的146受影响回归。
- 本次禁止 HTTP，因此未在线刷新 Issue。轻量记忆关键词检索无相关命中，未用旧记忆判断当前事实。

## 选择器修补为何关闭原反例

位置：`scripts/vnext/publication.py:3071`–`:3075`。悬空符号链接是“链接目录项仍存在，但目标不存在”；它的 exists() 是 False，is_symlink() 是 True。新增外层判断把两个路径的 is_symlink() 放在 exists() 前，因此任一链接都进入完整安装检查；内层原有 is_symlink() 直接抛出 PublicationError，不能继续选择旧 scanner。

双悬空、仅工具悬空且 policy 缺席、仅 policy 悬空且工具缺席都满足上述逻辑；两项完全缺席仍保持旧分支，两个普通文件存在仍选择 successor，部分普通文件安装仍由内层拒绝。此次没有改变旧 scanner、语法豁免政策或审计输出处理。

新增测试位于 `tests/vnext/test_main_scalability_audit.py:82`–`:93`。每个 subTest 都复制真实脚本/配置到临时目录，先删除两个普通文件，再按 both/tool/policy 三种情形创建指向缺席目标的真实符号链接，调用实际 `_execute_scalability_audit`，要求具体“successor installation is incomplete”错误。这覆盖此前只用 pathlib 状态模拟发现的三种遗漏形态。原有 `:73`–`:80` 继续验证工具缺席但 policy 存在，以及 policy 指向一个存在目标的有效别名。

独立执行一次指定命令：

```text
PYTHONPATH=scripts:tools PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest -v tests.vnext.test_main_scalability_audit.MainScalabilityAuditTest.test_dangling_successor_aliases_never_fall_back_to_legacy tests.vnext.test_main_scalability_audit.MainScalabilityAuditTest.test_partial_or_alias_successor_installation_fails_closed
```

结果：exit 0；**2项测试通过，0.361秒**。新增方法内部含3个 subTest；原有方法含2种安装状态。日志是本审阅者的新执行证据，未将创建者 `main-audit-alias-fix.log` 的0.389秒运行冒充独立执行。未重跑整个8项审计模块、303基础模块、历史模块或D04材料。

## 本次绑定同步

仅核对本次变化，未重跑完整 Requirement loader 或全部 execution files。结构差异确认 V13 只修改 publication.py 的 hash/size；V14 只修改相同 hash/size、V13 parent closure 和 parent baseline hash；V14 transfer 只修改 parent closure。没有借此改写规则或权限。

- 当前 publication.py：SHA256 `4dd32668e94c02f0e9ebe6f40dfaaf2914b67fa0a3cf7d1f4f92047ed2ca98f8`，276337 bytes；V13/V14 的 execution_authority.files 对应项均匹配。
- V14 parent.snapshot_files 的5个 V13 成员，全部 hash/size 与当前原件匹配；其中 baseline hash 为 `de7daf3103c112215c5f9b3aca94d26f47cb36a0f9650110cc3a3736ab57ca04`，81406 bytes。
- 按 `requirement_profile_v14.py:72`–`:81` 的五文件 hash、原 parent closure、validator hash 组成规则，并按 `canonical.py:419` 保留末尾 LF，独立重算 V13 closure 得到 `sha256:f78c9e5869b77b7646b575ce8a73f77bf7d555b843b10e41ce3c028991400663`；与 V14 baseline parent 和 transfer parent 完全一致。

第一次自写静态重算脚本漏加 canonical LF，导致脚本 assert 失败；读取实际 canonical.py 后补齐并通过。该检查脚本错误及修正写入日志，不是产品缺陷或失败验收。此次静态检查继承先前已审的未变绑定，不重复授予完整 loader 或业务信用。

最终限定结论：**PASS_FOR_DANGLING_ALIAS_FIX_ONLY_NOT_MERGE_READY**。原 P2 在本候选关闭；父执行者的146回归、main真实CI和其余交付责任仍须按各自终态证据确认。
