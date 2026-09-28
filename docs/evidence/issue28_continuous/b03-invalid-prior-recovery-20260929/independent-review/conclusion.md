# e1a668f 限定差异独立审阅

**结论：CHANGES_REQUIRED。** 精确对象为 `e1a668f116bb1fef087d4ba992462fcf57fb8443`，父提交 `a984001f892586f208dbe2d659195726e5334b5a`。审阅范围限指定 B03 后继、测试、fast 入口、V14 绑定和本次证据；为核对消费者，额外只读检查了既有 `ordinary_refresh_cycle.py`。未改代码、未发真实请求。

## 需修正的发现

1. **[P2] 一次后置来源检查失败会重新暴露失去当前信用的旧 B03。** `scripts/vnext/ordinary_b03_scope_update.py:83-87` 将旧成功识别为当前范围冲突；新来源随后可以产生一个通过 B03 范围检查的候选。代码在 `:159` 先把 `previous_scope_conflict` 清为 `False`，但 `:162-164` 仍会对 `source_identity_root` 模式复核处理副本。若该复核发现副本或来源已变化，`:165-168` 把本次终态记成 `EXECUTION_FAILED`，旧 `successful_attempt` 保持不变；`:187-194` 却返回指向**失去当前信用的旧尝试**的非空 `last_verified_candidate`，其中 `results` 还来自本次失败尝试。这个路径发生在混合来源刷新入口，违反“旧成功只作历史、篡改仍拒绝”的返回契约。应在全部后置检查完成且终态确定后才清除冲突标志；失败时不得把旧尝试和新结果拼作已核验候选。本项由实际代码控制流推出，未伪称已经执行真实并发篡改。

2. **[P2] B03 的新合法返回形状与 C04 续取校验矛盾。** 本补丁的材料测试在 `tests/vnext/test_b03_depreciation_scope_update.py:52-57` 明确建立 `PREVIOUS_INPUT_WITHHELD`、非空历史 `successful_attempt`、空 `last_verified_candidate`。但 `scripts/vnext/ordinary_refresh_cycle.py:380-381` 对混合来源 C04 的 `resume_from` 要求候选为空当且仅当成功指针为空；当 `metric_ids` 同时含 B03/C04、首轮已记账的 C04 请求后仍有待取来源时，合法的 B03 历史状态会被误判为 `ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED`，阻断下一次受限续取。应在保留 B03 指针/日志/终态完整性校验的同时，允许这个**无当前候选信用**的特定状态；不能放宽其他指标的校验。本项是跨文件静态反例，未执行真实 SEC 续取。

## 已核验与边界

- 独立重跑指定短测：`B03HistoricalRecoveryVerifierTest` 1/1 通过。另用短 mock 证实历史范围冲突回退后，机械行校验抛出的 `UPDATE_SUCCESS_ROW_CHANGED` 继续向外传播；其余篡改类别按既有校验器代码审查，未逐项重跑。
- 只读重算当前 V14 execution authority、semantic rule 和 wiring receipt，全部通过；闭包为 `sha256:377018aa27b4b50450f2a3f567bc0b619f253ef0b71137f8a4ccec45f93a3cdf`。精确 SHA 的 V13 manifest、默认控制器、`normal_run_v3.py` 与默认 CLI 路由和父提交逐字节相同，三份当前接线收据的执行权威 hash 一致。
- `material.log` 记载保存来源材料测试 1/1、155.370 秒通过；`fast.log`/`fast.exit` 记载 fast 141/141、107.492 秒、退出 0。这两项只核读既有日志，没有重跑。材料中的“变更来源”仅用合成 descriptor 证明已进入安装步骤，并被 `SYNTHETIC_INSTALL_STOP` 截断；未证明取得了真实纠正后的 Salesforce 年报、B03 正确数值或完整 390 坐标。
- `git diff --check` 对精确补丁通过。审阅期间另见 `execution-state.json` 有其他工作中的未提交修改；本审阅未触碰它。本次发现不构成生产、模型/SEC 调用、发布或全 PR 批准。

**底层工具调用：** 44 次（40 次 shell、2 次 web、1 次给执行者的审阅消息、1 次补丁写入；`functions.exec` 编排层未重复计数）。
