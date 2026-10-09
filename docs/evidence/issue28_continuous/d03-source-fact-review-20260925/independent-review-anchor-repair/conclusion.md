# D03 来源锚点修补：限定差异独立审阅

**结论：未通过本轮限定独审；不得据此接入真实 D03 请求。** 审阅对象为 `937849fb6a519cb3f00316ec6efe465cb5a56199` 相对直接前驱的 `scripts/vnext/regulatory_fact_review.py`、`tests/vnext/test_regulatory_fact_review.py` 和保存测试日志 `anchor-repair-test-final.log`。前次报告的来源绑定 P2 已在本模块的默认仓库根路径上修正；单个候选的冲突 P2 也已修正。不过，同一来源块内存在多个候选时，冲突仍可被拆到不同候选，令其中一个候选的未决标记消失。另有新响应在返回的 `provider_response` 字段中被改写的问题。下述发现只涉及离线候选接口，不把它写成现有生产结果的缺陷。

## 发现

1. **P2：同句、同块的多候选仍可拆散相互冲突的判断。** 新代码要求每个 `candidate_id` 有独立的 finding 下标，并阻止同一下标重复使用（`regulatory_fact_review.py:132-161`）；但随后仅检查引用该块的 finding 是否被**某个**候选领走（163-170 行），未按候选的 `statement_text` 或原有 `visible_block_character_span` 核对。未决判断只看各候选领走的 finding（176-185 行）。短探针构造两个 `candidate_id`，它们指向同一块、同一句原文：一项 finding 判为本注册人当前行动，另一项判为其他主体，各分配一个下标。外层校验接受，只有第二个候选进入 `unresolved`；第一个候选被视为已解决。`aggregate_facts_from_source` 对同一块逐条收集规则命中的句子，因此此类拓扑并未被来源工厂排除。探针为隔离的外层校验：认证函数与基础语义验证器使用替身，**没有证明现存 JPM 原件真的产生这两个候选，也没有完成全栈接受复现**。在真实接线前，建议用候选的精确句子范围约束 finding，或对同块同句候选合并冲突判断，并加一条完整路径反例。

2. **P2，接线前的证据身份：返回的 `provider_response` 不是收到的新响应。** `validate_candidate_response` 在调用既有 `validate_response` 时删去 `candidate_reviews`（`regulatory_fact_review.py:171-174`）；既有验证器会把它收到的解析对象填入 `provider_response`。本函数虽在顶层重新附上 `candidate_reviews`（189 行），却没有恢复 `provider_response`，也没有在返回值中保存原始响应字节；继承的 `raw_provider_response_preserved_separately=True` 因而不能由此返回值本身证明。短探针确认顶层有 `candidate_reviews`、`provider_response` 中没有。当前模块不生成原生 Run，尚无实际响应记录受损；接线时应明确保存和绑定原始响应，并使 `provider_response` 与实际收到的对象一致，或者更名并限定其语义。

## 已修正与复核边界

- **前次来源绑定 P2：本模块内已修正。** `candidate_request` 现在从 `repo_root` 重建来源，要求传入 `source` 与重建对象相等、`original` 与该来源工厂产生的请求之一相等，然后才复制来源引用和主体绑定（`regulatory_fact_review.py:35-50`）。对应测试用保存的 JPM 来源成功构造候选，并拒绝重算了 `request_id` 的伪造引用/主体请求。此结论只证明指定本地来源链的重建比较；不授新 SEC 获取或外部来源真实性信用。
- **前次单候选冲突 P2：已修正。** 同一候选同时领走当前行动与其他主体 finding 时，它保留在 `source_fact_candidate_review` / `unresolved`；漏分配引用同块的 finding 会被拒。测试覆盖这两种情况。剩余多候选问题见发现 1。
- 保存的指定测试日志显示 `1 test / OK / exit=0`，耗时 `185.804s`；本审阅读取该日志，**未重新运行这项完整来源测试**。我独立执行了指定三文件的 `git diff --check`（通过）和 `short-probe.log` 所记的短小外层校验反例。短探针明确替换认证与基础验证器，不能替代完整来源测试或真实模型输出。
- 未修改源代码、历史测试日志或其他证据目录；未发模型/SEC 请求，未触碰 #47/PR52，未作 commit/push。未审整条 D03 请求/响应持久化、原生 Result/Run、全部公司原件、模型语义准确性及生产行为。

本审阅共调用 **30 次底层工具**（其中 2 次写入、28 次只读；按 `functions.exec` 内实际子工具计数），没有长时间测试。证据目录只含本结论和 `short-probe.log`。
