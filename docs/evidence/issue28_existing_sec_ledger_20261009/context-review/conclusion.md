# 历史 context 字段选择接缝：限定独审结论

通过本次限定独审；指定差异内未发现需要阻断的 P1/P2 问题。历史 context 仅提供 `requirement_id` 时可以沿原 allowance 形式申领；连续入口仍要求 `requirement_id` 与 `requirement_closure_hash` 两字段。本结论只覆盖以下字段接缝与小录制验证。

- Base：`20398f3e1b7d07b6de36b8a57bfef86c9162b92e`。
- Reviewed patch / 实读 HEAD：`dad13e7779327c6a8dc4a169c77eee5eee61ceb4`。
- 工作区：`/Users/lyuhongwang/.codex/worktrees/issue28-sec-ledger/SEC_metrics`。
- 代码范围：`scripts/vnext/company_online.py` 的 requirement 字段选择和 `tests/vnext/test_historical_sec_capture_adapter.py` 的新增缺 closure 回归。
- 复用原审：`../independent-review/conclusion.md`，原审 patch 为 `17002f37358042e4c6f43b1d5d866f26dae35b55`。没有重新展开原 adapter 全部审阅，也不把原审结论扩成对当前 base 全树的确认。
- 开始：2026-10-09 11:45:42 UTC。
- 完成：2026-10-09 11:51:04 UTC（最终输出检查）。
- 实际工具计数：33（9 次 `functions.exec` 包装、24 次嵌套工具；Python 内的子进程不另计为工具）。
- 普通消息计数：3（初始说明、一次进度、最终报告）；问题 0；没有另发协作消息。

## 判断及原因

1. `_ledger()` 仍以 binding 的 `ISSUE_47_HISTORICAL_CALL_ALLOWANCE` 显式选择历史 adapter；该 adapter 具有 `check_request`，现有 continuous `CallLedger` 没有该方法。此次字段选择复用已有 Capture 的分支条件，没有新增 allowance 或改变分派。
2. 固定本地 Git 对象 `0918862a` 中的 `historical_sec_session.py` 原 binding、claim intent、SEC plan 与 receipt 保存 `requirement_id`，不保存 closure。当前 adapter 的 `_check_purpose()` 与 `claim()` 核对 context、requirement 和原 binding 的同一 id。此次历史分支只取该字段，与旧形式契合；没有用默认值、合成 hash 或改写 binding 补齐不存在的 closure。
3. continuous 分支仍从 context 读取两个原字段，`CallLedger.claim()` 仍将二者写入连续 intent。独立正例验证传入 claim 的对象恰好含两字段，落盘值与 context 一致。缺 closure 反例仍在 claim/HTTP 之前以 `KeyError('requirement_closure_hash')` 终止，计数保持 `[0,0,0]`。
4. 差异只替换进入锁前的字段收集；request digest、ledger lock、claim、pending、sec-plan 保存、fetch、receipt 和 terminal 顺序未变。两个 ledger 路径的独立录制探查均观察到 `claim → sec-plan → transport`；历史计数从 `[0,0,3]` 增至 `[0,0,4]`，连续计数从 `[0,0,0]` 增至 `[0,0,1]`，两者 binding 字节保持。
5. 新回归实际删除 fixture context 中的 closure 后进入捕获，检查 transport 一次、binding 不变、intent 只有原 requirement id 和原计数；它能覆盖此前 fixture 虽有伪测试 closure、真实旧 context 却无该字段的接缝。独立补查从精确 base Git 对象提取原 `Capture.get`，仅在内存替换该方法，重现原 `KeyError`，且未申领、未 transport、计数保持 `[0,0,3]`。

## 本次实跑

在 macOS `sandbox-exec` 的 `(deny network*)` 下、`PYTHONDONTWRITEBYTECODE=1`，对指定命令不提供 PYTHONPATH：

```text
python3 tests/required_unittests.py tests.vnext.test_historical_sec_capture_adapter tests.vnext.test_company_online
```

17 项测试，0 failures、0 errors、0 skips，unittest 报告 6.076 秒；包装进程墙钟 6.322328 秒，exit 0。包括新增缺 closure 回归与原 continuous/count/interruption/UNKNOWN/recorded-no-network 回归。未运行全仓或长材料测试。

另在同样禁止网络的单独进程运行四项有界补查，全部通过，包装进程墙钟 2.075049 秒：continuous 双字段正例及顺序、continuous 缺 closure 零 claim/零 transport、historical 无 closure 只传 id及顺序、精确 base 缺字段失败复现。探查完整源码、命令、stdout/stderr 与 UTC 均保存于 `review.log`；没有修改产品代码或测试源码。

## 限制与未覆盖

本审只处理 `20398f3e… → dad13e77…` 两个指定文件的实际增量。该 patch 另有 README 与作者前后日志变化，不纳入本审结论。固定原历史实现仅从本地 Git 对象读取；没有访问 #47 工作树、真实账本或运行根，没有对其取锁、写入或申领。

真实 SEC/provider 调用为 0/0；测试进程禁止网络。按仓库开工指令读取了一次实时 GitHub Issue #28，是只读工程上下文查询，不是额度或来源请求。未复核真实预算余额、历史授权来源真实性、实际来源根预检、完整历史 loader、业务结果、GitHub CI、生产采纳或部署。本结论不授真实调用、合并、正式采纳、发布或 active 切换权限。
