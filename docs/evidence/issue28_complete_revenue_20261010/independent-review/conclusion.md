# 限定差异独立审阅：83eaa4da

结论：**CHANGES_REQUIRED，1 项 P2 明确误接受**。指定 Pfizer FY2023 修复的来源/数值证据与新 Calculator 输出一致；新准入仍会把原文明确限定到公司部分业务的总额标成完整公司收入。此项属于新范围证明本身的直接矛盾处理，不要求建设通用语言理解平台。不能由本审阅授予全 B01、公司、PR 或正式采纳信用。

基线：`f6ef7886d6630f7675c25cd42e306c373ab05769`；审阅工作树 HEAD：`83eaa4da5d18c7accc0c093b1ef4db5f5158da16`。

## P2：同表成本与净利润不能证明全公司范围，明确排除说明被忽略

定位：`scripts/vnext/selected_revenue_scope_v1.py:71-80` 的所谓 full-statement 判定，以及 `:142-157` 的 split/complete_scope_proven 生成。

目前只要求同一 native context 的收入区段后面有一个成本及一个净利润 concept。这能证明表包含损益项目，但不能证明整表覆盖注册公司全部业务。一个只列分部、母公司或部分业务的损益表，同样可使用该公司的 CIK、全年、USD、无维度 context 并同时报告这些项目。新实现完全没有读取 caption/范围说明，也不处理已经显式出现的排除范围。

已运行两个小型隔离反例，使用现有正向 fixture 的原生数据/金额/期间/单位，重新计算更改后原件的 source hash；没有改产品、tests 或旧证据。日志见 `counterexamples.log`：

1. 只在收入表增加 `<caption>Income statement of Segment Alpha only; excludes all other company operations</caption>`。新 helper 返回 `REPORTED_COMPONENTS_AND_TOTAL`、`complete_scope_proven=true`；`admit_revenue_facts` 只保留 58,496,000,000 USD。公司部分业务被赋予全收入证明，且准入据此删除其他同期间收入候选。
2. 只在同表增加明确的说明行 `Total revenues exclude operations of Subsidiary Beta`。结果仍是 `complete_scope_proven=true`。

这是源文明确给出排除条件后仍授完整范围的已复现反例；不是声称真实 Pfizer 原件存在此排除条件。原生 context 无维度及可加总并不能推翻原件直接范围说明。当前输入核验/Calculator 只能继续检查主体数值身份，无法修正这份已经错误的范围赋义。

修复应限定于证明的必要上下文：在承认 split 完整范围前，复用现有结构读口保存并处理绑定该表/收入区段的 caption、标题和必要限定说明。已识别的直接排除条件不能仍产生完整范围证明或把受限总额准入为全收入；可以形成准确的局部未决并继续其他指标，也可以在现有源读口另行证明完整范围。保留 Pfizer 正向和完整客户合同收入的原选择。仅将受限表降为 `NO_DEMONSTRATED_SPLIT` 后原样接受同一已知小计，也不能闭合这个反例。

## 已核对的正向范围和保存身份

- 真实候选 `actual-calculator.json` 保存的 Pfizer FY2023 目标为 2023-01-01 至 2023-12-31，CIK 0000078003，USD；table_000113 的 Product 50,914m、Alliance 7,582m、Total 58,496m，native scale=6，可见年度/期间/单位一致、差额 0、XML 对应 MATCH。原错误 Result `a6e31052…08f7` 为 50,914,000,000；新 Result `128c170a…86da` 为 58,496,000,000。此处审阅保存的实际执行证据，未重跑大原件解析或公司 CLI。
- 本轮另用只读 SHA 校验 actual-calculator 所引用的 primary、XML、CompanyFacts 和目录原件/请求头：8 个文件均仍存在并与记录 SHA 相同。没有修改 #47/peer source-inputs。
- `admit_revenue_facts` 只筛 existing facts，保留合法事实对象/数值/fact_id/来源绑定；原 Spec 的概念优先级和 Calculator 未改。依赖 B01 在 B03 主计算前消费同一筛选结果，早期依赖回填也转发收入开关。
- 与基线逐 byte 对比，B01 Spec、Calculator、selected_income_source_v1、ordinary_income_input、historical_statement_cases 均未改；没有给旧结果/Spec/Run 重新签署绑定。
- shared resolver/preparer 的新开关默认为 False；financial_duration 的额外表头描述默认为空，普通旧调用保留原表头判断。普通保存入口只对 B01/B03 显式开启；新范围、源、期间、单位相关程序被加入处理身份，使程序变更触发重算。
- 当前公司保存证据的 FY2025 值为 62,579,000,000 USD，Result `536f3b12…ee1bf`、全年期间与旧选择一致。它是 `NO_DEMONSTRATED_SPLIT` 的保持原行为案例，不能被称为新全收入范围证明。本轮核对其九个源文件及七个结果文件 SHA，均与记录相同；保存记录中 first/repeat/results exit 均为 0，重复计算被禁用时结果七文件不变。本轮未重新执行该公司流程。
- `.github/workflows/company-current-records.yml` 的触发路径及实际 unittest 命令均已加入新 scope suite。未访问远端 CI，不以本地测试代替远端结果。

## 本轮验证及未覆盖

按委托的唯一必要短测试命令执行，**59 tests / 0 failures / 0 errors / 0 skips，0.400s**，见 `directed-tests.log`：

```text
PYTHONDONTWRITEBYTECODE=1 /private/tmp/issue28-company-c02-venv-20261006/bin/python tests/required_unittests.py tests.vnext.test_selected_revenue_scope_v1 tests.vnext.test_selected_income_source_v1 tests.vnext.test_ordinary_current_update
```

覆盖指定来源身份/单位/年度、可见短期间冲突、主/XMl 金额冲突、未完整收入区段、同申报总额存在、优先小计筛出后原 Calculator 正向选择、旧表头默认、普通保存派发、处理身份及相同输入复用。新增反例只有上面两个明确范围矛盾；没有继续穷举语义规则。

未运行大材料/公司 CLI、#47 历史接入、全公司/全 B01、远端 CI、SEC/provider/paid 或生产操作。当前未发现另一个可明确归因于本差异的误拒；这不表示所有收入布局已覆盖。历史消费者开发及业务完整交付仍由原负责方验收。

## 操作记录

只写本 `independent-review/` 目录的 `conclusion.md` 与三份必要日志：`directed-tests.log`、`counterexamples.log`、`evidence-inspection.log`。无 spawn/commit/push/网络/SEC/provider/paid/账户动作，无产品/tests/旧证据或 peer/#47 树修改。

工具量按包含嵌套口径：8 次 functions.exec + 15 次 exec_command = **23 次**（上限 40）；普通消息 2 条（开工说明 + 最终报告）。记忆快速检索未取得本收入差异的相关证据，结论依据本轮实际代码/指定证据/短测试/反例。

开始 UTC：`2026-10-09T21:04:22Z`；结束 UTC：`2026-10-09T21:08:27Z`；用时 245.8 秒（上限 20 分钟）。
