# 8fd9d912 B13 V7 限定独立审阅

**对象：**`8fd9d9129978b9351ceca33900a8a9e62c7a0783`，父提交 `1613dab6b4d41e378c5f6d3ef922789f14ff0331`。仅审委托列出的 V7 代码、测试、V14 绑定和 `b13-claim-context-v7-20260927/` 证据；先复用了 V6 语义回修 `a96fbe2` 的 `NEEDS_FIX` 与 V6 暂停 `d41a5e9` 的限定结论，没有重审全 PR。

**结论：V7 语义候选 NEEDS_FIX；当前暂停与入口拒绝 PASS_WITH_BOUNDS。** V7 在已有合成正例中，确实使分号后的“当前产能＋扩产计划”和 `but` 后的“历史产能＋当前产能”使用不重叠断言、共享整句上下文；旧 V6 的这两条互相牵制的反例因此有了可表达的形式。但下列新反例说明，不能移除 `B13_CLAIM_CONTEXT_VALIDATION_SUSPENDED` 或将 V7 当作可接受的 B13 判断。这里的“错误接受”指离线语义诊断除统一暂停码外没有留下未决，**不是**当前代码已生成 Evidence、Result 或 Run。

## P2：代词从上下文借错主体，正确主体反被拦截

完整合成块：`Our contract manufacturers operate plants; a supplier reported delays; they now have production capacity for current demand.` 第三分句的 `they` 是复数；前面的 `a supplier` 是单数。将第三分句标为 `other_entity / OTHER_ENTITY / CURRENT_REPORT`，V7 仅返回统一暂停码；将其标为本公司合同制造安排的 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT`，却额外返回 `B13_CLAIM_SUBJECT_CONFLICT:B0`，见 `subject-probe.log`。`capacity_two_stage.py:725-731` 从整句前文取**最后一个**词面主体标记，不核对代词与先行词关系。共享上下文保存正确，但现有主体判定可把它错误地用于排除。应为代词建立可核验的先行词关系；无法唯一确定时保留未决，不从最近的词面标记直接赋义。

## P2：`and` 连接的两个实际声明无法各自取得有效范围

完整合成块：`Our contract manufacturers have production capacity for current demand and plan to add manufacturing capacity next year.` 前半是当前产能，后半是扩产计划。`capacity_two_stage.py:633-651` 只在分号、`but`、`whereas` 分割，故整个句子只有一个可用断言范围。只提交一个 `physical_capacity_context` finding 时，两处物理产能词组都被范围覆盖，离线检查仅返回统一暂停码；提交两个同范围 finding 得到 `B13_CLAIM_OVERLAPPING_RANGES:B0`；把范围拆在 `and` 处则抛出 `B13_CLAIM_NOT_COMPLETE_SEGMENT_OR_CONTEXT`。见 `adversarial.log`、`adversarial-followup.log`。这同时存在吞并不同分类与误拦合法双 finding 的风险。应允许可证明的并列独立分句分别拥有范围，或对不能安全拆分的多声明保留未决；仍须保留“一个断言两种等义产能说法”的合法路径。

## P2：明显错误的期间和条件分类可绕过新增矛盾检查

- `Our contract manufacturers can provide production capacity for anticipated demand.` 被标成 `historical_statement / TARGET_REGISTRANT / HISTORICAL`，离线检查只有统一暂停码；同句正确的当前定性分类也只有统一暂停码。`can provide` 是当下能力表述，原文没有更早期间。
- `Our contract manufacturers have production capacity for anticipated demand.` 被标成 `conditional_statement / TARGET_REGISTRANT / CONDITIONAL`，离线检查只有统一暂停码；原文没有假设条件。
- `If demand rises, our contract manufacturers could provide production capacity for anticipated demand.` 被标成 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT`，离线检查也只有统一暂停码；原文是有条件的可能性。

这些类别与 `catalog/r5/capacity_semantic_review_v4.json:37-44` 的定义不符。`capacity_two_stage.py:713-714,732-748` 只看一组时态词，未覆盖 `can/could` 的不同含义，且对 `CONDITIONAL` 时间标签及 `CONDITIONAL_OR_BOILERPLATE` 类别没有相应矛盾分支。应在可证明的情形核对时间与条件；无法分辨的情形保留未决，不能机械地把 `can` 或 `could` 都当成现在时。同一探针中，把实际当前产能误标为 `planned_physical_capacity` 另被继承的 V4 规则报 `B13_VISIBLE_SOURCE_ROLE_NOT_ESTABLISHED`；因此问题限于上述漏检类别，不是所有错分类都放行。见 `adversarial.log`、`adversarial-followup.log`。

## 已验证的保护与证据边界

- **隔离执行：**指定短测 31/31 通过，`git diff --check` 通过。`guard-probe.log` 另外以 V7 请求核对录制普通判断、录制二阶段判断、直接原生接受、保存扫描接受、登记接受及回读路由，六者均在读取扫描/账本或构造结果前拒绝。`validate_interpretation()` 在 V7 分支固定增加 `B13_CLAIM_CONTEXT_VALIDATION_SUSPENDED`（`capacity_two_stage.py:902-913`）；共享原生构造器要求 `unresolved` 为空。当前没有由上述反例取得原生信用的路径。检查只覆盖这些直接入口，不等于完整 native Run 或公司组合冷读。
- **旧请求与绑定：**独立重跑 `verify_legacy_requests.py`：与父提交的一个固定样例比较，V5/V6 请求字节及 ID 相同，V5 检查对象相同；这不声称所有旧输入已遍历。重跑 `verify_current.py`：V14 closure `sha256:94d32ea6d0d8eb55b99c1e64f3ad79b86190f83682c4db839f7da65669fbd709`、execution authority `sha256:d456fd2dca1e6e5264e1ca471159592c794752829348aa9927f62331b8278a47` 有效，当前 provider/SEC/普通刷新收据各 95/50/50 项证据哈希匹配；这是当前绑定检查，不证明 V7 语义正确或授予调用权限。
- **旧日志读取：**已读 V6 两份独审结论与本补丁提交的 `README.md`、原短测和身份日志，用于限定本次增量与历史状态；它们没有代替上述重新执行。两个本次对抗探针使用合成 HTML 财报块和原 V4 验证器，未请求真实模型，也未验证真实来源中的模型表现、扫描遗漏率、完整 B13 数值、十公司组合、原生持久化或正式发布。

本审阅没有 provider/SEC 请求、commit、push、账本操作、生产操作或 #47/PR52 操作；未改父任务状态文件。现有 `execution-state.json` 工作树改动在进入审阅前已存在，本审阅未触碰。
