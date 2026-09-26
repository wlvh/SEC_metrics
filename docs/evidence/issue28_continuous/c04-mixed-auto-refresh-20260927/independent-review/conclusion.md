# 0cefb9bb 限定独立复核

**结论：NEEDS_FIX。** 受审对象仅为 `0cefb9bb4831316e7587ef25daccd86157148c7e` 相对父提交 `68abb7a1a12a0c765abbd6b642bc4e175a103e74` 的本次混合 C04 来源刷新增量。当前一次性录制正向可成立，B01 被阻断、C04 可形成候选，整体如实报 `UPDATES_INCOMPLETE`；但合法的每轮 1 次 SEC 请求配置无法持续取得排在第二位的来源。

## 必须修复的反例：混合模式的一次一请求续接会重复第一条 URL

`ordinary_refresh_cycle.py` 的 `c04_only` 在 `metric_ids=['B01','C04']` 时为 false，故 `resume_from` 被第 201–203 行拒绝。第 225 行的 `attempted` 只在单次 `refresh_and_process` 内存在。`_pending()` 第 68–72 行把 `refresh_for_new_discovery=True` 的已保存来源仍视为待刷新。真实保存的 Marriott 来源发现顺序为 submissions、Company Facts；两者均在本次 C04 `source_proofs` 中。混合录制正向测试只调用一次 `max_sec_requests=1`，取得 submissions 并将 Company Facts 留待后续。

第二次以同样合法参数调用时，不能使用 `resume_from`，`attempted` 又是空集合；`_pending()` 再次把 submissions 排在 Company Facts 前。于是第二次仍申领 submissions 的 SEC 槽，第三次亦然，Company Facts 无法前进。`one-request-boundary.log` 对当前保存的 Marriott 发现结果重算了第一次、同轮排除首项后及下一轮的 URL 顺序，复现了这一点。它是只读边界检查，没有触发 `capture`；重复真实申领是由上述控制流直接推出的。原有 C04-only 续接已经解决对应问题，本次混合路由没有接入。修复应让混合模式的下一条 URL 由可信的前次报告、账本和当次 C04 证明共同约束，或提供等价的持久进度机制；仍须在申领前拒绝非 C04 URL。

## 其余边界与证据

- 新代码仅在显式 `c04_successor=True` 且混合旧来源根时进入该路由；默认路径未改。混合模式在申领前调用当前 C04 `prepare_case`，以 `source_proofs` URL 过滤待取项，`session.capture` 再按当前公司来源发现重验；已提交的录制正向日志为一次成功 SEC 槽、C04 `CANDIDATE_READY`、B01 `UPDATE_BLOCKED`、整体未完成。未证明 URL 的测试返回零槽。真实新增 provider、paid、SEC 调用均为 **0/0/0**。
- 这个 URL 集合尚不能被称作“仅 C04 所需来源”的精确集合：`prepare_saved_governance_input` 同时读取 C03 的代理与薪酬来源，`prepare_c04_registration_case` 又把其全部 `source_proofs` 并入 C04。既有 Marriott 来源图中，29 个普通发现 URL 全部落在 29 个 C04 proof URL 内。当前自然待取的两条元数据 URL 确实服务 C04，且非刷新来源还受 `session.capture` 的声明与刷新条件约束；本审核**没有**复现无关 URL 的真实申领。不过现有负例只塞入“不在 proof 集合”的虚构 URL，不能证明一个已在宽泛 proof 集合里的非 C04 URL会被协调器先行排除。修复续接时应同时补这个边界，而非把 proof 集合成员身份当成充分的指标归属证明。
- 我独立重算 V14 closure `sha256:639b9bf39a3962784a59dee7d66704e648713e520948183e9b478c3993bdae65`、execution authority `sha256:9d4c0436fd23c6e7feb04af80f4f12504b06d21dcc69accbce484a910a0e9a16`、协调器字节 `032d7f75377eab56bd428da464fec10a9393d1ac60a17a10199c44fa4ba46596`，并核对 provider、SEC、refresh 三份当前收据及四条新增证据哈希；见 `identity-check.log`。`binding-check.log` 和 `final-receipt-check.log` 属中间字节，最终身份以 `binding-final.log` 及本次独立检查为准。V13 文件未在该提交变动。
- 既有 286.662 秒首次材料运行只因录制账本槽位测试断言写成零而失败，修正断言后的混合正向 139.157 秒通过。当前缩短的 C04 更新材料 164.576 秒、来源刷新材料 227.794 秒通过；此前 `68abb7a1` CI 两个 240 秒超时不能改写为业务断言失败。新版 CI 只保留单版完整来源材料，双版身份与重复输入复用沿用未改业务代码和先前保存证据；新隔离信用边界测试本次复跑 0.003 秒通过，见 `credit-boundary.log`。来源刷新距离 240 秒阈值较近，且查询 `0cefb9bb` 时尚无该 SHA 的 CI 运行；不能称该 SHA 的远端 CI 已通过。

本次只读检查本提交差异、上述指定源码/收据/测试及 286/139/164/227 秒现有日志；没有重跑长材料测试、真实 provider/SEC 请求、修改原账本、改动 `execution-state.json` 或审阅 #47/PR52。工具调用：**16 次 `functions.exec` 编排、40 次其内工具调用**（含写入此文件及最后只读核对）；其中真实 provider/SEC 调用 **0**。
