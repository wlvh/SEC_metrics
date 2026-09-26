# C04 四形式正常更新后继：保存来源的版本与恢复

原普通更新控制器`ordinary_update_cycle.py`仍由旧需求身份绑定，不能直接改其默认选源。新增`c04_update_cycle.py`只为C04复用原控制器的锁、不可变intent/terminal、成功候选核验和中断恢复；其配置固定四形式、源目录、当前V13需求闭包及控制器文件SHA。`tools/vnext_normal_update.py --process`遇C04即自动选该后继，把状态放在`metrics/C04-registration-v3`，旧`metrics/C04`历史目录不被改写；其他指标继续原控制器。共享`normal_run_v3`的默认参数、`_binding()`及返回结构未改。现行V13/V15需求闭包仍分别为`sha256:2620e1c13900bdfd7bb501b7a3ff9c2aece37ec25cb22a03d9a78e8d7872f300`与`sha256:9c02b4772e364f33b311c10b6282dca3a4083ad0aad528d1ad2a75ce33956a3e`；新控制器通过更新配置中的`controller_sha256`固定，未修改冻结旧文件或重签旧Run。

`verify_saved_update.py`以本仓库已取得的Marriott同一SEC submissions URL两份不同正文（SHA前缀`9112ca35`与`e3eeefe3`）通过原录制来源会话依次安装，**没有HTTP访问**。第一次与第二次均产生`CANDIDATE_READY`，输入`content_id`、原生Run ID及Result ID各不相同；两份C04仍分别为`PUBLISHED/0`，旧候选保留为独立版本，见`recorded-update-summary.json`、`result-readback.json`。这里证明的是来源字节变化会形成有身份的新候选，即便业务值没有变化；不是新财报实时发现或获取。重复相同来源得到`NO_SOURCE_CONTENT_CHANGE`且未建新Run，注入来源检查失败为`INPUT_FAILED`并保留上次成功，恢复后仍复用原成功；完成终态后模拟指针写入中断，再读可恢复而不重复建Run。Paramount原已验证来源得到`CANDIDATE_WITHHELD`、值`null`，再触发为`PREVIOUS_INPUT_WITHHELD`，没有从0条Item 4.01推导0。日志`recorded-update-retry.log`是实际一次完整禁网演练；首次`recorded-update.log`仅因验证脚本导错`request_log_attempt_id`的模块，在目标路径运行前失败，原件保留。

`cold_read_update.py`在独立Python进程中禁止网络与子进程，重读保存的两版Marriott成功记录，仍为`NO_SOURCE_CONTENT_CHANGE`，见`cold-read-summary.json`。`verify_mixed_update.py`以实际Marriott保存来源同时运行B01和C04，两个坐标均`CANDIDATE_READY`，B01使用旧`metrics/B01`状态，C04使用新版本命名状态，见`mixed-update-summary.json`。这些测试复用已成立的四形式C04来源/原生Run/冷读材料，不重做其全部原件核查。原Issue28真实账本在录制前后都为192槽、provider/paid/SEC `143/143/49`；新调用`0/0/0`，没有正式采纳、发布或生产调度。

已验证的新增能力是**正常保存来源更新入口无需人工逐公司选C04路线，来源字节变化能生成新版本，且已有成功与失败恢复状态可追溯**。尚未验证真实新财报的自动发现/获取、十家公司全部C04完成或缺同CIK前期年报时的替代否定业务规则；Paramount保持`WITHHELD/null`。当前实现和录制链的限定独审待完成，不能把录制成功扩成完整#28验收。
