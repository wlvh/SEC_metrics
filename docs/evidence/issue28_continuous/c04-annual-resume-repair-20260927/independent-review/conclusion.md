# efa9a6cb 限定独立复核

**结论：PASS_WITH_BOUNDS。** 仅审 `efa9a6cb068df6734a72802de690dbac60b2444e` 相对 `fa92989bc845d6fb13e6cdbe46b5ca8f15fef43b` 的指定增量。上一轮 `a5a3ceba` 的 P2——已认证 submissions 之后，缺失年报在续接捕获前被完整 C04 case 再次挡住——在这段协调器控制流内已修复。上一轮结论保留其历史含义；本结论不扩大为真实新财年自动更新验收。

第 358–375 行现在先尝试完整 C04 case。若它因 `ValueError` 失败，只有当前发现从已验证同 CIK submissions 声明的**确切**当前 10-K/10-K/A 主文件 URL、发现项角色恰为 `current_annual_primary` 且状态为 `MISSING_SAVED_SOURCE`、错误精确为 `SAVED_SOURCE_MISSING:<该URL>` 时，才把来源视为 C04 所需。该 URL 还必须在前次报告、SEC 槽、C04 历史、重建待办和账本预检所得的 `allowed_next_urls` 内；随后的账本及来源日志哈希检查仍在捕获前。实际 `session.capture` 会重新发现声明、验证官方 URL，并在账本锁内处理 `source_only_c04=True`。完整 case 可构造时仍按原 `source_proofs` 检查；默认及 C04-only 条件在本提交未改。

`boundary-repro.log` 独立覆盖四个短场景：确切缺件且在前次允许集合内时，模拟捕获收到唯一年报 URL；内层出现无关错误或 URL 不在前次允许集合时，均在 `CAPTURE` 阶段拒绝且捕获数为零；submissions 未验证时在 `DISCOVERY` 阶段拒绝。`short-tests.log` 的指定两项短测试通过（15.726 秒）。本次复现与新增测试均以替身代替前次报告认证及捕获；它们证明本补丁的条件分支和拒绝行为，不证明真实新年原件已获取、完整后续依赖发现、原生 Run 或失败恢复。原 365.477 秒混合续接及 330.682 秒 C04-only 保存日志只按旧代码范围读取，未重跑。

`identity.log` 独立加载当前 V14 Requirement：本提交及父提交身份、模块字节绑定、closure、execution authority 均一致；refresh/provider/SEC 三份当前收据列出的 50/93/50 个证据哈希全部匹配。V13 历史身份未在本增量修改。收据和测试均不授生产权限，未核称本 SHA 远端 CI 终态。真实新增 provider/paid/SEC 调用 **0/0/0**；未改原账本、父任务未提交的 `execution-state.json`、#47/PR52，也未提交或推送。

本轮新增 **9 次 `functions.exec` 编排、14 次其内工具调用**；连同上一轮分别为 **34 次、57 次**，低于累计上限（包含本结论写入及一次最终只读核验）。
