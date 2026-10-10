# a915570 限定独立审阅结论

结论：发现 1 项 P2 错误放行，需修复后再判断本次有限输入接口是否可接收。指定测试全部通过，实际保存原件正例也能重复得到相同来源范围身份；这两项成功没有覆盖下面的直接反例。

## 绑定、时间与资源

- 工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-risk-amendment/SEC_metrics`。
- 精确受审 SHA：`a915570a0961509d93c0759491cefebb444da988`；base：`f6ef7886d6630f7675c25cd42e306c373ab05769`。开工与结案核对均一致。
- 开始：2026-10-10 02:22:59 UTC；结束：2026-10-10T02:28:23.767624+00:00。
- 工具调用保守计数：30（functions.exec wrapper 11 + 其内部工具调用 19，包含最后产物核对）；硬上限 80。本次无重试、无子代理。
- 父代理协作普通消息：1（最终报告）；另有 2 条过程 commentary。将所有文本都计入时合计 3；没有提问。剩余工具预算 50，保留回修的检查空间；追加文字若也按全消息上限计，需由父任务重新明确额度。
- 新 SEC/provider/paid 调用：0/0/0；不调用网络，不操作账户，不写 #47 工作树、状态、旧失败或原业务记录，不 commit/push，不打包。
- 仅写本目录 `conclusion.md` 与 3 份日志。受审文件及原 evidence 固定，旧年度政策、财务输入规则与批准 D01 Spec 无差异。

## P2：直接复数 Item 1A 引用被遗漏，仍授予原标题输入信用

位置：`scripts/vnext/risk_heading_amendment_input_v1.py:79`（引用识别）；影响 `:82-88` 的跳过和允许引用判断。

`mentions` 只识别 `item 1a` 的单数写法以及 `risk factors`。完整、身份与原报日期正确的 Part III 修订，附加下面这段可见原文时：

```html
<p>This Amendment replaces the disclosures in Items 1A and 1B of the Initial Form 10-K.</p>
```

当前 API 返回 `INPUT_PROPERTY_PROVEN / PART_III_ADDITION_WITH_NO_AMENDED_ITEM_1A`，`issues=[]`，`risk_section_references=[]`。这段话明确指向 Item 1A 并声明替换，属于已经发现的输入冲突；并非要求系统推断隐藏风险或扩大指标定义。

同一缺陷在允许的 caution 引用后也会发生：

```text
These risks, uncertainties and other factors are discussed in “Item 1A. Risk Factors” in our Initial Form 10-K. Items 1A and 1B are replaced by this Amendment.
```

当前把整个段落登记为 `INITIAL_FILING_CROSS_REFERENCE` 并放行。移除允许引用后，剩余的复数 Item 引用没有触发 unresolved。单数对照 `... in Item 1A ...` 正确返回 `WITHHELD`，因此这不是构造材料绕开身份、note 或已知来源守卫，而是新引用识别的实际漏判。

完整结果见 `directed-counterexamples.log`。建议只修正 Item/Items 的明确编号引用识别，并加入正文、caution residual 两个失败回归；继续保留完整 source blocks 与 WITHHELD，不建立通用英语语义检查器。修复责任仍属于开发者；审阅没有修改代码。

## 已覆盖检查与证据

1. 指定命令 `python3 tests/required_unittests.py tests.vnext.test_risk_heading_amendment_input tests.vnext.test_amendment_note_layout tests.vnext.test_instant_amendment_paragraph_api` 实际执行 27 项，0 failure/error/skip，exit 0；unittest 0.251 秒，命令墙钟约 0.434 秒。见 `required-tests.log`。
2. 额外 8 个有限完整 source-frame 检查：基线通过；上述两个复数引用错误通过；单数冲突、引用原文、note 主体、原报日期和完整 note 添加其它目的均拒绝。实际 socket connect/DNS 被禁止。见 `directed-counterexamples.log`。
3. 只读实际已保存的 Paramount FY2025 一对原件，真实保存请求/body 由 `verify_saved_inputs` 重核，纯 API 2.882 秒。原件 3592 块、修订 1596 块保留在完整 `source_scope`；来源 SHA、SourceReference、消费文件 SHA、scope_id、原 source_scope_id、details 均与 `final-actual-saved-source.json` 精确相同。允许风险引用为块 79、caution 78、首个 Part III 81。见 `actual-source-review.log`。没有写回原 reproducer 的 JSON，也没有用历史 38 标题答案作输入。
4. 静态读取新 API、测试和 workflow 的实际增量；读取必要 annual v1/v2、完整 note grammar、paragraph/可见块及字节校验、批准 D01 定义；仓库架构/能力/交互/测试及 PR 治理只按本来源 API 相关条款解释。workflow 在 scripts 路径变更或新测试路径变更时触发，新增 step 明确运行这 3 个模块，并由 required runner 拒绝 unexpected skips；未声称远端 CI 已执行。
5. 新对象仅列 `D01` 与新 input class；完整原/修订源文档留存并绑定范围哈希；身份、字节真实性错误在 limitation 转换之前传播；未知目的等来源限制返回 WITHHELD。旧默认 source scope 的 D01 not-covered、financial clearance 与源文件未被改写。明确的 no-effect、financial、subject continuity、metric result、acquisition、production 字段仍为 false。
6. 固定 `0d862263` 的对方 selected-subject README 只读核对：当时的真实消费失败与已保存修订是准确依赖背景，本审阅没有消费其旧答案或把该来源检查写成对方公司完成。

## 未覆盖与权限边界

本审阅不重审旧 annual policy 的所有逻辑，不声称任意英语正文都语义无影响，不运行整公司/全年度、长材料或模型；不验证 #47 接入、保存/重复/独立 CSV 出口、完整选源中的全部修订枚举或其它指标。这一 API 是逐原报/修订对的有限输入证明，调用者仍必须对每一份所选修订分别检查，全部合格后才能消费原 Item 1A；逐对通过不授予整个修订集合信用。

结论仅覆盖上述确切增量与实际检查；不是全 Source、D01 业务结果、全 PR、真实获取、Ready、合并、正式采纳、部署或 active 批准。
