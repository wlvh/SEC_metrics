# 融资租赁、供应商项目与来源缺口

本增量为 B06 保留可以直接复核的来源信息：实际原文、原生概念、主体期间、货币单位、表行及单元格。它不把概念名当成债务性质，不把缺少单独披露当成零，也不批准完整债务集合。普通 Run 的接线仍待运行中的固定版本批次结束。

## 三份实际年报的区别

| 原件 | 已核对的披露 | 不能据此推出的结论 |
|---|---|---|
| Pfizer 2025 | 574,000,000 USD 供应商项目；原生报表分类明确指向 `AccountsPayableCurrent`，表列 `Confirmed obligations outstanding, ending`。完整原件及 XML 没有单独融资租赁概念，全文也没有相应文字命中 | 不因没有单独融资租赁披露而填零；报表分类不自动变成完整 B06 的排除批准 |
| Southwest 2025 | 24,000,000 USD 被标记为 `SupplierFinanceProgramObligationCurrent`，实际表行却是 **Deferred supplier credits**，位于应计负债明细；没有对应的原生报表分类枚举 | 不把它直接称为普通贸易应付款、借款或已批准排除项；金额性质的歧义保留 |
| Marriott 2025 | 确实存在融资租赁原生事实和相关原文；没有当前供应商项目余额 | 保持原有非正权益处理及债务范围检查的独立性 |

`prepare_saved_financing_inventory` 只接收公司与数据目录，从既有入口重新发现和准入原件；调用方不能传答案或挑选原生事实。输出包含 `zero_inferred=false`、`absence_established=false`、`debt_completeness=NOT_PROVEN` 和未授予债务集合处置的状态。它不创建 Result 或 Run。

## 实际来源缺口

JPM 最新主清单保存于 **2026-08-17**，七份历史分片却保存于 **2026-07-06**。例如清单称 `submissions-001` 覆盖 2025-07-15 至 2025-08-13，但保存的正文实际覆盖 2025-05-30 至 2025-07-02。其他分片也存在类似错位，影响事件清单和需要前期来源的指标。该问题不是过滤后的行数误比，也不能用跳过日期范围检查解决。见 `source-gaps/jpm-history-census.json`；本次未获取新来源。

## 验证

- `checks/seven-tests.log`：7 项测试通过；Python 3.9 同样通过。覆盖三份真实原件、保留实际供应商标签、HTML/XML 金额或报表分类冲突、假单位/概念命名空间、源字节绑定及连字符形式的融资租赁披露。
- `development/hyphenated-disclosure-first-failure.log`：补充反例发现 `finance-lease` 与 `finance‑lease` 曾被遗漏，现已修复并复验；仍不从文字命中推导金额或批准。
- `portable/execution.log`：三家公司在无 `.git` 的独立数据目录、新 Python 3.9 进程中完整重建一致；修改源文件或数据政策均拒绝。
- 所有实际源码和归档文件 SHA-256 见 `archive-index.json`。源语义及公司硬编码扫描通过。

新增 provider / paid / SEC 为 0 / 0 / 0；正式 active 未改。这里的具体来源限制继续纳入完整 390 坐标交付，不构成整个委托的停点或完成证明。
