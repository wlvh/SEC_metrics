# C04 有限来源刷新接入

`tools/vnext_ordinary_refresh.py` 现在在调用普通刷新协调器时明确选择四形式 C04 后继；`ordinary_refresh_cycle.refresh_and_process()`新增参数的默认值保留旧路径。C04 使用独立的 `metrics/C04-registration-v3` 不可变尝试历史，B01等仍按原路线运行。相邻C04失败不会改判别的指标成功或抹去原成功。原V6 B13停用和模型调用权限不变。

最终绑定下的禁网材料测试 `recorded-refresh-final-binding.log` 用Marriott同一申报清单URL两份内容不同的真实保存响应，并在每一版同时录制所需Company Facts。原生SEC测试会话共四条录制获取，真实SEC／provider／paid调用均为0。两次有限刷新都为 `UPDATES_READY`，各自产生C04 `CANDIDATE_READY`、`PUBLISHED/0`；来源变更形成不同的成功尝试和Result，第一版在第二版形成后按原不可变记录重读。录制链验证的是程序接线，不能证明下一份尚未出现的新财报业务结论。`test_c04_source_only_install`和8项刷新边界测试进一步检查旧来源根处理副本不被覆盖、无关规则漂移仍拒绝、录制获取留有明确C04来源模式、旧默认行为及相邻指标失败不被C04成功掩盖。

在原累计账本上实际执行的**零SEC、零模型**入口见`live-zero-refresh-final.log`及`live-zero-summary.json`。`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs`的旧处理配置与缺失的C04 v3规格仍保持原样；新Run在自己的输入根安装当前规则。Marriott保存来源形成C04 `PUBLISHED/0`、Result `sha256:a5517d36ec92517b057a4e8e5f1277cc8f2850d9108d563a1adb2ad71cb7c3f9`，独立进程禁网、禁子进程冷读通过。原账本前后均为143／143／49。因为该调用设置`max-sec-requests=0`，两项需刷新元数据没有本轮获取，整体如实为`UPDATES_INCOMPLETE`；**不能称实际新财报已自动获取或刷新完成**。

修复过程中保留失败原件：首份录制只刷新申报清单而漏刷新Company Facts，整体未完成；第二份在零元数据刷新时也正确未完成；最初真实零调用入口因旧安装配置不可变而停止，第二次因普通V13父级仍绑定旧SEC模块字节导致Run失败。限定修复没有覆盖旧文件或重签旧Run。仅对显式C04来源模式，旧获取根中的三项非来源处理副本可维持原字节；来源发现与当前规则安装仍各自核验，其他文件不符继续拒绝。当前普通`issue_28_v13`执行绑定、连续`issue_28_v14`父级五文件/转移身份及本次实际执行字节已同步；修前/修后身份与三份现行收据摘要见`binding-summary.json`。`final-wiring-after-all-evidence.log`只证明最终离线接线，未代替真实SEC传输。

本目录没有新tar.xz、MANIFEST重生成或生产变更。大材料不重演：原两版C04保存更新、Paramount `WITHHELD/null`、B01+C04混合路线和独立冷读仍在`c04-normal-update-20260926/`按原控制器字节解释；本次只重验受影响的获取→后继Run、父级身份、旧来源根及接线。新源码差异仍待精确SHA限定独审，未经审阅不发新增SEC获取。下一项真实来源刷新若沿既有#28许可执行，也只能在核对实际前置条件后按有界URL/次数申领；这份零调用证据本身不增加额度或用途。
