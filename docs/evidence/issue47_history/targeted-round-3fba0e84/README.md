# 定向运行：四份规则补丁落地后（运行树闭包 `3fba0e84`）

## 跑了什么

运行树是 `7cf3992e` 加注册补丁，各 Run 记录的闭包为 `sha256:3fba0e84…`。驱动是 `period-batch/frame_batch.py`，5 个期间、7 个位置，零 provider / paid / SEC 调用，合计 3,424 秒。只跑 `e14d3ca9` 应用的四份补丁会移动的位置：

| 位置 | 为什么跑 |
|---|---|
| JPMorgan FY2021、FY2023、FY2024、FY2025 的 D01 | 运行页眉 “Parts I and II” 不再取作标题 |
| JPMorgan FY2021 的 C02、C03 | 代理封面名称是图片时改从封面之后第一块读 |
| Southwest FY2022 的 B06 | 回退写法后继 |

C02 修复 49 在 50 期间里不移动任何已判读位置的选择（`c02-selector-repairs/` 第 49 节），没有单独重跑。**这不是全量帧**，也不改签任何旧批次。`rerun-results.json` 由 `../targeted-round-cf166529/collect.py` 从各期间矩阵汇总。

## 结果

7 个位置全部冻结出公共行，另一进程冷读到同一 run 与 result。

| 位置 | 结果 |
|---|---|
| JPMorgan D01 四年 | 发布，行数 59 / 55 / 56 / 56，各比 50 期间批次少 “Parts I and II” 一行 |
| JPMorgan FY2021 C02 | 发布，51 条摘录（此前在封面处按名停下） |
| JPMorgan FY2021 C03 | 发布 84,428,145（此前在封面处按名停下） |
| Southwest FY2022 B06 | 发布 0.7568…（此前停在回退解析器） |

## 阅读、接受与释放

- **D01 四年**：`tools/read_d01_headings.py` 在导出恢复的根上逐行读，用 50 期间批次记下的判断文件，四个位置都一致（`../content-acceptance/d01-jpmorgan-read-round-3fba0e84.json`）。`release_on_reading.py` 把四条坐标级缺陷 `D01_JPMORGAN_{2021,2023,2024,2025}_RUNNING_HEADER_PARTS_I_AND_II_TAKEN_AS_A_HEADING` 只对本轮的结果与闭包释放，修复状态改为 `RULE_FIXED_RESULT_RECOMPUTED_AND_READ`；50 期间批次里带运行页眉的旧结果照旧撤回。
- **Southwest FY2022 B06**：`tools/read_debt_to_equity.py` 从资产负债表与租赁附注读出同一比率（`../content-acceptance/debt-to-equity-read-round-3fba0e84.json`），一致并接受。
- **JPMorgan FY2021 C03：没读成，不接受。** `tools/read_c03_across_proxies.py` 只读代理里的 `ecd:PeoTotalCompAmt` 标签；结果读的是 2022 年代理的薪酬汇总表，那份代理没有 inline XBRL，读取器打不开路线读的那份申报（`FIRST_REPORT_NOT_ONE_TOTAL_IN_THE_FILING_THE_RESULT_NAMES`）。后来的代理本身也不一致：2023、2024 年代理给 FY2021 标的是 84,428,145（与发布值相同），2025、2026 年代理标的是 85,159,860。按所有者选的口径 A（以首次报告为准），值应取 2022 年代理的首报；要接受，需要一份不导入路线代码、直接读那张薪酬汇总表的阅读。阅读文件 `../content-acceptance/c03-across-proxies-read-round-3fba0e84.json` 留作记录，没有登记（它不接受任何值）。
- **JPMorgan FY2021 C02**：没有读。C02 往年由判读加统一裁定验收，这一份代理没有判读；留给 C02 的方法验证（#47 正文第 3.1 节）。

接受登记 891 → 896（D01 四条、B06 一条），已有条目一条未变。
