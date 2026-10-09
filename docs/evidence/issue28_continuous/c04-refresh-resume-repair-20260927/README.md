# C04 续接待刷新集合限定回修

`8115b114`的独立审阅在`c04-refresh-resume-20260927/independent-review/conclusion.md`保留`NEEDS_FIX_P2`：外部报告可改写`deferred_source_urls`仍通过续接。当前增量不改SEC获取器或普通V13父级，而是在认证前次第193槽、来源账本与同一C04状态之后，从该来源根**重新发现**前次已取URL之外的待刷新集合，核对完整发现身份、失败URL及报告集合逐项相同。下一URL仍须同时在前次真实待办和当前C04原生来源证明中。申领前又一次持账本锁比对末槽身份与累计，再核对来源日志摘要；这缩小了并发窗口，不等于对所有外部进程提供跨锁原子保证。

`resume-deferred-auth.log`是最终源码下的录制完整续接（117.000秒）：第一次只录制申报清单，第二次认证报告后只录制Company Facts；篡改捕获URL、篡改待办集合、旧报告重复使用均在新增申领前拒绝。`real-report-tamper.log`使用真实第193槽与原C04状态、仅临时改写待办集合，得到`ORDINARY_REFRESH_RESUME_DEFERRED_SET_CHANGED`，账本仍193槽、143／143／50。`real-resume-preflight.log`在真实原报告下得到正向认证，下一条仍为Marriott Company Facts，未发GET。11项边界短测及当前provider／SEC／刷新收据见`boundary.log`、`final-wiring-after-real-checks.log`。这些都不是第二条真实SEC成功记录。

普通V13需求身份保持`sha256:a573ed50d6a5e09e3477de53e5a8f83b01a600220379fdc8d73aba19bb32b3a2`；本次V14执行闭包、文件与三份收据摘要见`binding-summary.json`。原真实账本仍143／143／50。当前没有其他已知#28真实调用进程，但账本快照与获取器内部申领之间没有单把锁覆盖；第二条真实请求需由唯一执行者在即时复查末槽和来源摘要后、按原一次上限执行。出现别的槽、来源变动、未知结果或失败即停止，不自行重取第193条。新差异须先取得精确SHA限定独审；本目录没有新额度、模型调用或生产权限。
