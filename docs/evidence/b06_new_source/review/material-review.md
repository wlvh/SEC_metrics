# B06 两份真实材料独立验收审阅

结论：两份固定历史申报在同一最终实现 `3e4ceff32fc09a245a078e867ac9a129a89f4d2f` 下的来源身份、已声明披露模式、原生数值与独立算术复核通过。本次审阅只读最终原件、Run、审阅绑定和受信 journal；没有向执行结果回填数值，没有 SEC/provider 调用，没有修改生产代码。

| 案例 | 固定申报 | 实际期间／财年标签／提交日 | 独立重算 | 原生状态 |
|---|---|---|---|---|
| Southwest | `0000092380-25-000024` | 2024-01-01 至 2024-12-31／FY2024／2025-02-07 | 6,699,000,000 ÷ 10,350,000,000 = **0.6472463768115942028985507246** | FROZEN，validation PASSED |
| Salesforce | `0001108524-25-000006` | 2024-02-01 至 2025-01-31／FY2025／2025-03-05 | 9,111,000,000 ÷ 61,173,000,000 = **0.1489382570741994016968270315** | FROZEN，validation PASSED |

金额使用 Python Decimal 独立计算；数值直接从各自 XML 原件按本地名、主体、无维度 instant context、实际期末和 USD unit 筛选，重复同概念报告要求数值一致。没有调用生产 Calculator 来产生审阅答案。原表组成另作人工抄录和求和，再与原始 XBRL 数字及原生 MetricResult 比较。JSON 明列每一金额、等式、来源 URL/hash/admission ID 和原生 Run/Result ID。

## Southwest：总额已经包含融资租赁

原债务组成表的当年金额（百万美元）为 0、1,611、300、107、300、1,727、500、976、566、526、91，合计 6,704。最后一行明确为 Finance leases。融资租赁政策明确将对应负债分类在资产负债表的 Current maturities of long-term debt 和 Long-term debt less current maturities，支持其已在债务集合内；不是根据公司名或模型 coverage 推断。

表内 `6,704 − 1,630 − 5 = 5,069` 将流动到期部分和债务折价／发行成本明确作用于同一个总额。B06 所需总账面债务为 `6,704 − 5 = 6,699`，也等于 `1,630 + 5,069`；不额外再加 91 的融资租赁。租赁表进一步证明 `99 − 8 = 91` 为扣除未实现利息后的负债现值，`22 + 69 = 91` 为流动／非流动分拆。

## Salesforce：借款与融资租赁分列

借款表区分 principal 和 carrying value。本轮选择 FY2025 期末账面列；0、1,496、995、1,491、1,236、1,979、1,236 合计 8,433 百万美元，未误用 8,500 的本金列，也未借用 FY2024 比较列。流动借款为 0，非流动借款为 8,433。

原租赁政策将融资租赁负债分列在 accrued expenses and other liabilities 与 other noncurrent liabilities；借款组成表列举债券且没有融资租赁组成行。这些当前原文和报表结构共同支持非重叠。融资租赁表给出 `708 − 30 = 678` 的负债现值，流动／非流动 `337 + 341 = 678`。本轮总债务为 `8,433 + 678 = 9,111`，没有重复加入这两个租赁分项。

## 未登记关系及非 Git 原件准入

逐一对比现有人工关系注册表，两份 XML source SHA 的匹配数均为 **0**。

必要 primary HTML 的准入均为本轮实际 `SEC_FETCH`：

- Southwest `luv-20241231.htm`：SHA256 `30b0fff1b201973dc87958cb90f7c11d27bd1678f8cbaa9a9fec102101d6cb0b`。
- Salesforce `crm-20250131.htm`：SHA256 `4b181008a668650f4722d04347eb71ffa058ccc62a2e44f7b992d2b5261f9eaf`。

已用 Git 原始 blob identity 检查受审基线 `92fdd0e30c5f05db9d3d0136424934037dcff66e` 的树及全部祖先对象列表：两份 primary 均不存在。它们不是把历史已认可原件复制到新目录；其信用来自固定执行 journal 的真实获取条目。其他 submissions、Company Facts、XML 属于明确 `TRUSTED_SAVED_IMPORT`。四类必要来源的文件 SHA、URL、attempt 和唯一 admission 记录均相符。journal 实见 2 个 intent、2 个 terminal；无未收尾 SEC 获取。

## 首次及修后表现

所有历史文件仍在，未改写失败 Run。

| 实现 | Southwest | Salesforce |
|---|---|---|
| `88a56bd38f894d95c435f994312622698bc6a8ea` | FAILED：Requirement JSON is missing or unsafe | 同左 |
| `99e4b2cafc9136f8a039f024f0b4a6b23bac3b00` | 额外 recheck FAILED：SourceReference fields are empty: accession | 未运行此额外 recheck |
| `00ca4a3a8bf19115c2af4af8d184a4a25e871003` | FAILED：B06_SAVED_VERIFICATION_CHANGED；原 native-run 仍 OPEN | 同左 |
| `3e4ceff32fc09a245a078e867ac9a129a89f4d2f` | 新 accepted-run FROZEN / PASSED | 同左 |

这是确定性零模型路径；不存在旧模型响应换绑新请求的问题。最终两个结果均按各自原始提交口径计算；封存 submissions 中没有该期已知修订，`current_latest_verified=false`。不据此声称今天最新申报或修订影响已全部核验。

本审阅确认的是有限披露模式内的真实结果与证据，不将其外推为任意融资文本的通用识别能力。原生 Result 中 `publication=PUBLISHED` 是 Run 内结果状态，不等于 B06 已正式发布或获准切换 active。异进程冷重放、实际 CI、正式根不变与最终审阅包提取验收由父任务分别给出证据。

配套机器可读审阅：`/tmp/b06-final-material-review.json`。复核脚本：`/tmp/b06_final_material_review.py`。
