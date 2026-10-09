# 18d8d8a7 定向独立审阅

审阅对象：`18d8d8a7da38072576b82bcdd6c58d331c735352`，父提交 `d5ab46ed09476f39c00e56ff1051c0aff486c657`。范围限定为本补丁的 C04 恢复、V13/V14 当前绑定、三份接线收据和 `c04-recovery-credit-20260928/` 证据。**结论：PASS_WITH_BOUNDS；未发现阻断这项中断恢复修复的缺陷。** 一处旧代码说明与实际差异不符，见下文。

恢复顺序成立：`ordinary_update_cycle._recover()` 对尚未写入指针的每个 `CANDIDATE_READY` 终态先调用验收函数，全部通过后才执行末尾的 `atomic_write_json(current.json)`；验收抛错不会推进文件指针。C04 的 `run_once()` 明确传入自己的 `_verify_candidate()`，该函数先重放普通 Run，再比较终态摘要的 `publication` 与重放 Result、`source_credit` 与该 Run 的输入绑定。普通调用者未传参数时仍使用原 `_verify_candidate()`；记录字段和返回形状未改。独立构造的普通恢复短例确认默认验收在指针写入前调用。

保存材料的正反例与源码吻合：材料测试在 Marriott 成功终态落盘后删除 `current.json`，伪造 `source_credit` 并重算终态自身 `record_id`；`run_once()` 以 `C04_UPDATE_SUCCESS_CREDIT_OR_PUBLICATION_CHANGED` 拒绝，且指针仍不存在。还原终态后直接调用同一 `_recover()` 路径，原尝试成为 `successful_attempt`，指针写入，尝试目录仍只有一条。发布状态篡改另由短单测覆盖，但其普通 Run 重放被模拟；它不是第二次完整材料测试。本人重跑 `tests.vnext.test_ordinary_refresh_cycle` 与 `tests.vnext.test_c04_update_cycle.C04UpdateCreditBoundaryTest`，15 项在 7.322 秒内通过。保存的最终材料日志显示 1 项在 183.142 秒通过，旧初版 242.168 秒、fast 134/134 selector 217.677 秒；这些长测日志仅只读核查，未重跑。

当前绑定一致：本人重新加载 V13/V14 快照并执行 `validate_execution_authority()`，得到闭包 `sha256:69ac613ed512f13e3ef6c8519dd38ce6e67dca81b0d47415b088280e0f81415d`、`sha256:50e9f6d352cbc7ed560410ab4c15525262822ea9e477c28e7f56933d7c7c785b`。V14 的父级闭包、父级 `baseline_manifest.json` 摘要和 transfer 父级闭包均已跟进；执行权限摘要为 `sha256:0758cd7540cbbcf21b5d0b32031ca2c11e7bb090955642e69bed337a62c80fc2`。三份接线收据的执行权限摘要相同，C04 控制器摘要等于当前文件 `f48c52a27312de7ee8bfe9571d1cd7a87c7393a277a4a22fd7c8095c2bc5169b`；本人逐项核对其原有证据摘要（provider 95、SEC 50、普通刷新 50 项），均与磁盘字节一致。`validate_wiring_receipt()` 通过。补丁只改 V13/V14 当前需求文件，未修改更早冻结快照。接线收据的既有材料没有因重新绑定而成为本补丁的新材料证明；新增恢复正反例应以本目录日志和测试为准。

旧状态边界是拒绝跨版本续写。C04 `configuration.json` 绑定当前控制器 SHA 和 V13 需求闭包；本人将旧控制器 SHA 写入独立临时状态并重算记录 ID，当前 `_configuration()` 以 `C04_UPDATE_CONFIGURATION_OR_RUNTIME_CHANGED` 拒绝。本补丁没有旧包状态迁移；旧状态须按原安装身份读取。若 `current.json` 已存在，`_recover()` 会先重写同一状态，再由 `run_once()` 专项复验原成功终态；本结论所称“写入前复验”只针对**尚未成为当前成功的待恢复终态**，不扩大为每次 `current.json` 写入之前都复验。这一既有指针路径不产生新的成功引用。

非阻断的文档差异：`scripts/vnext/c04_update_cycle.py` 顶部仍写着 “The older ordinary controller stays byte-identical”，但本补丁确实修改了 `scripts/vnext/ordinary_update_cycle.py`，并重绑 V13/V14。建议在后续代码说明更新时改成“普通路径默认验收语义不变”；不能继续用“字节不变”解释历史兼容性。

未覆盖：没有重跑 183/242 秒材料或 217 秒 fast；没有触发真实 SEC/provider 请求、验证新财年在线自动更新、生产采纳、完整公司或 390 坐标。检查期间工作树原有 `docs/evidence/issue28_continuous/execution-state.json` 修改未触碰；未操作 #47/PR52。本人实际使用 **14 次 `functions.exec` 编排调用、45 次底层工具调用**；仅写入本报告，无其他写入。
