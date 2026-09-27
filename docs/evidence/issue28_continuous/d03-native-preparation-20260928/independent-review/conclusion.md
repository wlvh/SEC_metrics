# D03 原生输入准备：精确补丁限定独立审阅

**结论：PASS_WITH_BOUNDS，仅认可离线请求选择。** 对象是 `8c6b2fb0b96a6bf08462dd52f8fd4fa1c64befbf` 相对 `49f61a9f7ed7ec86c1266a2e1c3b6e37d3bbe954` 的 `d03_native_preparation.py`、对应测试、fast selector 和本目录证据。未发现阻断当前只读准备的缺陷；返回结构**不是可直接授予原生信用的凭证**。提交另改了 `continuation.md` 和 `execution-state.json`，不在本审阅裁定范围。审阅开始前 `execution-state.json` 已有他人未提交改动，我未触碰。

1. **来源、分组与覆盖。** `prepare_native_input()` 固定当前代码根和请求格式，从保存来源重新生成 D03 来源及分组；组内单元按顺序拼接必须与来源完整 `required_unit_ids` 相同。上游 `requests_from_source()` 还核对来源内容摘要和该完整单元序列。每个组保留原请求 ID，后继请求的来源 ID、公司、完整原单元和 `required_candidate_assessments` 必须相同；原、有效请求 ID 各自不能碰撞（`d03_native_preparation.py:25-60`）。`candidate_request()` 在实际路径重建并比较已保存原请求，然后重新计算后继请求 ID。JPM 保存来源正例在最终已存日志中为两项测试的一项；另一项的漏单元、漏必评、错前驱与错代码根是**合成替身反例**，不证明十家公司或真实响应均完成。
2. **旧来源事实信用。** 仅 `source_statement_facts` 非空的组被转换为逐候选后继；后继不含该字段，提示和响应协议改为每个候选单独审阅，并仅保留原请求 ID 作追溯（`d03_native_preparation.py:36-50`，`regulatory_fact_review.candidate_request()`）。无事实的组保留原请求及空列表；空列表不会触发旧验证器的肯定事实约束。返回的 `groups` 不暴露 `original_request` 正文。这里证明的是请求输入选择，未检验模型判断、跨组调和或原生接受。
3. **执行和信用仍关闭。** 新函数没有调用传输、持久化响应或创建 Candidate/Evidence/Result/Run；返回三个权限或结果标志均为 `False`。在目标 SHA 中，`scripts/` 和 `tools/` 没有调用 `prepare_native_input()` 的执行入口，现有真实请求校验也不会把这个后继对象当作已获准的原生执行。没有据此申领调用或改真实账本。

**后续接线前必须处理的身份边界。** 返回的 `source`、`groups`、`effective_request` 和 `group_mapping` 是可变字典或列表；`input_id` 只在返回前对摘要、组映射和单元 ID 计算一次，之后没有冷读或重新核对入口（`d03_native_preparation.py:61-71`）。例如返回后改动某组 `effective_request` 的提示或加入 `source_statement_facts`，原 `effective_request_id` 与 `input_id` 仍原样留在对象里。当前无消费此对象授信用的路径，所以这**不是已发生的错误原生接受**；若后继执行或验收仅信这些返回字段，就能把被改动的组误认成原组。接线时应从已认证来源重建请求，核对实际请求内容与其 ID、组映射和完整覆盖，并以独立真实执行及原始响应收据决定信用；单独重算可由调用方改写的 `input_id` 不足以证明来源。

验证：我只运行获准的短测 `test_successor_cannot_drop_original_units_or_required_items`，1 项通过（0.001 秒）；`git diff --check` 对指定范围通过。`final.log`/`final.exit` 只读显示最终两项测试通过（149.225 秒）；`material.log` 是收紧返回结构前的一项测试，不能代替最终版本。长测试未重跑，日志自身没有独立的提交 SHA 或逐测试名收据。没有真实 provider/paid/SEC 调用，没有修改源代码、原日志、#47/PR52、账本，也没有 commit/push。

本审阅共使用 **18 次底层工具调用**（按 `functions.exec` 中实际子工具计数，含报告写入和最后核对）；未启动长测试。
