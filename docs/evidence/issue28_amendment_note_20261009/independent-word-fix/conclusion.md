# 词内文字修补限定独审结论

结论：**LIMITED_REVIEW_NOT_PASSED（必需完整 API 负例）**。5cc 对前两次报告的具体 P1 反例已经修复；没有发现其新增文字重建函数自身引入的新错误。但本次明确要求的隐藏文字负例仍被完整 API 错误接受，属于同一文字分组问题的残余。**它在基线也存在，不能写成 5cc 引入的新回归**。本结论不重开旧模块全面审阅，也不授全模块、公司结果或生产信用。

## 绑定、时间、资源与保存

- 精确补丁：`5cc8bfcd36a5184dc7dba4982235ffadaff6eb88`；基线：`9a66f77a69fd40a750a8c85111327d0b778e0792`。
- 现场 HEAD：`a5467fed3d30927da28cbae45f183bdf481f2346`。三个源文件和两个对应测试最后逐字节等于 5cc。两个政策 JSON、`text_coverage.py` 和 `fiscal_year_labels.py` 最后逐字节等于基线；前两次独审证据分别 4 / 5 个文件仍逐字节等于 HEAD 保存内容。
- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-amendment-note/SEC_metrics`。只审新增差异，有限读取可见文字解析、分组和引用依赖以执行所要求的 API 检验，没有开展这些依赖的全模块审阅。
- 原件仅 `/private/tmp/issue28-amendment-note-review-inputs-9f3145f/` 的两个 HTML 与 `source-information.json`。两 HTML SHA256 前后保持 `5e1a509968b99ce829546d0eabeb6e663e711788577901f83d0cbaa53cf6a44a` / `ca8bf425a320024aa65885a23bad51b5e97b74f8aadf62bba9968ea13181f845`。
- 开始：2026-10-08 21:04:19 UTC；结束：2026-10-08 21:13:47 UTC。90 分钟及 80 次工具上限均未触及。
- 实际工具 **49** 次：19 次 functions.exec、26 次 exec_command、3 次 write_stdin、1 次 clock.curr_time。普通消息 **2** 条（初始说明、最终报告），问题 **0**，子代理 **0**。
- provider / paid / SEC：**0 / 0 / 0**。无联网、模型/SEC 调用、账户操作、commit/push、源/测试或旧证据改写；未读取 #47 工作树、账本、运行根。
- 产物仅本目录的 conclusion.md 和 5 份必要日志，无 tar。初始探针曾因误用大写 `</BODY>` 中止，核对原件为小写后修正探针并完整执行；没有据此修改产品或计入产品失败。`text-and-compatibility.log` 保留引用片段分组探针的实际中止，后续必需项目在另两份日志继续执行，不把中止脚本写成全通过。

## P1：隐藏行内文字使同一个已发生更正句被分成两组，仍错误接受

实际进入问题的位置为 `amendment_note_layout.py:53-58` 的既有分组依赖，以及新增 `paragraph_text` 在 63–71 行只重建组内文字；`instant_balance_amendment.py:58-65` / 全文扫描消费这些组。新 helper 能保留组内的原始空白和隐藏状态，但不能修复已经错误拆开的词。

本次要求检验隐藏文字。独立完整 API 向授权 FY2024 修订原件最后的 `</body>` 前仅追加下述普通排版句，在内存中重建 RawBlob / SourceReference 的 hash 和长度，保留原主体、期间、note、封面 false flag 与其余全部原文，没有来源获取信用：

```html
<div>We have cor<span hidden>formatting draft</span><div style="display:inline">rected</div> our financial statements.</div>
```

`hidden` span 不显示，也不在 `cor` / `rected` 间产生可见空白。独立的小 HTMLParser（只处理本反例的隐藏 span、连续保留 data）重建文字为：

```text
We have corrected our financial statements.
```

现扫描器分成两个单位：

```text
We have cor
rected our financial statements.
```

`_Gap` 读到被隐藏的 `formatting draft`，将它当作实质 gap，`paragraph_blocks` 于是切组；第一组没有财务对象，第二组没有完整更正词，全文检验分别跳过。完整 `inspect_instant_balance_amendment(..., note_layout='inline-paragraphs-v2')` 在基线读者和当前读者均返回 **INPUT_PROPERTY_PROVEN、issues=[]**，甚至整个结果身份相同：`sha256:33f54d49a998cb9b2efcf03dae7a2020245a9400fcc7e9d79c8c63b338c6e71f`。

这准确区分了新增差异和已有依赖：错误并非 5cc 新引入；但必需的完整 API 负例仍未拒绝，不能把两次旧 P1 的具体实例修复写成这条段落路线已经安全完成。它涉及普通隐藏排版元素及 B08/B09 的原始当前余额复用准确性，不依赖外部攻击者，也无需扩建金融关键词。

有界修复方向：分组判断与组内文字解析采用一致的可见文字边界，或者对不能证明正确连词的布局明确拒绝，不能仅把它拆组后继续获证。保留原 source_blocks / byte range / hash / 引用信息。下一次只复核这个实际修补及普通句、已报告词内拆分、上述隐藏 gap 反例的完整 API 同结论即可。

复现见 `remaining-api-and-compatibility.log` 的 `hidden_gap_word_cut_original`（基线和当前），以及 `hidden-gap-and-byte-verification.log` 的独立可见文字和扫描组对照。字节未变的 `_Gap` 没有因此被全面重审。另一个小完整 API 引用词内分组探针在 text 日志实际错误通过，但本次没有再扩展它的原件重现或独立问题数量；保留为同一分组边界的线索。

## 实际完成的限定检验

1. 指定环境实际运行两测试模块：**13 项通过，无 SKIP**，见 `unittest.log`。这是真实本地执行，不能称为远程 CI 成功。
2. 授权干净原件的新分支 INPUT_PROPERTY_PROVEN；对同一原件执行 12 个更正/当前余额负例，全部 WITHHELD，包括原两次 P1 的词组间拆分、`finan/cial`、`cor/rected`、`cur/rent`，以及原始空格位于片段末尾或开头、tab/newline、NBSP、注释、组内隐藏 span、前置 Unicode。见 `original-api.log`。反例全部只在内存构造。
3. 同一原件的 3 个仅隐藏更正文字的变体分别使用 `hidden` / `display:none` / `visibility:hidden`，均保持 INPUT_PROPERTY_PROVEN；9 个独立手写预期文字对照保留原始有/无空白，不把隐藏文字变成可见词间空格，见 original/text 日志。这只证明所执行形态，不能覆盖上面的跨隐藏 gap 分组失败。
4. 两项封面声明、真实条件性补偿记录和 13 个原始 note 块的 source_blocks / block_indices 等于原 source document；每片段原始 byte hash 重验通过，未捏造一个连续的原始范围，note 仍为 3 个实际段落。见 `original-api.log`。
5. 小完整 API 的普通、词组间、词内拆分及同块隐藏文字条件句均获证并各保留 1 条条件性记录；同原始 block 的 q 引用片段、条件句附加已发生拆词更正、当前已发生条件句均 WITHHELD。note 词内 / 同块隐藏拆分和封面词内拆分可完成；额外目的或额外当前更正均拒绝。见 text / remaining 日志。没有扩充业务词库或政策。
6. 从精确基线仅加载两个范围读者到隔离内存模块：默认 blocks-v1 在授权原件上旧、新均为相同 AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED；在清洁和条件性小完整 fixture 上**整个保存对象、instant_scope_id 完全相同**，没有新增 note_layout 字段。它们为合成诊断，不证明所有历史包。
7. 所有来源 hash、五个受审源/测试、有限不变依赖和旧独审证据最后再次核验，见 `hidden-gap-and-byte-verification.log`。所有本次常规结果的来源获取、年度连续性、债务完整性、指标创建和生产信用标志仍 false。

## 未覆盖与停止

未覆盖全模块 / 全 PR、长测试、公司消费者接线 / CSV / 历史输出、真实模型验收、正式发布、生产采纳、active 切换或未授权原件。来源与保存依赖没有重新全面审计。因必需隐藏负例直接错误接受，在这个具体残余处停止；不无限追加局部完善，也不把当前分组依赖的残余伪装为新增 diff 回归。
