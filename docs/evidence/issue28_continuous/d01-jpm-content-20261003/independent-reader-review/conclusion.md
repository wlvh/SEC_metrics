# bec78d9 JPM 单结果接收路径限定差异独审

结论：**PASS_LIMITED_DELTA；本次限定新增差异未发现需修的 P1/P2。** 正常读取入口中的26个独立反例均拒绝，7项新阅读测试及19项原阅读回归通过；无参数默认输出与精确前驱实现完全相同。

## 提交、范围与证据复用

精确受审 SHA：`bec78d987d1fb0af708cfda1e4c4fd94a43607f0`；前驱：`ea6293c5081ca6fe74c936574bc9dca497a33e3c`。实际检查限定为 `current_view.py` 新增显式 JPM 接收、该段 delta/机械汇总/机械生成器/短测/README，以及独立原件结论的身份与声明范围。八份实现、证据、测试文件的工作区字节均与精确提交一致，四份必需证明也与提交及 delta 内摘要一致。

复用 `independent-review-94955ac/conclusion.md` 的旧双D01联合绑定检查和 `independent-review-31beeab/conclusion.md` 的 V3 修复/安装/原生运行覆盖。本次没有重新阅读 JPM 整篇原件、重新执行普通 Run 或长冷读。标题内容信用仅来自 `independent-original/conclusion.md` 已报告的确切 FY2025 Item1A、56条标题级来源摘录；本审不把该报告升级为逐句风险发生事实、其他来源/期间或全公司验收。

## 亲自验证的读取与保存边界

正常 `load_current_view(include_jpm_reviewed=True)` 先核原390索引和四份必需证明的完整路径集合与实际字节，再按 JPM 公司键取机械条目。接收必须同时满足：固定已读 `f8da5496` Result、原 `99442738` 前驱、原生主体/指标/起止期间、显示 Spec、Run 身份、需求闭包、实际安装根和收据完整对象；原生记录和收据各自还须通过内容ID检查。单个对象自行重算出合法ID不能替代整条已核验对象关系。

另外只读核对现存原 attempt 与机械副本：原生 Result 全对象等于提交 delta；原/副本 manifest 相同，均为 OPEN；原 validation 为 NOT_RUN，副本为 PASSED，且副本收据全对象等于 delta 与汇总。收据四份 artifact 的字节数/摘要与实际原件和副本均匹配。未重新发机械收据，也未改原 Run/Result。

默认视图仍选用原双D01路径；执行精确前驱保存源码得到的默认输出与本提交默认输出完全相同。显式选 JPM 后只有 `jpmorgan_chase:D01` 一行不同，其余389行全对象相同、原期间保持、文本为56行。分母仍390，选中确诊缺陷18→17、保存范围D01接收2→3；20份旧C02/E01产品目标待验保持。原错误 `99442738` 身份仍存在于精确提交的缺陷登记，本次不会解除原错误，只选择另一已复核后继。

输出与行继续标记原 Run OPEN、候选公开行、无正式采纳/active信用，`all390_acceptance`、`production_authorized`、`full_current_head_reexecution`、`other_coordinates_newly_validated_by_this_delta` 均为 false，新增业务调用 `[0,0,0]`。17是该视图选中已登记缺陷数，不是全部剩余问题数。

## 独立反例与短测

26个反例均从正常读取入口进入，只在内存替换待读 delta，实际证明文件读取和摘要检查照常执行，未修改产品源码或保存证据：

- 四份证明逐个遗漏、添加未准证明：5次拒绝 `D01_JPM_REQUIRED_PROOF_SET_CHANGED`。
- 四份证明逐个改预期摘要：4次拒绝 `D01_JPM_PROOF_BYTES_CHANGED`；原索引摘要变化亦拒绝。
- 新Result配旧Run、错误需求闭包、安装根、显示Spec、财年、前驱、内容阅读Result、显示正文：8次拒绝相应身份/期间检查。
- 改公司、期间、正文并重新计算合法 Result ID；每个新对象先独立通过 `validate_record`，再更新 delta 内关联ID：3次仍拒绝固定 JPM 内容阅读身份。
- 改收据的 view 或 records artifact 并重新计算合法收据ID；两个新对象先通过 `validate_record`：2次拒绝精确机械收据全对象比较。另换入一份真实其他公司 PASSED 收据也拒绝。
- 重复坐标和声称正式采纳：2次分别拒绝范围与采纳检查。

因此，在精确提交保存证明作为接收依据的范围内，遗漏证明哈希、重签错误 Result/收据或拼接错身份不能获得本路径信用。这里不是对任意篡改源码和全部证明文件后仍能自行认证真实性的保证；哈希用于核对所选保存对象，不能自行证明内容或外部批准。

亲测命令及结果：

```text
/private/tmp/issue28-tokenizers-venv/bin/python -B docs/evidence/issue28_continuous/d01-jpm-content-20261003/test_reader.py
Ran 7 tests in 0.062s — OK
/private/tmp/issue28-tokenizers-venv/bin/python -B docs/evidence/issue28_continuous/current-390-d01-integration-20261003/test_current_view.py
Ran 19 tests in 0.219s — OK
```

日志：`inspection.log`、`native-and-receipt-bindings.log`、`proof-file-bindings.log`、`jpm-reader-tests.log`、`old-current-view-tests.log`、`independent-normal-reader-probes.log`、`view-controls.log`、`final-verification.log`、`operation-summary.log`。

## 限制与工作记录

未覆盖：父方新增登记、全PR/CI、原件内容复核报告以外的业务内容、新来源/年份、自动新输入更新、全390验收、正式采纳/生产；未重开已复用未变部分。所委托的新增接收差异范围内无未完成检查。

只读实时 Issue28；未 spawn、commit/push、业务/账户调用、外部评论或 #47/#54 现场/账本操作；未生成 tar。开工已有 `execution-state.json` 本地修改，本审未动。落盘仅本目录一个 conclusion.md 与日志；测试和有限探针均只读业务材料。

实际工具、消息与起止实测见 `operation-summary.log`，保守计入 functions.exec 编排和内部工具。普通消息为开头说明、一次进度、最终报告，共3条，问题0。

最终实测：UTC 2026-10-03T08:56:47+00:00 → 2026-10-03T09:04:20.269292+00:00；7.554分钟；35工具（11次functions.exec、23次exec_command、1次clock）；3普通消息含最终报告、0问题。最终复核八份精确受审文件未变、原Run/records未变，上限均遵守。
