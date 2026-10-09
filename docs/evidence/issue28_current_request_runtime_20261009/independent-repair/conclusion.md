# 三处回修的限定独立复核

Verdict: **PASS_LIMITED_REPAIR**。原独审的三项 P2 在本次指定增量内均已消除；本次范围内没有新增需要修复的发现。该结论只覆盖这三处回修，不重新批准整个 M1、全平台、真实业务验收或生产操作。

受审 base：`ebaf9a3631785c6a9b8bb58e8b394b454c7b46d7`。
受审 patch / 实际 HEAD：`416391c934f78672ddbd23fde23f418ac26a5f44`。

已读取本树 AGENTS.md、原 [独审结论](../independent-review/conclusion.md)、README.md 回修节和 review-repair-tested-tree.json；原 CHANGES_REQUESTED/3P2 及失败日志保留原意，没有修改。三份回修文件与保存测试清单的 SHA-256 均相同；base→patch 的非证据文件差异恰为这三份。复核结束时 tracked working-tree diff 为空，唯一新增持久文件为本目录 conclusion.md 与四个日志。见 [tree-check.log](tree-check.log)。

## 三项 P2 的处理

1. **Replay-only 的稳定拒绝顺序恢复。** `_execute_semantic` 的 `CONTINUOUS_REPLAY_OBJECT_CANNOT_EXECUTE` 检查先于新普通配置访问，因此原 `SimpleNamespace(request_bytes=b'{}', replay_only=True)` 继续返回指定 ValueError，而非 AttributeError。原 RegisteredNativeUpdateTest 中该反例独立通过。current live + recorded HTTP 的拒绝仍位于 build_plan、可能的 live 授权读取及 ledger.claim 之前；两项指定模式反例均独立通过，没有 claim 或 HTTP。没有删除断言或将原失败改名为通过。

2. **每个 prepared 的资源限制继续贯穿原生变体选择。** 新 `_prepared_transport_policy` 在 current 配置分支显式把 `prepared.limits` 交给既有 transport_policy，legacy 分支继续使用原选择函数。新变体和保存成功变体两分支都把同一对象的 limits 交给 request_body；原 111 后继分支把同一对象的 limits 交给 request_digest。已沿未改的 request_digest→request_body 和 historical_successor_allowed→group_for_request 核对：实际 provider 参数进入业务请求摘要，资源变化不会成为新增执行许可。新 CurrentVariantLimitsTest 独立通过，三组 8192 输出令牌 / 4 MiB payload 对象的实际 body 与按对象 limits 重建的 body 一致，保存变体分支也保留 8192 / 4 MiB。该测试的成功行与 replay 是明确的构造选择器状态和替代函数，只证明选择器传参；原 111 分支本次为代码/调用链检查，没有真实重放、申领或恢复原 111。

3. **Provider host 使用已有单一常量。** current_request_configuration.transport_policy 引用 `ai_adapter._DEEPSEEK_ENDPOINT_HOST`，不再新增 production host 字面量。已有 `tools/check_provider_egress.py` 独立返回 PASS；没有降低原扫描规则，也没有新增 HTTP 出口。

## 本次独立验证

所有命令在受审工作树执行。测试通过指定 Python 环境及 required_unittests runner；在导入受测模块前，于进程内阻断 socket connect、connect_ex、create_connection 与 getaddrinfo，并禁写 Python bytecode。没有真实 HTTP、GitHub、SEC、provider、paid 或 DNS。测试仅使用隔离临时目录。

- 指定短命令：CurrentVariantLimitsTest + RegisteredNativeUpdateTest + test_native_request_variants，**12 tests / 0.185s / 0 failures / 0 errors / 0 skips / exit 0**。其中包含原 replay-only 反例、旧配置/原生注册兼容及已有混合请求分区正反例。见 [short-tests.log](short-tests.log)。
- 指定两项 HTTP 模式拒绝：**2 tests / 6.610s / 0 failures / 0 errors / 0 skips / exit 0**。current live + recorded HTTP 拒绝，recorded ledger 无 recorded HTTP 拒绝，均检查无 claims.jsonl、无 HTTP bodies。见 [http-modes.log](http-modes.log)。
- 现有 provider egress gate：**PASS / exit 0**，扫描 384 个文件；gate receipt `sha256:34097ce390f239afc2c92cf707d65ccd5b6049f971aa5d2a57fd343738aefbf7`。这是既有扫描器的运行结果，不是扩大到全部 HTTP 实现的重新独审。见 [provider-egress-gate.log](provider-egress-gate.log)。

## 继承证据与未覆盖部分

旧 55 整链、native 41 秒来源/验收/replay、普通配置、账本、控制器和 HTTP 实现相对于本次 base 均未改。按本次委托复用原独审及 README 中的已有证据，**没有重新跑长材料、55 整链或 native 全链**，也不伪称这些已被本次独立重跑。三项短回归及两项拒绝检查不证明模型语义正确、公司缺失结论、指标 Result/Run、390 坐标业务验收、完整 CI、合并或正式采纳。

未读取或修改真实和 #47 的 ledger/source/state；未查询账户或秘密；未修改源码或 tests；未 commit、push、spawn、tar 或重新建立已退休祖先字节证明。没有重试旧独审、联系旧代理或重置其计数。

复核起始 UTC：2026-10-09 16:01:47 UTC。
复核结束 UTC：2026-10-09 16:06:34 UTC。
本复核工具调用总数：37（含 10 次 functions.exec 包装与 27 次子工具；与原独审的 49 次分开统计，无超限）。
本复核普通消息总数：3（开工说明、一次范围/验证进度、最终报告；无问题）。
