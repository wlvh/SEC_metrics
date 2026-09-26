# d77a604 C04 正常更新限定独立审阅

**Verdict：NEEDS_FIX（证据元数据一致性）；已验证的保存来源正向更新可承接。** 审阅对象为 `d77a604ae159c252257127b5b0c12e8fe83614fd` 相对父提交 `38732ea6f4a22f8b74e7ffb679463180bb36b876` 的指定路径增量。以下问题不否定原生 C04 的已保存材料正向结果，也不授予实时获取或生产权限。

## 发现

1. **P2：成功终态中的来源信用和发布状态可与原生 Run 不一致而仍被接受。** 新控制器在 `c04_update_cycle.py:111-125` 把 `publication`、`source_credit` 复制进 `terminal.metrics.C04`，并调用共享 `_verify_candidate`。共享核验只比对原生 `result_id`、公开行字节及输入描述（`ordinary_update_cycle.py:144-164`），不比对这两个终态字段。对第二个已保存成功版本做只读、内存中的反例：将 `publication` 从 `PUBLISHED` 改为 `WITHHELD`，或将实际 `RECORDED_TEST_ONLY` 的 `source_credit` 改为 `FORGED_CREDIT`，两次 `_verify_candidate` 均接受并返回原生结果。磁盘记录的 `record_id` 是内容哈希，可随这些字段重新计算；现有核验因此不能凭该哈希识别这种自洽重签。新路由在 `run_once` 返回整个 `terminal`，调用方会看到错误的信用/状态字段。修复应让新路由或共享核验从重放后的 Run/输入绑定逐字段校验终态信用和发布状态，并补一条重签负例。这个核验缺口存在于被复用的旧函数，本提交把它带入新的 C04 更新证据链；没有证据表明真实原件已被改写或生产已采纳。

2. **P3：重复选择 C04 时入口静默重复报告同一个结果。** `tools/vnext_normal_update.py:55-75` 先按指标名合并结果，再按原始 `metrics` 列表展开；只传两次 `--metric C04` 会调用一次 C04 控制器、输出两个相同条目并以 `UPDATES_READY` 退出 0。原普通 `run_company` 会拒绝重复指标。应在分流前一次性校验指标列表唯一且属于支持集合，避免把重复坐标算成两个已完成项。

## 已核对的正向行为与边界

- `normal_run_v3.py` 和旧 `ordinary_update_cycle.py` 在本提交中未改；新控制器显式传四形式 `EVENT_FORMS`，普通路线保留默认参数。提交中的 B01+C04 混合日志显示 B01 仍在 `metrics/B01`，C04 在 `metrics/C04-registration-v3`；这是新状态下的演练，未验证已有 `metrics/C04` 旧历史到新路径的跨版本接续。旧路径保留在磁盘，但新报告的 `previous_successful_attempt` 只指向新路径里的成功。
- 独立重放了 `/private/tmp/issue28-c04-normal-update-20260926-01` 中两份已保存 Marriott 成功终态：输入 `content_id` 分别为 `sha256:a2081bc1…`、`sha256:d51c0329…`，原生 `result_id` 分别为 `sha256:f4b106e8…`、`sha256:dfc733e4…`，两者均为 `PUBLISHED/0`；当前成功指针为第二版 `4e927e6679464e6abd8a450c11905d5d`。这支持“来源字节变化产生新版本，旧版仍可重读”，不证明新财年发现/获取。
- 已读 `verify_saved_update.py`、`cold_read_update.py`、`verify_mixed_update.py`、`read_result_versions.py` 与对应 JSON/日志。录制摘要把重复输入记为 `NO_SOURCE_CONTENT_CHANGE`、输入失败记为 `INPUT_FAILED`、恢复后复用成功；Paramount 维持 `CANDIDATE_WITHHELD/null` 后为 `PREVIOUS_INPUT_WITHHELD`。首次 `recorded-update.log` 是脚本导入错误，后继 `recorded-update-retry.log` 才是成功演练。上述失败/恢复场景本审阅未重新执行完整录制脚本，按已保存记录解释。
- CLI 和控制器固定显示 provider/paid/SEC `0/0/0`、`production_authorized=False`，本次未发真实 SEC/provider 请求。提交材料所称原账本 192 行、累计 `143/143/49` 未由本审阅重新核验。2026-09-26 读取 Issue #28 与 PR43 时，PR43 仍为 Draft、远端 head 仍是父提交 `38732ea6…`；本结论只审核本地精确提交，不表示已推送、CI 通过、Ready、合并、采纳、active 切换或长期调度。

## 实际执行与未覆盖

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_c04_update_cycle`：1 test，76.411 秒，OK。
- 只读 Python 调用 `cycle._verify_candidate` 对两份现存成功 Run 重放：两版 `content_id`/`result_id` 不同且当前指针指向第二版。只读内存修改终态两个字段的反例均被该函数接受。
- 内存替身调用 `tools.vnext_normal_update.main`，参数含两次 `--metric C04`：退出 0、`UPDATES_READY`、输出两条、控制器只调用一次。
- 未执行十家公司 C04 全批次、新财报真实发现/获取、完整录制脚本、生产发布与旧 C04 历史迁移。工具调用计数：本审阅共 20 次 `functions.exec` 编排调用、39 次内部工具调用（包括读取、一次单测和本文件创建/核对）；未使用子代理或真实 SEC/provider 请求，只读访问了 GitHub Issue/PR。
