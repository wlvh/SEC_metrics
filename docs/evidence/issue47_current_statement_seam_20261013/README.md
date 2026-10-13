# 当前年报输入直接消费共用陈述计算

回应公共负责人转交的PR238接收缺陷：当前B04/B07 wrapper先准备正常当前年报，却随后完整搜索历史目录，再重建历史annual；JPM历史分片冲突因此在结构性不适用判断前拒绝了原可用的当前入口。公共wrapper/适用性分派由#28修，本方仅提供共用核心的最小参数接缝。

`historical_statement_cases._prepare_historical_statement_case(..., prepared_current_annual=current)` 仅接受current-annual companyfacts组件族；B02比较族不能借用。current是`normal_annual_input_v2.prepare_saved_annual_input(...,ordinary_registered=True)`的实际输出。核company/input身份、当前选择规则、发行人财年、原actual dates及三个保存Source proofs。current路径以保存main中目标申报的五个身份字段作核对，不搜索历史shards；历史默认仍按原resolve→historical annual→filing_inventory执行。

后续主体/修订准入、原件范围/概念/期间/单位、适用性、CF claims和Calculator使用同一旧实现，没有第二计算器，也没有给JPM手写N/A。旧prior及历史subject规则继续保留。当前来源消失或主申报身份变化仍拒绝，不借前一年或缓存值。此接缝不是历史在线取源，也不调整当前/历史比较口径。

实际保存来源（sources只读）禁止`resolve_period_selection`、`prepare_historical_annual_input`、`filing_inventory`三入口：

- Marriott FY2025 B04：正常年报准备1.379s、共用case0.496s，2,601,000,000USD/PASS，完整prepared对象保持，见`current-source.json`。
- Marriott B07：共用case0.496s，5.118665018541409147095179234 ratio/PASS。
- Salesforce FY2026 B04：共用case0.536s，7,457,000,000USD/PASS，actual dates2025-02-01→2026-01-31，不被写成自然年。
- JPM FY2025 B04：共用case0.436s，原traits/Calculator规则返回N_A_STRUCTURAL、null/TRAIT_NOT_APPLICABLE，没有历史目录前置。

后三项见`boundaries.json`及执行日志。它们是shared case验证，不冒称公共wrapper已修改、公司保存/复跑/CSV已验收。公共方随后接回原PR238并验证其当前入口；其此前正确Marriott公司结果复用，不重全公司/五年或150格普查。

98历史入口、分派、修订范围控制0.910s、零失败/错误/skip，见`final-controls.log`；当前接口拒错company、错年、错input身份和比较族，旧历史主体/修订/单位反例保持。日期完整性守护是同一prepared对象已有的实际日期核对，不重新取得年报。

```python
current = normal_annual_input_v2.prepare_saved_annual_input(
    repo_root=source_root, company_id=company_id, ordinary_registered=True)
case = historical_statement_cases._prepare_historical_statement_case(
    repo_root=source_root, company_id=company_id, metric_id=metric_id,
    fiscal_year=current['table_input']['target_period']['fiscal_year'],
    prepared_current_annual=current, withhold_known_source_errors=True)
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_statement_cases tests.vnext.test_history_company_dispatch \
  tests.vnext.test_statement_metric_amendment
```

新增调用0/0/0；原Source、旧任务/Run/结果/失败及账本不改，无作者Ready/merge/采纳/部署/active。本批source-only/core结果不代完整1950业务责任。已有company workflow直接加载被修改的历史statement测试，不改公共runner/全局CI。
