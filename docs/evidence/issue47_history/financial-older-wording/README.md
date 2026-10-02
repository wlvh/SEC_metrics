# 金融指标：银行往年年报的旧措辞（2026-10-02）

## 发现

50 个期间的全帧批次（`../native-run-batch-2026-10-01/`）里，JPMorgan FY2021–FY2024 的 24 个金融指标位置中有 12 个按名扣留 `FINANCIAL_SOURCE_SEMANTICS_UNRESOLVED`：A03 两年、A04 两年、A09 三年、A11 四年、A12 一年。FY2025 的六个都有值。

逐个在恢复根上问 #28 的冻结检查器，读它们自己的拒绝理由与原文。数字它们都读到了，停下的都是"这个数就是要的那个量、覆盖整个发行人"的见证：检查器是照最新一份年报的句子和版式写的，往年年报说的是同一件事，只是措辞或版式不同。**12 个都是程序读不懂，不是申报没有披露**，归成六类：

1. **词汇表的冒号**：往年写 "AUM: “Assets under management”: …"，最新写 "AUM “Assets under management”: …"。（A11 四年）
2. **分部列表的旧句子**：往年写 "There are four major reportable business segments – A, B, C and D. In addition, there is a Corporate segment."，最新写 "has three reportable business segments – A, B and C – with the remaining activities in Corporate"。两句都列出报告分部、其余归 Corporate。A11 要把 AUM 表绑定到其中一个分部的章节，A09 要靠它把各分部的不良率表与全行那张分开。（A11 四年、A09 三年）
3. **被排除业务的旧名字**：markets-excluded 净收益率排除的业务，FY2021/FY2022 叫 "CIB Markets"，之后叫 "Markets"；每份年报都写了它是什么（"CIB Markets consists of Fixed Income Markets and Equity Markets"；后来 "Markets consists of CIB's Fixed Income Markets and Equity Markets"）。冻结检查只认后来的名字，标签和引言两处都是。（A04 两年）
4. **字母脚注前的一条无标记总注**：主要财务数据表与它的 (a)…(f) 脚注之间，往年多一段不带标记的总注（"Effective January 1, 2020, the Firm adopted …"；另一年是一次收购对业绩的影响）。冻结的脚注读取在第一个无标记块就停，所以读不到写明 LCR 是三个月平均的那条 (d)/(b)。FY2021 那条脚注还把量写成标签自己定义的缩写（"the percentage represents average LCR for …"），后来写 "average ratios for"，冻结的单位检查只认后者。（A03 两年）
5. **反事实表头的另一个方向**：FY2021 的 VaR 口径调整表头是 "Amount by which reported average VaR would have been higher"，冻结规则只认 "Amounts by which reported average VaR would have been lower for the years ended:"。两种写法下这张表的 "Total VaR" 行都是调整额，不是报告的总额。（A12 一年）
6. **目录里的页码**：FY2021/FY2022 的目录把一个含 "Firmwide" 的章节名和下一列的页码排在同一行，不良率普查把页码当成候选比率。同一冻结模块里 A04 的普查已经把"源文件自己命名为目录的表里、没有期间列的数"放在一边，A09 的普查没有这一条。（A09 两年）

## 修复

`scripts/vnext/historical_financial_wording.py`（规则文件）：

- **后继就是冻结函数自己的源码加列出的替换**。每处替换必须在该函数源码里恰好出现一次，替换后和整个模块源码一起编译——不替换时编译结果就是冻结的代码对象本身，构建后继时当场核对，所以磁盘上的冻结文件在载入后改过会按名拒绝。后继在冻结模块自己的命名空间里、经 release-aware 视图运行。
- **先问冻结的，冻结的答不出才问旧措辞，旧措辞答出才采用**。采用时结果带 `historical_older_wording`，写明规则、用了哪几类措辞、冻结检查器自己的状态；其余情况原样返回冻结答案，所以冻结检查器读得懂的年报（实测包括每个最新年度）记录逐字节不变。
- 六类措辞之外再无改动；第 4 类的缩写只认行标签自己用括号引号定义的缩写（"(“LCR”)"），标签没定义的名字不算。
- A09 的冻结 fallback 在函数体里 import HTML 检查器，视图换不掉它；后继把这一行去掉、改从命名空间读，由视图绑定到旧措辞版本。

