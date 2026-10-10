# D04 同原件获取记录复用：定向独立审阅

结论：在指定差异范围内未发现需要修复的缺陷。此次补丁允许 D04 在完整原件集合相同、Company Facts 描述分别唯一关联自身来源证明时，忽略重复保存的获取尝试 ID。主体、期间、路径、其余描述、原件内容与重建请求仍须一致。这是限定离线代码审阅结论，不是实际公司运行、来源真实性终态、生产采纳或合并批准。

审阅对象：base `f51d8c3d27f3169b9cdb3a246295830882240c1f` → patch `406681ffb2c63c9f85652381b5a160ddf29a08d5`。实际 HEAD 为后者；审阅前后这三个范围文件相对 patch 均无工作区差异：

- `scripts/vnext/capacity_update_input.py`：`_annual_content` 的可选参数、新私有 Company Facts 关联检查、`source_equivalence` 的 D04 条件比较。
- `tests/vnext/test_d04_provenance_reuse.py`：五项限定回归。
- `.github/workflows/vnext-fast.yml`：三组小测试的显式接线。

读取 README、before/after 日志与 `original-source-diagnosis.json` 作为问题线索；它们不作为本次实测通过证明。为核实调用位置，仅额外读取相关小函数及既有小测试：D04 请求构建、`SemanticRequest.validate`、普通来源检查/`verify_saved_inputs`、严格 unittest runner。没有读取私有账本或运行公司长链。

检查结果：

- 放宽条件严格限定 D04。当前与原记录的完整原件集合必须相同；Company Facts 的 URL、accession、document、attempt、path 在各自记录内必须匹配且仅匹配一个 proof。顶层与 `original_input` 两处均检查，原记录也检查。
- 默认 `_annual_content` 仍保留 Company Facts attempt；B13 路径不启用该忽略参数。其他来源的 attempt 及 Company Facts 的主体、期间等字段仍参与完整比较。
- 身份封印、顶层实质字段、原件集合和重建后的完整请求仍由原检查控制。测试中不同请求会报 `UPDATE_NATIVE_SUBSTANTIVE_REQUEST_CHANGED`；缺失、失败、冲突或不完整的 D04 分组不能获得公司完成信用。
- 关联函数本身不是来源真实性验证器。实际进入请求复用时，既有 `SemanticRequest.validate` 仍核对当前和原 proof；`verify_saved_inputs` 核对最新获取状态、内容 hash 及请求绑定。这些检查没有在本补丁中被绕过或改写。
- 本 diff 没有修改历史 source/request/response；小测试确认 current/original source 对象未被原地修改，receipt 的 `new_provider_execution`、`new_acquisition_credit`、`original_provider_bytes_rewritten` 均为 false。实际历史档案字节未另行读取，本结论不声称完成该档案审计。

实际验证：Python 3.14.7，执行指定命令：

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_d04_provenance_reuse tests.vnext.test_current_d04_company tests.vnext.test_registered_native_update.RegisteredNativeUpdateTest
```

`small-tests.log`：18 tests，0.236 秒，0 failures / 0 errors / 0 skips，runner 摘要为 OK。追加限定检查见 `counterexamples.log`：16/16 通过，覆盖当前/原记录两层未关联 attempt、变更 Company Facts 主体/期间/URL/accession/document/path、重复 proof、descriptor 指向旧 attempt、默认比较未扩大、实质请求变化以及 source 不变/零新增信用。独立反例只通过一次性本地 Python 与内存 mock 执行，未修改源文件或仓库测试。

工具执行记录：首次测试命令的 shell 收尾误用了 zsh 只读变量 `status`，导致外层命令返回 1；Python 测试已完整执行且日志为上述 OK。后续直接读取日志与严格 runner 实现确认测试结果；反例命令改用 `result_code`，正常退出。没有将外层 shell 错误隐藏为测试通过，也没有重复真实调用。

未覆盖：实际公司长链、私有 ledger、真实 SEC/模型请求、GitHub CI 终态、生产运行；由父任务按原权限另行验证。本次未使用网络、未接触 #47 目录/状态、未读取大材料、未执行 tar、未改写源码/测试、未 commit/push、未 spawn。

限制与计数：6 次 `functions.exec` + 10 次内嵌 `exec_command` = 16 个工具节点（包含本结论落盘和读回）；普通消息 2 条（初始告知与最终报告，0 问题）。首次显式记录 UTC `2026-10-10T10:24:32Z`；反例执行 UTC `2026-10-10T10:25:49.880463+00:00`；报告写入 UTC `2026-10-10T10:27:06.825507+00:00`。未达 80 节点/90 分钟/3 普通消息上限。
