# B02：同一概念下，目标年报重述了上一年（2026-10-02）

## 发现

50 个期间批次的报表阅读（`../content-acceptance/cross-source-read-full-frame.json`）里，Pfizer FY2021 的 B02 读出 DIFFERS，其余 27 个比较值都一致。

- 发布值 0.9396773885654290350291113868 = (81,288,000,000 − 41,908,000,000) ÷ 41,908,000,000。两年都用 `RevenueFromContractWithCustomerExcludingAssessedTax`，上一年取自 FY2020 10-K，也就是首次报告的数。
- FY2021 10-K 自己报告的 2020 年同一概念是 41,651,000,000：Pfizer 在 2021 年把 Meridian 列为终止经营，重述了 2020 年。按目标年报自己的比较数，增长是 0.9516。
- 也就是说，分子（2021 年收入）不含 Meridian，分母（2020 年首次报告的收入）含 Meridian，口径不一致。

已批路线（`catalog/deterministic_metrics.json` 的 `comparable_annual_revenue` 分支）规定上年收入取自上一年的申报（`accession_role: prior`），路线按规定实现；但分支名所说的"可比"在上一年被重述时不成立。此前的成对可比检查只在两年用了不同概念时才问，同一概念下的重述没有覆盖。

## 修复

`scripts/vnext/historical_results.py` 的 `paired_measure_problem`（规则文件）：同一概念的两年也要问一次——目标年报对上一年在同一概念下报了一个与上年取值不同的数时，按名扣留 `HISTORICAL_PAIRED_MEASURE_NOT_COMPARABLE`，并标 `same_concept_recast`。目标年报报的上年数等于上年取值、或根本没报上年数时，保留已批分支的答案。

不按重述后的数重新计算：那等于把上年数的来源从上一年的申报改成目标年报，属于改变已批分支，不在这次修复里做。

## 测量

`measure.py` 把 frame4 每个有值的 B02 与 A07 Run 记下的两条声明（当年、上年）交给新旧两版检查，目标年报的声明取自检出里保存的 Company Facts：46 个位置，只有 Pfizer FY2021 的 B02 移动（`measured-frame4.json`）。所有报表阅读里读过的 46 个 B02，40 个目标年报的比较数等于上年取值，其余是已被扣留的概念差异（Pfizer FY2023/FY2024）和这一个。

## 验证

- `tests/vnext/test_historical_paired_measure.py`：Pfizer FY2021 真实的同概念重述被扣留；FY2024 对 FY2023 的 Revenues 是另一个真实重述（595.53 亿对首次报告的 584.96 亿），也被扣留；把上年取值改成目标年报报的数、或从目标年报的声明里去掉上一年（构造），都不问；概念不同的扣留不带重述标记，原记录不变。
- 注错（`injections.py`，内存里改模块副本，不改检出文件）：四个注错——恢复"同概念不问"、把没报上年当成重述、给每个问题都标重述、把同概念的组合记成桥接——各由为它写的用例抓到，结果在 `injections.json`。
- 缺陷按坐标登记 `B02_PFIZER_2021_PRIOR_YEAR_AS_FIRST_REPORTED_AGAINST_A_RECAST`，撤回 frame4 发布的值；等新闭包下的定向重跑给出扣留结果后，按结果编号与闭包释放。
