限定独审结论：PASS，无本次范围内的阻断项。

本次只审阅 base `fb9cc768ffcc8b1ada445895ff5f04aa9fbe1d8e` → patch `4d58197892eea09ee0cc6fde10a860a29a5111fd` 的一个生产行及新增 16 行回归测试；patch 的第一父提交就是该 base，实际工作树 HEAD 等于 patch。静态字节参照 main 已保存提交 `f51d8c3d27f3169b9cdb3a246295830882240c1f`。本结论不构成全 PR、业务金额正确性、生产采纳或真实来源运行验收。

实际核查：`scripts/vnext/company_local.py:383–391` 的分支仅在选中指标完全属于 B01/B02 时进入。第 391 行改为对每个选中指标使用完整 `INCOME_PROCESSING_FILES` 加 `company_fiscal_range.PROCESSING_FILES`，再以 `dict.fromkeys` 保留首次出现顺序并去重。B01 原先已经用收入依赖；B02 原先误用较窄的 statement 依赖。新行使 B02 也纳入收入来源相关模块，同时保留原 range 依赖。这是依赖登记修复，没有改计算公式、工厂、年份列表或 controller 调用参数。

其他指标或混合选择无法进入上述限定分支，仍按未修改的第 392–423 行分派；当前默认 `latest-complete-fy` 路径及 scope 选择也没有差异。已有小测试实际覆盖 B01/B02/B04/B05 混选、收入与 lodging 混选、liquidity/capital/rpo/bank/event/geography/average-risk/bank-scope 等分派及 current mode。新增 `test_reported_growth_range_tracks_both_income_and_range_readers` 验证 B01 与 B02 都包含两个完整依赖集合、没有重复路径，并确认此处不会提前调用来源发现。仅 B01 或仅 B02 的行为由相同分支及对每个 selected 的同一表达式静态证明，本次没有另跑大公司材料。

静态比对 main `f51d8c3d27f3169b9cdb3a246295830882240c1f` 与 patch 中既有 `historical_*.py` 的 18 个模块及 `selected_income_source_v1.py`，19 个文件全部逐字节相同。`historical_statement_cases.py` 的 SHA-256 为 `454131a7a443402eb7bef6e6af4ae9975e00edcc060861e3d97d648e74b22afc`。此次只检查依赖常量和字节保留，没有重审旧 source/fiscal label 解析逻辑或 183 行 range helper。

验证命令：

```text
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_history_company_dispatch
```

实际结果：exit 0，19 tests，0 failures，0 errors，0 skipped，0 allowed skips。测试 UTC 起止 `2026-10-10T08:53:34.191220+00:00` → `2026-10-10T08:53:34.528236+00:00`；命令耗时 0.337016 秒。新增回归及原有分派测试均通过。源码与测试工作树字节经收尾检查仍匹配 patch，tracked diff 为空。

独审 UTC 起止：`2026-10-10T08:52:28.803168+00:00` → `2026-10-10T08:54:33.923548+00:00`，耗时 125.120380 秒。工具计数 8 个节点：4 次 functions.exec wrapper + 4 次嵌套 exec_command；测试命令 1 次，普通报告消息 1 条。未触及 12 节点或 5 分钟上限。没有 spawn、源码/测试修改、commit/push、network、真实调用、公司原件重跑、#47 目录访问或 tar 操作。只新增本目录报告和日志。

证据在同目录：`static-review.log` 保存 diff/分派及初始状态；`dependency-context.log` 保存限定分支/依赖常量和 main f51 的 19 文件字节比对；`dispatch-unittest.log` 保存测试完整输出；`test-metadata.log` 保存测试 UTC 与退出码；`final-verification.log` 保存精确 HEAD、工作树字节、收尾状态和计数。
