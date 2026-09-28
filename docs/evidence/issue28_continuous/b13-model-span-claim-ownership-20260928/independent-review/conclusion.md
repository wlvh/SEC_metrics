# B13 V8 断言范围与归属：7676f49d 限定独立审阅

审阅对象为 `7676f49d37c02e6bfe597d44ba333cfc4222daab`，父提交 `ba56a51fb069ff53c4b9a831b901c4323c06d534`。仅检查该提交的 B13 V8 断言范围、主体/期间/类别冲突、V7 兼容、V14 绑定与失败关闭；继承 `b13-model-spans-v8-offline-20260927/independent-review/conclusion.md` 对未变部分的审阅。本次结论：**NEEDS_FIX，V8 可保留为暂停的离线候选，不能解除真实执行或原生接受暂停。** 新增测试证明前审三个确切句子的处理已改进，但两个等价表达仍会让错误解释只留下强制暂停码。当前暂停门阻止这些错误成为原生结果；若解除，错误接受风险仍在。

1. **[P1] 单个范围仍可吞掉两条产能断言；分开范围后，第二条也可被错误排除。** 原文 `Our contract manufacturers have production capacity for current demand and plan to add capacity next year.` 同时说现有产能和下一年扩产。用一个 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT` finding 覆盖整句，完整 `validate_interpretation()` 的 `unresolved` 仅有 `B13_MODEL_SPAN_VALIDATION_SUSPENDED`。换成两个不重叠范围，第一条给正确的现有产能标签，第二条 `plan to add capacity next year.` 错标 `other_context / TARGET_REGISTRANT / HISTORICAL`，结果仍仅有该暂停码。`capacity_two_stage.py:759-771` 只数 `manufacturing capacity`、`production capacity` 这类完整词组，漏掉第二条省略了修饰词的 `capacity`；`capacity_two_stage.py:785-787` 在第二个范围未出现完整词组时直接跳过主体、期间和类别冲突检查。这是前审“一个范围吞并两条断言”的同一失败类型，不能以本次宽范围测试通过视为已关闭。需要证明来源中的每条独立产能陈述各有正确归属；关联无法证明时保持具体未决。

2. **[P1] 关系从句没有逗号时，供应商产能仍被归给申报主体。** 原文 `A supplier that we selected has production capacity for current demand.`；把整句错标 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT` 后，完整校验同样只返回强制暂停码。`A supplier we selected ...` 也一样。`capacity_two_stage.py:793-797` 新增的删除逻辑只处理 `, which/that ...,`，随后沿用“产能词前最后一个主体词”的判断，把从句中的 `we` 当作产能拥有者。这与前审的逗号版反例是同一归属问题；不能把逗号变体通过当作主体关系已被证明。需要限定地证明主句产能谓词的主体，证明不了就保留未决，不建议继续仅按标点或关键词扩充替换式规则。

上述反例均用仓库测试相同的 `quantity_source` → `program_source` → V4→V8 请求、完整 `candidate_refs`、原文字节范围和 `validate_interpretation()` 构造；没有改动来源或请求验证器。审阅也确认本次新增测试中的逗号关系从句、`and expect to add manufacturing capacity next year` 分段、错误主体/历史期间/排除类别会产生预期冲突，故不是把所有正向结果都归为失败。新 `current_plan_frame` 对该确切并列句有效；本结论不推断一般英语并列、指代和时态已处理。

**本次亲自执行：** 指定短测 `PYTHONPATH=.:scripts /private/tmp/issue28_py314_venv/bin/python -m unittest tests.vnext.test_capacity_two_stage tests.vnext.test_capacity_reference_contract` 为 **36 tests / OK（7.106 秒）**。另运行只读 V7 请求身份比较，得到 `V7_REQUEST_BYTES_UNCHANGED`（15,826 字节、同一 request_id）；从代码差异看，新增相对从句删除、宽范围检查和并列计划上下文均限于 V8，V7 原有判断条件等价。当前 V14 `load_requirement_snapshot`、`validate_execution_authority` 与三份 `validate_wiring_receipt` 亲自重验通过，闭包 `sha256:79958e52a5cc0869f4610eb8bf6d49082a32749276d13f3936bb7de22abfefa8`，执行权威哈希 `sha256:030e03a169e48926b3cb182a5f8aded6511f6365f58041c25b464a82a3e7b813`，`capacity_two_stage.py` 字节哈希 `f58588a8db96c6102a6105913309dc43f84cc436852ea8c0188389f0579590e2` 与两个 V14 字段一致。三份接线收据的补丁仅更新当前哈希，没有新增调用或生产权限。

**只读日志与未验证边界：** 本提交的 `fast.log` 记录 135 个 selector 中 134 个通过，`test_invocation_control` 在并行 30 秒门限下返回 124；整套快速测试不能记通过。`invocation-standalone.log` 记录该模块单独 25 项通过，本审未重跑。未执行真实 provider/SEC、长材料测试、模型解释、完整 B13 原生公司链或远端 CI；本次证据不证明模型会给出正确范围，也不更新 190/191/192 的历史身份或任何执行授权。

