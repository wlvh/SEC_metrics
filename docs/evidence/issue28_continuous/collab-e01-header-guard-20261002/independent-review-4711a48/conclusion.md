# 指定补丁 E01 来源防护限定独立审阅

结论：**NEEDS_FIX_LIMITED — 新增 1 个 P2；本范围未发现 P1。** 新 V2 每份已发现 8-K 的正文/头文件字节、同申报引用、头文件条目与 claim 集合核对已有接线；新增大写交叉引用排除规则仍会忽略真正标题，使“正文候选条目未列于头文件即具名拒绝”不成立。获准短测 2/2 通过不能排除此缺口。

- patch SHA：`4711a488d850b9cf488efcbd745d5108eb18b8e4`。
- parent SHA：`d6f82b229b6f679d704e7d4acab27e421440e60c`。
- #47 纯来源 SHA：`0097c911df0e3e62fc681b7bfda2385edfc9bfcc`；仅读取本仓库已有 Git 对象，未 fetch、未访问或修改对方工作树。
- 规则：读取当前 `AGENTS.md` 的 `COLLAB-28-47-v1.1`；实时 Issue #28 更新时间 `2026-10-02T14:11:40Z`，其中协作节与本地同文。当前公开 Issue 仍把本增量记作待接收，故没有将它当成已验收状态。

## 新增 P2：隐藏前文或另一段的词误抹掉真正标题

位置：`scripts/vnext/e01_header_document_guard_28_v1.py:24`（同时影响 V2 入口 `scripts/vnext/ordinary_e01_item_text_input_v2.py:106`）。

`_visible_text` 会把 HTML 各文字节点拼成一个串，串中仍有隐藏节点文字。新增 `.lower()` 引用词检查直接使用标题前 40 个字符，既不排除该前文中的隐藏节点，也不保留段落边界。对标题本身的隐藏检查只查看标题跨度，不能解决此问题。

亲测的最小内存反例：

```html
<p style="display:none">SEE</p>
<h2>Item 2.01 Completion of Acquisition or Disposition of Assets.</h2>
<p>The company completed an acquisition.</p>
<p>SIGNATURES</p>
```

可见内容的 Item 2.01 明确为真正标题，隐藏 SEE 并非读者能看到的交叉引用。未改的旧读取器 `item_headings` 仍识别 `2.01`，但新增 guard 返回空集合；当 `listed_item_codes=[]` 时，`check_document_header_items` 返回 `[]`，没有抛出约定的 `ORDINARY_E01_ITEM_HEADED_BUT_NOT_LISTED:...:2.01`。删除隐藏 SEE，或把它改成同样隐藏的 DOCUMENT，立即恢复具名拒绝。这把问题定位于本补丁的新增排除逻辑，而不是需要扩展旧标题识别算法。

另一亲测反例是独立可见前段 `<p>Location: Portland, OR</p>` 紧接同一个 `<h2>Item 2.01 ...</h2>`。州名缩写 OR 被转成引用词 `or`，真实标题也被忽略。相反，真正同行的 `SEE Item 2.01 ...` 被排除正确；链接目录后接真正标题仍能触发拒绝。完整原文、返回值和控制组见 `counterexamples.log`。

影响限定为来源防护：当同结构的已认证原件进入实际 V2、头文件及生成 claim 均为空时，入口的集合一致性检查会通过，漏列保护也不会拒绝，后续来源输入可能仍有 `candidate_count=0`。这里不声称当前保存的 Enphase/Pfizer 原件实际具有该缺陷，不声称已生成错误 Result/Run 或并购零值。

建议在新 guard 内只对标题所在可见结构中的真正引用上下文做大小写无关检查，保留隐藏节点及段落边界的区别，增加以上控制组；保持旧 V1 文件与已有 Input/Run/Result 字节不动。本审阅没有实现修复。

## 本次覆盖与亲自验证

