# B06 回退解析器认两种往年写法（Southwest FY2022 出数）

## 问题

`../README.md` 的诊断里，Southwest FY2021–FY2023 的 B06 都停在最后一级——回退解析器的完备性检查（冻结的 `b06_disclosure.verify`）。FY2022 停下的原因是两行它不认识的内容：

- 债务表里一行 “Pass Through Certificates due 2022 - 6.24%”（转递证书，一种有担保的债务工具；这一年已到期，期末为 0）。冻结的债务工具识别词只有 notes、debentures、loan、credit agreement。
- 一项养老金义务 `us-gaap:DefinedBenefitPlanBenefitObligation`（2.41 亿美元）。冻结的扫描只因概念名以 obligation 结尾就把它列为“可能的融资项”，又没有把养老金归入“性质不同”的那一类。

两者都是程序不认识年报里已有的写法，不是年报没有披露。

## 修法

历史 B06 级联（`scripts/vnext/historical_debt_results.py`，规则文件）的最后一级改用冻结函数的后继（`historical_financial_wording.successor`：冻结函数自己的源码加列出的替换，替换必须恰好命中一次）：

- `fallback_verify_v1`：`b06_disclosure.verify` 加两处替换（`OLDER_FALLBACK_FORMS`）——债务工具识别词多一个 certificates；“标准概念、性质不同”的排除式多一个 definedbenefitplan。
- `fallback_verify`：`b06_disclosure_v2.verify`，只把调用冻结清单的那一行改为调用 `fallback_verify_v1`；v2 自己的内容检查照常跑。
- `fallback_resolution`：`normal_candidates._b06_resolution`，只把调用 v2 的那一行改为调用 `fallback_verify`。`_fallback_case` 调它。

冻结模块不改，#28 的普通路线不受影响。冻结解析器能答的申报，后继的答案逐字段相同：两种写法只会改变冻结清单标为 UNRESOLVED 的行，而只要有 UNRESOLVED 行，冻结解析器就不会给出答案。

## 量测（零调用）

- 内存探针（`../probe.py` 的同一套调用，在恢复根上）：Southwest FY2022 由扣留变为 0.7568073360157200336857864695。分子是 `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` 减 `DeferredFinanceCostsGross`，即 8,088 百万美元（含融资租赁，年报的租赁政策写明融资租赁计入长期债务各行）；分母 `StockholdersEquity` 10,687 百万美元。转递证书一行计入债务成员（值 0），养老金义务归入“性质不同”。
- 全帧对比（`frame-measured.json`，`frame_compare.py`）：50 期间批次的计划上，同一恢复根、零调用，冻结与后继各跑一遍级联。只有 Southwest 三年移动，已有的数值一个都没变：
  - FY2022：由扣留变为上面的值。
  - FY2021：冻结停在债务成员合计不符（`DEBT_MEMBERSHIP_SUM_CONFLICT`：转递证书一行当年不为 0，没被认作债务，不计入合计）；认出之后合计对上，停在下一级（见下一条），仍扣留。
  - FY2023：由养老金义务处停到下面说的叙述句，仍扣留。
  - 其余 47 个位置的阶段、理由、值与选择逐个相同。这与冻结代码一致：两处替换只改变冻结清单标为 UNRESOLVED 的行（债务表里未被识别的行、未被归类的期末 XBRL 事实），而清单里只要有 UNRESOLVED，冻结解析器就不给答案（成员合计或 `UNRESOLVED_FINANCING_ITEM` 检查会先停下）。
- 往下一级（内存里再加两种写法量过，没有采用）：FY2021 还卡在资产负债表一行值为 0 的 “Construction obligation” 和一个每股转换价（单位美元/股）；这两处也认之后，又停在一句回购会计处理的叙述上。FY2023 停在 “The net carrying amount and principal amount of the Convertible Notes was $1.6 billion …” 这句四舍五入的叙述上。这些要新的叙述规则，不在这次范围内，两年照旧扣留。
- 同一轮也量了 Enphase FY2024（备注账面语法）：它卡在可转债的实际利率（无量纲单位）上，冻结语法对“保修计量利率”有同形分支却没有它；补上后又停在一句“截至 2023 年 12 月 31 日”的往期余额叙述上，所以这次也不采用。

## 用例与注错

`tests/vnext/test_historical_debt_fallback_forms.py`（saved-source 层，7 例）用 `source-records.json`（级联在恢复根上交给回退解析器的输入，由 `collect_inputs.py` 采集）和已存字节（检出或已提交的取数导出）重建输入：

- FY2022：冻结的解析在两行处扣留；后继给出上面的值，两行的处置如上，清单里没有 UNRESOLVED，v2 的内容检查完整跑过。
- Southwest FY2024、Salesforce FY2026（冻结能答）：后继的答案与冻结的逐字段相同。
- FY2021、FY2023：后继照旧扣留，停在上面说的下一级。
- 三个后继各自只带列出的替换；`_fallback_case` 调的是后继。

`injections.py` → `injections.json`：5 个注错（去掉 certificates、去掉养老金排除、v2 仍调冻结清单、解析仍调冻结 v2、级联仍调冻结解析）。

## 未做

这是规则文件改动，原先作为待提交补丁保存在 `../../pending-rule-changes/`，打算等模型出口收据提交之后再提交。10-03 虚拟机重启打断了重封，重封要从头再跑，于是先把补丁作为正式提交落地（见 `../../pending-rule-changes/README.md`）。还没做的：在新闭包下定向重跑 Southwest FY2022 的 B06，用 `tools/read_debt_to_equity.py` 从原件读过再接受。
