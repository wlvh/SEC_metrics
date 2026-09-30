# 页码不是附注标题、括号编号是附注标题：Pfizer FY2024 与 Lumen FY2020–FY2023 的 D02（2026-09-30）

## 问题

全帧批次里 Pfizer FY2024 的 D02 以 `TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE` 失败（在 #47 的后继之前，冻结准备就停下了）。冻结导航报 `UNRESOLVED_NOTE_16A`：Item 3 引用 "Note 16A"，而文档里有两个 "Note 16" 标题候选。

成因是冻结附注扫描（`text_business_candidates._note_references`）的一条规则：加粗的单独编号块、后面紧跟一个以字母开头的加粗块，就当作附注标题——这是为 Macy's 旧年报 "1." 上方写 "Organization and Summary of Significant Accounting Policies" 那种版式写的。Pfizer 把每一页的页码也这样印：加粗、单独一块，在页脚 "Pfizer Inc." / "<年> Form 10-K" 之后。于是凡是一页以加粗章节标题开头，页码就被读成附注标题。FY2024 第 16 页以 "GLOBAL OPERATIONS" 开头（块 767 是页码 "16"，768 是该标题），所以 Note 16A 有了两个候选 [767, 3938) 与 [3792, 3938)。FY2025 第 16 页后面是正文，没有触发。

**同一批次还有第二个同样报错的位置：Lumen FY2023。** 原因不同：Lumen 在 FY2024 之前把附注标题印成 "(18) Commitments, Contingencies and Other Items"——编号在括号里——而冻结附注标题正则从编号开始匹配，不认开头的括号，所以 Item 3 引用的 Note 18 根本没有标题候选。全部 61 份年报里冻结导航未解析的恰好是 Pfizer FY2024 与 Lumen FY2021/FY2022/FY2023、CenturyLink FY2020（Lumen 更名前的 FY2020 年报，引用 Note 17）这五份。

## 量了什么（`navigation_effect.py` → `navigation-effect.json`）

在导出恢复的根上把 62 份年报（DEI DocumentType 为 10-K）逐份建成文本文档（61 份建成；Hilton 那份因 DEI 日期写法不支持，与本项无关）：

- 冻结规则由"单独编号 + 加粗块"造出的附注标题共 485 个，**Pfizer 六年每年 71–78 个，几乎全是页码**；Macy's 两份旧年报 36 个是真正的附注标题；另有 BAC 与 Pfizer 表格里的数字各两个。
- 判据（`historical_text_results.page_number_blocks`）：一个纯数字块，旁边的块在文档里重复至少 3 次（页脚），且同一页脚同一侧还站着比它小 1 或大 1 的数字。Pfizer 的页码全部符合；**Macy's 的 36 个真标题一个都不符合**——它们旁边是只出现一次的段落，或者是没有相邻编号共用的运行页眉。
- 括号编号的加粗块在 62 份年报里只出现在 Lumen FY2020–FY2023（各年附注 1 到 23 或 24 的完整序列）和本帧之外 Hyatt 的两个表头里。
- 新导航（`note_references`）把冻结扫描原样跑在"给它看的文本"上：页码置空，"(18) 标题"呈现为冻结正则认得的"18) 标题"；结果点名的每条摘录再换回申报原文，所以给扫描看的文本不会进入任何摘录。61 份里**恰好六份的导航结果变化**：Pfizer FY2024 的 Note 16A 定位到真正的 "Note 16. Contingencies and Certain Commitments"（[3792, 3938)，与 FY2025 同为"更宽的父附注"）；Pfizer FY2021 的定位范围不变，只是标题候选列表里少了页码 631；Lumen FY2021/FY2022/FY2023 的 Note 18 与 CenturyLink FY2020 的 Note 17 精确定位到括号编号的那个附注（至下一个编号附注为止）。函数说明里的"六份"是先写后量的，这次测量证实了它；页码那一半第一次单独量时只有 Pfizer 两份。

## 接线

D02 的冻结准备经 `release_aware_with` 换上这份导航（`_D02_LEGAL_SCAN`、`_D02_PREPARATION`），#47 自己的附注定位 `referenced_note_candidates` 也用它。C02 不经过这里。

## 实测

- `d02_compare.py` → `d02-compare.json`：在恢复根上用当前路线为 14 个位置建 D02 候选，并与全帧批次冻结的 Run 里的候选比对。**Pfizer FY2024 由失败变为 110 条摘录，Lumen FY2021/FY2022/FY2023 由失败变为 46/29/38 条**；其余 10 个（Pfizer FY2025、FY2023，Lumen FY2024、FY2025，Ford FY2021、FY2024，Marriott FY2021、FY2025，Southwest FY2022、FY2025）候选哈希与批次逐个相同。新建出的这些**不是内容验收**：Pfizer、Lumen 其他年份都有已登记的 `_LEGAL` 关键词代理缺陷，这几年没有读过。
- 用例：`tests/vnext/test_historical_note_navigation.py`（14 例，读导出里的 Pfizer FY2024/FY2021、Lumen FY2023、Macy's FY2021 与检出里的 Pfizer FY2025）。
- 注错：`injections.py` → `injections.json`（9 个，在最终代码上跑）；只有页码那一半时的 7 个注错结果留在 `injections-page-numbers-only.json`（7 个全部被抓）。
- 第一版还有一道"结果不得点名页码块"的守卫：置空的块既不匹配附注引用也不匹配标题，这道守卫没有任何输入能触发，按"自己新写而无例检验的判据删掉"删去。零 SEC、零模型调用。
