限定新增差异独审结论：LIMITED_APPROVE（仅 namespace 依赖修后增量）；未发现此增量内新的可操作缺陷。原审 P2 在此精确差异内得到解决；原审历史 REQUEST_CHANGES、旧 Source 与旧 packet 的原字节和摘要保持。

本次只审 `97f8380db30fc954587aec2cddcd8f103ffa16e0` 相对 `7c50eab93f8e99d28dd6ecd5a04bf9992a479ad7` 的 `scripts/vnext/d03_context_requests.py` namespace 增量、对应 unittest 新增反例和新增实际事实包。工作区开始及结束 HEAD 均为该 SHA，branch 为 `task/b06-new-source`。未变部分按 `../independent-review/conclusion.md` 原有限范围继承；不将继承范围、当前 CI 或父测试当成本次新增独审证据。

增量机制：原 XML 中的前缀需要用所在元素自己的命名空间对应表解释。现在第63—78行分别收集 fact、context、unit 所引用的 environment，检查 context/unit 的引用存在，并输出以环境 ID 为键的对应表。保留原 fact 的 `namespaces` 字段；相同环境自然去重。新增字典作为 context 元素的一部分进入原有 `evidence_json_bytes(found)` 字节计算，不在字节限额之后追加。

本次独立证据：

- 指定命令独立运行：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts /private/tmp/issue28-tokenizers-venv/bin/python -m unittest tests.vnext.test_d03_context_requests -v`，9/9通过，0.015秒，见 `targeted-tests.log`。没有把父测试日志充作本次执行。
- 另以未变的 `_shared` / `_seal_unit` 建立独立来源表示，完成34项独立断言，见 `independent-probes.log`。事实、context、unit三种环境分别让 `z` 表示事实、维度、币种，正确保留全部环境并按各自环境恢复含义；无关环境不输出；原 fact/context/unit 数据不改；共享环境及两两共享分别正确去重。
- 对 context/unit 分别删除 environment、environment ID、原依赖对象，以及把 ID 改成非字符串，均明确拒绝。该独立缺失测试只保留被测单元，避免新增仓库测试中额外重复事实造成的歧义影响判断。来源及单元身份均重新建立，使请求确实进入依赖检查。
- 完整独立 context为1453字节，未补 environment 字典的形状为949字节。1453临界额度完整通过，1452和949额度均保留UNRESOLVED且不输出半份 context；累计额度同样计入每个导出行的字典。重算包摘要后篡改币种前缀对应表仍被来源重建拒绝。独立过程禁止 socket 和 child subprocess。
- 新增实际样本为 Marriott `f-408`，仅1个原责任单元、1个精确事实请求。直接读取磁盘 Source 与新 packet，固定来源摘要 `5c4aae9c6a1f671d348b0e41c3eefb526a3710a4c9d463f77f7e39d54f909b5b`，新包摘要 `384b0d45cd0c6515207d62ef1a82161897c929e9cdaff36150ef860a448e3fa4`；磁盘字节、无损序列化及独立新进程冷回放一致。环境集合另从原 Source 的 fact/context/unit 引用直接重建比较；该实际样本所需环境恰好只有1个，因此不同环境的正向能力由上述独立三环境反例证明。
- 新实际 context为3952字节，去掉新字段后为3108字节；原字段逐项与来源一致，3108额度不能容纳完整新包。`semantic_acceptance=false`、`company_result_created=false`、`business_calls=[0,0,0]`保持。没有执行会写父证据的 `verify_actual.py`。
- 34份保护文件在审前/审后摘要相同，包含相关产品/测试文件、父审结论/日志、父证据、保存 Source、原/新实际 packet及claims账本。起始已有的 `execution-state.json` 修改未由本审阅写入。只新增本目录的一份 `conclusion.md` 和日志。

边界与未覆盖：本次不是 D03 内容语义、全公司责任、后续请求总上限、4096输出合同、生产输入检验、DeepSeek验收、原生Run/Result或生产批准。外部可信来源摘要及获取真实性仍由调用方提供，本次未重新认证获取。未重跑旧长链或全套测试，未模型抽取、未真实模型/SEC请求、未账户操作、未spawn、未commit/push、未打包。此次 GitHub 只读检查仅为读取 Issue28 现行边界，不是业务调用。一次AGENTS文件名搜索意外扩及用户目录，随即停止；未读取命中目录的文件内容，后续搜索限定仓库范围；此搜索不作为审阅证据。

资源登记：开始 `2026-10-04T03:25:41Z`；结束 `2026-10-04T03:31:15Z`；用时 334 秒。实际工具保守计31（8次functions wrapper＋23次nested工具，含最终写入）；普通消息3（开场1、进度1、最终报告1）。无问题消息；低于工具80、90分钟和普通消息3硬上限。详见 `resources.log`。本结论仅绑定上述精确 namespace 差异，不能提升为全PR批准。
