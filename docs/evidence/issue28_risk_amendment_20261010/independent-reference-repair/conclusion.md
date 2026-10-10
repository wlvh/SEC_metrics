# 4ba6a44 编号引用修复增量的限定独立审阅

结论：**CHANGES_REQUIRED（仅本轮新增差异）**。原审的两个精确错误放行场景已关闭，但新编号列表解析仍会忽略明确列在第二位的 Item 1A；完整 API 在独立正文和合法 caution 引用残余两处均可复现错误放行。此处是一项 P2 的两个入口表现，不重新签署原 a915 完整接口审阅。

## 受审绑定与范围

- 精确 SHA：`4ba6a440cb708711794f415cb39b965d2fbf2f91`；比较 base：`a915570a0961509d93c0759491cefebb444da988`。
- 工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-risk-amendment/SEC_metrics`；开工和最终核对 HEAD 一致，两个受审文件与精确 SHA 的 Git bytes 一致。
- 仅审 `scripts/vnext/risk_heading_amendment_input_v1.py` 与 `tests/vnext/test_risk_heading_amendment_input.py` 相对 a915 的差异：Item/Items 编号、列表、跨度检查；合法 caution 引用删除后的残余处理；PROCESSING_FILES 增加实际 serializer/canonical 依赖。
- 原审 `../independent-review/conclusion.md` 保留 CHANGES_REQUIRED 的历史结论。身份、默认接口、完整 note、原件校验及其余未变逻辑复用原证据；本轮没有重审、重放大原件或运行整公司。

## 原两个精确场景的有限关闭证据

原独立正文 `This Amendment replaces the disclosures in Items 1A and 1B of the Initial Form 10-K.`，以及原合法 caution 引用之后的 `Items 1A and 1B are replaced by this Amendment.`，现在均经完整原件/修订 source frame 返回 `WITHHELD / UNRESOLVED`，reason 为 `RISK_AMENDMENT_RISK_SECTION_REFERENCE_UNRESOLVED`，引用登记为 `UNRESOLVED_RISK_SECTION_REFERENCE`。独立重放见 `directed-references.log`。此关闭只针对上述确切输入及上下文，不使原独审的其它范围改签为 PASS。

## 新发现 P2：列表分隔符不能解析时，被当成没有风险章节引用

位置：`scripts/vnext/risk_heading_amendment_input_v1.py:74` 的 `separator`，连带 `:75` 的列表捕获和 `:104` / `:109` 的跳过/放行。

新函数只接受逗号、`and`、`or` 与跨度词/横线。遇到 `Items 1B & 1A`，捕获在 `1B` 后结束，随后找不到带 Item 前缀的第二个 `1A`，于是返回 false。下面的完整、身份和 note 正确的构造修订即可复现：

```html
<p>This Amendment replaces the disclosures in Items 1B &amp; 1A of the Initial Form 10-K.</p>
```

正文中的 `&amp;` 正常解析为可见 `&`，明确编号引用和替换声明都在原文内。完整 API 实际返回 `INPUT_PROPERTY_PROVEN / PART_III_ADDITION_WITH_NO_AMENDED_ITEM_1A`、`issues=[]`、`risk_section_references=[]`，错误授予原标题输入信用。把同一段放到唯一允许的 caution 引用之后，API 又返回 `INPUT_PROPERTY_PROVEN`，整段被登记为 `INITIAL_FILING_CROSS_REFERENCE`。合法句子删除后的第二条明确编号引用仍被漏掉。

同一个机械问题也独立复现于 `Items 1B and/or 1A` 和 `Items 1B; 1A`；三种写法各在独立正文与 caution 残余出现，合计 6 个完整 API 错误放行。这里没有要求分类任意英语含义：第二个 1A 已被直接列名，遇到不支持的列表形式至少必须保持 WITHHELD，不能把未解析的引用视为没有引用。各原文、期望、实际决定、引用状态和 scope_id 保存在 `directed-references.log`。

建议在现有 Item/Items 机械识别边界修补上述已证实列表缺口，并添加正文及 caution 残余回归；不扩建语义、时态、主体或未知段落分类器。审阅者未改开发代码。本缺口在旧单数实现也存在；本报告将其标为这次列表修复仍未覆盖的直接变体，不声称是新提交引入的历史回归。

## 已验证的新增行为与复用

1. 指定命令原样执行：`python3 tests/required_unittests.py tests.vnext.test_risk_heading_amendment_input tests.vnext.test_amendment_note_layout tests.vnext.test_instant_amendment_paragraph_api`。29 项、failure/error/skip 均为 0，exit 0，unittest 0.283 秒；命令墙钟约 0.455 秒。使用 `PYTHONDONTWRITEBYTECODE=1`；见 `required-tests.log`。通过不能覆盖上面的新增反例。
2. 有界编号探测 20 项，完整 API 探测 16 项；没有重跑完整来源/三公司/年度大材料。`Items 1B and 1A`、逗号列表、`Items 1 through 2`、`Items 1 to 1B`、三类横线跨度正确发现 1A。单独 `Item 1B`、Items 10–14 及 `Exhibit 10.1A` 在机械检查没有误认；完整 API 的无关项正例及其合法 caution 对照均通过。直接探测的 socket connect/connect_ex/DNS 被禁止。
3. PROCESSING_FILES 新增的 `normal_annual_input_v2.py` 实际拥有被调用的 `exact_json_value`；`canonical.py` 实际拥有严格 JSON、内容哈希以及 serializer 内部的 canonical 校验。增量登记符合真实依赖，不重建递归权限证明。
4. 只读核对现有 `../reference-repair-actual-source.json`：记录执行 2.892776541877538 秒，12 个 tested_processing_files SHA 均匹配当前受审文件；scope_id `sha256:011bfe85ff98017aa34ea4abd6c48ae2bb1512c9c5dd54606dd16c000a0116ef`。来源摘要、原件 SHA/引用、scope_id、source_scope_original_id、details、decision/classification/input_class/issues/policy_hash 均与原 final-actual-saved-source.json 一致。此为既有执行证据的字节绑定检查，未宣称本代理重新执行实际源或原记录原本标为 committed-SHA。见 `saved-evidence-binding.log`。

## 起止、调用与权限边界

- 可审计开始：2026-10-10T02:39:01.205136+00:00；结束：2026-10-10T02:57:32.967005+00:00；远低于 90 分钟。
- 工具保守计数 20：functions.exec wrapper 7，nested exec_command 13，包含本次写入和最终核对；上限 80。普通消息合计 1（仅最终报告），过程 commentary 0、问题 0；无 followup/reset/spawn。
- 新 SEC/provider/paid：0/0/0；无网络、模型、账户、commit/push、tar、#47 工作树或状态操作。仅写当前 independent-reference-repair 目录的 conclusion.md 与 4 份日志。
- 结论仅为新差异的有限独审，不能授予原完整接口、模型判断、财务输入、D01 结果、整公司、全 PR、Ready、合并、正式采纳、部署或 active 信用。未知命名引用及未能解析的直接编号引用仍应保持 WITHHELD。
