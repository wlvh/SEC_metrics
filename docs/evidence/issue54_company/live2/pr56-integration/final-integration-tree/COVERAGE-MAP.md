# 换 base 后的 CI 覆盖去向（PR55 × PR56 `d7154605`）

比较对象：原开发基础 `0bc24734` 工作流（PR55 `adbea30e` 继承同一套作业，公司步骤另加 `test_company_local`）、PR56 `d7154605` 工作流（只有 `fast` 和 `main-foundation`），以及隔离组合树 `5c9fecb3` 的合并工作流。实际执行日志见 `real-base-d7154605/`。

## 一、结论

1. PR55 自己的公司测试（6 个模块，67 项，含 `test_company_local`）在合并工作流中执行，组合树结果 OK。
2. 与本次接收能力直接相关的**继承检查**，大多在 PR56 中**缺少测试文件**，或者**测试文件在、但最终工作流没有执行**。这些测试都来自固定里程碑，测的是随 PR56 进入 main 的基础代码。经确认，改由 PR55 在改目标时一并带入，并以 `company-*` 作业执行；PR56 不需要再复制一份。
3. 已实证可以恢复：在组合树上从 `0bc24734` 按原件带入 26 条路径（测试和夹具），并按旧工作流设置材料根目录环境变量后，下表全部 OK，**没有跳过**。
4. 不设环境变量时，`test_ordinary_update_cycle` 等测试会以 `skipped` 结束、显示 OK。这类跳过不能当作覆盖。

## 二、PR55 关注能力的逐项去向

| 原检查（旧作业） | 关注点 | PR56 现状 | 组合树实测 | 最终应由谁、以什么方式执行 |
|---|---|---|---|---|
| `test_company_handoff`、`test_company_source_authority`、`test_company_results`、`test_company_processing`、`test_company_event_census`（fast） | 公司导入事务、中断恢复、篡改拒绝、局部更新保留、冷读 | PR55 带入 | 67 OK | 合并工作流的 `fast` 公司步骤（PR55） |
| `test_company_local`（原在 v2 快测） | 本地 run 编排 | v2 运行器不再执行 | 包含在上面的 67 项中 | 已移入公司步骤（PR55 `adbea30e`） |
| `test_ordinary_source_authority`、`test_ordinary_source_session`、`test_ordinary_storage_identity`（v2 快测） | 来源准入、整账本前缀、稳定来源身份 | 缺失 | 6 / 10 / 2 OK | PR55 `company-source-core` |
| `test_continuous_sec_acquisition`、`test_continuous_call_ledger`、`test_continuous_call_policy`（v2） | 采集会话、调用账本、调用政策 | 缺失；call_policy 另缺夹具 `provider-wiring-v6-suspended.json` | 1 / 8 / 5 OK（238 秒 / 1 秒 / 9 秒） | PR55 `company-source-core`（call_policy 含夹具）；sec_acquisition 在 `company-acquisition-c04` |
| `test_normal_source_requirements`、`test_prior_html_dependency`（v2） | 来源发现与前期依赖 | 缺失 | 11 / 10 OK | PR55 `company-source-core` |
| `test_normal_source_authority`（v2 快测） | 保存来源证明 | 存在且执行 | OK（在 119 项中） | `fast`（已覆盖） |
| `test_normal_run_v3_material`（ordinary native Runs，需 `NORMAL_V14_MATERIAL_ROOT`） | 实际 OPEN Run、来源绑定文件负例 | 缺失 | 设变量后 1 OK（274 秒）；不设变量为 skipped | PR55 `company-native-runs`（设 `NORMAL_V14_MATERIAL_ROOT`） |
| `test_ordinary_source_run_material`（recorded source update，需 `ORDINARY_SOURCE_MATERIAL_ROOT`） | 录制来源更新、改图与改史拒绝 | 缺失 | 1 OK（348 秒） | PR55 `company-native-runs`（设 `ORDINARY_SOURCE_MATERIAL_ROOT`） |
| `test_remaining_source_run_material`（矩阵 marriott/jpmorgan，需 `REMAINING_SOURCE_*`） | 剩余来源原生 Run、来源绑定拒绝 | 缺失 | Marriott 1 OK（739 秒）；jpmorgan 见最终执行 | PR55 `company-remaining-source` 矩阵 |
| `test_ordinary_update_cycle.OrdinaryUpdateCycleTest`（需 `ORDINARY_UPDATE_MATERIAL_ROOT`） | 真实更新历史、来源变化、**中断恢复** | 文件存在，工作流不执行；不设变量为 skipped | 1 OK（771 秒） | PR55 `company-update-history` |
| `test_ordinary_update_cycle.OrdinaryCompanyUpdateTest`（需 `ORDINARY_UPDATE_COMPANY_MATERIAL_ROOT`） | **局部更新**：混合结果下其它指标保留 | 同上 | 1 OK（779 秒） | PR55 `company-partial-update` |
| `test_c04_update_cycle`、`test_c04_refresh_resume`、`test_c04_source_only_install`（v2） | C04 更新锁、恢复、来源安装 | 缺失 | 3 / 2 / 9 OK（188 / 236 / 1568 秒） | PR55 `company-acquisition-c04`（update_cycle、refresh_resume）；`source_only_install` 独立作业 `company-c04-source-install`（50 分钟时限） |
| `test_d04_native_assessment`、`test_native_request_construction`（v2）、`test_d04_run_material`（going-concern 作业） | D04 保存处理与原生请求 | 缺失 | 19 / 13 / 2 OK（740 秒） | PR55 `company-source-core`；`d04_run_material` 在 `company-going-concern`（按原作业设三个 D04 开关和材料根） |
| `test_registered_native_update` | 已登记原生更新 | 缺失 | 9 项中 8 OK、1 skipped（`ORDINARY_NATIVE_UPDATE_*` 在旧工作流中同样没有设置） | PR55 `company-source-core`，`--allow-skips 1` |