- 按指定 Git 对象审读新 guard、V2 入口、测试增量，及旧 `e01_item_text_28_v1.py`、`ordinary_e01_item_text_input.py`、`normal_zero_ai_results.py`、`deterministic_router.py` 的相关依赖。
- V2 对 `filings` 的全部申报循环，包括空 claim 情况；唯一正文/头文件角色引用、各自长度/哈希、原始 header 与生成 claim 的条目集合及正文引用一致性；后续候选 item 只能引用该发现集合。上述结论为代码路径审阅，未重跑真实材料。
- 新输入具有明确 V2 record type、guard/adapter 哈希和 checks 字段，`verify_current_e01_item_text` 重建全输入后要求完全相等；输出明确语义未执行、Result/Run 未创建、生产未授权。旧 V1 输入直接进入该 verifier 会因重建差异拒绝；这一实际材料执行仅读既有 4 项定向日志，未冒称本次重跑。
- 亲自运行且仅运行获准的 unittest selector：`PYTHONPATH=scripts PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_e01_header_document_guard.E01HeaderDocumentGuardFastTest`，2 项通过（`fast-test.log`）。另执行 6 个很小的内存反例/控制场景，无 SEC/provider/paid 请求。
- 测试前核对 22 个相关工作树文件与 patch SHA 字节完全一致；4 个旧来源/默认执行依赖与 parent SHA 一致（`preflight.log`）。反例之后再次核对实际执行的 guard、V2、旧 reader、router、canonical 和测试文件与 patch SHA 一致（`static-bindings.log`）。
- 独立静态核对 V13/V14 的新增 2 模块及配置绑定哈希/长度、4 个旧依赖绑定、V13 new_rule_files 与 V14 引用的 V13 全 5 文件；均相符。重算 V14 execution authority hash 为 `sha256:3c399cd48b055c79e7a13dccf6795e077cba074d13aee14c4a0525ef54ce5445`，与三份接线收据相符；收据除相应身份字段外无变化。配置及 V13 decision register 除 rule_paths 外相同，未更改默认 flags 或放开生产许可。
- 核对来源出处 Git blob 为 `5118de2ddcf38faba72c2b7578b036d5e43f8485`，原函数文本 sha256 为 `cca3d096f5bc598c8533dca20ca6a0060c723eb46bec92f5c98d99678a0bbadd`，与 source-provenance 一致。

## 仅读既有执行证据及未覆盖

读取 README、source-provenance、binding-before/after、rebind/install/cold 脚本、定向及 fast 日志、installed 与两份 installed-cold 记录，及父代理补充的未提交 `tested-commit-equivalence.json`。补充文件明确原执行发生于提交前最终绑定工作树，`execution_at_commit_claimed=false`，没有把未来 SHA 当成原执行时身份。

既有证据的实际范围为：定向 4 项/17.511 秒；fast 148 selectors/104.546 秒；只安装 Enphase/Pfizer 两家公司保存来源，正文/头文件检查分别 6/9 份、候选 0/3、安装 39.351 秒；另进程冷读 14.821/16.973 秒，验证其各自 V13 权限与 V2 输入。README 的有限范围、零真实调用及不授语义/Result/Run 信用与这些记录相符。本次没有重跑材料测试、全部 fast、安装、冷读、160 份审计或长链，也没有把静态身份核对说成重新认证完整 Requirement 闭包或原件内容正确。

未覆盖：E01 并购语义判断、具体计数/去重、完整召回、全部十家公司正常材料、旧 E01 Result 当前新口径接受、新 E01 Result/Run、390 信用、真实 provider/paid/SEC、生产/active 操作。D02 资料增量不在此次源码审阅范围。同族子代理审阅是工程独立检查，不能冒充独立人工或用户验收。

## 资源及现场

开始 UTC：`2026-10-02T14:35:31.024735+00:00`。
结束 UTC：`2026-10-02T14:43:50.225344+00:00`。
工具调用实际合计 **24**：外层 `functions.exec` 11 次，嵌套 `exec_command` 13 次；其余工具 0。没有达到 80 次/90 分钟上限。普通消息 **3**（2 条 commentary、1 份最终报告），问题 0。

只新增本目录 `conclusion.md`、`preflight.log`、`fast-test.log`、`counterexamples.log`、`static-bindings.log`；没有开发、commit、push、打包、修改任何运行状态、账本、快照或 #47 现场。父代理原有 execution-state 与 tested-commit-equivalence 未提交状态未处理。
