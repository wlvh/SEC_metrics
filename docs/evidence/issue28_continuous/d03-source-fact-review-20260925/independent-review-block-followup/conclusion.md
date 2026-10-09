# D03 来源事实候选：同块冲突与响应身份限定独审

**结论：本次限定补丁通过；未发现新的阻断项。** 审阅的精确提交为 `5e0b815e2df928b323c2bf3814bb6556dc5e740c`，直接前驱为 `937849fb6a519cb3f00316ec6efe465cb5a56199`。范围仅为 `scripts/vnext/regulatory_fact_review.py`、`tests/vnext/test_regulatory_fact_review.py` 和 `anchor-repair-followup-test.log` 的差异，针对前驱限定审阅报告中的两项 P2。这个结论只认可离线候选接口的修补；不授予真实 D03 请求、原始响应持久化、原生 Run 或生产信用。

## 两项 P2 的处理

1. **同块多候选冲突不再造成假解决。** 新 `_candidate_uncertainty` 按 `(unit_id, block_index)` 统计候选；同一块有多个候选时，每个候选均进入 `source_fact_candidate_review` 与 `unresolved`，即使其中一个单独领到当前行动的正向 finding（`regulatory_fact_review.py:110-133,202-205`）。新增测试直接检查两个候选各领一个相反 finding 后都未决（`test_regulatory_fact_review.py:118-133`）。我另用短小的外层校验探针复核了整个 `validate_candidate_response` 的分配检查到返回值路径；隔离替换了来源认证和既有语义验证器，所以这不是完整来源或模型响应复现。单候选正向 finding 仍可保持无该项未决。

2. **返回的响应对象与字节证据声明一致。** 返回值现在以严格解析后的**实际收到的响应对象**覆盖既有验证器处理过的对象；`provider_response_raw_sha256` 对传入的原始 `bytes` 直接计算 SHA-256；`raw_provider_response_preserved_separately` 明确为 `False`（`regulatory_fact_review.py:143-149,198-210`）。现有 JPM 测试检查响应对象相等及规范化输入字节的哈希（`test_regulatory_fact_review.py:61-70`）；我的短探针另以含空格和换行的非规范化 JSON 字节核对哈希确实绑定原字节。**哈希不是原始字节副本**；未来接入调用时仍须真实保存并绑定这些字节，不能把本返回值当作持久化证明。

## 证据及边界

- 保存的 `anchor-repair-followup-test.log` 记载指定 `unittest` 模块 2 项测试、`OK`、60.087 秒；本次依任务约束只读取日志，没有重跑完整来源测试。指定三文件的 `git diff --check` 独立通过。
- 本审阅独立运行的短探针结果在 `short-probe.log`。其来源认证和基础语义验证器为替身，只核对本次补丁所负责的外层校验、未决聚合、响应对象及原始字节哈希。没有真实同块 JPM 材料、多公司材料或真实模型输出的全栈验收。
- 按整个块保留未决是保守修复：同块但不同句且各自清楚的候选也会一并未决。若后续真实材料显示它阻断必要的正向完成，应基于精确语句范围再限定关联；本次没有证据证明该代价已经发生，不把它写成已证实缺陷。
- 未修改源代码或既有日志，未运行长材料测试，未发 provider/SEC 请求，未触碰 #47/PR52，未 commit/push。审阅不覆盖整条 D03 请求、运行、发布链及旧提交。

本审阅共调用 **24 次底层工具**（按 `functions.exec` 内实际子工具计数，包含报告写入与最后一次目录核对）。
