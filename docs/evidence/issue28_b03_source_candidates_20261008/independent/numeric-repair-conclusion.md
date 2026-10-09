# af660f1 数值修复差异限定独审

结论：**原 3 项 P2 均已实质修复，本次数值修复差异审阅通过；未发现新增阻断项。** 该结论只覆盖 `e349491db03e50e286c178b3d2d6f6425f770952 → af660f1e52bf7b1199d7c56ea65e6b20227ec930` 的数值事实接纳与局部未决处理。原 `conclusion.md` 的失败结论和日志保留，不倒改原补丁状态。没有授予完整 D&A、B03、MetricResult、Run 或生产信用。

## 实际覆盖

- 同一代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-b03-source/SEC_metrics`。开始及报告写入时复核 HEAD 为 `af660f1e52bf7b1199d7c56ea65e6b20227ec930`。
- 阅读新模块/测试的精确差异和 README 新说明；复用首次审阅的原件绑定、期间/主体/单位/fullQName/维度、旧默认及无结果发布结论。
- 阅读提交中的 `numeric-repair-tests.log` 和 `numeric-repair-real-summary.json`；后者记录开发者对三年原件对的重放及候选/证明未变。本阶段未重新读取原件，不把该摘要当成新的独立原件验收。
- 未重开三年完整业务范围、跨页披露解释、消费者闭环或 PR61 runner/workflow；未运行 fast 或其他长材料。

## 原 3 项 P2 的复核结果

1. **数值标签证明已补上。** 新 `_numeric_value`（42-48 行）核对合法 inline namespace/nonFraction，或实际 XML 元素 URI/local name 和声明概念一致。重放首次审阅完全相同的 `wrong:nonFraction` 反例，输出不再给候选，并给 `DEPRECIATION_SOURCE_NUMERIC_TAG_NOT_SUPPORTED`。
2. **数值写法先验检查已补上。** 新入口在共同正规化前核对已存在的 reported-fact 数值写法策略（53-59 行），并禁止普通 XML 使用 inline scale/sign/format。原 `1,38` 反例不再成为 138，保留独立 49 并给具名未决；普通 XML 元素形式的相同反例亦被局部拒绝。实际采用的策略随候选输出保存，可核对其支持子集。
3. **nil 变成局部无值状态。** 数值/上下文解释的 ValueError 在单事实层处理（122-126 行）。原 nil 反例返回独立有效的 138，给两条 D&A nil 原因，既不推零也不抛出全局 C03 异常。另一个不受支持的 transform 也只阻断其事实，保留其他候选。

## 实际测试

指定命令：

`TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest discover -s tests/vnext -p test_ordinary_depreciation_sources.py -v`

独立重跑结果：**11 项全部通过，0.016 秒，exit 0**。日志：`numeric-repair-tests-independent.log`。

另做 **18 项内存实验，全部符合预期**，日志分别在 `numeric-repair-probes.log` 与 `numeric-repair-original-counterexamples.log`：

- 合法未格式化数值：138.5、-138、+138、.5；普通 XML 元素的 138.5 也正确配对。
- 已支持 dot-decimal transform：1,380 与 1,380.5 正确正规化。
- 真实区分 inline/XML 表示：合法 inline scale/sign 和普通 XML 的 -1380 配对；固定零 transform 和 XML 的 0 配对；XML 擅用 inline scale 则只局部拒绝。
- 未声明 transform 的逗号、内部分隔空格、科学记数法被具名拒绝；未支持 transform 也局部拒绝。
- 原 3 项精确反例全部转为预期的局部拒绝/未决；所有检查结果保留 `metric_result_created=false`、`definition_complete=false` 和候选 `full_da_role_established=false`。

这些实验是受支持的有限数值表示检查，不证明任意 XBRL transform 均受支持，也不承担完整指标计算验收。

## 保持的边界与执行记录

FY2021 的 visible_blocks 仍只是包含事实的原结构块，跨页续文要从原件重新打开；该事实复用首次审阅，本阶段未重新解释完整披露。维度细分仍不授包含/加法证明，完整 D&A 与消费者接入均未审为完成。

- 原任务起点：2026-10-08T15:39:05Z；本阶段首次 clock：2026-10-08T15:51:30Z；报告 clock：2026-10-08 15:55:03 UTC；原绝对截止 17:09:05Z 不重置。
- 本阶段工具 **18 次**（6 次 functions.exec 外层、12 次嵌套工具）；原累计 42，加总 **60/80 次**。
- 普通过程消息 0，问题 0；本次最终报告 1，累计普通消息 **2/3**。
- 只新增本代码根 `independent/` 内本报告和 3 份新日志；没有覆盖原失败结论、打包、开发、commit、push、spawn、业务请求或原件/对方现场/账本动作。
