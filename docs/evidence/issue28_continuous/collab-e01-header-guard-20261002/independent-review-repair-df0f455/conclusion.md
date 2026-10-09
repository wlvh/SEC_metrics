# E01 可见块引用范围修复增量限定独立复核

结论：**NEEDS_FIX_LIMITED — 原 P2 的隐藏 SEE／前段 OR 两个反例已修正；新块边界实现引入 1 个 P2。本范围未发现 P1。** 指定短测 3/3 通过；隐藏换行元素仍使同一可见段落的真正引用误报成标题，因此本机械范围尚不能接受。

- patch SHA：`df0f455ffcff35836cd70d8ea3bd9a9c2706f743`；parent SHA：`4711a488d850b9cf488efcbd745d5108eb18b8e4`。
- 先读取本方 AGENTS.md，规则版本 COLLAB-28-47-v1.1；实时读取 Issue #28，更新时间 2026-10-02T14:47:27Z。此次是指定 SHA 的增量工程复核，不读取或操作 #47 工作树、账本、分支、运行根；不复审整个 E01。

## P2：隐藏换行元素切断可见引用前文

位置：`scripts/vnext/e01_header_document_guard_28_v1.py:28–31`，引用过滤消费处 `:64–70`；实际调用处仍为 `ordinary_e01_item_text_input_v2.py:106`。

`_HeadingContext.handle_starttag` 在检查元素是否可见之前，遇到任何 `br` 都增加 `block_number`。下面这份合法的最小 HTML 中，`br` 被 display:none 隐藏，读者看到的同一段文字是 `SEE Item 2.01 Completion of Acquisition or Disposition of Assets.`，这是跨内联元素的真正引用：

```html
<p><b>SEE</b><br style="display:none"><b>Item 2.01 Completion of Acquisition or Disposition of Assets.</b></p>
```

亲测 parent guard 返回空集合，指定补丁返回 `{'2.01'}`；空头文件触发 `ORDINARY_E01_ITEM_HEADED_BUT_NOT_LISTED:synthetic-hidden_style_break:2.01`。只有隐藏换行元素变化、可见内容相同，却由正确排除变成误拒。`<br hidden>` 和 `<span style="display:none"><br></span>` 两个控制组也复现；去掉隐藏 br 即恢复排除。证据在 `hidden-boundary-regression.log`，两版函数均按精确 Git 字节在内存执行，旧依赖未改。

影响仅为新增 V2 来源输入防护：有此结构且该引用条目没有列在头文件的正常输入会被误拒。没有证明当前 Enphase/Pfizer 保存原件实际受影响，也没有证明错误 Result/Run。修复应让隐藏元素及隐藏祖先内的元素不制造可见块边界，保持真正可见独立块对真实标题的隔离；沿用既有隐藏判定即可，不需要增加一般语言规则。

原审 P2 中隐藏 SEE 和独立前段 OR 的真实标题现均被保留，空 header 会具名拒绝；这些原反例可以按具体行为结案，但本次新回归须单独处理。另一个长隐藏文字占满原 40 字窗口的控制，在 parent 和 patch 都存在，`hidden-boundary-regression.log` 已明确标作继承限制，**不计为本次新差异 P2**，没有扩展调查或修复范围。

## 亲自验证

1. 精确短测命令：`PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_e01_header_document_guard.E01HeaderDocumentGuardFastTest`，**3 项／0.001 秒／exit 0**，见 `fast-test.log`。
2. 八个微型内存正反例：原隐藏 SEE、前段 OR、同行 SEE 跨内联、隐藏内联 SEE、短隐藏内联、长隐藏内联、无隐藏节点和链接目录后真实标题，见 `counterexamples.log`。另做五个 parent/patch 对照控制，只定位新增隐藏 br 边界回归，见 `hidden-boundary-regression.log`。它们均为合成内存材料。
3. 执行前核对父代理的未提交 `tested-commit-equivalence-repair.json` 共 **13 项**，哈希/长度与 patch Git 字节一致；按其中声明核对两份安装根保存字节。该文件明确 `execution_at_commit_claimed=false`，没有把提交前执行冒称为提交时测试。四个旧依赖仍与 parent 相同。执行结束再次确认实际使用的六个产品/测试文件与 patch 一致，见 `preflight.log`、`completion-check.log`。
4. 静态核对 V13/V14 guard 绑定及 V13 new_rule_files、V14 所引用 V13 五文件；guard SHA-256 为 `d7de1604aa8cb39f0a238ebaaed713de91e3ad552fb7c181f15747ecab6a9867`。V13仅改 guard 哈希/长度，V14另更新必要父闭包引用及 baseline 哈希。adapter/旧 reader/config/Decision Register 相关字节不变。重算 V14 execution authority 为 `sha256:185d7ca80cc4b1e13e4a79047e7969348f1fced051aa5a5308f6ce40d8dc3f7d`，与三份接线收据一致；收据仅身份字段变化。出处记录 guard 哈希及 peer 函数文本哈希相符，见 `static-bindings.log`。本次没有加载并重新认证整个 Requirement 闭包；V13/V14 总闭包值是读取提交方绑定记录并核对有关引用。

## 仅读执行证据及未覆盖

读取原审 conclusion/counterexamples、README、binding-before/after-repair、binding-repair、directed/short-repair 日志、install/cold/rebind 修后脚本、installed-repair、两份 installed-cold-repair、source-provenance-repair 及 13 项字节等价 JSON。**本次未重跑这些材料或长链。**

提交方日志的范围为修后定向 **5/5／16.882 秒**；两家公司安装 **38.387 秒**，Enphase **6 份核对／0 候选**、Pfizer **9 份核对／3 候选**；另进程冷读 **14.768／16.829 秒**，两份 Input ID、候选数、核对数与安装记录一致。最后仅直接读盘比较三模块字节及上述字段，没有重新执行安装或 cold。未变条目文本哈希、零真实调用、未创建 Result/Run、116 个旧导出禁用均是这些既有执行证据的限定声明，不能升级成本次完整验证。旧 148 项全 fast 仍是修前树的历史通过。

未覆盖：E01 并购语义、计数／去重、完整召回、十家公司全部保存材料、旧 Result 的新口径接受、新 Result/Run、390 信用、160 份全审计、完整 Requirement 认证、全 fast、真实 provider/paid/SEC 和生产/active。C02 `3436-contract-alignment.json`、执行状态及缺陷登记的其他提交增量不在本源码复核范围。父工作树额外 execution-state 修改及未提交等价 JSON只登记，不修改。同族子代理的独立工程检查不冒充人工、用户验收或 GitHub APPROVE。

## 资源与现场

开始 UTC：`2026-10-02T15:02:23Z`。
结束 UTC：`2026-10-02T15:11:35.651354+00:00`。

工具实际合计 **32**：外层 functions.exec **12**，嵌套 exec_command **19**，嵌套 clock__curr_time **1**；其他工具 **0**。普通消息 **3**（2 条 commentary、1 份最终报告）；问题 **0**。未达到工具 80／90 分钟限额。

只新增本目录 conclusion.md 及六份必要日志：preflight、fast-test、counterexamples、hidden-boundary-regression、static-bindings、completion-check。未开发、commit、push、打包、再 spawn；未改任何产品源码、父执行状态、账本、快照、分支或 #47 现场。
