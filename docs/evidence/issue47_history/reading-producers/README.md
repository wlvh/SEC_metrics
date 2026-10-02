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

## 银行指标（2026-10-02）

`tools/read_bank_measures.py` 读 JPMorgan 年报自己的表格，产出 `../content-acceptance/bank-measures-read-full-frame.json`，覆盖 A03、A04、A09、A11、A12、A13。它不导入任何金融检查器，既不导入 #28 的冻结检查器，也不导入 #47 的旧措辞后继。读法：按 `<table>` 切开文档，去掉标签取每行单元格，从年报给该量的行名读，取表头年份行里目标年度那一列，按表头写明的单位换算。A04 读"managed basis"净收益率，A09 读"Firmwide"不良率，A11 读资产管理总额，A12 读拆成 Avg./Min/Max 的表里 Total VaR 的 Avg. 列，A13 读首个数字列为营业收入那张表里目标年度下的 Total international。A03 要两处同时成立：三个月平均表里注册人名下（名字取自申报自己的 DEI）的 LCR，以及主要财务数据表里的 Firm LCR 平均值。凡点名该量并写明目标年度的表都读，几张表必须一致；期间取表头自己写的口径（全年、时点或三个月），而且必须等于结果的测量期间。

对第一份 50 期间批次（闭包 `500ddf5f`）：五年 30 个位置都读出了值。其中 18 个有已发布值，逐个一致；另 12 个是该批次扣留的往年位置，读数与 `../financial-older-wording/measured.json` 里后继给出的值逐个相同，要等新闭包下的定向运行出了结果才有可比的已发布值。

**局限**：它只确立"年报点名的那一行在这个期间是这个数"，不确立路线那些见证要确立的事——这一行就是定义要的量、覆盖整个发行人（词汇表、分部、引言、脚注）；这一点它直接采用年报自己的行名。

**有一张表它不读**：国际指标表写的是 "in billions, except where otherwise noted"，下面另有一块营业收入写 "in millions"。这张表里的资产管理总额（3,113 十亿）它不读，因为表头写了两种单位，它判断不了这一行用哪一种。值本身由资产管理表读出。

**注错**（`bank_injections.py` → `bank-injections.json`，在内存里改读取器副本，检出不改）：11 个注错加一个对照，全部由为它写的用例抓到。

**注错查出读取器自己的一个潜在缺陷**："营业收入列之外也读"那个注错第一次跑时，在真实年报上抛了异常，原因是 `read_international_revenue` 在循环里把期末日期的名字 `end` 重新赋成了行号。每份年报只有一张营业收入表，所以已提交的阅读没碰到它；第二张营业收入表就会在 `_window` 里拿到整数而崩溃。已改名，并补了一例两张表的用例。

**同一轮还查出七个阅读用例共有的缺口**："不导入路线模块"的检查只收 `from X import` 里的 X，于是 `from vnext import <路线模块>` 这种写法能通过检查。"导入一个金融检查器"那个注错正是这样写的：用例从磁盘读源码，第一次没有抓到。现在七个用例都把别名一起计入。银行这一例改读被测模块自己的源码（`inspect.getsource`），这样注错能被它看见。现有工具里没有一个用这种写法，所以这个缺口没有藏住任何东西。

## 银行报表事实（2026-10-02）

`tools/read_bank_statement_facts.py` 读 JPMorgan 年报主文件自己的 inline XBRL，产出 `../content-acceptance/bank-statement-facts-read-full-frame.json`，覆盖 A01、A02、A05、A06、A07、A08、A10。路线从 Company Facts（A05–A08、A10）和 accession 的 XBRL 实例（A01、A02，带两个必需维度）取数；这份阅读读的是年报主文件，用报表阅读的解析（`tools/read_statement_facts.py`：数值一律按小数读，按 scale 与符号换算，同一事实重复出现必须一致），不导入路线的任何模块。它从目录（`catalog/deterministic_metrics.json`）取的是已批定义——每个分量的概念、期间、来自哪一份申报，A01/A02 的确切维度——不是路线的代码。

- 目录规定取自上一年申报的分量（A05、A06 的上年末余额，A07 的上年净利润），从期间选择点名的上一年年报读。目标年报在比较列里也报了同一年的数，两处必须相等，否则不读（`PRIOR_YEAR_RESTATED_IN_THE_TARGET`）：两半来自同一年两个版本的组合，正是路线要扣留的情形。
- A01/A02 只读上下文维度恰好等于必需维度的事实，多一个都不读。
- 算术是目录的公式，小数精度 28、ROUND_HALF_EVEN：比率 a/b、差 a−b、平均分母比率 a/((b+c)/2)。

对第一份 50 期间批次（闭包 `500ddf5f`）：五年 35 个位置里 32 个与发布值逐位一致；2 个是该批次没有发布值的 FY2021 A01/A02；1 个不读——FY2021 的 A05。FY2021 年报在同一概念 `Assets` 下报的 2020 年末总资产是 3,384,757,000,000，而发布值用的是 FY2020 年报首次报告的 3,386,071,000,000。这一处已登记为缺陷 `A05_JPMORGAN_2021_PRIOR_YEAR_ASSETS_AS_FIRST_REPORTED_AGAINST_A_RECAST`；Company Facts 那条路径也独立量出同一处，且 A05/A06 只有这一处（见 `../b02-same-concept-recast/README.md` 末节）。

**局限**：它确立"年报对这个概念、这个期间、这组维度报的是这个数"，以及按目录公式算出的值；不确立目录选的概念就是定义要的量——那是已批定义本身。读法也接受申报人自己命名空间下与已批概念同名的事实；两个命名空间说法不一时不读。

**注错**（`bank_statement_injections.py` → `bank-statement-injections.json`，在内存里改读取器副本，检出不改）：7 个注错加一个对照。第一次运行有两个注错被比预期更多的用例抓到，是预期写窄了：去掉"重述就不读"，已提交阅读里 FY2021 A05 那一处也会变；"上年取自目标年报"，等于拿目标年报和它自己比，重述检查永远不触发，构造的重述和真实的那一处都会被读出。两处预期已改并写明原因。
