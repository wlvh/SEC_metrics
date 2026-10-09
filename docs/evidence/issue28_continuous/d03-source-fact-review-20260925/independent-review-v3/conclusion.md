# D03 来源事实第三轮限定独立审阅

**结论：`3384bee8d9a58d6b629edbcd39a47b9b793ee517` 相对 `452c828793a89fd84ca84860b770480b768ae99e` 的限定差异仍未通过。** 上轮报告的两种跨句误关联在新增测试所列措辞中得到修复，但扫描仍会把明确属于另一主体的结束句归到首句，使首句的当前涉入保护失效。这是独立构造的规则反例；没有证据表明 JPM 原件出现该措辞，也不据此判定完整 D03 或整个 PR。

## 单个最小阻断反例

> We are involved in various legal matters, including investigations by governmental authorities. That investigation concerns Acme alone, whereas ours remain open. That investigation was closed.

首句明确报告本公司的当前涉入；第二句明确区分 Acme 的调查与仍开放的本公司调查。第三句结束的是 Acme 的调查，不能据此撤销首句。独立探针分别将三句置于同一可见块，以及将后两句作为按顺序传入的后续块；两条路径均把首句标为 `SEMANTIC_REVIEW_REQUIRED / UNRESOLVED`，原因码 `LINKED_RESOLUTION_REQUIRES_INTERPRETATION`。随后 `check_aggregate_classification(..., kind='HISTORICAL_STATEMENT', reported_status='UNRESOLVED')` 返回空列表，容许把该明确的本公司当前涉入归为历史/未决。

原因在 `regulatory_statement_facts.py` 第 25–31 行：第二句以 `That investigation` 起头，命中 `linked_resolution`；虽然它同时包含新的调查主题且明确转到 Acme，`_NEW_ACTION_TOPIC` 的阻断条件仍因 `and not linked` 而失效。第三句再命中关联结束并撤销首句保护。新增测试第 103–122 行只覆盖 `In a separate matter...` 和 `Our vendor may face investigations...` 这类非关联起头的中间句。此处只要求守住已经明确分开的事项，不要求扩建通用自然语言解析。

## 已核实的修复、身份和边界

- 直接的同块/相邻块 `These investigations have been closed.` 仍转为 `SEMANTIC_REVIEW_REQUIRED`；上轮 Acme 另起事项及未来供应商调查的测试也保持首句 `SOURCE_REPORTED_FACT`。指定短测 `PYTHONPATH=scripts python3 -m unittest tests.vnext.test_regulatory_statement_facts.RegulatoryStatementFactsTest -q` 本轮实跑 **9 项通过**。`git diff --check` 无报错。
- 保存的 JPM 正例经独立小文件重算，`fact_id` 仍为 `sha256:69b4af995d78bd8353a873c568d51d690ed477b28432c09196f46fa12a9ee972`，状态仍为 `SOURCE_REPORTED_FACT`。未重跑长 JPM 材料测试。
- 当前实现文件 SHA-256 为 `69aae1eb4255b32f2090a54c3f78951c7012c8893e5f46c6d4d16680966640d7`、9126 字节，与 V14 baseline 两处绑定相同。本地读取 V14 快照重算需求闭包 `sha256:c63c7d6a53d296db456b5188399590304fb1e1812d11d7401d5554a3d741d92d`、执行身份 `sha256:0e3696a15a9bedb21a51fc970a4232d5aae53b14a2df21a7bdb17e686e060314`；第三轮 D03 接线、SEC 检查和 provider/SEC 收据日志使用同一闭包。所保存接线与 SEC 日志各报新增调用 `[0,0,0]`，收据日志报 `network=DISABLED`。我核对日志与当前绑定，没有重跑接线、收据检查或检查目录外的账本原件。
- `repair-v3-fast.json` 保存 `PASSED`、128 个 selector；该套件和第三轮的长材料测试均未在本独审重跑。README 明确指出 B13 190 只读复用尚未在第三轮闭包下重放；第二轮日志不能作为第三轮精确绑定的复用证据。

本次只审指定代码、测试、V14 baseline 与 D03 第三轮材料。没有审 D03 全文覆盖、模型输出、原生 Candidate/Evidence/Run、十家公司结果、生产采纳或整个 PR；未发模型或 SEC 请求，未碰账户、生产、#47/PR52，未 commit、push 或归档。工作树原有的 `execution-state.json` 修改未触碰。按本目录 README 已写明的第三轮停止条件，这个阻断应交回主任务决定是否暂停该确定性证明路线，而不把局部规则和禁网接线误写成真实 D03 完成。
