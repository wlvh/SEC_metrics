# 限定独立审阅结论

结论：LIMITED_REVIEW_NOT_PASSED。发现 1 项 P1；必须先修复下述错误接受，再对修改差异进行限定复核。本结论只覆盖指定补丁和两份授权原件，没有批准全模块、全 PR、公司结果或生产采纳。

## 固定审阅对象与资源

- 精确补丁：`9f3145fe6b8974346c431568736680026d19e926`。
- 基线：`8588ccbbb1c91d81e0fb1a89dff3575214282549`。
- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-amendment-note/SEC_metrics`。
- 源码差异限定为 `amendment_note_layout.py`、`annual_amendment_scope.py`、`instant_balance_amendment.py` 和 `test_amendment_note_layout.py`。只为追踪这四个文件的实际行为，有限读取未改的 `_Blocks`、`_DefinitionBlocks`、来源记录校验函数；没有进行这些依赖的全模块审阅。
- 两个批准政策 JSON 与基线字节完全相同；报告落盘前四个范围文件与精确补丁字节完全相同，HEAD 未变化。
- 原件仅取自 `/private/tmp/issue28-amendment-note-review-inputs-9f3145f/` 的两个 HTML 及 `source-information.json`。SHA256 分别为 `5e1a509968b99ce829546d0eabeb6e663e711788577901f83d0cbaa53cf6a44a` 和 `ca8bf425a320024aa65885a23bad51b5e97b74f8aadf62bba9968ea13181f845`，前后独立核对一致。没有读取 #47 工作树、账本或 PR52。
- 注册开始：2026-10-08 20:21:49 UTC；本审阅首次实际工具时间：2026-10-08 20:24:37 UTC；结束：2026-10-08 20:31:47 UTC。硬截止 2026-10-08 21:51:49 UTC 未触及。
- 实际工具调用总量：32，含 11 次 functions.exec、20 次嵌套工具、1 次 collaboration.send_message；没有子代理。普通消息总量：3（初始说明、一次向父代理报送发现、最终报告），问题 0。
- 新 provider/paid/SEC 调用：0/0/0；没有联网、账户查询、模型调用、SEC 请求、commit、push 或源/测试改写。输出仅本目录的 conclusion.md 及 3 份必要日志。

## P1：更正句跨行内块时会被错误认定为原始余额输入可复用

位置：`scripts/vnext/instant_balance_amendment.py:110-131`，特别是 114-119 行。新分支已在说明段落与封面声明中将同一段落的行内片段重新组合，但全文更正检查仍逐个原始 `block` 检查；只有同一片段同时含财务对象和更正词，才进入冲突分支。

独立完整 API 反例：在授权 FY2024 修订原件的结束 `</BODY>` 前追加下列普通披露句，保留原有主体、期间、说明、封面 false flag 与所有其他原文。变体只在内存中构造，各自重建 RawBlob/SourceReference 的 SHA256 与长度，没有修改原件，也没有赋予获取信用。

```html
<div>We have corrected our financial statements.</div>
```

返回 `WITHHELD`，原因 `INSTANT_AMENDMENT_FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED:1833`。

将同一句仅按本补丁支持的 `display:inline` 方式拆开：

```html
<div>We have corrected our <div style="display:inline">financial statements</div>.</div>
```

完整 `inspect_instant_balance_amendment(..., note_layout='inline-paragraphs-v2')` 返回 `INPUT_PROPERTY_PROVEN`、`issues=[]`。`We have corrected our` 含更正词但没有财务对象；`financial statements` 含财务对象但没有更正词，二者在 119 行分别被跳过。第二个有限反例也错误通过：

```html
<div>Our current <div style="display:inline">assets</div> have been restated.</div>
```

这是正常排版造成的错误接受，涉及 B08/B09 原始当前余额输入的准确性，不依赖外部攻击者。旧默认路径对这份原件会在说明片段数量处拒绝；新布局路径解除该限制后，不能继续用片段而非同一实际段落检查真实财务更正。无需扩建通用语言规则：应在新布局的全文检查中对经过相同保守拼接的段落应用既有财务对象/更正/条件性条款规则，并保留全部原始块、范围和引文状态。至少需要上述普通句与行内拆分句同结论的回归证据。

复现记录：`original-and-correction-probes.log`。该日志是审阅者自行执行；开发者已有 probe JSON/日志仅作为已有材料核对，没有被当成本人的执行。

## 已独立覆盖且通过的限定部分

1. 按指定解释器和环境实际运行 `python -m unittest -v tests.vnext.test_amendment_note_layout`：9 项通过，见 `unittest.log`。覆盖真实段落数量上限、行内片段、块级/实质内容 gap、范围有序性、额外目的、不同法规及条件性与当前更正的区分。
2. 授权真实 FY2024 原件的默认路径仍返回 `AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED`；显式新路径识别 13 个原始 note 块、3 个实际正文段落，保留各块范围和 SHA256，干净原件返回 `INPUT_PROPERTY_PROVEN`、issues 空。封面两项声明分别保留完整原始 source_blocks / block_indices；没有捏造单一原始范围。
3. 在同一原件上构造 5 个内存限定负例，并完整调用新 API：附加说明目的、说明主体冲突、说明期间冲突、说明片段带 q 引文、将原条件性 clawback 改为当前已发生重述，全部返回 WITHHELD。主体/期间/引文保护与完整 note fullmatch 继续有效，见 `boundary-and-compatibility-probes.log`。
4. 从 git 精确基线只加载两个范围读者到隔离的内存模块，与当前默认 API 独立比较：实际原件的异常类型及原因完全一致。另由授权原件生成有限等义排版/措辞 fixture（行内 div 改为 span、还原旧已支持的 purpose/References/法规别名）；旧、当前默认 API 的整个返回对象完全相等，均为 `INPUT_PROPERTY_PROVEN`，相同 `instant_scope_id=sha256:28b498e91e6b93589f646f600c9ee58cc30314a4c069be7f4308a0a1fb2099cd`，均不出现 note_layout 新字段。这一 fixture 是合成材料，不冒充原件或所有旧包兼容证明。
5. 显式新分支保存 `note_layout='inline-paragraphs-v2'` 并进入内容身份；默认值为 `blocks-v1`。新增代码只扩展已支持 purpose 的三个明确措辞变体和同一法规的定义别名，政策文件没有改写；保存的 source、Run、production 信用标志继续为 false。

## 缺口与停止理由

因可复现 P1，不能签发限定通过结论。没有长测试、全 PR/全模块批准、公司消费者接线/CSV/历史输出验收、真实模型验收或生产动作。FY2025 开发者兼容报告没有对应授权原件，故没有自行执行，也不作为本人的兼容结果。无需扩大范围或继续追加完善；先修复上述同段落更正检测不一致，再对实际差异作有限复核。
