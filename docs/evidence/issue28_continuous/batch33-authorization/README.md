# Issue #28 D04→B13 33 组受限执行批次

用户在本任务明确批准 D04 先行方式 B、随后 B13，以及本批新失败经实质修复后的每组至多一次补验。执行者按此指令转录至 [Issue #28 评论5791560371](https://github.com/wlvh/SEC_metrics/issues/28#issuecomment-5791560371)；`authorization-original-user-text.md` 保留原文，`server-comment.json` 保留服务器返回。`initial-group-set.json` 固定 16 个 D04 与 17 个 B13 业务组，33 个初始请求摘要互异。原账本根、binding、171 失败及累计 122/122/49 不改；本批子上限 66/66/0，不增加总上限 240/240/80。

当前执行补丁仅允许精确组身份、既定顺序及初次机会；首次申领消费恢复标记并只移除旧 171 的停止。113、114 各一次同摘要例外绑定原失败；111、170、171 仅允许对应 V3 后继组，旧原件不升级。新 402、未知远端结果、来源真实性或用量异常保持停止。修后补验入口在发生实际新失败且补丁、测试及限定独审证明接通前保持拒绝，不能因本地文件或不同摘要自动重抽。

后继小差异收窄了“本批SEC0”的解释：它禁止把SEC请求记到33/66批次内，**不撤销**原总委托下独立的Issue28 SEC来源获取准入。批次首次D04业务申领后，独立SEC claim仍由原权限、余额和SEC通道停止守卫判断，不带批次授权标记；账本及原生输入的冷读保留它与provider claim的确切前驱顺序。限定独审在补丁`1c6bb186`发现一项P2：保存历史的验证器原可误接纳SEC已停止后的第二条SEC申领，真实账本会拒绝。定向反例先复现，再把SEC停止条件接入冷读，31项定向和127项快速测试通过；`independent-review/sec-cold-read-repair.md` 对`4a5d4bb4`修后差异限定复核通过。第172次新HTTP402仍关闭PROVIDER，不能据此清除或重发；本项代码修正本身没有发SEC请求。

`server-authorization-check.json` 证明 GitHub 服务器转录与当前执行绑定一致；`offline-wiring-summary.json` 和 `offline-paramount-113-summary.json` 分别证明当前版本的首组工厂、模拟传输、接受控制、冷读账本，以及原 113 无损同摘要路径。两者禁网且真实调用均为零。`fast.json` 为当前 Python 3.13.5、tokenizers 0.22.2 环境的 127/127 快速测试。`recorded-complete-enphase-summary.json` 是前一字节绑定的六组录制 Run 和**同进程机械重读**，用于复用未改的公司级路径，不称为当前补丁的跨进程独立冷读。`b13-170-source-audit/offline-wiring.json` 是最终接线收据，按当前执行权限文件哈希检查。

`independent-review/conclusion.md` 对 `c92c7698` 首轮 33 组受限申领差异未发现阻断，29 项指定测试通过；它不覆盖未来尚未实现的修后第二次申领。原账本随后安装授权，第一条真实请求直接执行 Enphase D04 第 0 组，没有作余额探针。`live-0172-summary.json` 绑定第172次原始终态：服务端返回 `HTTP_402 / Insufficient Balance`，无可用模型输出和 usage/cost 数值；该次已按规则计入一次 provider/paid，PROVIDER 因新停止再次封闭。本批开发错误补验授权不覆盖账户402，新172的同摘要重发也尚未获批准，因此不继续发模型请求。

用户随后报告已充值，并于2026-09-24明确回复“批准172一次受限恢复”。这项确切指令保存为`recovery172-user-approval.txt`；充值和批准都不会自行改写原172失败。`continuous_recovery_172.py`与`config/issue28_recovery_172_v1.json`已准备一次性路径：Issue服务器转录及最终字节绑定未完成时，不安装`recovery-172.json`、不产生第173次申领。`recovery172-offline-summary.json`用当前Enphase保存来源验证旧失败、模拟新402、独立测试授权与同摘要成功的原生收集；失败均保留在前缀，只有新成功替代当前信用。36项定向与127项快速测试通过，真实调用新增0。`recovery172-independent/conclusion.md`对待批准实现完成限定独审，未发现阻断；最终权限评论字节仍须做限定增量复核。录制结果不计真实公司完成。

这份材料仍不代表新增完整 D04 或 B13 公司结果。各公司必须完成全部组、原生 Result/Run、公开行与必要冷读后才计完整候选。D03、账户操作、生产采纳、Ready、合并和 active 切换均不在本授权内。
