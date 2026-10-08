# C03：从没有 inline XBRL 的代理的薪酬汇总表读 CEO 总薪酬（2026-09-30）

## 为什么是实现工作而不是口径决定

已批 C03 定义："来源：DEF 14A，优先 ecd XBRL facts；候选：CEO / PEO total compensation"。2022 年申报的 8 份代理（首次报告 FY2021，1 月财年末的报告 FY2022 或 FY2021）没有 ECD 事实，它们自己的薪酬汇总表（Summary Compensation Table，SCT）就是剩下的已批来源。此前记录里"是否用后来年份代理的 PvP 标签值"那个待决项因此撤回：读首次报告该年的代理的 SCT 是实现工作；用后来年份代理里的重述值才是另一件事（本轮只把它用作独立核对，见下）。

## 冻结读法为什么不行

冻结的 `governance_compensation_table.resolve_compensation_table` 是为年报第三部分写的：期间从年报的 DEI 事实来，Total 从与表头单元格对齐的行单元格读。代理没有 DEI 事实；8 份里有 5 份表头与行不对齐——Enphase 的 "$" 单独成格、Ford 用零宽单元格填充、Macy's 表头拆成三行且 CEO 头衔印在名字的下一行、Lumen 表头只写 "Total"、Paramount 与 Macy's 的标题带年份（"SUMMARY COMPENSATION TABLE FOR FISCAL YEAR 2021"、"2021 SUMMARY COMPENSATION TABLE"）。逐份补这些版式就是拟合。

## 读法（`scripts/vnext/historical_proxy_compensation.py`，规则文件）

依据是 SEC 规则本身：Item 402(c) 规定 Total 是同行其他金额之和。

- 每位高管的行从"年份等于钉定年报财年"的那一行开始、到下一个这样的行为止（代理按新到旧列每位高管的年份，每位列名高管都有最新年）；这些行里年份之前的文字与纯文字行就是姓名与头衔。
- 该财年行里年份之后的金额按顺序读出（"$"、零宽格不算格；"(3)" 这类脚注标记去掉；"—" 等读作 0），**最后一个金额只有等于其余之和才当作 Total**。列错位、"$" 格、零宽格都过不了这个等式；过了的就是申报人报告的 Total。
- 注册人 CEO：块内文字含 "Chief Executive Officer"/"CEO"/"PEO"，前面紧挨的不是 Deputy/Assistant to/Vice/Office of/Staff to，后面不是逗号、"of" 或破折号接另一机构（Macy's 的 "Chairman & CEO, Bloomingdale's" 是子公司 CEO）。
- 一年两位 CEO（前任与继任、联席）按定义扣留，两位都保留为候选。
- 身份：封面 + SEC 记录中该 CIK 在申报日的名称（`historical_proxy_identity`）；期间：表内年份等于钉定年报的财年标签；币种：表内有 "$"，且沿用冻结读法对外币与"以千计"语境的拒绝；标题（年份若有须等于财年）在表前 12 个非链接块内或表头行里。
- 新规格 `catalog/r6/C03_proxy_compensation_table_v1.md` 写明这个解析器与它的依据。注册补丁给它加了与住宿路线同形的窄豁免（只对 `issue_47_v1`、C03、这个解析器名、整案重建）：`run_store` 否则要求确定性表格观察带审阅批准效力。

## 实测

8 份代理（`tests/vnext/test_historical_proxy_compensation.py`）：

| 代理 | 结果 |
|---|---|
| Paramount 前身 FY2021 | 20,035,212（Bakish） |
| Enphase FY2021 | 19,019,162 |
| Lumen FY2021 | 22,654,781（Storey） |
| Pfizer FY2021 | 24,353,219（Bourla） |
| Ford FY2021 | 22,813,174（Farley） |
| Macy's FY2021 | 12,290,931（Gennette；子公司 CEO Tony Spring 不算） |
| Marriott FY2021 | 扣留：Capuano 18,391,882 与已故前任 Sorenson 12,278,151 |
| Salesforce FY2022 | 扣留：联席 CEO Benioff 28,602,112 与 Taylor 22,794,415 |

**独立核对**：各注册人 2023 年代理的薪酬与业绩 ECD 标签（`ecd:PeoTotalCompAmt`）给同一财年的 PEO 标的汇总表总额，用例里用另一个正则读法读出，**8 份的每个候选（含两家各两位）全部逐位相等**。这是另一份、带标签的文档，所以它是核对，不是取值来源。其中一处要说明：Macy's 2023 年代理把"2021 财年"（止于 2022-01-29）标在自然年 2021 上，所以核对按"期末相差 60 天内"匹配。

注错：`injections.py` → `injections.json`，在隔离克隆里原地改代码后跑；对照（两个测试模块）通过，13 个注错全部由为它写的用例抓到。其中 `THE_ROUTE_DOES_NOT_TAKE_THE_PROXY_TABLE_S_ANSWER`（路线不接读表的答案）只由路线层那一条用例抓到——读表本身的 18 例看不见路线有没有用它。

## 不保证的

- 规则写在这 8 份上、也核在这 8 份上；与后来标签的一致是独立证据，但不是留出样本。
- Salesforce FY2022 与 Pfizer FY2021 今天在期间选择处停下（历史分片陈旧），这两个位置的 Run 要等分片刷新。
- 定向原生 Run 等全帧批次跑完、运行树同步（含新的注册补丁）之后。零 SEC、零模型调用。
