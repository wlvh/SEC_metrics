# c94bf076 D03 offline packet: limited follow-up review

**结论：PASS_WITH_BOUNDS。** 仅审阅 `c94bf076815df2c5bc1659b2fbe422aaa08270d2` 相对 `0af0f717333a82ab104440859564e17077020e69` 的增量；上一轮对性能修复、来源认证与请求匹配的核对不重做。上一轮 `NEEDS_FIX` 所指的“任意新包可宣称旧模块 SHA”已收窄为仅接受一个确切的历史包 ID；冷读文件的哈希与解析也改为使用同一次读取得到的字节。

## 增量核对

- `d03_recorded_response_store.py:119-131` 在核对包正文的内容哈希后，仅当旧模块 SHA **同时**配对 `sha256:4bac51a935deadda11f456ba39f6976647fe2d5cd05fe194f89fbc7ef7ce02d6` 才走旧包兼容路径。新包只把模块 SHA 换成旧值并重算 ID，若所得 ID 不是这个固定值就拒绝。旧包的 ID 和旧模块 SHA 与上一轮核对的历史记录一致。
- `expected_packet_id` 是调用者可选提供的期望值，且在重新验算包 ID 之前先比较；错值会拒绝。它必须从包之外的可信记录取得才有额外身份意义。`cold_read_old_expected.py` 把旧 ID 固定在脚本中，没有从正在读取的包取值；相应保存日志报告禁网、禁子进程冷读成功，原响应哈希及两项 unresolved 保持。本人只审脚本和日志，没有重跑旧包。
- 五个文件现各读一次进入 `raw_files`，同一份字节完成长度、SHA 与 JSON 解析（`d03_recorded_response_store.py:132-146`）。这关闭了上一轮指出的“先哈希文件、随后另开文件解析”的窗口；读取后磁盘文件即使改变，也不会改变本次返回所用的已校验内存字节。
- 测试保留未知 SHA、`LIVE` credit、原响应文件改写和缺件拒绝，并新增错期望 ID、不同包冒用旧模块 SHA 的拒绝。`repair-material-tests.log` 中首次反例失败是因为无额外差异的测试包与已登记旧包内容相同，重算后正好得到旧 ID；最终测试加了不同包标记。`repair-material-tests-final.log` 报 2 项完整材料测试通过、78.737 秒；这是保存日志，不是本人重跑。本人只运行了短核验 `test_real_ledger_root_cannot_hold_an_offline_packet`：1 项通过、0.001 秒。

## 仍需准确表述的边界

当前模块 SHA 分支继续允许一个**新**离线包以自身正文重算 ID；在未提供外部 `expected_packet_id` 时，旧包改填当前 SHA 并重算 ID 也可能作为不同的新包通过。返回的新 ID 会变，若调用者以旧包 ID 作外部期望则会拒绝。因此修复证明的是“确切旧 ID 配旧模块 SHA”及“可选外部期望一致”，而不是所有获准 SHA 间的改写都能凭包自带 ID 检出。

内容哈希证明读到的字节与指定内容身份一致，不能单独证明过去由哪个进程写入、真实 provider 曾返回这些字节，或该离线包获得原生 Result/Run、D03 业务结论和生产信用。历史脚本中的 `old_creator_module_identity_preserved` 应按“旧 SHA 与确切旧包身份保持一致”理解。新 head 远端 CI 未由本次审阅核验。

本轮使用 5 次 `functions.exec`、10 个内层工具调用；连同上一轮累计 16 次 `functions.exec`、37 个内层工具调用，均在限制内。没有重跑超过 120 秒的材料、发真实请求、改动 #47/PR52、提交、推送或修改父任务状态。
