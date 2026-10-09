# d99fe489 限定独立复核

**结论：NEEDS_FIX（一个旧 C04 单指标续接的输入兼容回退）。** 本次只审 `d99fe4896d46eaa6e3c38f54d151ee2d1b9ecb84` 相对 `73c053a4` 的指定差异，承接 `c04-mixed-auto-refresh-20260927/independent-review/conclusion.md` 原有 `NEEDS_FIX`，没有重审整条 PR。前轮指出的混合模式每轮重复 submissions URL 已在默认零模型请求路径修复；下面的回退不否定这项修复。

## 需修复：旧 C04-only 续接误受混合模式的零模型预算限制

`scripts/vnext/ordinary_refresh_cycle.py:242-245` 将新条件 `max_provider_requests == 0` 同时施加于 `c04_only` 和 `mixed_stale`。父提交的 C04-only 续接只要求单公司、`max_sec_requests=1`，允许 `max_provider_requests=1`；CLI 也公开这个有限预算参数。C04-only 的 `requested` 只有 C04，而模型准备循环只处理 B13/D04，所以该参数在这个路径不会发模型请求。现在同一合法调用在读取报告、接触账本或发请求之前直接抛出 `ORDINARY_REFRESH_RESUME_C04_ONE_REQUEST_REQUIRED`。`short-compatibility.log` 用最小预检复现，父提交条件和当前条件已逐行核对。默认值 0 的旧 C04-only 测试仍通过，但没有覆盖这个已接受输入。建议只把零模型预算限制放在混合续接分支，保留旧 C04-only 条件，并加一条短回归测试。

## 已核实的修复与边界

- 混合旧处理根的来源选择先取当前 C04 原生证明，再要求发现角色属于 C04 元数据、年报或事件正文/头文件；仅有宽泛证明但角色为 `proxy_primary` 的 URL 被排除。`short-role-scope.log` 是我在确切提交上重跑的短测试。当前代码还在前次报告/SEC 计划、收据、终态、账本末槽、C04 持久尝试和重建待办之间核对；指标集合必须一致，其他已支持指标仍为 `UPDATE_BLOCKED`，未接线指标须为 `UPDATE_NOT_IMPLEMENTED`。这些检查均在下一次 `capture` 前执行。
- 已保存的 `mixed-two-step.log` 与测试源码一起证明禁网录制两轮各一条：submissions 后为 Company Facts，录制账本两槽、真实新增调用 0/0/0；C04 为可读候选/内容未变，B01 保持阻断，总报告 `UPDATES_INCOMPLETE`。`c04-only-resume-current.log` 的原单指标续接、两种报告篡改及重复报告拒绝通过。两项长材料分别耗时 365.477 秒、330.682 秒；本审核按委托只读取日志，没有重跑。新混合报告的指标集合与未接线指标状态由代码检查，未另做完整材料级篡改演练。
- 我独立加载 V14 Requirement 并重验执行绑定与三份当前 provider/SEC/refresh 接线收据的证据哈希：closure `sha256:93b6b5d6e320e606789d62df0e73a825728100e800a72d68304966e45036fcbb`，execution `sha256:3507e50c656e12bd3a6a42e943de76a194eebd4caf6097a1b1148580337c8b57`，本模块 `ac07d189748f3e30f91b6cd965ae06d9929772f80adcaae8e96cc7260df01575`，见 `short-identity.log`。两份长日志与 `summary.json`、三份收据中的哈希一致。提交前工作树的录制通过不等于当前 head 的远端 CI 终态，也不产生真实新财年或生产信用。

本审核没有发真实 provider/paid/SEC 请求，实际新增 **0/0/0**；没有更改原账本、父任务未提交的 `execution-state.json`、#47/PR52、生产状态或历史失败。只写了本目录的这份结论和三份短日志。工具调用共 **18 次 `functions.exec` 编排、40 次其内工具调用**（含写入与末次只读核对），低于约定上限。
