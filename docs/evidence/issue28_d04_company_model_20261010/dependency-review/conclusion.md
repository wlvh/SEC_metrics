# D04 实际依赖 P2 修补限定独审

结论：**CHANGES_REQUESTED**。原 P2 提到的来源构建与解释依赖已补入，新增有限控制通过；但同一遗漏类别仍有一个直接反例，不能按“D04 当前实际依赖已完整接入”结案。

审查对象：base `d8c36ca4ab6b0b3d38151bb47f07660f32ceeab9` → patch `666f245f67ccca4763da486b4c7d97cd2506cd86`。开始与最终 HEAD 均为 patch；本次检查的源码、测试字节与该提交完全相同。

[P2] 引文定位实际消费的政策文件仍未进入当前更新配置。`scripts/vnext/r6_semantic_source.py` 调用 `regulatory_investigation_candidates._quotation_ranges()`；该函数在 `scripts/vnext/regulatory_investigation_candidates.py:101-103` 读取 `_POLICY["quotation_tags"]`，政策来自同文件第 17 行的 `catalog/r6/regulatory_investigation_candidates_v1.json`。本补丁 `scripts/vnext/ordinary_current_update.py:77-85` 纳入了 Python 模块，却未纳入这份 JSON。README 关于“regulatory assertion policies are likewise not used by D04's quotation helper”的说明遗漏了这个实际使用的字段：D04 不使用其中的监管认定规则，但确实使用引文标签规则。不能因同一文件还含 D03 规则就忽略 D04 消费的部分。

有限复现见 `quotation-policy-control.json`。对现有 `<blockquote>…</blockquote>` 原始字节，实际 `_quotation_ranges()` 返回 `[0, 52]`；仅在内存把 `quotation_tags` 变为空集合后返回空列表，证明该政策改变确实影响 D04 来源构建。独立注入这份政策文件的 changed hash，实际 `_configuration()` 仍完全相等；真实 `run_once()` 在首次 `CANDIDATE_WITHHELD` 后继续返回 `PREVIOUS_INPUT_WITHHELD`、`calculation_performed=false`、同一 result_id，仅一次 producer 调用。底层来源观察、保存结果是明确的小替身；未修改任何政策文件或真实来源、总账与公司记录。这是更新失效复现，不是模型判断或公司业务证据。

建议把 `catalog/r6/regulatory_investigation_candidates_v1.json` 补入 D04 的 processing_files，并在本次已有的五个有限依赖案例中加入这份 JSON，验证改动触发一次处理、后续稳定复用、旧结果不改。无需递归证明树，也无需把 B13 专用容量政策加入 D04；已检查 D04 对 capacity_semantic_review 的共享来源/单元表示辅助函数导入，这不等于消费其 B13 业务政策。

本次自行验证：指定命令 `/private/tmp/issue28-company-c02-venv-20261006/bin/python tests/required_unittests.py tests.vnext.test_current_d04_company tests.vnext.test_ordinary_current_update` 运行 **38 tests、0 failures、0 errors、0 skips**，退出 0；进程 0.685053 秒，unittest 自报 0.356 秒。新增回归对五个已列依赖执行真实配置与更新控制：改变后新版本，稳定后禁止 producer，旧模拟记录及其目录保留。日志 `required-tests.log` 与 `required-tests-summary.json`。另有一次只读辅助命令因误写 import deepcopy 失败，随后纠正；错误明确保存在 `inspection-error.log`，不算验证通过。

未覆盖：不重审公司链、PR106、SDK 或旧全差异；未运行公司长处理、十公司材料、递归原执行证明、完整 CI、真实模型/SEC/账户/网络调用；未逐项穷尽所有传递依赖。未开发、commit、push、spawn 或打包。仅写入本 dependency-review 目录中的结论和日志。本结论不授 Ready、merge、生产采纳或 390 指标验收。

时间与资源：开始 2026-10-09T18:55:53+00:00，结束 2026-10-09T18:58:20.736755+00:00，实际用时 147.737 秒；**16 次工具调用**（7 个 functions.exec 包装 + 9 个嵌套工具），普通消息 **2 条**（一个发现更新 + 最终报告）。低于 20 次工具与 10 分钟上限。新 provider/paid/SEC 为 0/0/0。
