# 定向运行：JPMorgan 往年金融指标、Pfizer FY2021 B02 与 D01 跨页拒绝（运行树闭包 `004c5771`）

## 跑了什么

运行树同步到 `94cbc3e7`，加注册补丁。该提交在这棵树上铸出的闭包正是各 Run 记录的 `sha256:004c5771…`，这是复算核对过的，不是按时间推断的。驱动是 `period-batch/frame_batch.py`，3 个工作进程，零 provider / paid / SEC 调用。

| 期间 | 指标 | 为什么跑 |
|---|---|---|
| JPMorgan FY2021–FY2025 | A01–A13 | 往年措辞后继（`bc0a2ac7`）与成对可比检查（`336ab3ae`）之后，银行指标第一次在带这些规则的闭包上跑 |
| Pfizer FY2021 | B02 | 同概念重述的成对可比检查 |
| Southwest FY2022–FY2024、Enphase FY2025 | D01 | 跨页标题改为按名拒绝（`94cbc3e7`）之后核对 |

**这不是全量帧**，之后的闭包也不是这一个。结果编号只依赖 Spec 与输入，不随父代闭包移动。

## 结果（`rerun-results.json`，由 `collect.py` 从各期间矩阵汇总）

70 个位置，68 个冻结出公共行，另一进程冷读到同一 run 与 result，0 个不一致；另 2 个是按名拒绝。

- **JPMorgan 新出值 12 个**：在 50 期间批次（`500ddf5f`）里这 12 个都是 `FINANCIAL_SOURCE_SEMANTICS_UNRESOLVED`，现在都有值。
  - FY2021：A03 1.11、A04 0.0164、A09 0.0072、A11 3.113 万亿美元、A12 5,500 万美元
  - FY2022：A04 0.02、A09 0.0059、A11 2.766 万亿美元
  - FY2023：A03 1.13、A09 0.0052、A11 3.422 万亿美元
  - FY2024：A11 4.045 万亿美元
- **按名扣留 `HISTORICAL_PAIRED_MEASURE_NOT_COMPARABLE`**：
  - JPMorgan FY2021 A05：FY2021 10-K 重述了 2020 年末总资产。
  - Pfizer FY2021 B02：FY2021 10-K 按同一概念重述了 2020 年收入。
- **JPMorgan FY2021 A01/A02 仍是 `HISTORICAL_ACCESSION_ROUTE_UNRESOLVED`**：这个闭包还不带日期写法的 FASB 命名空间读法（`13a54eb5`）。下一轮定向运行在当前闭包上重跑。
- **JPMorgan 其余 52 个位置**（含 FY2021 A01/A02）：结果编号与 50 期间批次逐个相同。
- **Southwest FY2022/FY2023 D01**：按名拒绝 `D01_MULTISPAN_HEADING_UNSUPPORTED`，没有 Run，与 `94cbc3e7` 的设计一致。FY2024 与 Enphase FY2025 出公共行。

## 阅读与释放

- 12 个新值由 `tools/read_bank_measures.py` 从年报自己的表格读出。这个工具不经路线的金融检查器，结果见 `../content-acceptance/bank-measures-read-round-004c5771.json`。
- 两个扣留结果分别释放 `A05_JPMORGAN_2021_PRIOR_YEAR_ASSETS_AS_FIRST_REPORTED_AGAINST_A_RECAST` 和 `B02_PFIZER_2021_PRIOR_YEAR_AS_FIRST_REPORTED_AGAINST_A_RECAST`。释放只点名这两个扣留结果与本闭包；批次里已发布的旧值照旧撤回。
