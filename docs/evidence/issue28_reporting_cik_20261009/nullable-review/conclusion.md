# 限定 nullable P1 回修与 runner 登记复核

结论：**原 P1 在本次限定范围内已修复；新增两个 runner selector 登记通过。未发现此增量新增的 P1/P2。** 本结论不代表整个 runner 已可运行：两个基线已存在的重复 selector 仍使其正常执行在开跑前报 `FAST_TEST_SUCCESSOR_SELECTOR_CONFLICT`，见下文。原 `independent-review/conclusion.md` 的 **REQUEST_CHANGES / P1** 原件与字节保留；本目录是另存的后继复核记录，不能倒改原结论。

## 精确受审范围

工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-reporting-cik/SEC_metrics`。Base：`79ff47b4aad95946f4bd403d5a06f5731656d369`；Patch / 实际 HEAD：`abb7abdd78b0330b0c2464668e81cd4de7fdf375`。

只审 `_reporting_company_view` 的显式 null 处理及 `render_ordinary_records` 调用、新增 `test_reporting_company_projection` 回归、`run_fast_tests_v2.py` 两个 selector 登记。只读追踪 unchanged Calculator 的 null 合同、保存/读取对来源和记录的检查、B12 与 lodging Trace 生成入口。未重开前身身份、公司 CLI、全历史或金融材料审阅。父 37 例组合、接收方 59 例及前 reviewer 63 工具 / 3 消息均未算成本次独立执行。

## P1 修复的依据

Calculator 的现有合同会明确生成 `entity=None` / `accession=None` 的 Trace；该值不再被视为损坏。helper 仍要求 annual issuer 属于该逻辑公司登记 CIK、annual 与 Trace company 一致、两个 Trace 键实际存在、组合主体权限明确为 `False`。任何已经填入的 issuer / accession 必须与 verified annual 一致，null 不遮盖填值冲突。

只要有任一来源目标字段为 null，就要求 case 中存在同逻辑公司、同 accession、同 CIK / 主文档 URL 的 primary reference。只有 Result 的 `value is None` 且 `text_payload is None` 时，调用方才开放同 CIK submissions inventory 作为呈现身份依据；这不会给数值或文本来源信用。对应的来源引用/字节核对由原保存路径在渲染前执行，本回修没有改动该路径。

独立执行 `python3 tests/required_unittests.py tests.vnext.test_reporting_company_projection`：**12 例，0 failures / errors / skips**。UTC `2026-10-09T14:13:53.656060+00:00` 至 `2026-10-09T14:14:03.164235+00:00`；unittest 9.266 秒，进程 9.507862 秒。包括真实 saved current Marriott B12 结构性不适用、B10 / B11 数值、Salesforce B12 RPO `72400000000 USD / 2026-01-31` 的 save/read，以及原生 Calculator 构造的 WITHHELD null Trace。WITHHELD 是构造回归，不是真实披露不足验收。详见 `required-tests.log`。

另有 **27 个有限检查**，不是 27 个新增 unittest：显式双 null 与单 null 可用正确 primary；错误 accession、错误/缺失文档引用、外公司或另一已登记 CIK 的 reference、未知/foreign reporter、缺 entity/accession 键、组合或未知主体权限均拒绝。renderer 的真实原生结构性 null Trace 在构造的 inventory-only 引用子集下仅保留空值状态；仅为检查 guard 所构造的数值和文本 payload 均拒绝 inventory-only。构造引用子集和无效 payload 不登记为真实业务结果。详见 `finite-boundary-checks.log`。

helper 输入对象在各有限检查前后相等；源文件、registry、Calculator、原 writer/reader、测试、runner 与原 review conclusion 的前后 SHA256 相等。本增量只复制 company dict 改呈现 `primary_cik`，不重写原 Result/Trace。这里只声称本次检查的对象和文件未变，没有声称重新扫描全部旧运行树。

## Runner 登记与必须保留的限制

实际变量为 `SOURCE_TESTS`；`SOURCE_MATERIAL_TESTS` 不存在。pure class `tests.vnext.test_reporting_company_projection.ReportingCompanyProjectionTest` 仅在 fast 出现一次，source class `tests.vnext.test_reporting_company_projection.CurrentNullableTraceProjectionTest` 仅在 source-material 出现一次，跨列表计数为零，旧整个 module selector 已退出。实际 import、CLI help、两类 CLI list 均 rc 0。四个 runner 函数 `_run_source_case` / `_selected_tests` / `run_fast_tests` / `main` 的 AST 与 Base 完全相同。详见 `runner-validation.log`。

**已有 runner 执行阻断仍存在，不能把登记/list 成功报告成 runner 实跑成功。** 两个已存在的 fast selector `tests.vnext.test_selected_event_source_v1` 和 `tests.vnext.test_registered_event_projection` 各重复两次；独立加载 Base 与 Patch 证实重复集合完全相同。直接调用 `run_fast_tests(jobs=1, suite='fast')` 在真正执行任何 suite 前报 `FAST_TEST_SUCCESSOR_SELECTOR_CONFLICT`。本次不修改或重新审阅这两个基线登记，但父交付若要求正常 runner 开跑，仍须处理该已观察到的阻断。

首个 runner 探针直接断言整个列表无重复而失败，未产生日志；随后只读比较 Base/Patch 定位为基线已有问题，保留在 `runner-validation.log`，没有将首个失败伪装成通过。

## 未覆盖和操作偏离

未重跑父前身 CLI、完整历史/金融原件、全 source suite、完整 fast suite 或 CI；未复核全部其他 null Trace 路线，未授予 #47 新业务信用、生产采纳、Ready、merge 或 active 权限。未 spawn / commit / push / tar，未主动写入 #47、source 或 ledger；输出仅本目录 `conclusion.md` 与日志。测试临时 save 根与离线 sitecustomize 临时文件均已清理，测试与有限反例均通过 socket 禁止 connect / connect_ex / create_connection。

**操作偏离如实登记：**本子任务要求无真实请求，但审阅开始时执行了一次只读 `gh issue view 28 --repo wlvh/SEC_metrics --json body,title,updatedAt`（rc 0，返回 updatedAt `2026-10-09T13:50:12Z`）。该 GitHub HTTP 读取超出限定，不能写成“本次无真实 HTTP”。没有 SEC / provider / paid 请求；发现该限定后没有再发外部请求。该操作没有扩大受审源码或任何发布/调用权限。

## 工具、消息与时间审计

开始 UTC：`2026-10-09 14:11:55`；完成 UTC：`2026-10-09T14:19:44.815664+00:00`。本次 **9 次 functions.exec 包装 + 14 次 exec_command + 1 次 clock__curr_time = 24 次工具**，包含本文件/审计日志写入调用，低于 80 上限。普通消息共 **3 条**：开始 commentary、进度/偏离说明 commentary、最终答复；0 问题。未调用其他工具；内部 subprocess 不计作 MCP 工具。未复用开发 agent 51/3、原 reviewer 63/3 或接收方预算。精确文件摘要和 git 状态见 `final-integrity-and-audit.log`。
