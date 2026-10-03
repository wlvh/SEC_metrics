# E01 可见性与同段引用窗口增量限定独立复核

结论：**PASS_LIMITED — 指定隐藏 br 的 P2 与继承的长隐藏节点挤占窗口问题已修复；本次增量范围未发现新增 P1/P2。** 原隐藏 SEE、前段 OR 的真实标题继续保留，真正同段的 See 引用继续排除。

- patch SHA：`0de97ec9e280e578c809320c6c18c65381070f99`；parent SHA：`df0f455ffcff35836cd70d8ea3bd9a9c2706f743`。
- 读取指定 SHA 的 AGENTS.md，协作规则为 COLLAB-28-47-v1.1，并实时只读 [Issue #28](https://github.com/wlvh/SEC_metrics/issues/28)。AGENTS.md 与 parent 字节相同。本次为最后一次指定差异工程检查，未操作 #47 现场、分支、运行根或账本。

## 已覆盖的具体差异

`e01_header_document_guard_28_v1.py:31–48` 在改变可见块编号前复用继承的隐藏判定：元素自身隐藏、祖先隐藏或属于不显示的元素时，开始/结束标签不会制造边界。`:22–24` 不再把 br 当段落边界。`:78–81` 先取同块可见前文，再截取最后 40 个字符；长隐藏文字不再占用这个窗口。旧 `_Visibility`、`_hidden_by_style`、标题与引用词表达式均未改变，没有增加语言词表。

亲测原最小隐藏 br 反例及隐藏属性、隐藏祖先中的 br，现在返回空标题集合，空头文件不会误触发漏列拒绝；精确 parent 在同控制中仍返回 2.01。原长隐藏内联节点控制也由 parent 的误识别 2.01 改为正确排除。新增的小型独立控制验证隐藏祖先内的嵌套块及 template 中的块不会切断 See 前文，真正可见的嵌套块仍隔开前文。

原隐藏 SEE／前段 `Location: Portland, OR` 后的独立真实标题仍返回 2.01，空头文件具名拒绝，列明 2.01 时接受。隐藏同段 SEE 后的可见 br 也保留真实标题；真正同段的跨内联 See 以及跨可见 br 的引用均排除。完整原文、parent/patch 返回值、空头文件行为在 `visible-boundary-controls.log`。这些是合成内存控制，未声称保存财报原件实际存在这些结构。

## 亲测与静态身份检查

仅运行获准 unittest selector：

```sh
PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_e01_header_document_guard.E01HeaderDocumentGuardFastTest
```

**4 项／0.002 秒／exit 0**，见 `fast-test.log`。另执行 **12 个微型内存控制**，全部符合预期；没有执行材料、安装、cold 或全 fast 测试。

测试前独立核对父方未提交 `tested-commit-equivalence-boundary.json` 的 **13 文件**哈希/长度及声明的两份安装根保存字节与 patch 一致，`execution_at_commit_claimed=false` 正确保留提交前执行身份；并核对 5 个继承/调用依赖与 parent 字节一致。测试后再次确认 7 个必要入口、依赖与测试文件字节，见 `preflight.log`、`completion-check.log`。额外 execution-state 修改与未提交等价 JSON仅登记，未处理。

静态核对 guard 在 V13 的 `new_rule_files`/执行文件、V14 执行文件以及必要未改依赖中的哈希/长度。guard SHA-256 为 `54502a58b3ef5775197fa114eb454234307067212bb81217214a45816b5042f7`，长度 4073；V13 baseline 只有 guard 两处身份共 4 个叶字段变化，V14 baseline 只有 guard 身份和必要父闭包/baseline 引用共 4 个叶字段变化。V14 引用的 V13 全 5 文件身份相符，transfer 仅更新父闭包引用。

独立重算 V14 execution authority 为 `sha256:0ce2449e717db6dec400758f36af8290fa8974d5f854c3c07db06427880e8e4a`，与三份接线收据相符；三收据除对应身份字段外无变化，没有扩大许可。V13/V14 总闭包值沿提交绑定记录读取，分别为 `sha256:313038b01c1572ec22814de504667ae599b27ce3a59cb4911f4adada7f6e6433` / `sha256:2e6d7d5b1043723e602c112d3b9b43da638d37979652d3e65b4ccfefe28651d3`；本次没有完整 Requirement loader 重放认证。出处记录的 guard、peer Git blob与原函数文本哈希相符，见 `static-bindings.log`。

未改的 V2 调用处 `ordinary_e01_item_text_input_v2.py:106–108` 仍对每份发现的正文执行该防护；这是调用路径静态核对，本次未重跑正常材料入口。V1 reader、V1 adapter、V2 adapter与 AGENTS 字节未改，旧输入/Run/Result未重签。

## 仅读日志与保存范围

读取首轮 `independent-review-4711a48/conclusion.md`、上轮 `independent-review-repair-df0f455/conclusion.md`/`hidden-boundary-regression.log`，以及本批 README、binding-before/after-boundary、source-provenance-boundary、rebind-boundary、directed-boundary、scalability-boundary、short-boundary-repair、installed-boundary、两份 installed-cold-boundary 和对应日志；没有重跑。

提交方既有日志记录定向 **6/6／17.032 秒**，绑定源码无业务硬编码检查 **1/1／11.517 秒**；后者不等同于性能基准。两家公司安装 **37.658 秒**，Enphase **6 份核对／0 候选**、Pfizer **9 份核对／3 候选**；另进程 cold **15.007／17.127 秒**，Input ID、检查数、候选数与安装记录一致。只读盘比较三模块保存字节及相关记录字段相符，未重建材料输入，也未重新验证保存原件全部内容。原条目哈希不变、116 个旧导出禁用、零真实调用和 active/来源日志未变仍是这些既有执行证据的限定声明。原 148 项全 fast 仅是修前树的历史证据，不是本 SHA 的全 fast 通过。

旧两次 NEEDS_FIX 原报告保留历史原义，本次只按具体反例和增量修复给工程限定信用，不改旧结论原件。

未覆盖：并购语义判断、具体计数/去重、完整召回、任意 HTML/CSS 支持、十家公司全部材料、旧 E01 Result 新口径接受、新 Result/Run、390 信用、完整 Requirement 认证、160 份全审计、材料/安装/cold/全 fast 重跑、真实 provider/paid/SEC、生产/active，以及提交中执行状态等其他范围。没有发生业务真实请求；实时读取 Issue 属于只读技术信息。此同族子代理独立工程检查不冒充独立人工、用户验收或 GitHub APPROVE。

## 资源与现场

开始 UTC：`2026-10-02T15:31:18Z`。
结束 UTC：`2026-10-02T15:41:45.987793+00:00`。

工具实际合计 **32**（含本次记录保存）：functions.exec **10**，嵌套 exec_command **20**、clock__curr_time **1**、web__run **1**。普通消息 **3**（2 条 commentary、1 份最终报告），问题 **0**。未达工具 80／90 分钟上限。

只新增本目录 `conclusion.md`、`preflight.log`、`fast-test.log`、`visible-boundary-controls.log`、`static-bindings.log`、`completion-check.log`。未开发、commit、push、打包、再 spawn；未修改产品源码、父方执行状态、账本、快照、分支或 #47 现场。
