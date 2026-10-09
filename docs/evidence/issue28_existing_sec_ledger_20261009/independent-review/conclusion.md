# 指定补丁限定独审结论

结论：在本次指定范围及受信任内部工具前提下，通过限定独审；未发现需要阻断该补丁的 P1/P2 问题。此结论仅覆盖代码与小型录制数据上的行为，不授予真实调用、合并、正式采纳、发布或 active 切换权限。

- Base：`73ead3b4c987ab10e7eaef3feed9bd5cec43e136`
- Reviewed patch / HEAD：`17002f37358042e4c6f43b1d5d866f26dae35b55`
- Worktree：`/Users/lyuhongwang/.codex/worktrees/issue28-sec-ledger/SEC_metrics`
- 固定历史实现参考：仅只读本地 Git 对象 `0918862a` 中的历史 SEC ledger/session/extension/resume 代码；未打开或操作 #47 工作树、账本或运行根。
- 范围：`existing_historical_sec_state.py`、`company_online.py` 的历史显式分派与窄 capture 差异、两个新增测试模块、company-current-records workflow、run_fast_tests_v2 selector。
- 开始：2026-10-09 11:13:37 UTC（北京时间 19:13:37）。
- 完成：2026-10-09 11:21:47 UTC。
- 工具计数：44（包括 functions 包装调用及其嵌套工具；不把 Python 子进程另计为工具）。
- 普通消息计数：3（初始说明、一次进度、最终报告；问题 0；无另行协作消息）。

## 本次独立实跑

1. 在 macOS `sandbox-exec` 的 `(deny network*)` 下运行指定命令，设置 `PYTHONDONTWRITEBYTECODE=1`：

   ```text
   PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_existing_historical_sec_state tests.vnext.test_historical_sec_capture_adapter tests.vnext.test_company_online
   ```

   21 测试，0 failures、0 errors、0 skips，5.086 秒。日志：`required-small-tests.log`。

2. 再按新增 workflow 的原样 Python 命令验证，不设置 PYTHONPATH（显式 `env -u PYTHONPATH`），确认它不依赖前一测试进程的导入状态。21 测试，0 failures、0 errors、0 skips，5.065 秒。日志：`workflow-exact-command.log`。`tests/__init__.py` 的现有导入路径处理使该入口正常运行。

3. 仅调用 fast selector 的两个新增条目的实际子进程执行器；没有运行全 fast suite 或 source-material suite。两模块分别运行 5 和 6 测试，均返回 0。日志：`supplemental-probes.log`。

4. 在同样的小型录制 fixture 上独立补查五项行为，全部通过：
   - 两条恢复记录的保守 reserve 逐条累计；扩展额度与原 binding 限额保持分离。
   - 原已归属槽之前的导入 403 前缀不阻止已限定用途，但一次新增 429 仍计数并持久阻断后续 capture。
   - 响应已保存、receipt 保存中断后仍消费一次机会，留下 pending/INCOMPLETE_ATTEMPT，无法重抽。
   - adapter 构造后用途 URL 改变时，在 HTTP transport 之前拒绝。
   - 两个 adapter 实例竞争同一原目录锁：仅一方取得新 claim，另一方以 UNRESOLVED_ATTEMPT 拒绝；原 claim 字节仍为前缀，总计只增一次。

上述共有 21 个指定测试、五项新增探查；计重复运行为 58 次测试/探查执行。补查脚本首次因导入 tools CLI 模块缺少 tools 目录而在 setup 阶段中止，尚未执行探查；调整审阅脚本的导入路径后通过。初始错误保留在同一日志，不是产品代码失败。未修改实现或测试文件。

## 代码与证据判断

- 原 binding 未被改写。原 claims 和外部 mirror 一致后才追加；新 ordinal 取原 claim_count + 1，上一 intent_id 延续。新 intent 与 terminal 字段形式同固定历史实现；锁仍取得同一稳定目录。
- 有效扩展按已持有 claims 前缀核对后增加 SEC 限额；每条 lost_segment.reserve_sec_calls 纳入累计使用数。窄用途 counts_before/maximum_counts 同上下文一致，新 claim 必须恰好处于 counts_before，无法借用总余额继续第二次。
- 只在历史 record_type 显式匹配时启用 adapter，原 continuous CallLedger 路径保持；指定的十个原 company_online 测试仍通过。
- Capture 对历史用途要求原 source-inputs 与 registry、单个已登记 URL、refresh=False；HTTP config 强制 max_retries=0。其他 URL、其他源根、refresh 或抬高上下文 cap 均在 transport 前拒绝。
- UNKNOWN、新 403/429、计划中断、receipt 中断不会减少已消费的机会。未归属的新增日志尾部拒绝。新增成功记录携带真实录制 persistence 的 immutable body/header、wire、proof 和逐字节日志前后绑定。
- 现有 `validate_acquisition_checkpoint` 对新增成功录制 capture 的实际读取验证已由指定测试执行，并返回一个 admitted source；其信用为 RECORDED_TEST_ONLY。固定历史 ledger 的源码形式另外作了对照；没有运行其完整 live 入口或完整旧运行材料。

## 限制与未覆盖

作者 README、actual-bounded-preflight.json、final-stop-and-prefix-tests.log 已读取，始终作为作者证据。1547 claims、保守 reserve 224、累计 1771、总限额 1867、单 URL 上限 1772 等真实状态不是本审阅人独立重算的结果，不能由本结论升级为独立实账验证。

没有对真实根取锁、写文件、申领或构造真实 transport；没有任何网络访问、SEC/provider 调用、账户操作、commit/push。没有读取实时 Issue 或重复验证历史批准来源，现有授权是否仍有效由接收者按当前任务边界核对。本次没有重建批准防伪或递归 Requirement。

未跑长材料测试、实际数据根 receiving-consumer preflight、GitHub CI、完整旧历史 loader 执行、业务结果验收或生产采纳。后续若需真实用途执行，仍须先完成接收方正常入口与实际 source-inputs 的有限预检，且只能使用原已存在的用途。

