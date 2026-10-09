# 限定 P1 修补独立复核结论

结论：**LIMITED_REVIEW_NOT_PASSED**。原 P1 已报告的完整词组拆分反例均已修复，但新增全文段落检查仍有同一排版问题的残余错误接受：行内排版在单词内部拆分时，程序凭空插入空格，已报告的更正或当前余额因此被跳过。发现 1 项 P1，须修复后只复核实际增量；不据此重开已审字节未变的 9f 全部差异。

## 固定对象、时间与实数

- 基线：`9f3145fe6b8974346c431568736680026d19e926`；精确修补：`993d3fbb4ea6c7d767f6f757b57f3bb360c1a7a3`。
- 现场 HEAD：`9a66f77a69fd40a750a8c85111327d0b778e0792`。993→HEAD 仅证据目录 `.gitattributes` 两行 raw log whitespace 属性；审阅结束前源码、测试与 workflow 均再次逐字节等于 993。
- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-amendment-note/SEC_metrics`。
- 本次仅审 `scripts/vnext/instant_balance_amendment.py` 新增段落检查、`tests/vnext/test_instant_amendment_paragraph_api.py` 和 `.github/workflows/amendment-note.yml`；有限追踪不变的段落/来源/引用依赖，不重审其全模块。
- `config/annual_amendment_scope_v1.json` 与 `config/instant_balance_amendment_v1.json` 均与 9f 字节相同；SHA256 分别为 `ed7c8d776c47b08a5238d41d250fa7d4712994f2df34148383040e2435a93202`、`50790b4f32651a2d93044d32b58aeace432d6dcde7fa9b42f599dbb05acb0892`。
- 授权原件仅 `/private/tmp/issue28-amendment-note-review-inputs-9f3145f/` 中两份 HTML 及 source-information.json。两 HTML 的 SHA256 前后保持 `5e1a509968b99ce829546d0eabeb6e663e711788577901f83d0cbaa53cf6a44a`、`ca8bf425a320024aa65885a23bad51b5e97b74f8aadf62bba9968ea13181f845`。
- 注册开始：2026-10-08 20:45:53 UTC；首次实际工具：2026-10-08 20:47:08 UTC；结束：2026-10-08 20:52:50 UTC。绝对截止 2026-10-08 22:15:53 UTC 未触及。
- 实际工具共 **23** 次：11 次 functions.exec、9 次 exec_command、2 次 write_stdin、1 次 clock.curr_time。普通消息共 **3** 条（初始说明、一次进度、最终报告），问题 **0**；子代理 **0**。
- 新 provider/paid/SEC：**0/0/0**。没有联网、账户查询、模型调用、SEC 请求、commit/push、源码/测试改写；没有读取 #47 工作树/账本/PR52。仅本目录 1 份 conclusion.md 和 4 份必要日志落盘。原 9f 失败结论及其 3 份日志最终逐字节等于 993 保存内容。

## P1：段落拼接插入原文不存在的空格，拆词更正仍错误通过

位置：`scripts/vnext/instant_balance_amendment.py:58-64`，尤其 62 行，以及新的全文调用 118-124 行。

`paragraph_blocks` 已识别同一实际段落，但 `_text_units` 使用 `' '.join(b['text'] for b in group)`，无条件在片段间插入空格。`display:inline` 不在无原始空白的词内增加空格；这会把 `financial` 改成 `finan cial`，或把 `corrected` 改成 `cor rected`。随后既有财务对象/更正规则找不到完整词组，124 行直接跳过。这不是新增同义词或新业务口径问题，而是修改了已有明确句子的文字。

独立完整 API：向授权 FY2024 修订原件结束 `</BODY>` 前添加以下句子，仅在内存构造变体并重建 RawBlob/SourceReference 的 SHA256 与长度，保留主体、期间、完整说明、false correction flag 和全部其余原文，无获取信用。

```html
<div>We have corrected our finan<div style="display:inline">cial statements</div>.</div>
```

按 HTML 行内排版语义，句子仍是 `We have corrected our financial statements.`；独立 HTMLParser 连续保留原始 data chunks 也重建出该句。扫描器却得到 `We have corrected our finan cial statements .`。完整 `inspect_instant_balance_amendment(..., note_layout='inline-paragraphs-v2')` 返回 **INPUT_PROPERTY_PROVEN、issues=[]**，`instant_scope_id=sha256:8de9196abbdb8afc0a472bf62c2508b9276f5e6f7b8cd7e55d97676aa27351cd`。相同原件追加完整普通句已实际返回 WITHHELD。

同一原因另外两个有限完整 API 反例也错误通过：

```html
<div>We have cor<div style="display:inline">rected</div> our financial statements.</div>
<div>Our cur<div style="display:inline">rent assets</div> are $42 million.</div>
```

其原始 data chunks 分别重建出 `We have corrected our financial statements.` 与 `Our current assets are $42 million.`；新拼接得到 `cor rected` 与 `cur rent assets`，均返回 INPUT_PROPERTY_PROVEN、issues 空。这使 B08/B09 的原始当前余额复用属性错误获证，涉及正常排版和数据正确性，不要求外部攻击者。

完整真实原件变体证据见 `word-fragment-original-api.log`；小完整 API 及精确扫描文字见 `word-fragment-probes.log`。后者的直接块文本相接辅助字段会丢已被块解析器去掉的原始边界空格，日志末尾已明确说明；准确可见文字以保留原始 data chunks 的前者为准。

建议有界修复：段落检测保留真实行内文字及原始空白边界，或在无法证明正确连接时明确拒绝该布局；不要通过扩展批准政策词库掩盖人为拆词。保留 source_blocks、每片段范围/hash、引用集合、既有条件性全句规则和旧默认路径；给完整普通句、词组间拆分、词内拆分加入同结论的完整 API 回归即可，无需重建语言规则平台。

## 本次实际通过的限定覆盖

1. 指定环境实际运行 `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest -v tests.vnext.test_amendment_note_layout tests.vnext.test_instant_amendment_paragraph_api`：**12 项通过、无 SKIP**，见 `unittest.log`。其中新增 API 模块为 3 个测试方法，plain/split current correction 的三项 subTest 均执行。
2. 授权干净 FY2024 原件的新分支仍 INPUT_PROPERTY_PROVEN；原 P1 的完整普通更正句、词组间行内拆分更正句、`current`/`assets` 之间拆分的重述句，以及同样拆分的当前余额句均返回 WITHHELD。原 P1 的具体重现已修复，不能据此签完整段落检查通过。
3. 两项封面声明与条件性条款保存的 source_blocks 等于原 source document 对应 block_indices；逐片段原始 byte range/hash 重新核验，未捏造一个连续原始跨度。
4. 小完整 API 中，原条件性条款的普通句与词组间行内拆分均允许且各保留一个条件性记录；片段带 q 引用、条件句附加已发生的财务更正，以及封面声明附加拆分更正均 WITHHELD。新引用集合判定没有将引用片段误当成可豁免条件。
5. 从 git 精确 9f 只加载旧 instant 模块到内存，与当前 blocks-v1 默认 API 对照：授权原件旧、新均同异常 `AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED`；清洁小完整 fixture 与普通条件性小 fixture 的**整个保存对象完全相同**，instant_scope_id 相同，均不新增 note_layout 字段。它们为合成诊断材料，不构成所有旧包或未授权 FY2025 原件的兼容证明。
6. 新 workflow 的实际 run 字段正是两模块 unittest 命令，loader 选择 **12 项**，并已在本地实际执行同一模块集。workflow 触发 paths 覆盖本次源/测试/workflow，依赖 checkout/setup-python 已固定 SHA。**GitHub 远程 run 未核验**：本任务禁网；本地指定解释器为 Python 3.12.10，workflow 配置为 3.14，不能将本地执行写作远程 CI 成功。

以上第 2–6 项见 `full-api-and-compatibility.log`。主体、期间、完整 note/范围等未变边界沿用前次已覆盖的限定证据，不重复授予全模块信用。所有新 API 结果的 acquisition/annual/debt/metric/production 信用标志仍 false。

## 签审范围与缺口

本结论只针对 9f→993 的 P1 修补及新短例/CI 接线。不覆盖长材料、全 PR/全模块、公司消费者接入/CSV/历史输出、真实模型验收、生产采纳或 active 切换；不改变旧 9f 失败。发现直接错误接受后停止追加完善，下一步是修复这个原文空白边界问题并对实际差异有限复核。
