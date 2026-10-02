# 865d8220 D01 跨页边界增量独审

结论：**PASS_LIMITED**，仅针对 `865d82205d6b0fa37b11ad15e7000122016c6c8a` 的修后差异。首审 `1457e99a` 的 `NEEDS_FIX` 历史结论保留；其两项新跨页规则问题在本补丁所声明的范围内关闭。此结论不授予 D01 对任意分页版式的完整支持、当前 390 坐标或生产采纳信用。

**误合并已消除。** 新源码不再拼合两个块，也不再制造覆盖页码和目录行的单个 `raw_start_byte`–`raw_end_byte`。把首审的“两个加粗标题中间只有数字 `1`”反例送到正式 `create_deterministic_text_candidate` 后，得到两条独立候选 `Regulatory Risks`、`other market risks`；二者各自原始字节片段分别恰为标题文字，哈希与片段一致，Evidence 为 `PASS`，无页码混入。这关闭首审的错误合并和由合并造成的“展示文字并非单跨度逐字摘录”问题。修法是收回跨页合并能力，而不是证明一般跨页标题已能正确抽取。

**已知跨页形式在 Candidate 前拒绝。** 对“加粗前半句 → 页码 `42` → 带链接的 `Table of Contents` → 小写起始的加粗续句”的完整年报夹具，直接调用正式候选入口得到 `TextCoverageError: D01_MULTISPAN_HEADING_UNSUPPORTED`，没有产生 Candidate。源码从 `create_deterministic_text_candidate` 经 `prepare_text_sources` 调用该检查；正常更新在运行失败时保留失败终态，不会将这次输入标为成功结果。检测器只识别这一已证明的四块结构；其他分页形式尚无同等拒绝保证，不能把本次有界拒绝当作 D01 对未来新财报的完整自动更新验收。此限制属于尚未实现的来源表示能力，不能记作公司披露不足。

**现行来源与绑定保持。** 我在禁网条件下只读重建十家当前保存年报的 D01 显式候选，十个候选哈希和标题数均与修前 `measure-current.json` 及修后 `current-ten.json` 一致；来源请求日志哈希前后不变。这沿用首审已核对的 Marriott/Paramount 内容结论，没有重审其全部原件。V13、V14 快照分别只读通过 `validate_execution_authority`；V14 另通过语义绑定和三份接线收据验证，闭包分别为 `sha256:306300d4…`、`sha256:3112b476…`。修后受绑定执行文件的哈希为 `4916849e…`；本提交未改 V12 冻结目录、冻结文本解析器或旧 Run 路由。提交者的 fast 记录显示 145/145 通过；本次未重跑 fast。

我还只读核对提交者保存的 Paramount 私有普通更新原生文件：成功终态 `CANDIDATE_READY`、重复输入 `NO_SOURCE_CONTENT_CHANGE`，Run 的 V13 闭包和候选哈希与证据文件一致，Evidence `PASS`，38 条标题，Result ID `sha256:6795449b…`，两次终态的真实调用计数均为 0/0/0。提交者另有异进程冷读同一 Result ID 的记录；本次未重跑私有 Run 或冷读。此为新绑定的私有可读性证据，不是正式 390 汇入或生产授权。

本次亲自运行指定 `tests.vnext.test_d01_emphasis_successor`：**5/5 OK**。另亲自运行上述两个正式候选反例、单跨度原件哈希/Evidence 检查、十家只读哈希对照、V13/V14 与三份接线验证、私有产物只读核对；结果转录见 `unittest.log` 与 `boundary-and-binding.log`。未发真实业务请求，未操作 #47/PR52，未 commit/push，未修改首审结论或当前执行状态。`tool_calls=18`（直接工具调用），`message_count=1`（最终报告，无进度消息）。
