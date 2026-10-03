# B13 两阶段离线候选：c44bb047 限定增量复核

审阅对象固定为 `c44bb047481476b6736de0d17d277af05775f640` 相对 `a48d282ed719c210001aab4dbfef67b892631900` 的 `capacity_two_stage.py`、其定向测试、`measure_saved_sources.py` 和本目录 `README.md` 差异。继承初版 [限定独审](../independent-review/conclusion.md) 的两项 P2；未重审初版未改字节或整个 PR。结论：**两项 P2 在这个离线边界内均已修复；指定增量未发现新的阻断项。** 这不授予真实调用、原生结果或生产信用。

1. **严格整数单元序号：已修复。** `validate_scan` 逐项要求 `type(index) is int`，然后比对完整的从零开始序号。定向测试增加 JSON 布尔值和小数反例。用第 190 次保存来源重放时，`false` 和 `0.0` 替换第零项均以 `B13_SCAN_UNIT_CENSUS_INCOMPLETE` 拒绝；见 [boundary-replay.log](boundary-replay.log)。这证明形状校验，不证明模型确实逐单元读懂原文。
2. **第二阶段接受重算摘要的超限结果：已修复。** `interpretation_request` 现在必须取得扫描原始响应字节，并以当前完整请求重新运行 `validate_scan`；传入的 `scan_result` 须与重新得到的形状结果逐字段相同。`validate_interpretation` 也沿这条入口重验。因而候选上限、引用归属、必评覆盖、响应哈希和身份一起从原始字节重建，单独重算 `scan_result_id` 不足以通过。第 190 次 Enphase 第 1 组有 1,276 个可用引用：64 个有效引用可构造第二阶段；65 个直接扫描报 `B13_SCAN_CANDIDATE_CAP_EXCEEDED`；把 64 改成 65 并重算摘要、仍配旧原始字节时报 `B13_SCAN_RESULT_NOT_BOUND`；配新的 65 引用原始字节也报超限。第二阶段结果校验同样拒绝篡改，详见 [boundary-replay.log](boundary-replay.log)。

指定短测试 `PYTHONPATH=scripts uv run --no-project --offline --with tokenizers==0.22.2 python -m unittest tests.vnext.test_capacity_two_stage tests.vnext.test_capacity_reference_contract -q` 本次实际运行 **21 项，OK**。`git diff --check` 通过。提交的 `fast-after-p2.json` 记录 128 个 selector、整体 `PASSED`、69.059 秒；本次只读核对记录，未重跑该套件。

测量脚本仅调整为把同一原始扫描字节传给第二阶段。本次从保存的 190 和 171 来源只读重算，结果与 `measurement-after-p2.json` 及原 `measurement.json` **逐字段相同，两份 JSON 文件 SHA-256 也相同**；见 [measurement-replay.log](measurement-replay.log)。重新测得 16 个需新执行的组，按每组至多两次是假设 **最多 32 次新请求**，不是许可或实际消耗。5 组可用引用不足 64；Ford 第 9 组使用 23 个合成引用，判断输入 195,083、连 4,096 输出预留为 199,179。README 已明确 `min(64, 可用引用数)`、五组例外以及合成输入不能证明真实模型输出或正确性。旧测量 JSON 的键名 `option_b_assessment_input_at_64_refs` 对这五组字面上不精确；README 的实际数量说明消除了主要误读风险。若以后重命名字段，应生成新的派生记录，避免改变本次历史测量。

仍未覆盖：扫描原始字节是否来自真实 provider 的不可变录制、模型漏报和假阴性、真实 4,096 输出能否完成、真实超限时的停止及账本计数、双阶段原生保存和冷读、旧 190 与新结果合并、完整公司 B13、远端 CI、正式采纳与生产。原 191/192 失败不会因本次离线修补获得第三次机会。本次未发模型或 SEC 请求、未碰账户、未执行长测试或 #47/PR52，也未 commit/push。

本次实际使用 **12 次编排工具调用、28 次底层工具调用**，其中只读查看、短测试与重放在前 9 次编排调用中完成；其余用于写报告和核验工作区。未触及 80 次工具、90 分钟限制。
