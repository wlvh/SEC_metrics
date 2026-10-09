# 限定独立复核结论

Verdict: CHANGES_REQUESTED（仅本次指定差异范围；三项 P2）。

受审 base：`6e51f416b12d2e284be1662482ca7a46a37d1e43`。受审 patch / 实际 HEAD：`ebaf9a3631785c6a9b8bb58e8b394b454c7b46d7`。已独立比较 tested-tree.json 中的 14 项源码、配置、测试与 workflow SHA-256，全部相同；结束时 tracked diff 为空。

## 发现

1. **[P2] 在拒绝 replay-only 输入前读取新配置，破坏已有稳定拒绝行为。** `scripts/vnext/continuous_semantic_calls.py:910` 在原 `CONTINUOUS_REPLAY_OBJECT_CANNOT_EXECUTE` 检查之前读取 `prepared.requirement`。现有非执行输入 `SimpleNamespace(request_bytes=b'{}', replay_only=True)` 因此抛出 AttributeError，不能返回原预期拒绝原因。`tests/vnext/test_registered_native_update.py:115` 的实际本地复跑为 1 test / 0.018s / 1 error / 0 skips / exit 1；父任务提供的本地 CI 解码日志也有相同栈。这是本补丁引入的检查顺序回归，不是退休祖先权限字节或反作弊要求。修复时应保留 replay-only 的早期拒绝，同时保证 current live + recorded HTTP 的组合仍在 claim 之前被拒绝；不要删除该测试或改成接受 AttributeError。证据：[replay-only-regression.log](replay-only-regression.log)。

2. **[P2] 原生请求变体选择丢失新对象携带的 limits。** `scripts/vnext/continuous_semantic_calls.py:550-566` 的 `select_native_request_variants` 使用默认配置重建 policy / provider body，没有传入 `prepared.limits`。使用仓库现有 `synthetic_source()`，真实配置、真实 SemanticRequest 和真实变体选择函数，在全新临时 recorded ledger 中准备三组 output_tokens=8192 / max_payload_bytes=4 MiB 的请求；选择 INDEXED_UNITS_V1 后，三个对象仍保存 limits.output_tokens=8192，三个实际 wire.max_tokens 都变成 4096，均不等于按对象 limits 重建的应发 body。CLI 同时公开 `--indexed-unit-responses` 与 `--output-tokens`，因此会产出互相冲突的对象，后续真实对象检查/prepare 无法成立。应在变体构造及已成功版本重读分支中一致保留每个 prepared 的 limits；普通配置下 transport 的资源配置也应取该对象值。反例只构造/选择请求，无 claim、HTTP、Candidate/Result 或业务信用；未使用真实预算根。证据：[mode-and-variant.log](mode-and-variant.log)。

3. **[P2] 新普通配置模块重复 provider host 字面量，现有网络出口扫描不能通过。** `scripts/vnext/current_request_configuration.py:57` 重写 `api.deepseek.com`，被现有 `tools/check_provider_egress.py` 的 host-only-in-adapter 检查拒绝。父任务提供的实际 CI 日志在 34 项旧兼容/来源 audit 测试及 Main source-aware scalability audit 通过后报相同错误；独立运行现有 gate 也为 exit 1 / `provider host literal escaped ai_adapter.py`。这不是要求恢复祖先权限链，而是新模块没有复用现有单一 HTTP 边界常量。应引用现有 `ai_adapter._DEEPSEEK_ENDPOINT_HOST`，保留 gate 与原预期。证据：[provider-egress-gate.log](provider-egress-gate.log)。

## 已核对的有效边界

- current configuration 只加载普通配置及实际消费的原 allowance 字段，当前 WB-3 context 的 files 为空；配置变化影响诊断身份，没有创建 Requirement 或新调用机会。原路径的分支仍保留历史解释，未要求重建已退休的祖先权限链。
- 真实请求对象、body、context measurement、plan、usage check 使用 RequestLimits；默认 body 与原 context identity 保持；8192 能到当前实际 transport 的录制 HTTP。live_scope 继续禁止 D03 及非默认 live limits。发现 2 限定在额外变体选择链。
- 原 CallLedger 的 append claim、原 initialization anchor、三项累计计数、33 组机会判断、旧失败/UNKNOWN、重开与重复请求检查继续使用。新 live_ledger 仅重开既有 binding，不初始化真实根或重新安装消费过的恢复机会。
- 当前 recorded 请求在没有显式 recorded_provider_http 时于 claim 前拒绝；当前 live 请求在该 HTTP scope 内也于 claim 前拒绝。录制 scope 使用固定非业务 credential，不落回网络。
- written terminal reconciliation 从已有 journal/marker/execution/plan 封存，不发送新请求；unknown intent 仍计数并停止。普通 saved read 无模型重放；current native replay 配置不同时要求保存版本；历史分支保留旧 runtime 解释。

以上是代码及明确测试范围的判断，不是全模块、全部 legacy 入口、PR、真实模型业务结果或生产许可的批准。原真实账本的数量和 hash 只从开发者既存证据读取，复核没有重新获取真实账本来独立重算。

## 复核证据与未覆盖项

独立短套件：CurrentConfigurationTest + test_continuous_call_ledger + test_request_limits + InvocationControlTest，**42 tests / 6.436s / 0 errors / 0 failures / 0 skips**；使用指定 Python 环境及 required_unittests runner，并在进程内阻断 socket connect / connect_ex / create_connection。见 [short-tests.log](short-tests.log)。

独立重跑两项指定 HTTP 模式反例：**2 tests / 6.813s / 0 errors / 0 failures / 0 skips**。同一日志另保存上述三组变体 limits 反例。

known replay-only 回归：**1 test / 0.018s / 1 error / 0 skips**。既存 55-test / 88.910s 总链、native-current-request 35.409s 与 native-current-replay 41.292s 直接读日志，没有重跑长原件/55整链/native 全链；这些日志属于开发者保存证据，不伪称独立跑过。

未执行任何真实 HTTP（含 GitHub/SEC/provider/paid）、账户或秘密查询；未修改源码、tests、其他状态、真实或 peer ledger / source；未 commit、push、打包、spawn 或触碰 #47。唯一持久写入是本目录的 conclusion.md 与四个日志；测试使用临时隔离目录并清理。

复核起始 UTC：2026-10-09 15:38:14 UTC。
复核结束 UTC：2026-10-09 15:47:34 UTC。
工具调用总数：49（含 18 次 functions.exec 包装、30 次子工具、1 次父任务消息工具；无超限）。
普通消息总数：3（开工说明、一次父任务发现通知、最终报告；没有问题或例行更新）。
