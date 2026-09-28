# d4927a8 定向独立审阅

审阅对象：`d4927a86f0d7f94461ce58030856503c34604e56` 相对父提交 `ea6ac14e8afc8464eeeca6f004b2016d1678ce40` 的增量。**结论：在指定范围内未发现阻断项、可复现的新增错误接受或误拦。**这次改动把同一次渲染已验证的 Run 记录和来源案例交给候选复验使用，未删掉复验条件；不据此推断主 CI、生产采纳或跨财年更新已完成。

- `render_ordinary_run` 仍先调用 `_mechanically_replay_open_run(..., require_complete_results=True)`（冻结路径仍用 `load_frozen_run`），随后从安装的来源重新构造 `replay_case`。新私有参数默认 `False`；默认返回仍精确为 `row/evidence/receipt/files` 四字段。只有 `_verify_candidate` 显式请求时，才附带该次调用已经验证的 `manifest/records/case`。行、证据和 CSV 字节的构造逻辑未改；receipt 中的 `renderer_sha256` 随代码字节前进，这是预期的身份变化。
- `_verify_candidate` 原来先独立重放一次，再由渲染器重放一次；现在只取渲染器同次重放的记录及案例。终态配置与指标集合、Result ID、`_completed_result`（含 B13/D04 特例）、每份行文件字节及终态 SHA、来源描述 `_descriptor` 的比较均保留。C04 包装层对发表状态与来源信用的再次比较也未改。稳定的已保存输入下，原两次重放与新一次重放使用同一磁盘根和同一验证函数；发现的差异仅是错误发生的先后顺序可能变化。
- 下一次 `run_once` 以及中断恢复会再次调用 `_verify_candidate`，继而重新进入 `render_ordinary_run` 的磁盘重放；补丁没有跨调用缓存。该代码和现有保存来源材料覆盖独立冷读，但不能把它扩大解释成并发改写文件时的原子快照保证。
- V13 的 `new_rule_files` 中 `ordinary_update_cycle.py`，V13/V14 的执行文件绑定，V14 父闭包、父 `baseline_manifest.json` 摘要与 transfer 父闭包都与本 SHA 实际字节一致。独立加载 V13/V14 得到闭包 `sha256:7ff851292f26326a83dfaec46ee0a418163a8bfcd8b20ce032e5e7c8a9f8fed4` 和 `sha256:6372c5dbd59d2127227eb3c1ad1f34cd4a6742ba62d1cbd691f04cece8a3cf45`，两者的 `validate_execution_authority` 均通过。三份当前接线收据的执行权威摘要均等于 `sha256:8946340d0d801fbf181a9fc1b3753b864e491051eb35d3a678e6d49931417350`；provider 收据经原验证器通过，SEC 与普通刷新收据的零调用字段和各证据文件摘要经独立核对通过。差分未改冻结 Requirement 包或 #47/PR52 文件。

本次实际运行指定短测 15 项，6.337 秒，通过，见 [short-tests.log](short-tests.log)；独立闭包与接线检查见 [binding-check.log](binding-check.log)。已保存的长材料只核读：C04 材料 1 项 136.796 秒通过并断言默认四字段；原 profile 326.990 秒、修后 272.203 秒；fast selector 134/134 项、209.913 秒通过。上述计时只证明这次本机样本约 54.8 秒的缩短，不预测 CI 的 480 秒单项结果。本次未重新运行长材料、fast 或真实 provider/SEC 请求；未检查本 SHA 以外已闭合的业务问题。

工具计数：本审阅共 13 次外层工具调用、34 次内层调用（含两次只读网页读取；不计上游已有日志生成）。审阅开始时 `execution-state.json` 已有未提交改动，本审阅未触碰。
