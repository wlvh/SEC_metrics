# 进程死亡恢复快测：复用已验证的历史测试根

`tests.vnext.test_invocation_control` 的 `test_process_death_after_egress_recovers_unknown_without_call` 在本轮固定源码下，先于双作业 fast 中达到30秒外层限时；随后在单作业 fast 和精确单测中也出现 `process.exitcode is None`。失败日志保存在相邻的 `b13-model-span-claim-ownership-20260928/fast.log`、`followup-fast.log` 和 `invocation-exact-isolated.log`，原失败不改判。该测试父进程已经通过 `setUp()` 建立并验证历史权限测试根，spawn 子进程却又调用 `historical_test_root()`，重复复制 `requirements/config/catalog/scripts/tools/docs` 等目录。单独建根计时约6.81秒（`b13-model-span-claim-ownership-20260928/invocation-historical-root-timing.log`）；叠加子进程导入及调用，10秒死亡窗口可能在模拟出站之前耗尽。它是有证据的耗时机制，而不是 D03/B13 业务断言。

测试专用 `crash_after_egress()` 现在接收父进程已经验证的同一路径，直接赋给子进程的 `_REPOSITORY_ROOT`。测试仍经现有 `execute_invocation()`、模拟传输的 `os._exit(73)`、磁盘待决与恢复入口，断言 `UNKNOWN_REMOTE_OUTCOME` 且不能再发调用；没有增大10秒、30秒或任何作业限时，没有跳过历史权限校验，也没有改生产调用控制。失败时若尚未触发模拟出站，进程退出码仍无法伪造为73。

修后精确单测 `exact-after.log` 1/1通过、总耗时9.39秒，整模块 `module-after.log` 25/25通过、总耗时16.98秒；旧精确单测总耗时23.13秒且失败。`fast-tree-before.json` 固定当前相关代码与绑定文件哈希。双作业全套 `fast.log`/`.exit` **FAILED**：135个 selector 中12个返回非零，12份错误尾部均含 `No space left on device`；包含该模块在内，不能将它记为代码断言失败或全套通过。

只读盘点显示本机数据卷当时仅余约1.3GB，历史测试临时目录已有123个；其中精确识别出**本轮测试产生且无进程使用**的三个目录（两份完整副本、一份因磁盘不足中断的副本）。`current-test-temp-cleanup.json` 保存三个路径、创建时间、大小及目录结构。首次安全前置检查因中断副本缺少后续目录而拒绝清理，未删任何文件；调整为允许该已知部分副本后，执行者的删除命令仅针对清单里的三个精确路径，空间恢复到约5.0GB。其他历史临时目录、原仓库、原账本和#47不在命令目标中；本地材料不含删除过程的独立整树审计。

恢复空间后，调用原 `tools.run_fast_tests._run_case` 仅执行本补丁影响的 `tests.vnext.test_invocation_control` selector；`fast-selector-after-cleanup.json` 记录 **25 tests / OK、return_code 0、14.712秒**，仍在原30秒限内。其余 11 个本轮磁盘不足的 selector 不因这条结果获得本地通过信用；之前未变代码的旧CI证据按原SHA保留，新提交须看远端CI。没有 provider/SEC 真实请求，也不改变 B13 V8 停用或历史调用信用。

精确 `ab765369` 的[限定独立审阅](independent-review/conclusion.md)为 **PASS_WITH_BOUNDS**：审阅者另用原快测 selector 独立运行25/25通过（8.06秒），核对测试仍要求模拟出站后退出73、磁盘待决、恢复UNKNOWN及不重发。它没有运行完整fast，也没有把12条ENOSPC失败算通过。清理方面，审阅者确认三个指定目标现已不存在、仓库和账本路径仍存在，但不能独立证明清理期间其他字节绝对未受影响；这项边界保留。