**顺带修了视图机制自己的一个漏洞**（`historical_dei.release_aware_with`，规则文件）：被覆盖的名字如果在函数体里只被 import、从不作为全局变量读取，覆盖什么都不改变，却能通过"该名字被代码读取"的检查——A09 正是这种情况，差一点就用上了一个静默无效的覆盖。现在这种覆盖按名拒绝（`HISTORICAL_DEI_OVERRIDE_NAME_ONLY_IMPORTED`）。现有的覆盖都是全局读取，不受影响。

## 测量

`measure.py` 在五份年报上（FY2021–FY2024 取自获取导出，FY2025 取自检出）对 A03/A04/A11/A12 各跑冻结检查器与路线的检查器，对 A09 跑 HTML fallback 的冻结版与旧措辞版，结果在 `measured.json`（25 行，零调用）：

| 年度 | A03 | A04 | A09（HTML fallback） | A11 | A12 |
|---|---|---|---|---|---|
| FY2021 | 1.11 旧措辞（总注、缩写） | 0.0164 旧措辞（旧名） | 0.0072 旧措辞 | 3.113 万亿 旧措辞（冒号、分部） | 5,500 万 旧措辞（表头方向） |
| FY2022 | 1.12 冻结 | 0.02 旧措辞（旧名） | 0.0059 旧措辞 | 2.766 万亿 旧措辞 | 5,800 万 冻结 |
| FY2023 | 1.13 旧措辞（总注、缩写） | 0.027 冻结 | 0.0052 旧措辞 | 3.422 万亿 旧措辞 | 4,300 万 冻结 |
| FY2024 | 1.13 冻结 | 0.0263 冻结 | 0.0066 冻结 | 4.045 万亿 旧措辞 | 4,700 万 冻结 |
| FY2025 | 1.11 冻结 | 0.025 冻结 | 0.0066 冻结 | 4.791 万亿 冻结 | 4,000 万 冻结 |

"冻结"表示冻结检查器自己答得出，这 13 行路线返回的答案与冻结检查器的逐字节相同（`route_answer_is_the_frozen_answer`）；"旧措辞"的 12 行就是批次里扣留的 12 个位置，冻结检查器全部答不出、后继全部答出，记录写明用了哪几类措辞。每个最新年度都是冻结答案。A09 只量了 HTML fallback 这一支：后继与冻结函数只在这一支上不同（结构化主路径原样）。

## 验证

- `tests/vnext/test_historical_financial_wording.py`（快速层，构造文档，不到一秒）：每个目标函数从磁盘源码编译出的就是载入的代码对象；每个后继恰好带它的替换；替换不恰好出现一次、没有替换、不是顶层函数、源码载入后改过，都按名拒绝；旧分部句子绑定章节而冻结的不绑，最新句子两者一样，"其余归 Treasury"或两份列表不一致都不绑；冒号形式读得出、多一个冒号或换成别的分隔符读不出；一条总注不再挡住字母脚注，标题或两条无标记块仍然挡住；标签定义的缩写证明单位，标签没定义的名字不证明；冻结答出就原样返回、旧措辞答不出就返回冻结答案、采用旧措辞时带标记。
- `tests/vnext/test_historical_financial_wording_filings.py`（saved-source 层，读导出里的 FY2021 年报，约 160 秒）：五个指标的后继各跑一次，值等于测量值；四份只改一处措辞的构造副本（排除另一项业务的标签、排除另一项业务的引言、不说方向的反事实表头、不再叫目录的目录）都被拒绝，和冻结形式一样。
- `tests/vnext/test_historical_dei.py` 新增一例：只被 import 的名字不能覆盖。
- 注错（`injections.py`，在内存里改模块副本，不改检出文件）：结果在 `injections.json`。

## 不主张

- 内容验收：值等于申报里那个数，只说明路线读到了它；独立阅读另做。
- 这六类只在这一家银行的往年年报上测过；规则不点名公司，但别家的往年措辞没有被测过。
