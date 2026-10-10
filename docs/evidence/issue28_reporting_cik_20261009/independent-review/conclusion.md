# 限定独立审阅：79ff47b reporter CIK

结论：**REQUEST_CHANGES，发现 1 项 P1**。前身显示身份修复本身可复现，但新增检查对所有普通记录无条件生效，拒绝原本有效且未携带单一 issuer 的 Trace，破坏现有结构性不适用及部分扣留/数值路线。指定的 30 例测试全部通过，不能消除这一兼容性反例。

## 精确范围及发现

- 工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-reporting-cik/SEC_metrics`。
- Base：`4a03f22393182eb642a0472f1480354ff430267c`；受审 patch / 当时 HEAD：`79ff47b4aad95946f4bd403d5a06f5731656d369`。
- 修改：`scripts/vnext/ordinary_projection.py` 的 24 行新增；`test_reporting_company_projection.py`、`test_precalculated_case.py` 的新增断言；company-current workflow 及 `run_fast_tests_v2.py` 的选择项。其余受审提交内容仅用作说明与父执行证据，不当作独立实跑。
- 只读追踪了 registry、traits、Projector 行/证据格式化、普通结果保存/读取，以及现有 Trace 生成入口。没有改动这些文件。

**[P1] 全部普通记录被要求具有单一 entity/accession，原生空 issuer Trace 被错误拒绝。** 位置：`ordinary_projection.py:216-217`（无条件调用），具体拒绝位于 `:37-43`。原有 Calculator 允许未指定来源 issuer 的目标，明确将 Trace 的 `entity` / `accession` 保存为 null（`calculator.py:852-862`）；这不是内容损坏。`normal_accession_results.py:187-190` 的 `N_A_STRUCTURAL`、`capacity_run.py:167-182` 的 B13 结构性不适用，以及债务/治理来源不充分时的部分 WITHHELD 路线均保留这个契约。数值路线也存在同类目标：`normal_lodging_results.py:79-81` 的 B10/B11 与 `normal_accession_results.py:183-213` 的观察值目标没有填入 entity/accession，Calculator 同样形成 null。

独立最短反例用原生 `_manual_result_trace` 按 unchanged `normal_accession_results` 的参数生成 `N_A_STRUCTURAL / PUBLISHED / TRAIT_NOT_APPLICABLE` B12 记录，沿原先真实 FY2021 的 annual/source metadata 渲染；Base 成功，Patch 抛 `ORDINARY_PROJECTION_TRACE_SUBJECT_CHANGED`。这是构造的兼容性对照，不是假称整份财报已重新通过。详见 `native-null-trace-regression.log`。

应保留已验证 annual 的登记 CIK 和 false 组合边界；对实际携带 issuer 的 Trace 检查 entity/accession 一致性，同时明确处理旧允许 null issuer 的 trace，不重写旧 Result/Trace。至少加入原生结构性不适用、扣留及 B10/B11 数值 Trace 的呈现回归。如何在空 issuer 路线上从既有来源证明 reporter，须沿已有输入/引用合同处理，不能把 null 当成已证明一致，也不能仅删掉跨主体检查。

## 独立实际执行

1. **指定回归**：`python3 tests/required_unittests.py tests.vnext.test_reporting_company_projection tests.vnext.test_precalculated_case tests.vnext.test_successor_income_projection tests.vnext.test_registered_event_projection`。独立执行 30 例，0 failures、0 errors、0 skips；unittest 19.221 秒，进程 19.499 秒；UTC `12:56:26.341086` 至 `12:56:45.840075`。临时 sitecustomize 禁止 socket connect/create_connection。见 `required-tests.log`。
2. **真实前身 B12 最短 save/read**：只读 `/tmp/issue47-paramount2021-b12-case.json.gz`，gzip SHA256 `5ba07aea42fdefbc37fdb679685a1cbe26475429f6676ab510ac5285513a6898`。原 annual 和 Trace 都为逻辑公司 `paramount_skydance_paramount_global`、entity `813828`、accession `0000813828-22-000005`、cross combination false。Base renderer 与 Patch save/read 的唯一 metric-row 差异为 CIK `2041610 -> 813828`；空值、USD、FY2021、N_A_STRUCTURAL、Result ID、Trace ID、input ID 与全部 expected records 保留。Registry、case 对象及读前后的保存文件字节不变。源重新选择函数被禁止，socket 被禁止；临时输出已清理。该真实 B12 没有证据行，因此不以它声称验证了前身 evidence 行。见 `independent-predecessor-save-read.log`。
3. **父已生成 B01 的独立只读检查**：实际读取原保存结果及其 CSV / Trace，不重跑父 CLI。metric 与 evidence CIK 都是 `813828`；Trace entity/accession 同原年报，值 `28586000000 USD`、期间 `2021-01-01..2021-12-31`。独立重哈希真正的 Company Facts evidence JSON；另读 target-primary 原件，检查其保存引用 SHA、DEI `0000813828` 与 FY2021 原生 Revenue `28,586`、scale6。主 HTML 与 Company Facts 各有自己的 SHA，不能互换。旧运行文件读后字节不变。见 `saved-b01-original-identity.log`。这是独立保存身份/单个来源事实读取，父首次/重复 CLI 和完整来源处理仍为父证据。
4. **兼容性反例**：原生 null issuer 结构性 Trace 的 Base 成功 / Patch 失败，UTC `13:02:39.778173`；见 `native-null-trace-regression.log`。

新 reporter-view helper 在确有单一 issuer 的路线正确检查登记 CIK、逻辑公司、Trace entity、annual accession 与明确 false 组合权限，并只复制 company 字典用于行/证据格式化；registry、现有 Result/Trace/input 字节不会被这个 helper 修改。现有 30 例中的 current `2041610` 视图保持、Marriott metric/evidence current CIK、短期间/原表头矛盾扣留、已批准 event-wide-window 独立检查均通过。其局限是没有覆盖上述原生 null issuer 呈现路线；宽窗单测直接调用 `_registered_event_period`，不证明所有 event records 已走过新 reporter guard。

## 未覆盖与操作边界

没有独立重跑整份来源材料、全财报、公司首次/重复 CLI、完整 CI、所有指标/历史年份；没有给予 #47 业务信用、生产采纳、Ready、merge 或 active 权限。未发真实 HTTP/SEC/provider 请求，未操作账户、总账、来源树或旧运行根，未 spawn、commit、push 或打 tar。输出仅为本目录的一份 conclusion.md 和必要日志；临时 save 根由 TemporaryDirectory 退出时清理。因本子任务禁止真实 HTTP，本次未实时重新读取 Issue #28；执行范围以父明确限定委托为准，未从旧文档扩大权限。

探针出现两项 harness 问题，均在处理/认定前纠正：第一次最短 save harness 缺 PYTHONPATH=scripts 导致 git_workspace 导入失败；一次 B01 原件检查误把主 HTML SHA 与 Company Facts evidence SHA 相等当条件，改为各自同实际保存引用核对。这两项不是受审源码缺陷，详细更正记在对应日志。

## 实际工具与消息审计

开始 UTC：2026-10-09 12:55:07；完成 UTC：2026-10-09 13:04:43 UTC。本次共 **19 次 functions.exec 包装 + 44 次子工具 = 63 次工具**，子工具为 42 次 exec_command、1 次 clock__curr_time、1 次 write_stdin；包装和子工具均计入父要求的 80 次上限。普通消息共 3 条：开始 commentary、一次进度 commentary、最终答复；无问题。未使用其他工具。父执行日志、父实跑时间未计入独立执行。
