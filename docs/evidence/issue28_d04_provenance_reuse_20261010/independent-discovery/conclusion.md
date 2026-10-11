# D04 primary submissions 刷新：新增差异定向独审

结论：在此次新增差异范围内未发现需要修复的缺陷。只对 D04 同一主体 CIK 的 primary submissions URL、空 accession、精确 CIK JSON 文件名，允许发现资料的原件字节刷新；完整 D04 实质来源、年报选源和重建请求仍必须相同。receipt 保留实际旧、新 metadata hash，并继续声明零新增调用/获取信用。该结论仅为限定离线代码审阅，不代表实际公司长链通过、历史私有档案审计或生产批准。

审阅精确范围：`406681ffb2c63c9f85652381b5a160ddf29a08d5` → `5cf816503c03e98edb67a463d6d0ce436a1c48d8`；HEAD 已核验为后者，源码/测试相对此 patch 无工作区差异。

- `scripts/vnext/capacity_update_input.py`：新增 `submissions_url` 导入；内部 `bodies` 对符合上述三项条件的 D04 发现资料使用比较占位值；新增 `discovery_only_body_changes` receipt 字段。
- `tests/vnext/test_d04_provenance_reuse.py`：新增 primary discovery 正例与 changed task/annual/foreign-CIK/history-shard 负例。

原 `independent-review` 的结论和日志未修改；本结论不将其覆盖继承为新增差异的独审。README 末段、capture-proof diagnosis、intermediate failure 和 discovery before/after 日志只作线索；本次未重新核查实际 Marriott 的四个请求或私有 source/proof。

实现核对：

1. 发现资料的豁免端点通过 prepared annual 的 entity 构造，不接受 foreign CIK 或历史 shard。空 accession 与 exact document label 两项缺一时仍比较实际 body hash。B13 始终比较实际 body hash。
2. 非 metadata 顶层实质字段、年报内容（包括 amendments/期间/主体/关系）和全部重建请求保持原严格比较；仅发现资料 hash 的豁免不会隐藏新语义单元、正文或 Company Facts body 的变化。新增 receipt 保存实际旧、新 hash；source 对象和原请求没有原地改写。
3. 已读取当前公司使用的 `current_d04_result.prepare_current_d04_case`：先构造并核查当前来源，再找等价原来源和完整原请求集合；原 source/request 字节、成功 terminal/plan/response 与当前语义由既有 `replay_original_d04_response` 读取链核验。source_equivalence 只是来源等价判断，不能单独证明 proof 真伪。
4. `normal_annual_input.select_filing` 从保存的最新 submissions 重选年报并保留当前期 amendments；相关历史 shard 尚未加载会阻止 preparation。`prepare_ordinary_going_concern_source` 必须取到每份当前年报/修订原件。内存反例验证 newly discovered unsaved amendment 会在进入等价比较前报具体缺失 URL。
5. 现有 complete company gate 仍拒绝 missing/failed/conflicting/unresolved group。新披露若导致任务变化，必须重新处理；本修复不能借旧四组结果补齐新任务。旧 registered-native 路径和实际公司长链未运行，本结论不把局部比较通过扩大为所有消费者通过。

实际实测：

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_d04_provenance_reuse tests.vnext.test_current_d04_company tests.vnext.test_registered_native_update.RegisteredNativeUpdateTest
```

`small-tests.log`：20 tests，0.265 秒，0 failures/errors/skips，正常退出。`counterexamples.log`：17/17 限定独立检查通过，覆盖精确 receipt hash、原 source 不变、零新增信用；非空 accession、错误 document label、foreign CIK、history shard；Company Facts/HTML body、amendment、主体、期间、新增/改变 unit；B13 default；真实重建请求一致以及改变请求协议仍拒绝；新发现但未保存的 amendment 阻止 preparation。反例使用一次性内存 mock；没有改写仓库测试。

未覆盖：实际公司长链、真实四组请求复用终态、私有 ledger/原档案字节、GitHub CI 终态、真实 SEC/模型请求、生产运行；均留给父任务按原权限验证。无 network、#47 目录/状态访问、bigtest、tar 操作、源码/测试改写、commit/push 或 spawn。

工具与限制：本增量 7 次 `functions.exec` + 9 次内嵌 `exec_command` = 16 工具节点；与前次 16 节点累计 32。普通消息本增量仅最终报告 1 条，累计 3 条（0 问题），未重置计数。三次只读搜索命令因猜测的不存在文件名/未匹配 glob 返回非零；后来读取实际文件完成核查，均计入节点，未据此声称测试失败或跳过。首次增量显式 UTC `2026-10-10T10:33:11Z`，反例 UTC `2026-10-10T10:35:15.350386+00:00`，落盘 UTC `2026-10-10T10:36:35.384769+00:00`；前次首次显式 UTC `2026-10-10T10:24:32Z`。未达累计 80 节点/90 分钟限制，普通消息已到 3 条上限。
