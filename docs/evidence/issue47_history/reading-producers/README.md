# 授予接受的阅读，改由已提交代码产出

## 问题

第三层交付（内容接受）有 154 条，来自九份阅读。此前只有 D01 与 E01 两份的产出代码在仓库里；报表（75 条）、事件计数（35 条）、治理 C03/C04（14 条）、住宿表（6 条）、RPO（1 条）、Paramount 薪酬表（1 条）这几份阅读只有结论 JSON，代码散落在会话临时目录——容器回收就没了，而且无法从仓库重跑、也无法审查它们是怎么读的。

这不是形式问题：报表阅读的临时代码用 `int()` 解析数值、失败就静默跳过。Salesforce 把折旧写成 "1.2"（scale 9），过不了 `int()`，于是那条事实对阅读不可见，阅读顺着链条落到另一个概念，并把差异写成了"路线是对的"。实际那条事实只是固定资产折旧（见 `../b03-depreciation-scope/`）。

## 现在

| 阅读 | 产出工具 | 测试 | 接受 |
|---|---|---|---|
| `cross-source-read.json` | `tools/read_statement_facts.py` | `test_statement_fact_reading` | 75 |
| `event-count-read.json` | `tools/read_event_counts.py` | `test_event_count_reading` | 35 |
| `e01-eight-o-one-read.json` | `tools/read_e01_eight_o_ones.py` | `test_e01_eight_o_one_reading` | 3 |
| `governance-read.json` | `tools/read_governance_facts.py` | `test_governance_reading` | 14 |
| `lodging-table-read.json` | `tools/read_lodging_table.py` | `test_single_readings` | 6 |
| `rpo-read.json`、`paramount-compensation-table-read.json` | `tools/read_single_facts.py` | `test_single_readings` | 2 |
| D01 四份（含 Paramount 前身 FY2024） | `tools/read_d01_headings.py` | `test_d01_byte_reading` | 12 |
| `debt-to-equity-read.json` | `tools/read_debt_to_equity.py` | `test_debt_to_equity_reading` | 4 |
| `d02-both-directions-read.json` | 逐块人工判断的记录 | — | 8 |

每个工具都：不导入路线的计算模块（用例按导入树断言）；已发布值从点名的运行根与 Requirement 版本经收据读取；身份在阅读当时记录（`RECORDED_AT_READING_TIME`）；已提交阅读的每个位置都能从已保存字节重算（用例逐项比对）。重新产出后登记仍是 154 条，身份字段除 `established_by` 外逐项不变。

## 重写时读出的两件事

1. **Salesforce B03**：修好小数解析后，阅读读到的正是路线取的那条事实，读数等于已发布值——但结论是 `DIRECT_CANDIDATES_DISAGREE`。两个都按链条走的读者彼此一致，说明不了链条第一个概念覆盖了什么；三个"总 D&A"概念是同一量的不同名字，两个取值不同就说明其中一个不是总量。
2. **Southwest C03**：把 SEC 的 fixed-zero 横线如实读成 0 后，2025 年出现两个 PEO 合计（0 与 16,587,882），阅读一度拒绝。表格本身说明了那条横线是什么：Gary C. Kelly 那一列只在 2021、2022 年有薪酬，2025 年的横线是"该年不是 PEO"的占位。旧代码靠 `int()` 跳过横线碰巧读对；现在按表格自身证据把占位放到一边并记录，从未被支付的人的横线照常计入。

注错记录：`statement-injections.json`、`governance-injections.json`；事件与住宿等的注错写在 TESTING.md 对应条目里。

## 不主张

这些阅读确立的只是"已发布值与申报在这些读法下一致"，不确立定义本身是否回答了业务问题；读者与写路线的是同一个人。
