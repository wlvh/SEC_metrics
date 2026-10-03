# B13 V6 断言范围回修：限定独立审阅

- 精确对象：`a96fbe21756dceca007e15c84bb3380251847517`，相对父提交 `151ce51f2217a2b1bd4e5b71492d47d67c2e9242`。只审本次 B13 V6 回修增量、对应测试、V14 执行绑定和新接线证据。
- 结论：**NEEDS_FIX**。前驱审阅的两个原始反例已分别得到正确的未决与通过结果；但本补丁又引入一条可通过原生语义接受门的错误历史排除，以及一条正确的当前／计划分类被误拦的路径。两者均用完整合成来源、扫描、V6 响应及原 V4 来源验证器复现，并以父提交代码作差异对照，见 `adversarial.log`。这些不是实际模型响应或生产事故。

## P2：删除“同一区间多产能短语”保护后，可把当前产能整句排为历史

原文：`Our contract manufacturers had manufacturing capacity for obsolete products, but currently have production capacity for current demand.` 第一部分是过去的产能，`but` 后是同一主体当前的产能。扫描选中 B0；V6 响应只给完整句一个 `historical_statement / TARGET_REGISTRANT / HISTORICAL` finding，并把 B0 的完整字符区间赋给它。父提交的 V6 返回 `B13_ASSERTION_MULTIPLE_PHYSICAL_CLAIMS:B0` 未决；本提交返回 `unresolved=[]`。

原因是 `capacity_two_stage.py:633-635` 只要求每个产能短语被某个区间覆盖；原来的多短语未决检查被完全删除。新 `all_occurrences=True` 检查虽然逐个找短语，但 `:124` 将句子按 `but` 拆开，后半句省略了已在前半句明确写出的主体，`:134-138` 因而识别不到它，`:717-723` 不加未决。原 V4 验证器也没有拦住该完整响应。`capacity_native_assessment.py:36-38` 的原生门只要求未决为空且无显式 `UNRESOLVED` 标签；隔离地给内部 record builder 合成阶段证明后，它产生 `EVIDENCE_CHECK PASS` 和错误的 `HISTORICAL_STATEMENT` candidate（`native-gate.log`）。该合成调用绕过了真实登记阶段身份检查，**不证明已取得原生执行信用**；它证明语义接受门对这个错误标签没有后续保护。若其他组也无当前 finding，后续 B13 文本路径会把当前相关来源当作缺席候选。

修复需同时保留“同一断言两种等义说法可通过”和“两个时间／类别不同的实际声明不能合并成一个标签”。不能恢复按词组数量一概拒绝；无法确定两处关系时应留未决。

## P2：代词区间扩为整句，使两个合法 finding 必然重叠

原文：`Our contract manufacturers have production capacity for current demand; they plan to add manufacturing capacity next year.` 这是一个当前产能声明加一个后续扩产计划，主体由分号前的 `Our contract manufacturers` 明确给出。分别给第一分句 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT`、第二分句 `planned_physical_capacity / TARGET_REGISTRANT / CURRENT_REPORT` 时，父提交 V6 的两个非重叠区间得到 `unresolved=[]`。本提交的 `_assertion_segments()`（`:576-580`）只给第二个以 `they` 开头的分句放行**整个句子**的区间；改用这个合法区间后与第一 finding 重叠，`:630-631` 返回 `B13_ASSERTION_OVERLAPPING_RANGES:B0`。若继续用第二分句自身区间，又会被 `B13_ASSERTION_NOT_COMPLETE_SEGMENT` 拒绝。因此正确的两类声明无法同时取得空未决集，见 `adversarial.log`。

这里应把代词的先行词与第二断言绑定，同时允许两个不同声明各自拥有不重叠的分类范围；不能把整句机械地视作一个不可分声明，也不能重新放行没有前文绑定的孤立 `they`。

## 已确认的回修范围与证据边界

- 对前驱分号 `they have` 错误排除，单独截取后半句现在报 `B13_ASSERTION_NOT_COMPLETE_SEGMENT`；完整句错误排除进入 `B13_ASSERTION_EXCLUDED_CURRENT_TARGET_REQUIRES_REVIEW`。指定短测还验证内部原生接受门及登记重读入口均因该未决拒绝。一个断言中的 `manufacturing capacity, including production capacity` 正确分类现在是空未决。以上是有限合成正反例，不说明真实模型会作何回答。
- 用父提交源码在当前进程内生成相同 V5 输入，默认 `interpretation_request()` 的请求字节及 `validate_interpretation()` 的检查对象与本提交逐字段相等（`v5-compat.log`）；本补丁没有发现 V5 默认路径变化。
- 指定三套短测 **32/32 通过**（`short-tests.log`）。已存 `assertion-scope-repair-native.log` 是一次 **125.635 秒**禁网单组录制／重读通过；本审阅只读其日志，未重跑。`provider-wiring-test-assertion-repair.log` 记录禁网工厂测试通过。旧完整默认 Run 日志有失败，本审阅没有把它们写成本提交的完整 Run 成功或把失败归因于本次 V6 回修。
- 本地加载 V14 Requirement 得到 closure `sha256:805130a44789ce57fe7d8f5149918c06612b21de2b06229edabcade9e0c7f9ff`、execution authority `sha256:a96131315e295cd3d8d9c97ce6e349f491687d90a5f8e2beb68fbad7d78251c2`。两个更改文件的字节与 manifest 两处登记一致；provider 收据 55 项、SEC 收据 15 项证据哈希均匹配当前文件（`binding-check.log`）。两收据均记本轮新调用为 0；哈希相符不能消除上述语义缺陷。
- 本审阅未发 provider／SEC 请求，未重跑超过 120 秒的测试，未形成完整 B13 公司结果，未验证真实模型质量、190 目标混合组合或生产采纳；未操作 #47／PR52。既有 `execution-state.json` 工作树修改未由本审阅触碰。
