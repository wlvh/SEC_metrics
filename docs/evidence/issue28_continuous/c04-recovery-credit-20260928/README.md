# C04 恢复指针前的专项信用复验

起点为已推送 `d5ab46ed09476f39c00e56ff1051c0aff486c657`。本增量处理一个正常更新故障：C04 的成功终态已落盘、`current.json` 尚未写入时，普通恢复代码只运行普通 Run 复验；C04 自己额外要求的发布状态与来源信用核对在指针写入后才会执行。错误终态最终会被拒，但恢复过程不应先将它记为当前成功。

`ordinary_update_cycle._recover()` 新增可选验收函数，默认仍用原普通验收；显式 C04 后继传入现有 `c04_update_cycle._verify_candidate()`。这不改变普通更新的默认返回结构、记录类型或成功规则。C04 仍按旧 `configuration.json` 身份运行；本改动不提供跨执行版本迁移，旧包须按原安装身份只读。

仓库保存来源测试 `tests.vnext.test_c04_update_cycle.C04UpdateCycleMaterialTest.test_saved_marriott_positive_creates_native_result` 复用同一 Marriott 正向 Run：模拟成功终态写入后指针中断，将终态中的来源信用改为伪值并重算终态自身 ID；恢复在写 `current.json` 前以 `C04_UPDATE_SUCCESS_CREDIT_OR_PUBLICATION_CHANGED` 拒绝。还原原终态后，调用同一恢复入口，`successful_attempt` 仍是原 Result 的尝试，当前指针得以写入，尝试目录仍只有原一条，没有新 Run。初版测试也通过，但多做了一次完整来源重建，`material-initial.log` 记录242.168秒；测试范围收窄到恢复职责后的最终 `material.log` 为1项通过、183.142秒，低于CI该选择器240秒限制。无实际 SEC/provider 调用。

本地另有 `directed.log` 15项、`provider-boundary.log` 5项通过，快速套件 `fast.log` 134/134 selector通过（217.677秒）；快速套件在材料测试最后一处精简前运行，该处只改变材料测试自身，最终材料另行通过。`wiring.log` 在当前未冻结 V13/V14 执行文件和父级身份更新后，核对 provider/SEC/普通刷新禁网收据及显式 C04 控制器 SHA，均通过。`binding-before.json` 和 `binding-after.json` 记录代码根、旧新文件字节及需求闭包。三个既有当前接线收据只同步执行权限哈希、需求闭包与 C04 控制器 SHA；其证据列表未重打包，实际 C04 正反材料和接线检查见上述日志。

这仅修复一个 C04 中断恢复时的错误信用指针窗口，不新增公司结果、390坐标、新财年在线更新或生产资格。原账本真实新增调用 0/0/0；旧 D04/B13/D03 原件和 #47 边界未变。代码及需求绑定会影响堆叠于本分支的 #47 读取当前父级闭包，按 `[shared-with-#47]` 登记；默认普通更新路径仍使用原验收器。
