# b2f7ed41 C04 正常刷新限定独立审阅

**Verdict：NEEDS_FIX。** 审阅对象是 `d77a604ae159c252257127b5b0c12e8fe83614fd..b2f7ed4148f4d26a8d7f63ae9ec860ef54d86172` 的指定增量。前次成功终态的 `publication/source_credit` 漏核和 CLI 重复指标问题已在新控制器及入口关闭；保存来源的 C04 正向接线、当前绑定与零调用收据可承接。下面两项正常刷新范围问题仍需修复，不能把 C04 单坐标成功外推为默认全范围正常更新。

## 发现

1. **P2：公开刷新入口的非 C04 单指标调用被拒。** `tools/vnext_ordinary_refresh.py:29-31` 对每次调用固定传 `c04_successor=True`，但 `ordinary_refresh_cycle.py:99-100` 要求所选指标必须包含 C04。因此原本合法的 `--metric B01`（或其他单个非 C04 指标）在任何发现、获取和更新之前抛出 `ORDINARY_REFRESH_C04_ROUTE_REQUIRES_C04`。`boundary-repro.log` 用未接入传输的测试会话复现了同一协调器入口；没有执行真实 CLI 或网络请求。`refresh_and_process()` 的 Python 默认参数为 `False`，保住了旧直接调用，但没有保住公开 CLI 的显式指标选择。应让 CLI 仅在指标集合包含 C04 时启用该后继，或者让协调器允许无 C04 时使用原路径，并补公开入口的非 C04 单指标回归。

2. **P2：标为 C04 的旧处理副本豁免被施加到全部普通来源请求，默认全范围的其他指标仍无法使用旧来源根。** `ordinary_refresh_cycle.py:93-100` 默认选择配置的全部指标；`120-139` 用覆盖全部 39 指标的发现结果选 URL，并给每次 `session.capture()` 传 `source_only_c04=True`。`continuous_sec_acquisition.py:62-82,124-149` 据此跳过旧根中三项处理规则的字节一致性检查，并给任何所选 URL 的计划写 `C04_REGISTRATION_FOUR_FORM_UPDATE_V1`，没有校验该 URL 属于 C04。于是这一豁免能放行非 C04 的已声明 SEC 依赖；仍受官方 URL、发现集合、账本额度和零重试约束，不能据此称发生了越权真实调用。另一方面，其他普通指标继续走 `ordinary_update_cycle.run_company()`，其 `normal_run_v3.prepare_case()` 从来源根读取并要求当前 `config/issue28_normal_results_v2.json`。本机既有真实来源根的该文件 SHA 为 `830c5f27…`，当前仓库为 `deebcd3e…`；`boundary-repro.log` 的只读 `_policy(source)` 返回 `ORDINARY_INTEGRATED_INSTALLED_POLICY_CHANGED`。所以 C04 单项可成功时，默认全范围里的 B01 等并未获得相同可完成路径；当前材料没有验证默认全范围正向完成。应将 C04 处理副本豁免与 C04 所需来源及坐标真正绑定，并让其他指标在旧来源根上按当前绑定规则完成，或明确拒绝混合范围且保持原 CLI 单指标可用。修复后需要一例含 C04 和 B01 的旧根正向刷新，以及一例非 C04 URL 不能借 C04 标记绕过其处理规则的负例。

## 已核实的修复、身份和计数边界

- `c04_update_cycle._verify_candidate()` 先用共享机械重放核对原生 Result 和公开行，再把成功终态的 `publication` 对照重放 Result、`source_credit` 对照输入绑定。该绑定在 `normal_run_v3.replay_case()` 中由来源重新构造并与文件和 Run 身份比较。新测试对两个字段分别重签并要求拒绝；保存的 `targeted-test-retry.log` 显示两项通过（161.677 秒），本审阅没有重跑该长材料。`tools/vnext_normal_update.py:50-51` 也在进入循环前拒绝重复和不支持的指标。
- 本审阅独立运行 `test_ordinary_refresh_cycle` 和 `test_c04_source_only_install`：9 项、11.972 秒、OK，见 `short-tests.log`。运行当前 `validate_final_wiring.py` 得到 `PASS_CURRENT_C04_REFRESH_OFFLINE_WIRING`，V14 closure `sha256:9c58dcfb…`、执行绑定 `sha256:28622528…`、C04 控制器 SHA 与收据一致，见 `offline-wiring.log`。该脚本明确用替身跳过真实 SEC authorizer，不能算真实传输验收。已有 `recorded-refresh-final-binding.log` 记一项两版保存元数据录制测试通过（199.650 秒）；本审阅只读取该日志和测试实现，没有重跑。
- 独立读取保存的真实账本零调用 `report.json`、C04 `current.json/terminal.json` 与来源根当前文件：报告前后均为 `[143,143,49]`、本次 `0/0/0`，C04 `CANDIDATE_READY` 的尝试和 Result ID 与 `live-zero-summary.json` 一致，终态 `PUBLISHED`、来源信用 `PREEXISTING_SAVED_ACQUISITIONS_ONLY`；来源刷新和总状态分别是 `REFRESH_INCOMPLETE`、`UPDATES_INCOMPLETE`，见 `saved-report-check.log`。这是旧保存来源形成的候选，不是新 SEC 获取、正式发布或完整刷新。失败原件、父级绑定、收据的保存日志与此口径相符；未把旧失败改写成成功。

## 实际执行与未覆盖

只做了上述 9 项短测、离线绑定验证、只读本地记录/源码/Issue 核查和无传输边界复现。未重跑 160/200 秒材料、完整公司刷新或冷读；未发真实 SEC/provider 请求，未操作 #47/PR52，未提交、推送、打包或改变生产状态。当前工作树原有 `execution-state.json` 修改不属于本审阅，本审阅只写本目录。审阅合计 22 次 `functions.exec` 编排调用、54 次内部工具调用（含本文件写入和核对），低于 80 次上限。
