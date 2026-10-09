# q 行内引用片段限定独审

结论：**LIMITED_REVIEW_PASSED（仅 b2d84a3 的 q 两处标签增量及新完整 API 测试）**。本次实际差异没有发现新增问题。原引用词内分组线索现在在显式 `inline-paragraphs-v2` 路线正确拒绝；旧 word / hidden 报告保持各自原范围及原结论。

## 绑定与资源

- 精确提交：`b2d84a3c4f8770698c43d9cb95fd16c030d33f24`；基线：`77e3bca3698d03ac006e7bd23abdee54e799864a`。开始与最后 HEAD 均等于精确提交。
- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-amendment-note/SEC_metrics`。
- 仅审 `amendment_note_layout.py:16` / `:44` 新增 q 为行内标签与 `test_instant_amendment_paragraph_api.py:71-80` 新测试。未全面重审原语言、来源或引用模块；只读取必要依赖执行所委托检查。
- 起止：2026-10-08 21:22:22 UTC 至 2026-10-08 21:26:14 UTC。实际工具 **13** 次（6 次 functions.exec，7 次 exec_command）；普通消息 **3** 条（初始说明、测试进度、最终报告），问题 **0**、子代理 **0**。
- provider / paid / SEC：**0 / 0 / 0**；无联网、模型 / SEC 调用、commit/push、源 / 测试 / 旧证据改写，不读 #47 或大原件。
- 产物仅本目录 conclusion.md 与四份必要日志，无 tar；临时小 fixture 用既有测试构造函数生成并在进程结束前删除。

## 结果与因果

新 q 标签允许可见词内片段跨其开始及结束标签保持同一段。`finan<q><div style="display:inline">cial</div></q>` 现在完整重建为 financial；cor / rected 同样完整保留。它只改变文字分组，不改变引用身份：原 `quoted_block_indices=[15]` 保留，合组的 block_indices 为 `[14,15,16]`，引用交集仍是 `[15]`。

未变完整 API 的 `instant_balance_amendment.py:126-129` 因这项引用交集拒绝把该条款登记为正常条件性补偿说明。相同原文、相同小完整 filing，在隔离内存仅替换基线 layout 的前后结果为：

| 小完整 API 输入 | 基线 v2 | 当前 v2 |
| --- | --- | --- |
| 干净财报 | INPUT_PROPERTY_PROVEN | INPUT_PROPERTY_PROVEN |
| 普通非引用条件句 | INPUT_PROPERTY_PROVEN，1 条条件性记录 | INPUT_PROPERTY_PROVEN，1 条条件性记录 |
| financial 词内 q 引用片段 | INPUT_PROPERTY_PROVEN，0 条条件性记录（原线索重现） | WITHHELD，FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED:14,15,16 |
| 整句 q 引用 | WITHHELD | WITHHELD |
| 普通已发生财務更正句 | WITHHELD | WITHHELD |

每个有关 source_block 均等于原 parser 块，block_indices 保持，原始 byte span 的 SHA256 全部重算通过；未捏造连续原始范围。所有结果的获取 / 年度连续性 / 债务完整性 / 指标创建 / 生产权限标志均 false。

`q style="display:block"`、真实 p 边界及可见 gap 仍分成两组；加入 q 没有取消既有块级及实质内容边界。

## 测试和兼容范围

指定环境及命令实际完成 **16 项 unittest，无 SKIP，exit 0**，包括新增 quoted_word_fragment 完整 API 方法，见 unittest.log。本地执行不能称作远程 CI。

对以上五种完整小输入，省略 note_layout 的旧默认 `blocks-v1` 在基线 / 当前的**整个结果对象与 instant_scope_id 完全相同**，且都没有新增 note_layout 字段。两个政策 JSON、annual / instant API、text_coverage 与 fiscal_year_labels 六个依赖逐字节等于基线和当前提交。

这里的“旧默认未改”仅是兼容事实：上述词内 q 反例在旧默认仍同样返回 INPUT_PROPERTY_PROVEN。本次显式新布局修补不宣称修复旧默认，不把这个既有行为列为新差异回归或扩大本次任务。

首个独立探针误把封面 / Item15 的 financial 文字也计入“追加条件句只有一组”的断言，因本人探针计数错误中止；API 前后结果已正确，日志保留。修正筛选到追加 fixture 块后完整执行全部五例、文字 / 边界检查和字节核验通过，见 api-and-default-comparison-followup.log；没有修改产品或将中止段写成全通过。

最后 tracked diff 仍为空，受审文件及两份沿用旧结论均等于精确 HEAD 保存字节，见 byte-verification.log。未覆盖全面原件、全模块 / 全 PR、公司 CSV、消费者接线、历史结果、模型 / 生产验收、正式采纳或 active 切换；本次有限结论不授这些信用。
