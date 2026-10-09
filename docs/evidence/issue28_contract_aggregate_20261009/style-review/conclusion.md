# P2 样式回修限定独立复核：PASS

结论：98930711 的样式识别修补已纠正旧 P2 的三个实际变体。在本次限定差异内没有发现新的 P2。普通明确隐藏的空叶单元仍可跳过；重复 display 声明、含 CSS 注释的样式、普通可见 spacer、非空和带事实/子元素的单元保留原表格处理。本结论只关闭旧样式误删根因，不重开整个 B03 模块，也不要求通用 CSS 渲染能力。

工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-contract-aggregate/SEC_metrics`。base：`2bec3464e735bc5cbf928573b1bd1538b06789f3`；patch 与实际测试 HEAD：`98930711a31d85d1b5406149ef83271cce793543`。产品审阅只涉及 `scripts/vnext/b03_contract_amortization_scope.py` 的 `_RevenueTableIndex._hidden_cell` 和 `tests/vnext/test_b03_current_input_scope.py` 新增测试；其它代码只读必要的继承接缝。

UTC 首次现场时间：2026-10-09T12:16:06Z。UTC 结论写入：2026-10-09T12:20:39.623173+00:00。总工具调用 28 次，包含 9 次 functions.exec 包装、17 次 exec_command 和 2 次 clock__curr_time；包含结论写入后的最后一次只读核验及该核验元数据登记。普通消息 3 条（初始告知、一次进展、最终回复），问题 0，子代理 0。未 commit/push/tar 或发真实 provider/SEC 请求。只新增本目录一份 conclusion.md 和三份 .log；未操作 #47 工作树、ledger 或历史 run/source 根。

## 独立执行的关键证据

亲自执行指定命令：

```text
python3 tests/required_unittests.py tests.vnext.test_b03_current_input_scope.ContractAggregateTest
```

7 tests，0 failures/errors/skips；unittest 0.007s，命令子进程 0.255442s，返回码 0。完整命令、cwd、base/patch/HEAD、UTC 及代码 SHA256 见 `required-class.log`。本次没有独立重跑整个 26-test 模块或三份历史真实原件。

另亲自执行 13 项 helper 小输入和 8 项直接索引小输入，21/21 通过，见 `style-boundaries.log`。对于旧三个 P2，直接从 base 的 AST 取出原 `_hidden_cell`，在相同现有合成材料上仅替换这个方法，原版本确实返回隐藏并错误给予四项收入扣减证明；patch 版本保留可见空 spacer、年列定位不成立时返回 None：

| 原样式 | base：错误给予关系证明 | patch：拒绝关系证明 |
|---|---|---|
| `display:none;display:table-cell` | 是 | 是 |
| `display:none!important;display:table-cell!important` | 是 | 是 |
| `display:table-cell;/* x;display:none; */` | 是 | 是 |

这一比较实际进入目标方法与关系判断，并非在前置条件失败后声称不能复现。单一明确 `display:none`、大小写/空格/`!important`、带其它普通声明、自闭合空 td 和仅空白的成对 td 仍合法，原事实 ordinal 1–4 保留。直接索引中非空 td、td/th 事实子元素、空 span 子元素、entity 和旧注释 spacer 与 inherited 原处理一致；明确空 td/th 才省略。原始 source、事实数、事实字节位置保持。

## 一项不阻断修补的测试说明

新测试的注释样式为 `/* display:none; */ display:table-cell`。这条在 base 原正则下已经保留单元并拒绝关系，因此单独靠它不能回归捕捉旧报告的注释误删。旧报告真正失败的是 `display:table-cell;/* x;display:none; */`；我已对该原写法独立重现旧错误并确认 patch 修复，日志单列 `old_p2_3_comment_exact` 与 `new_test_comment`。建议维护时将新增测试中的注释样式替换成旧失败原写法，或加同一 subTest；这是测试针对性的改进，当前代码修补本身已通过，不新增 P2 或要求再次全模块独审。本审阅未修改代码或测试。

## 代码差异、父证据及未覆盖

AST 对照确认：除 `_hidden_cell` 外产品函数不变；除新增测试方法外既有测试 AST 不变。`financial_structured.py`、`table_grid.py` 和 `tools/run_fast_tests_v2.py` 相对 base 的提交字节不变。数量/范围/gross-to-net/年列判断没有由此次修补重写。见 `scope-and-log-inspection.log`。

旧报告和日志保持原义：旧独审 25 tests/5.335s（子进程 5.611737s）以及父执行修后 26 tests/5.247s 只作已有日志核读，不能转写为本次独立执行。父 `style-fix-saved.json` 与 `final-saved.json` 内容 SHA256 相同，三年保存日志各保四项关系：FY2021 55+20=75m、FY2022 60+29=89m、FY2023 65+22=87m 对 consolidated 88m。87/88 差异仍在。上述三份历史原件属于父执行证据，没有在本审阅独立读取或重跑。

未覆盖：完整 CSS 语法/优先级、三历史原件独立重跑、#47 历史消费者/公司 CSV 接收、完整 B03 D&A 范围、全 fast/远端 CI、真实 provider/SEC、生产采纳或合并。重复同值 display 和无关 CSS 注释也会保留原单元，属于此次明确采用的保守边界，不声称推断其浏览器可见性。完整经济摊销、fulfillment-cost 与 lease expense 的原消费者限制不在本次回修范围，此 PASS 不升级三个历史 B03 的业务状态。

受审字节 SHA256：产品文件 `c6f8f3bfead15fb3388d44c417ee3eedda28ea4dbf31a93d5e543a45d8197f74`；测试文件 `49d7287bc181035162f4cf6825feea68f2378353d8472393b037fdfea2c6bdfc`。旧 NEEDS_FIX 报告 SHA256 `f69ccd57ff798afb0be3435eaabea162fe13ef89bfc1e970d6ecfc8563e9f82a` 保持。最后核验的当前 HEAD、UTC、范围与日志 SHA256 登记在 `scope-and-log-inspection.log`。
