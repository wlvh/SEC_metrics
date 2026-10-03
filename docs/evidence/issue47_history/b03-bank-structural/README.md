# B03：银行的"结构性不适用"被 D&A 范围检查改写（2026-10-02）

## 发现

50 个期间的全帧批次（`../native-run-batch-2026-10-01/`，提交 `877793e9`）里，JPMorgan 五年的 B03 都以 `RunStoreError: MetricResult applicability differs from Spec/traits` 失败，没有具名理由。

读失败 Run 目录里留下的记录：B03 的规格只适用于非金融公司（`applicability.all = ["non_financial"]`），计算器对银行给出 `N_A_STRUCTURAL / PUBLISHED / TRAIT_NOT_APPLICABLE`，B01 同样。随后历史路线的 D&A 范围检查运行了，它的条件只看"结果已发布"；年报里标注了直接的 D&A 合计，而路线没有取任何 D&A，于是检查给出扣留，把结构性答案换成了 `APPLICABLE / WITHHELD / B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN`。Run 存储按规格和公司特征拒绝了它。拒绝是对的，错的是检查的条件。

这是本 Issue 接入 B03 扣留时引入的缺陷：在补取 JPMorgan 的分片之前，银行的期间从未选得出来，B03 也就从没有在银行上运行过。#28 普通路线的同一检查（`b03_depreciation_scope.assess_direct_depreciation_scope`）只在 `publication == "PUBLISHED"` 且 `reason_code == "PASS"` 时才问，没有这个缺陷。

## 修复

`scripts/vnext/historical_zero_ai_results.py`（规则文件）：与 #28 相同，只在结果已发布且 `reason_code == "PASS"`（确实用 D&A 算出了值）时问 D&A 范围。

- 结构性不适用：没有取 D&A，不问。
- 与 D&A 无关的"无意义"答案（Paramount FY2025 接续注册人首个年度 146 天，`ANNUAL_DURATION_OUT_OF_RANGE`）：不问。修复前它被问过，检查答 KEEP，所以值没有变；修复后不问，值仍不变（结果记录不含选择细节，结果编号不变）。

## 验证

- 用例 `tests/vnext/test_historical_da_scope_route.py::AnAnswerThatTookNoDAIsNotAsked`：
  - JPMorgan 的期间在检出里选不出来（检出里的分片陈旧，新分片在获取导出里），所以银行是构造的：Salesforce FY2026 自己的年报（它的直接候选确实互相矛盾），公司特征换成银行的。要求结构性答案保留、检查没有被调用；同一年报在真实特征下仍按名扣留。
  - Paramount FY2025：让年报"说"一个构图无法消解的矛盾（构造），首个年度不足一年的答案不被改写。
- 注错（`injections.py`，在内存里编译改过的模块副本，不改检出文件）：对照两例全过；把条件改回"只要已发布"，两例都失败；改成"已发布且适用"，只有 Paramount 那例失败，说明 `PASS` 这一半也承重。结果在 `injections.json`。
- 两个 B03 路线用例模块 21 例全过；本世代快照重铸，`--check` 通过。
- 真实材料上的确认：JPMorgan 五年的 B03 在新闭包的定向重跑里重跑（见 `../native-run-batch-2026-10-01/README.md`）。
