# `d1caf720` E01 Item 8.01 来源回修限定独立审阅

**结论：PASS_LIMITED。** 相对 `80322de9bfe171245c2d37bdff43c370321ea418` 的本次增量，封住了前次独审记录的两类直接错误接受：加粗的 9.01 交叉引用与真实异标签 9.01 标题并存时，不再静默截短 Item 8.01；带行内 `opacity:0.0` 或 `color:transparent` 的正文不再作为已证实可见文字进入记录。保存的 Southwest 正例仍可从原始字节重建。前次 `NEEDS_FIX` 保留其当时结论，本审阅只认可这次精确补丁的限定回修。

受审目标为 `d1caf720ea30683490885c4dca09463a68a1eb1b`，父提交正是 `80322de9bfe171245c2d37bdff43c370321ea418`。只看 `scripts/vnext/e01_item_source.py`、`tests/vnext/test_e01_item_source.py`、`repair2-summary.md` 的增量；审阅时 HEAD 等于目标提交，三文件工作树字节与目标提交一致。工作树另有执行状态文件改动，未纳入本判断，也未触碰。

实现检查与独立输入复现相符：`_visible_801_section()` 仍按原有同标签规则选初始边界，但随后检查 **全部标签** 的结构化 9.01 候选数量。加粗 `<p>` 交叉引用之后再有真实 `<h2>` 结束标题的样例返回 `E01_ITEM_SOURCE_ITEM_801_BOUNDARY_AMBIGUOUS`，没有产出截短的成功记录；只有单一加粗 `<p>` 结束标题的正常样例仍接受并保留收购正文。样式检查把上述两种行内透明写法均返回 `E01_ITEM_SOURCE_VISIBILITY_UNPROVEN`。这属于保守拒绝，不等于判明哪段文本由浏览器最终显示。

独立重跑指定 `test_e01_item_source` **4/4 PASS**，指定绑定检查返回 `PASS_EXISTING_V14_AUTHORITY` 且 `new_module_runtime_authorized=false`。独立只读读取已保存的 Southwest `d83756d8k.htm`、既有 E01 Run 的 claim 与 SourceReference：原件哈希匹配，`bound_801_primary_section()` 与 `verify_bound_801_primary_section()` 重建相同记录，旧 claim ID 保留，正文 174 字符，不含 Item 9.01，未创建指标结果。另读取执行方 `repair2-fast.log`，其记录为 `FAST_LOCAL_ONLY`、142/142 selector 通过；本审阅未重跑 fast。`repair2-summary.md` 对本轮父执行证据和非生产边界的描述在这些检查范围内成立。

没有开展通用 HTML/CSS 渲染规则审计、跨 8-K 布局召回、E01 业务定义、当前公司 Result/Run、真实来源获取、生产资格、完整 PR 或 Issue #28 总体验收。新组件仍未接入当前 V14 运行权威；本结论不授 E01 内容判断信用，也不改变历史 E01 数值。没有真实 provider/SEC 调用、#47/PR52 操作、commit、push 或发布。命令和观察值见 `review.log`。

审阅工具计数：外层 `functions.exec` 8 次，内层工具调用 25 次；普通进度消息 3 条，无提问。计数截至本证据写入。
