# e349491 B03 原件候选适配限定独审

结论：**限定审阅未通过，存在 3 项 P2，需要修复后再接入消费者。** Marriott FY2021 的真实原件重放与已保存候选逐字段一致；当前实现没有创建 MetricResult/Run，没有证明完整 B03 或完整 D&A，也没有生产信用。本结论只针对新源候选 API 的事实接纳与未决处理，不重审受信任的 PR61 runner/workflow，也不要求扩建业务口径。

## 精确对象与覆盖

- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-b03-source/SEC_metrics`。
- 审阅 HEAD：`e349491db03e50e286c178b3d2d6f6425f770952`；比较基线：`8588ccbbb1c91d81e0fb1a89dff3575214282549`。开始与结束均核对 HEAD。
- 修改范围：`scripts/vnext/ordinary_depreciation_sources.py`、`tests/vnext/test_ordinary_depreciation_sources.py`、README 及 architecture/capability/interact 对应增量。
- 为核对实际行为，只读追踪所调用的本地解析、上下文证明、金额正规化、精度选择和原文块索引函数；未审改它们。
- 检查已选 primary/XML 的 hash/URL/accession/company/document 绑定、年度 DEI/主体/期间、完整命名空间概念、USD 单位、维度配对、精度冲突、未决状态及无自动默认接入。
- 阅读 real-2021/2022/2023，复核全部顶层/候选内容 id。只独立重放 FY2021 的一组 primary/XML 原件，路径来自固定位置文件；两个原件 SHA 和候选引用的原文 span SHA 均吻合。FY2022/2023 未重新读取原件。
- 未运行 fast 长材料、公司计算、业务请求、provider/paid/SEC 请求、生产或账本动作；未开发、commit、push、spawn 或修改对方工作区/原件。

## 必须修复的发现

### P2-1：已解析的 name 属性不足以证明它是受支持的数值 XBRL 标签

位置：`scripts/vnext/ordinary_depreciation_sources.py:81-99`，尤其 95-97。

当前代码核对概念的 URI/local name、context 和单位，却未核对原标签的类型和命名空间。`_ReportedFactMetadata` 的 concept 从 name 属性取得，原生事实流又把任何带 contextRef 的标签都计为事实；所以两者 ordinal 一致不能补上这项证明。在原测试样本中，仅把 primary 的 `ix:nonFraction` 改为 `wrong:nonFraction`、wrong 绑定非 XBRL URI，金额、context、unit、name 和重新绑定的原件 hash 均保持，输出仍给出 138/49 两个候选，issues 为空。XML 同伴为正确事实也不能证明 primary 是数值事实。

应在新适配层区分合法 inline 数值标签和普通 XML 数值概念元素，核对前者的 inline namespace/type，后者的实际元素 QName；不把不受支持的标签当作已核对数值。该负例验证来源表示的正确性，不依赖外部攻击者假设。

### P2-2：未经支持的数值写法会被共同正规化成一致金额

位置：`scripts/vnext/ordinary_depreciation_sources.py:97`（随后 137-140 使用已正规化值配对）。

新入口直接使用 `_source_value`。它最终调用会删除逗号和空格的 `_numeric_xbrl_value`，却没有像已有 reported-fact 入口那样先核对数值写法是否受支持。将 XML 同伴的 138 改为未声明数值 transform 的 `1,38` 后，程序仍产生 value=138 的配对候选且 issues 为空；不合法/不受支持的写法被静默改成整数，再被 primary 的 138 看作相互确认。

应分别核对 XML decimal 写法和已支持 inline transform 的数值写法，然后正规化；无法证明时给具名未决，不应借另一份原件掩盖该表示问题。不能仅追加“正规化后相同”的测试。

### P2-3：正常的 nil 事实会使所有候选一起丢失

位置：`scripts/vnext/ordinary_depreciation_sources.py:95-99` 及 121-123。

单条候选的 `_source_value` 调用不在事实级错误处理内。在原测试样本中，把 primary/XML 的维度细分 49 改为合法 `xsi:nil="true"` 空事实，同时保留独立有效的 138，整个 API 抛出 `GovernanceSignalError: C03_NIL_TARGET_COMPENSATION`，不返回 138 或具名 nil 未决。nil 是来源正常可报告的无值状态；它也不应被解释成零。

应保留有效事实，并将此条无值事实列入源候选 issues/未配对状态；金额解释失败与原件整体身份失败分开。错误信息也应表述 D&A 原件问题，而不是 C03 高管报酬问题。

上述反例均只在内存中改变测试样本；没有写原件或业务账本。结果保存在 `independent-probes.log`。本次没有修代码。

## 已证实的正向行为与实际边界

- 指定的 8 项单元测试全部通过（0.014 秒，exit 0），日志见 `tests.log`。
- 5 项额外正向/拒绝核对通过：prefix/context id 重命名仍按完整 QName/范围配对；兼容舍入选较精确金额；金额冲突仅移除相应候选；不同 member 不配对；货币命名空间错误不供候选。
- FY2021 独立重放得到 4 项源候选、2 项 context specialization、0 issues，完全匹配保存记录。原文说明摊销 165m 中包含报销费用 62m，折旧 138m 中包含 49m；代码没有把它们加到各自总额上，也没有声称完整 D&A。
- FY2021 折旧原文跨页：当前 visible_blocks 在“including ”处结束；其后原件块明确说减值相关项目在 2020/2019。此续接块未进入候选 visible_blocks（`cross-page-context.log`）。因此该字段只能称为“包含该事实的原结构块”，不能作为完整披露段落交给下游据此判断本期减值；原件引用仍可重新打开，当前输出也保留未决且未下本期结论。此点作为已知边界记录，不将完整 D&A/后续解释工作扩成本次修复目标。
- 旧 ordinary 默认/公司 CSV 路径没有接入新 API；这里只检查补丁实际新增引用与接口说明，未借未重跑的旧完整材料宣称端到端验收。

## 测试、时间与资源记录

- 指定命令：`TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest discover -s tests/vnext -p test_ordinary_depreciation_sources.py -v`。
- 独立核对：8 个内存反例/配对实验中 5 个预期行为通过，2 个不应接纳的表示被接纳，1 个 nil 实验抛错；3 年保存候选自校验通过；1 年真实原件对重放通过。
- 接受任务起点：2026-10-08T15:39:05Z；首次 clock：2026-10-08T15:40:00Z；报告 clock：2026-10-08 15:46:49 UTC。绝对截止为 17:09:05Z，本次未接近上限。
- 工具调用累计：42 次（保守计数包含 10 次 functions.exec 外层及 32 次嵌套工具调用）；普通过程消息 0、问题 0、最终报告 1。上限 80 次 / 90 分钟。
- 本次只写本代码根允许的 `docs/evidence/issue28_b03_source_candidates_20261008/independent/` 内 conclusion.md 和 3 份日志。不打包。
