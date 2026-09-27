# 8ce178a5 混合刷新恢复限定独立审阅

结论：**NEEDS_FIX（新增一项 P2）**。相对父提交 `134dcf4fc1630ef6e45fae012909eb7e6410e5e0`，前次两项 P2 的指定反例已被处理：有成功 B01 尝试的报告不能把该行改写为阻断后继续；处理副本创建失败的报告保留原 SEC 成功收据，可在下一次捕获前重建副本并接续。然而，新增的“无普通指标尝试”判断把**本轮没有尝试**等同于**磁盘上从未存在该指标配置**，会拒绝真实的阻断报告及一类旧报告，继续妨碍独立的 C04 来源接续。

## 发现

**P2：真实 `UPDATE_BLOCKED` 行在已有配置时不能续跑。** `scripts/vnext/ordinary_refresh_cycle.py:238-247` 的 `no_ordinary_attempt()` 除要求报告没有 `attempt_id`、`terminal` 等，还要求 B01 的 `configuration.json` 和 `current.json` 都不存在；`:261-272` 对带副本 ID 的新报告使用它，`:324-336` 对无状态字段的旧报告也使用它。但 `ordinary_update_cycle.run_once():276-277` 先写配置、再读取和恢复状态，`run_company():349-357` 把之后抛出的异常转成没有尝试 ID 的 `UPDATE_BLOCKED`。本审阅用注入的状态读取失败运行该实际函数，得到 `UPDATE_BLOCKED`、无 `attempt_id`、**配置存在而当前指针不存在**（`blocked-history-short.log`），没有网络或 SEC 调用。若此前同轮 SEC 捕获成功、C04 已写终态且仍有待办 URL，刷新报告会有 `current_processing_source_status=READY` 和这条真实阻断行；续跑在第二次捕获前必然报 `ORDINARY_REFRESH_RESUME_OTHER_METRIC_CHANGED`。历史无副本 ID 的 `SOURCE_SCOPE` 报告也可能在同一状态根中已有更早的 B01 配置；旧实现只要求本轮 B01 阻断，新检查会拒绝它。这里的完整双来源捕获组合未独立重跑，失败结论由已执行的普通更新写入顺序和续跑谓词直接推出。

应绑定**本轮前后**普通指标的持久状态，区分已有历史、此次新尝试和此次未尝试；不能用“配置文件不存在”代替这个判断。修复后需覆盖“SEC 成功、B01 在配置写入后阻断、C04 成功、仍有另一 URL”的正向续跑及成功行降格的拒绝，并为旧 `SOURCE_SCOPE` 报告给出真实旧状态根的兼容证明。单个 B01 失败不应使无依赖的 C04 来源获取无法恢复。

## 本次确认的修复及边界

- 成功 B01 行降格为 `UPDATE_BLOCKED` 时，原测试保留的 B01 配置使新谓词拒绝；保存的录制材料测试还断言篡改尝试编号先于第二次捕获被拒，随后原报告完成另一 URL。该防护针对报告篡改，不意味着可抵御同时任意改写受信任状态根的操作者。
- 处理副本失败的新报告带 `FAILED`、无副本 ID、单条 `PROCESSING_SOURCE` 错误；`:298-323` 核对阻断行并在账本锁下重建副本，后续仍核对 C04 终态、SEC 收据、待办 URL 和捕获前账本。保存的另一项录制材料测试验证了失败报告接续、错误阶段篡改拒绝和两次捕获。这不覆盖报告写出前进程崩溃等其它恢复情形。
- 新状态字段只在显式混合旧规则路线输出；无字段且无副本 ID 的旧报告仍有独立分支，但上述已有普通指标配置情形不兼容。`refresh_and_process()` 签名及 `tools/vnext_ordinary_refresh.py` 默认共享入口未变。再次使用旧报告时，`:161-181` 的账本计数/末条和 `:467-476` 的捕获前身份检查会拒绝已前进的账本；本审阅未重新执行重复捕获的长材料测试。
- 本审阅亲自执行 `PYTHONPATH=scripts /private/tmp/issue28_py314_venv/bin/python -m unittest tests.vnext.test_ordinary_refresh_cycle`，11/11 PASS；亲自检查 V14 execution authority 与接线 receipt，均通过。读取已保存 `resume-followup-material.log`（2/2 PASS，377.258 秒）、`resume-followup-fast.log`（132/132 PASS，118.568 秒）、`resume-followup-short.log`、`binding-resume-followup-after.json`；没有重跑材料或快测。快测选择器只追加一个新材料用例，V14 manifest 的模块哈希及三份 receipt 与现工作树一致。

审阅仅针对指定差异及直接相邻的状态写入/来源副本代码；未验证真实 HTTP/provider、完整公司结果、390 坐标、正式采纳或 #47/PR52。没有修改产品代码、提交、推送或打包；新增项目调用 `provider/paid/SEC = 0/0/0`。工具使用：`functions.exec` 14 次（其中 39 次本地 `exec_command`、2 次 `apply_patch`），低于 80 次上限；协作消息 0 条、最终报告 1 份；耗时低于 90 分钟。
