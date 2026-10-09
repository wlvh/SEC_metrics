# 指定补丁限定独立审阅：NEEDS_FIX

结论：发现一项 P2。分部汇总去重本身成立；私有表格索引识别 display:none 的边界过宽，会删除实际可见的普通空 spacer，使不成立的年列定位获得收入扣减证明。需要有限修正该识别条件与相应回归，未要求新增完整 CSS 或通用表格解析平台。

审阅基线：`9493ed0e973570f1331a898c73633ae4e69c8bab`。指定补丁及实际 HEAD：`2bec3464e735bc5cbf928573b1bd1538b06789f3`。工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-contract-aggregate/SEC_metrics`。审阅范围为 `scripts/vnext/b03_contract_amortization_scope.py`、`tests/vnext/test_b03_current_input_scope.py`、`tools/run_fast_tests_v2.py` 增量。只读取必要的调用方、继承表格解析与项目说明；未改产品代码。

UTC 开始：2026-10-09T12:06:42Z。UTC 结案记录写入：2026-10-09T12:12:46.884494+00:00。总计工具调用 32 次，包含 functions.exec 包装和其内部 exec_command；普通消息 3 条（初始告知、一次进展、最终回复），问题 0，子代理 0。此计数包括写入本结论后的最后一次只读核对。

## [P2] 可见空格单元不能按任意 display:none 子串删除

位置：`scripts/vnext/b03_contract_amortization_scope.py:34–37`，`_RevenueTableIndex._hidden_cell`。

当前正则只检查样式字符串中是否出现一项 display:none，不检查后面是否重新将 display 设为可见，也会在注释里匹配 display:none。例如下面第一格是可见空 spacer，第二格也是可见空 spacer；当前代码两者都删除：

```html
<td colspan="4" style="display:none;display:table-cell"></td>
<td colspan="4" style="display:table-cell;/* x;display:none; */"></td>
```

在补丁现有 ContractAggregateTest.material() 的第三个分部总额事实前插入第一格，保留其余原输入与 header：普通 `<td colspan="4"></td>` 使 helper 返回 None（列定位不成立），上述可见样式却返回全部四项证明。后写同样带 !important 的 display:table-cell 也出现相同错误接受。这些是独立执行的小机械反例，并非外部攻击或新的语言理解要求。误删实际可见列直接改变本补丁承诺保留的年列定位。

建议在此私有索引里只跳过可明确识别为隐藏的单元格。对于重复/冲突 display 或包含不能直接安全判定的样式语法，保留 inherited 的 cell；不需要实现完整 CSS cascade。增加一项后写可见 display 和一项注释反例即可。复现代码及 16 项小探针的输入、期待、实际结果在 `mechanical-boundaries.log`：13 项通过，3 个变体错误接受，属于同一根因。

## 亲自执行的验证

`python3 tests/required_unittests.py tests.vnext.test_b03_current_input_scope` 在指定 HEAD 独立执行，25 例通过，0 failures/errors/skips；unittest 5.335s，子进程总计 5.611737s。日志为 `required-module.log`，有完整命令、工作树、HEAD、UTC 起止和返回码。当前 Marriott 测试走临时复制来源/结果目录，验证 145+313=458m、排除收入扣减 135m；Salesforce 继续 WITHHELD/null，保留 B01 和两个不同候选的来源说明。

另执行 16 项 helper 机械边界与 4 项直接索引检查，后四项全部通过。非空隐藏 td、空 span 子元素、self-closing span 子元素、事实子元素、嵌套表格、非空隐藏 th、普通 spacer、命名/数字 entity 均保留 inherited 的处理；真正空叶 td/th 可省略。所有小索引比较的原始源字符串、事实数量与字节位置保持；错误年 header、错误 gross/net、重复 consolidated、无 individual segments 的 aggregate、segment sum 大于 consolidated 均拒绝。具体结果分别在 `mechanical-boundaries.log` 与 `structural-and-parent-log-inspection.log`。

通过代码逐项检查：唯一 consolidated、同 product 的唯一 OperatingSegments total、不同 segment member、total==segment sum、segment sum<=consolidated 保留；每个 amount 均仍经过原表 gross/deduction/net、年列、符号、金额/scale 对照。aggregate 不加入金额，不替代 consolidated；selected-component 的来源 bytes、entity/period、namespace 与 USD 检查未被此补丁删除。原始来源不改写，通用 _InlineTableIndex/table_grid 文件无修改。fast selector 仅追加该 6 例 class，runner 函数 AST 与 base 相同。

## 父执行证据和未覆盖

只检查父执行 `README.md`、旧失败、`final-saved.json` 和 reproducer 代码，未调用 reproducer，也未读取其真实历史 source-root。`final-saved.json` 记录 FY2021 55+20=75m、FY2022 60+29=89m、FY2023 65+22=87m 对 consolidated 88m；每年四项原 ordinal 全部保留并区分 consolidated / segment / total。该摘要属于父执行日志检查，不能列作我亲自独立重跑三份历史原件的通过证据。87/88 差异没有在补丁中被四舍五入或补加。

未执行三历史原件独立重跑、#47 历史消费者/公司 CSV 接收、完整 B03 D&A 范围验收、全 fast/CI、模型/provider/SEC 请求、发布/active 切换。完整年均经济摊销、fulfillment-cost 与 lease expense 仍按原消费者限制判断；此结论不升级三个历史 B03 为成功，也不授生产或合并信用。未操作 #47 工作树、真实账本/历史运行根，未 spawn/commit/push/tar。

本次新增文件仅为本目录 `conclusion.md` 和三份 `.log`。父证据与指定代码/测试/runner 字节保持原状。
