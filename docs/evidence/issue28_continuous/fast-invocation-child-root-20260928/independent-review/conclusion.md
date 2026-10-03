# 精确提交 `ab765369b1c07ca19231ae9ce26146081a842700` 限定独立审阅

基线：`d8263295da590d5de7ed16fd241585d28fb37f22`。结论：**PASS_WITH_BOUNDS，仅适用于这次测试夹具修复**。未发现使进程死亡、待决状态恢复或禁止重发断言失效的差异；本结论不授予全 fast、生产调用或业务结果信用。

父进程的 `setUp()` 从带缓存的 `historical_test_root()` 建立测试根，并将该根绑定到 `invocation_control._REPOSITORY_ROOT`。这次差异把同一路径传给 spawn 子进程，免去子进程再次复制大型目录。子进程仍执行原 `execute_invocation()`，`ProcessCrashTransport.send()` 在检查请求身份及首次尝试后调用 `os._exit(73)`。测试要求退出码 73、磁盘上恰有一条 `PENDING_REMOTE_OUTCOME`，随后以同一执行身份恢复为 `UNKNOWN_REMOTE_OUTCOME`，断言无终态尝试且恢复传输调用数为零。因此它仍会在未到模拟出站、恢复错误或发生重发时失败。提交未改生产调用控制，`join(timeout=10)` 和 fast 的 30 秒限时均未增加。父进程的帮助函数检查了 Issue #15 历史快照；“已验证测试根”应按这一既有检查范围理解。

独立使用原 `tools.run_fast_tests._run_case(test_name="tests.vnext.test_invocation_control")` 复跑：25 项通过、返回码 0、8.06 秒，见 [selector.log](selector.log)。提交内的精确单测、整模块及清理后 selector 记录分别为 1/1、25/25、25/25 通过；本次复跑与其相符。旧精确日志确有 `73 != None`，旧 fast 两份记录分别为该 selector 返回 124 和 1，不能把旧失败抹去。

提交内全 fast 记录为 **FAILED**：135 个 selector 中 12 个非零，12 条错误尾部都有 `No space left on device`；其中一条还返回 124 并带 30 秒超时标记。因此磁盘不足有直接证据，同时不能断言每个失败只有这一种原因；其余 11 个 selector 不随本模块复跑取得通过信用。

清理清单只列出 `/private/var/folders/.../T/` 下三个具名 `historical-authority-test-*` 临时副本；独立检查确认三个路径现均不存在，源码仓库与固定账本路径仍存在，提交差异未修改生产控制文件。清单记录了目标、创建时间、大小与顶层结构，但没有可独立重放的删除命令审计或账本前后哈希；因此只能确认**现有证据支持限定目标且未发现触碰仓库/账本**，不能把“删除过程绝对未触碰任何其他字节”提升为已验证事实。当前工作树的 `execution-state.json` 有另行未提交改动，本审阅未修改它。

仍需以该提交对应的新 head CI 判断远端完整 fast；本地全 fast 的 ENOSPC 失败保持失败记录。进程 10 秒窗口仍受机器负载影响，本次实测证明当前机器上修复有效，不保证所有环境永不超时。