## 三、不属于 PR55 关注点的继承覆盖（交基础方 / #28 说明）

旧 v2 快测 98 个模块中，PR56 缺 48 个；`source-material` 66 个模块中缺 54 个，另有 4 个存在但不执行（`test_normal_companyfacts_results`、`test_normal_zero_ai_results`、`test_normal_annual_input_v2`、`test_c04_registration_successor`）；各原生 Run 材料作业（lodging、capacity、instant、continuity、note/special debt 等）的测试也都缺失。完整清单见 `old-ci-v2-selection-vs-pr56.json`。它们测的是随 PR56 进入 main 的 #28 指标路线代码。是带入，还是明确说明"不在本次接收范围"，由基础方 / #28 决定并登记；PR55 不复制，也不把它们算作 PR55 的合并前置，但不能当作覆盖没有变化。

## 四、其他事实

- PR56 `d7154605` 的 fast 作业（`timeout-minutes: 5`）在 GitHub 上被取消（run 37211664413，作业运行 5 分 15 秒）：补件后 119 项都真实执行，超过了 5 分钟的作业时限。main-foundation 和生成检查都成功。调整时限或拆分作业，由基础方公开处理。
- 本机 `run_fast_tests.py --jobs 4`：114/119 通过；5 个金融测试超过每项 30 秒上限（单独运行均 OK，各需 34–48 秒），有无 PR55 都一样。按超时记录，不算通过。
- `tools/run_fast_tests_v2.py` 在纯 `d7154605` 中仍有大量无法加载的选择项，任何工作流都不运行它。保留还是删除，由基础方决定。

## 五、最终接线（2026-10-04 更新）

PR56 `0be58051` 已把原 119 项拆成 94 项短测试和 25 项材料测试，两组不重叠、不遗漏，fast 作业的取消问题已解决。上表中的核心覆盖改由 PR55 承接：带入 26 条路径（32 个文件，均为 `0bc24734` 原件，见 `../main-retarget/carry-manifest.json`），并新增 8 个 `company-*` 作业（`../main-retarget/vnext-fast.main.yml`）。每个作业使用独立、初始不存在的材料根，通过 `tests/required_unittests.py` 执行，跳过数超过原工作流已有值即失败。最终组合版本上的实际执行结果见 `../main-retarget/README.md`。
