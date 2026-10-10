指定 SHA 限定独审结论：REQUIRES_FIX；发现 1 项 P2。

审查对象为 base `84d15f35eb3f0a7b6dc9e0b06100ceba738c7adf` → patch `7a2ffdd20b95888dbf0b518e6b3096f2dc67b056`。实际 HEAD 为 patch，开始时工作树干净。新增审查范围仅 `selected_reported_revenue_v2.reported_revenue_scope` 的 operating 分支、`selected_revenue_scope_v1._statement_scope` 的两个 default-empty 参数，以及 `ReportedOperatingRevenueTest`。结论不预设 PASS，不授合并、采纳、生产、active 或真实调用权限。

**[P2] 新增 operating 分支把括号中的范围限制和“小计”字样删除后授予完整总额信用。**

定位：`scripts/vnext/selected_reported_revenue_v2.py:57-60`、`:71-74`。新 operating 判定及其费用总额判定共用 `_label_key`；该旧函数在 `selected_revenue_scope_v1.py:38-39` 删除任意单词型括号 `\([a-z0-9]+\)`，并不限于经过证明的脚注标记。因此在新增 operating fixture 上仅替换可见标签：

```python
b'Total operating revenues' -> b'Total operating revenues (domestic)'
b'Total operating revenues' -> b'Total operating revenues (subtotal)'
b'Total operating expenses' -> b'Total operating expenses (domestic)'
```

三例 base 均返回 `NO_REPORTED_TOTAL_PROVEN` / `complete_scope_proven=False`；patch 三例均返回 `REPORTED_CONSOLIDATED_TOTAL` / `complete_scope_proven=True` / `58496000000`。复核同时传入匹配的原生 XML，因此不是漏供 XML 所致；标签中的限定直接消失，而 native entity/period/amount/XML 只证明数字绑定，不能撤销原文范围限制。`_statement_scope` 对这些有原生事实的行跳过 unknown 检查，现有排除关键词检查也不捕获 `(domestic)` 或 `(subtotal)`。

这项代码复用了旧 normalization，但之前 operating label 没有新完整信用；错误接受由此次新增分支暴露，属于本次新增范围。建议在 operating 分支用保留括号限定的原文标签进行准入；若需要接受脚注，只删除已证明属于脚注的标记。把上述三例加入限定负例，未知或小计范围不得获完整总额信用；维持旧普通 V2/V1 默认输出。无需改业务口径、扩建语言分类规则或按公司设特例。

**已经确认的部分与证据。**

- 指定四套定向测试实际通过：61 tests，0 failures / errors / skips，exit 0；runner 用时 7.675 秒，完整 subprocess 7.993 秒，记录于 `directed-tests.log`、`test-execution.log`。现有新增测试未覆盖上述括号限定，测试通过不能消除该发现。
- 额外小反例共七种：未知无原生注释行拒绝；明确 Segment 限制无完整信用；错误可见年列拒绝；`Subtotal operating revenues` 不授完整信用；三种括号限定错误接受。逐例 base/patch 对照见 `counterexamples-and-compatibility.log`。
- 基于相同小 valid fixtures 对比 base 与 patch 的完整返回字典：普通合法 V2、显式 single-line、V1 三种均完全相等，含 `scope_id`。基线模块从指定 base 原字节在内存加载，基线 V2 绑定基线 `_statement_scope`，不以新 helper 代替旧实现。该证据限定于这三种样例，不声称穷尽全部旧输出。
- 实现未按公司、CIK、固定年份、表坐标或金额特判；返回原生已报告 revenue amount，没有相加收入组件或改为收入减费用。operating expense 在同一原生 context、同表且收入之后；旧实体/年度/单位/可见列/已报告金额与 XML revenue 核验调用仍在。
- 读取主证据 README、`actual-original.json`、`final-actual-company.json` 及保留失败日志。保存公司记录的三个测试代码 SHA256 与 patch 当前字节完全匹配。记录的 Southwest FY2025 B01 为 `28063000000 USD`、`2025-01-01..2025-12-31`、原生 revenue ordinal 168 / table33 row7 col15；expense 为 `27635000000` / ordinal189 / 同 c-1，scope 为 complete。first/repeat/independent-reader exit 均 0，repeat 保留原结果字节及目录；公司读取仍明确为 `SAVED_RECORD_CHECKED_CONTENT_NOT_ACCEPTED`。本次只核读保存记录，不复跑真实公司或大来源，不把历史记录说成本次现场公司重验。
- 原 synthetic positive 失败、原 standard-section 报 `STATEMENT_LOCAL_SCOPE_UNRESOLVED`、原 PYTHONPATH 缺失 `tests` 失败均保留；其存在与本次成功回归分开解释。`actual-original.json` 的 old/new scope status 同为 `REPORTED_CONSOLIDATED_TOTAL`，不单凭其字段证明原版本已经完成 scope；独立 base/patch 小样例对照是本次行为差异证据。

**未覆盖与边界。**

未重跑完整公司、实际大来源、全 CI、所有 operating statement、39/390 指标、网络/SEC/provider/模型；未检查生产采纳或消费者安装闭环；未访问或修改 #47 目录、账本、状态。保存正向材料证明一个已有坐标，不证明未知括号范围也可接受。未改源码、测试、旧证据，未 commit/push/tar，未 spawn。新增输出只在本独审目录，一份结论与日志。

**执行计数。** UTC 开始 2026-10-10T07:25:51+00:00，完成 2026-10-10T07:29:51.249715+00:00；耗时 240.25 秒。工具节点 16（8 wrapper + 8 nested），普通消息 2（初始进度 1 + final 1，问题 0），均在 30 节点 / 15 分钟限制内。provider/paid/SEC = 0/0/0。计数为本代理本次限定独审，不使用更宽总授权。
