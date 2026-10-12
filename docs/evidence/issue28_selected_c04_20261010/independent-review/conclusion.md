# Selected C04 限定独立审阅

公共源码结论：在下列实际覆盖范围内，未发现新 adapter 的业务阻断问题；这不是全模块、全部公司或生产验收。配套测试在指定 `4e8af508` 有一项 P2 可移植性问题。父执行者随后提交 `76d372fa` 回修，本审阅仅静核该测试回修，不把它写成已亲跑的修后测试或已通过 CI。

## 身份、资源和范围

- 工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-selected-c04/SEC_metrics`。
- 指定 base：`84d15f35eb3f0a7b6dc9e0b06100ceba738c7adf`；指定 patch：`4e8af50824d8ce0e69c877864977ca25b05573fa`。
- UTC 开始：2026-10-10 08:04:03 UTC；UTC 结束：2026-10-10 08:14:38 UTC。本任务在 15 分钟上限内停止。
- 工具节点共 **32**：13 个 `functions.exec` wrapper、19 个 nested tool 调用；这包括初始无命中的轻量 memory 查询、失败的审阅控制，以及最终报告写入和检查。普通发送消息 **2**：一次无问题开场、一次最终报告；没有提问或另发进度消息。
- 审阅者未 spawn、commit、push、联网、真实调用、打开 #47 工作树、运行长公司链/大原件重放或 tar。
- 实际限定 diff：`c04_registration_successor.py`、`c04_verified_document_alias.py`、`ordinary_saved_result.py`、新 `test_c04_selected_input.py`、现有 C04 workflow 命令、fast-selector 末尾增量。未将历史四 forms/alias reader 扩成全模块审阅。
- 父执行者在共享工作树后续改测试并提交 `76d372fa`，也归档过本任务当时已有的日志。本报告保持公共源码的 `4e8` 审查身份；父提交不代表此前已有独审结论。

## 发现

**[P2] 新兼容测试依赖固定 Git 历史对象，无法在不含该原件的 checkout 运行。**

指定 `4e8` 的 `tests/vnext/test_c04_selected_input.py:100–107` 在运行时执行 `git show 84d15f35:...`。C04 作业的 checkout 定义（workflow 162–165 行）没有为该作业取完整历史。对缺少指定 Git 原件的独立小目录执行原 `4e8` 测试方法，确认它在字典比较前抛出未处理的 `CalledProcessError` / rc128。原本地测试能通过依赖于本工作树确实保存了 base 对象。该缺陷影响测试可移植性和 CI，并不证明 C04 业务输出错误。

原件缺失控制仅隔离 Git 原件不可读取的错误路径，不是实际 CI 作业重演。父执行者告知其读取的实际 CI 日志也将唯一错误归为该 `git show`；本审阅没有联网核对 CI，不把这个告知写成自己亲读的 CI 证据。

父回修 `76d372fa` 只将该兼容测试改为读取提交内的完整小输出 fixture，比较原 synthetic input SHA256 和完整默认 dictionary；源码三个公共文件与 `4e8` 逐字节相同。审阅静核了 exact `4e8→76` 测试/fixture diff，并核对 fixture 的 `baseline_reader_sha256` 与真实 base84 reader 字节相符。该回修从静态结构上移除了运行时 `git show` 依赖；本任务没有亲跑 `76` 测试，没有授予修后 CI 信用。

## 亲跑检查

1. 按委托原命令运行：

   `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_c04_selected_input tests.vnext.test_governance_signals.AuditorSignalsTest`

   当时 HEAD 为指定 `4e8`，15 tests / 0.260s，0 errors、0 failures、0 skips，rc0。覆盖显式 DEI namespace 选择、拒绝假 namespace/非法 policy、主体/期间冲突、selected 输入成对要求、坐标/相邻 prior/binding/缺 proof、默认 gate、默认完整 dictionary 与原 base reader 等价，以及既有 C04 prior/事件完整性正反例。日志：`required-small-tests.log`。

2. 亲跑原 successor 中三项小控制（排除 Marriott 大材料方法）：同 CIK/alias 原请求 proof、注册 event 的 history alignment、不批准 form 子集/错 metric。3 tests / 0.002s，零 errors/failures/skips，rc0。日志：`inherited-small-controls.log`。

3. 亲跑 11 项独立受控 synthetic 检查，实际执行 selected 公共 adapter、annual parser、完整四 forms census/manifest、Spec 一致性检查和 Calculator：

   - 可比相同 auditor、四种 form 都完整且无 Item4.01 -> 0。
   - 相同年末 auditor 下，在 8-K、8-K/A、8-K12B、8-K12B/A 各自放入 Item4.01 -> 1。
   - 缺 prior、错 prior 主体、错 prior 实际期间 -> WITHHELD，无 0。
   - 缺 8-K12B/A 原件 -> 在结果前失败。
   - alias-reader 默认仍拒绝 exact-name-only fallback；显式 exact-name option 才允许该路径。

   **边界：此控制替换了 `_Sources` 和物理 saved-proof verifier，仅对很小的 fixture 检查业务与结构；它不证明真实来源获取、实际归档准入、公司 writer/readback 或公司链。** annual reference→proof 对应 guard 和实际年报解析仍运行。网络连接被禁止。日志：`controlled-selected-adapter-corrected.log`。

4. 亲跑 exact `4e8` 测试方法的 Git 原件缺失控制，确认前述 P2。核对 `final-actual-selected.json` 的 11 个 public-code hashes 与指定 `4e8` Git 字节全部相符。日志：`tree-and-portability-control.log`。

第一次 synthetic 控制用错 SGML URL 后缀，失败日志保留在 `controlled-selected-adapter.log`；改用现有 `hdr_sgml_url` 后上述控制成功。第一次可移植性控制恰逢父修改了共享测试，其 ROOT 重定向触发 fixture FileNotFoundError；随后从 Git 加载 exact `4e8` 测试纠正，说明保留在 `live-tree-portability-harness-failure.log`。这两次均是审阅 harness 问题，不归为产品失败，也未删除原失败。

## 源码与保存边界

- `selected_base` 与 `labelled_annual` 默认均为 None；显式选择必须成对。非显式路径保留原 latest preparer、YEAR_ONLY DEI 和旧 alias fallback。
- 显式 branch 核对 company/entity、实际日期、current accession、base binding hash、相邻 prior，并将每个当前/前期 annual reference 的 URL/accession/document/request/原始 hash 对应到实际 verifier 所检查的 proof 列表。源 bytes/ref 身份与同 CIK/实际期间仍由既有 reader 检查，错主体或期间不会变成 0。
- 四 forms 的来源清单逐个重建并核对完整性，在该清单核验成功之后才解释 names comparison；相同年末名字不能代替事件 census。缺可比 prior、来源冲突保留 WITHHELD；存在明确 Item4.01 的正向定义继承原业务规则。
- C04 只增加到 `EXPLICIT_CASE_METRICS`；默认 `SAVED_METRIC_IDS` 未增加 C04。既有 current-update gate 仍要求 selected fiscal year 与 callable factory，默认调用拒绝 C04；parent gate 的小测试亲跑通过。
- Spec 保存/读取仅阅读了既有 writer 的 Spec closure、实际 Spec 文件、target period、trace/result 和 source-proof 检查；未亲跑 selected C04 writer/company update/readback。workflow/fast-selector 增量仅安排测试，不构成默认 route、正式采纳或 active 切换。

## 仅阅读的证据与未覆盖

阅读 README 和 `final-actual-selected.json`，只核记录身份与树绑定边界。最后真实材料记录写明测试在 base84 上有未提交源码：17.841710s / repeat2.472222s / 独立读取0.456725s，0 新 provider/paid/SEC、无生产授权。其 11 个 public-code hashes 确与 `4e8` 一致；**这仍不是亲跑 4e8 提交后的 Ford 执行。** 本任务没有打开来源 archive、核验 Ford 四份大原件、重跑 28 events 或上述公司保存链。

未覆盖：全旧模块/所有 form 布局、长 Marriott 安装链、Ford 原件真实独立审阅、#47 CLI/factory 实现及其正式验收、全公司/39指标/生产/active/合并权限、实际 CI 日志和修后新 CI。父提交 `76` 的 fixture 静核另见 `portability-fix-static-76d372fa.log`，没有代替修后亲跑。

所有本任务产出仅在本目录：本 `conclusion.md` 和七份 `.log`。工具和消息预算未耗尽；审阅按限定边界结束，未为扩大验收而追加演练。
