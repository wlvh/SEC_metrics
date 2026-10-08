# 隐藏 gap 修补限定复核

结论：**LIMITED_REVIEW_PASSED（仅 77e3 的隐藏 / void / self-closing 分组增量）**。此前独立完整 API 隐藏 gap 反例在当前补丁上已正确 WITHHELD；源可见文字现在保持同一更正句。没有在本次实际增量中发现新增问题。旧 `conclusion.md` 的 5cc NEEDS_FIX / LIMITED_REVIEW_NOT_PASSED 保持原文，本报告不将它改签为通过。

## 固定对象与累计资源

- 补丁：`77e3bca3698d03ac006e7bd23abdee54e799864a`；基线：`a5467fed3d30927da28cbae45f183bdf481f2346`；最后 HEAD 与补丁相同。
- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-amendment-note/SEC_metrics`。只审 `amendment_note_layout.py` 新增隐藏 / void / self-closing 分组及两个测试模块的新 2 个方法。新 parser helper、annual / instant API、政策、正文规则、引用规则等未变字节不重审；只为执行必要 API 复用它们。
- 原件仍仅 `/private/tmp/issue28-amendment-note-review-inputs-9f3145f/` 的两 HTML 和 source-information.json。两 HTML hash 前后保持 `5e1a509968b99ce829546d0eabeb6e663e711788577901f83d0cbaa53cf6a44a` / `ca8bf425a320024aa65885a23bad51b5e97b74f8aadf62bba9968ea13181f845`。变体只在内存重建 RawBlob / SourceReference hash 和长度，无获取信用。
- 原累计开始：2026-10-08 21:04:19 UTC；本次 follow-up 首次工具：2026-10-08 21:15:57 UTC；累计结束：2026-10-08 21:19:34 UTC。原 90 分钟截止 22:34:19 UTC 未触及。
- 累计实际工具 **68** 次：26 次 functions.exec、35 次 exec_command、5 次 write_stdin、2 次 clock.curr_time。本次增加 19 次，累计上限 80 未触及。
- 累计普通消息 **3** 条：原初始说明、原最终报告、本次最终报告。问题 0、子代理 0。本次无进度消息。
- 累计 provider / paid / SEC **0 / 0 / 0**；无联网、模型 / SEC 调用、账户操作、commit/push、源/测试改写或 #47 工作树 / 账本 / 运行根读取。
- 本次只追加本 hidden-gap-followup.md 与 3 份日志。原 5cc 的 6 个产物以及前两次独审 4 / 5 文件最后逐字节等于补丁保存版本，旧失败与负例未改。

## 完整 API 的前后对照

向原同一授权 FY2024 修订原件 `</body>` 前追加此前同一反例，保留原主体、期间、note、false flag 及其余原文：

```html
<div>We have cor<span hidden>formatting draft</span><div style="display:inline">rected</div> our financial statements.</div>
```

当前 `_text_units` 产生一个单位，文字为 `We have corrected our financial statements.`，保留所有原 source_blocks / block_indices 与每片段原始 byte hash，不伪造单一连续范围。

为区分实际修复与仅测试变化，本人从精确基线只加载旧 layout 依赖到内存，调用未变的完整 API，再恢复当前 layout：

- 基线：INPUT_PROPERTY_PROVEN，issues=[]，结果身份 `sha256:33f54d49a998cb9b2efcf03dae7a2020245a9400fcc7e9d79c8c63b338c6e71f`，重现旧失败。
- 当前：WITHHELD，`INSTANT_AMENDMENT_FINANCIAL_CORRECTION_LANGUAGE_UNRESOLVED:1833,1834,1835`，结果身份 `sha256:955967c63d0c65f4c0613ce84acad902849abc2100a3f51207dd01032488e8db`。

见 `hidden-gap-followup-api.log` 的 baseline / restored_current 对照。没有借用开发者执行结果。

## 实际通过的限定检验

1. 按原指定环境和同一命令实际运行两 unittest 模块：**15 项通过，无 SKIP**，新增两方法真实执行，见 `hidden-gap-followup-unittest.log`。这只证明本地执行，不是远程 CI。
2. 授权干净原件 INPUT_PROPERTY_PROVEN；此前 exact 反例与 7 个仅改变隐藏 gap 的变体全部 WITHHELD：display:none、visibility:hidden、自关闭 span、hidden img（普通 / self-closing）、隐藏 div/p、隐藏 span 内 void 子元素。没有新增广泛句式或金融关键词。3 个仅隐藏更正文字的正常变体仍 INPUT_PROPERTY_PROVEN。所有结果的来源获取 / 年度连续性 / 债务完整性 / 指标创建 / 生产信用标志均 false。
3. self-closing hidden 元素、hidden void 和含 void 子元素的隐藏容器关闭后，随后可见 `visible gap` 文字仍原样保留；它们不会泄漏隐藏状态。8 个人工 source-range gap 反例中，未知 tag、display:block、br、div、实质可见文字、实际 p 边界、hidden 自关闭 / void 后的可见 gap，均保持分成两组，不能当成空行内 gap 混入。
4. 已修复句的 source_blocks / block_indices 完全等于原 parser 片段，逐字节 hash 重验，无捏造连续原始范围。三个改动源/测试文件最后等于精确补丁；annual / instant API、text parser / quotation 依赖和两个政策文件均等于基线；旧证据及原件 hash 保持。见 `hidden-gap-followup-byte-verification.log`，落盘前再次重验。

API 日志保留一次探针断言的实际中止：初始探针错误要求将已被原 source block 保留的可见文字再拆组；正确判据应为不丢可见文字。本人在日志中注明原因，随后分别检查可见文字保留和人工遗漏 gap 的拒绝合组，后半脚本实际完成。没有据此修改产品，没有把中止段写成全通过。

## 范围与未覆盖

本次只关闭所委托的隐藏 gap 修补增量及旧 exact 隐藏反例。旧报告中的未改引用词内分组线索没有重开，也没有在本次结案；其存在不能被本报告改写成所有文字布局均已通过。未授全模块、全 PR、公司结果、历史 CSV、消费者接线、真实模型验收、生产采纳或 active 切换信用。原已审默认保存对象 / 条件性规则等未变证据沿用其原范围，不重建平台或追加语言规则。