## 8990fb9d 相对 7676f49d 的增量复审

对象为 `8990fb9d401e8d9d843ecd122d74bebb15fe7e46` 相对上节已审提交的新增差异。结论仍为 **NEEDS_FIX；V8 保持暂停的离线候选**。上节两个确切 P1 反例已有有界处理：`... and plan to add capacity next year` 的宽范围得到 `B13_MODEL_SPAN_MULTI_CAPACITY_ASSERTION`，分开的错误历史/背景标签得到具体期间与类别冲突；无逗号供应商从句的错误 `TARGET_REGISTRANT` 标签得到 `B13_CLAIM_SUBJECT_AMBIGUOUS`。以下是对同一新增机制的正反例检查，不能由这几个通过的断言推断语义闭包。

1. **[P1] 一条范围吞并现有产能与扩产计划的根本风险仍存在。** `Our contract manufacturers have production capacity for current demand and plan to double it next year.` 明确把下一年的扩产计划与现有产能分开；单个 `physical_capacity_context / TARGET_REGISTRANT / CURRENT_REPORT` finding 覆盖整句，在本 SHA 的完整 `validate_interpretation()` 中仍只返回 `B13_MODEL_SPAN_VALIDATION_SUSPENDED`。`capacity_two_stage.py:760-780` 把“独立断言”近似成同句 `capacity/capabilities` 名词次数，代词 `it` 承接产能时仍只有一个匹配。不能在解除暂停时把该响应视作完整分类；需要在限定来源结构内证明独立陈述的覆盖，无法证明时具体未决，而不是继续仅添加词面变体。

2. **[P2] 扩大的名词检查会误拦明确无关的储存能力。** `Our contract manufacturers have production capacity for current demand and our storage capacity is ample.` 的唯一 B13 产能 finding 正确覆盖前半句时，返回 `B13_CLAIM_UNCOVERED_PHYSICAL_SOURCE:B0`；若再把后半句正确标成 `other_context / TARGET_REGISTRANT / CURRENT_REPORT`，则返回 `B13_CLAIM_TARGET_CAPACITY_EXCLUDED:B0`。`capacity_two_stage.py:766-780` 把同句所有 `capacity` 都当成待覆盖的物理产能，`capacity_two_stage.py:794-801` 又把后句的储存能力当成省略修饰词的生产产能。现有扫描提示本来要求不要枚举普通产品储存背景；这条合法输入不应因非 B13 容量被迫未决，且“补一条背景 finding”也无法绕开误拦。

3. **[P2] 供应商的正确排除标签也被新歧义分支拒绝。** `A supplier that we selected has production capacity for current demand.` 给出正确的 `other_entity / OTHER_ENTITY / CURRENT_REPORT` finding，完整校验仍返回 `B13_CLAIM_SUBJECT_AMBIGUOUS:B0`。`capacity_two_stage.py:811-825` 把主句的 `supplier` 与限制性从句中的 `we` 视作同等产能主体线索。这避免了上轮错误接受，却同时阻断了有明确语法主体的正确答案。应让无法证明的归属保留未决，同时保留此类合法主体关系的正向路径。

**本轮亲自执行：** 与仓库测试相同的来源构造、V4→V8 请求、完整扫描候选和响应验证重现上述输出；指定短测 **36 tests / OK（8.266 秒）**。只读 V7 身份比较再次得到 15,826 字节与同一 request_id；V8 强制暂停仍在 `validate_interpretation()`，测试边界通过。V14 快照、执行文件字节和三份当前接线收据重验通过：闭包 `sha256:ad3c189d7be270bfdeb2ff0049eb20015f405d2d23479077de81a94cc4a14441`，执行权威哈希 `sha256:69b561b3f39a1c27474e137d1230f2742ad937af917c61f31482b090ccbfd9f6`；三收据差异仅改当前绑定哈希。正确分开的 `plan to add capacity` 在新局部检查中没有宽范围或主体错误码，但原有语义检查仍返回 `B13_VISIBLE_SOURCE_ROLE_NOT_ESTABLISHED`，不能将该测试写成完整正向接受。

**只读日志与未验证边界：** 本 SHA 的 `followup-fast.log`/`.exit` 是 **FAILED，135 个 selector 中 134 个通过**；失败的 `test_invocation_control` 返回 1，`process.exitcode` 为 `None`，本审未重跑全套或改动该测试。`followup-fast-launch-empty.log` 为空，不能计作一次测试。未执行真实 provider/SEC、长材料测试、模型解释、完整 B13 原生公司链或远端 CI。历史 190/191/192、生产权限和暂停门均不因本审阅改变。
