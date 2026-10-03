# B13数量增量独立审阅：发现限定上下文错误接受

范围：a56e0ae→989c564新增数量读取/分类守卫、数值Run接线及对应测试；另复核原68税收抵免内容守卫。当前文件的计数/分组/request_context_format变化仅作版本定位，不在本审阅通过范围；D04分支、6e5 D03和历史完整模块未获覆盖。审阅者此前仅调查实际来源，未实施这些代码。

## P1：假设数量可被强制赋予真实数量角色

用原`quantity_source()`工厂生成合法合成原件、原source/ref/hash，数量两句仍是现有正例：

- `For fiscal year 2025, we produced 80 widgets worldwide.`
- `For fiscal year 2025, our available annual production capacity was 100 widgets worldwide.`

增加以下两种明确原件上下文分别探测：

1. `<h2>Hypothetical example:</h2>`后有两个说明段落，再出现两句数量。标题作用域未被新同级标题结束，但数量读取只看前2块，已越过标题。
2. 两句数量放在同一段落，后接`These quantities are hypothetical examples, not actual production or available capacity.`。读取逐句匹配数量，未核对同块后置限定。

两个反例均实际：`calculate_source_comparable_pair`计算0.8并声明source_assignments_independently_verified=True；`validate_response`对错误ACTUAL_PRODUCTION+AVAILABLE_CAPACITY接受、unresolved=[]；原生`build_acceptance`返回PASS。合理的非实际角色OTHER_CONTEXT或CONDITIONAL_OR_BOILERPLATE反被`B13_SOURCE_QUANTITY_CLASSIFICATION_CONFLICT`拒绝。`result.json`保存完整HTML及三种标签的结果；`probe.py`可复验。

这是新增来源角色守卫与数值提取共用的不完整上下文问题，不能称作无披露或仅误拦截。需要用原件证明标题作用范围，并让明确同块后置否定限定对应数量；数量提取与角色检查使用同一规则。不要扫描全文hypothetical后否定其他独立实际章节，也不能把固定前2块改成另一个任意距离。

本次没有执行带该错误原件的完整磁盘Run，因此不称已观察到最终数值误发布。静态核对当前数值分支直接消费此计算结果；原生接受也未挡住错误标签，来源/身份合法本身不能弥补内容关系缺口。

## 有限有效范围

无假设的原正例同样实际0.8、原生接受PASS；已读数值代码确实重建原件字节/段落、数量/倍率、期间、主体、产品及设施范围，复用原Calculator。数值记录重放比较完整预期记录集合，不能仅重签0.81替换0.8。存在这一真实实现进展，不能再描述成“数值完全未实现”。

独立运行15项现有数量/角色/原68测试通过0.084秒（existing-tests.log）。其中原68原请求响应由当前检查拒绝、原SUCCEEDED断言成立；先前本任务还确认全部7个原文件哈希未变，见父目录summary。税收抵免与借款额度的已知反例拒绝有效，不代表所有混合叙述的角色均被验证。

单独尝试数值磁盘Run测试因当前`r6_regulatory_semantics.py`与执行绑定未同步而失败（numeric-run.log，1.291秒），在数值分支执行前退出。保留失败，不将旧CI34943286777或源码断言当成当前独立执行通过。受影响完整Run在共享实现固定后再补验。

实际Ford/Enphase原件数量调查见父目录README：季度美国制造能力、全年销量/出货、非合并联营企业批发子集、取消车型和设施数都不能拼成可比量。当前缺成对数量证明/完整真实语义处理；此独立审阅新增真实公司B13结果0，不给真实披露限制或390完成信用。八家结构性不适用维持原含义。

## 版本与边界

reviewed-functions.json保存相关函数文本/哈希（探针前后不变），其中含版本定位的整个prepare_case/_prepare文本不意味着覆盖其D04或新context-format分支。

- `_quantity_context_qualified`: ef93fb8bcbf7802c2e58b7ed1057df31a81e4a2feac0d1ad950b4940f20bdead
- `explicit_annual_quantity_statements`: e0ab0d7bef37e33b31ef05502f33880bccd7e872b1b7db46f0ddb7c871b47009
- `calculate_source_comparable_pair`: 30091a79f04dde6dccd3c5eeb5eb1d3b337c44ff9b635c9800ed9bec434c7df2
- `validate_explicit_quantity_classifications`: 56b41f03afd1afcd041cbe864a6749cf85babe70fe63c6663caf1b7be9fd6ce1
- `_tax_credit_without_capacity`: c70735e8389181222dfb173b58f7ed83fb2bba91c0af907ca8c4eab78ac187a0

结论：本轮数量作用域存在已复现P1，真实B13受影响路线继续暂停；不是独立审阅待办，也不是全模块批准。未改实现，调用0/0/0。随后若本审阅者获派实现修复，该后继工作属于工程实施，需要其他审阅者核对，不以本报告自批修复。
