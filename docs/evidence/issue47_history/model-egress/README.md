# #47 模型出口：限定差异与离线验证（供独立安全审阅）

**这是什么**：让 #47 的历史 D04 路线在所有者另行批准后能发出受限模型调用所需的最小改动（`egress-registration.patch`），以及在一棵应用了补丁的临时副本里做的离线验证（`verify.py` → `offline-verification.json`）。

**不是什么**：不是调用许可，也没有发出任何调用；补丁在仓库里**没有应用**。今天的仓库：控制器不给 `issue_47_v1` 造授权对象，适配器不把字节交给 #47 的请求类型，出口扫描器通过——这三点由 `tests/vnext/test_historical_model_calls.py` 在未打补丁的树上断言。#28 的工作现场、额度、账本和旧评估都不读、不借、不复用。

## 为什么必须改冻结文件

一次模型调用要过三道门，三个文件都被此前的世代按字节记录：

| 门 | 今天的行为 | 补丁做什么 |
|---|---|---|
| `invocation_control._prepare_successor_invocation_authority_from_requirement` | 按 requirement_id 登记世代（issue_28_v2、R4 修订、issue_28_v14），其余一律拒绝 | 加 `issue_47_v1` 分支：字段由 `historical_model_calls.invocation_authority_fields` 在验证 #47 自己的许可后描述，**授权对象仍只由控制器的私有工厂创建** |
| `ai_adapter._scoped_transport_payload` | 只把字节交给 #28 的 `SemanticRequest`（按模块名＋类名）或 LiveScopedReaderRequest | 加一种类型：`historical_model_calls.HistoricalSemanticRequest`（同样按模块名＋类名），交字节前从保存的申报字节重验请求 |
| `tools/check_provider_egress.py` | 固定传输调用方与出口令牌引用的精确集合 | 把同一个 `historical_model_egress._Transport.send` 加进两个集合 |

另有一处是量出来的：控制器只对 `issue_28_v14` 容忍"价格未知"（计划的 `estimated_cost` 为 null）；#47 的计划同样没有价格快照，否则在建计划时就被拒。所以 `_continuous_observations` 也要认 `issue_47_v1`。

还有一处是跑出来的：三个文件都在 `issue_47_v1` 的执行授权里（继承自父代），不重记就在建授权时以 `Successor execution authority bytes differ` 拒绝——先后撞到 `ai_adapter.py` 与 `tools/check_provider_egress.py`。所以 mint 工具要把三者加进 `RE_RECORDED_FROM_TREE`。

## 补丁的全部内容（6 个文件，`git apply --check` 对当前仓库通过）

| 文件 | 改动 |
|---|---|
| `scripts/vnext/invocation_control.py` | +11 −1：`issue_47_v1` 分支；`_continuous_observations` 认它 |
| `scripts/vnext/ai_adapter.py` | +4：认 `HistoricalSemanticRequest` 并调用它的 `transport_payload` |
| `tools/check_provider_egress.py` | +2：同一个 `_Transport.send` 进两个精确集合 |
| `tools/vnext_mint_historical_requirement.py` | +9：三文件进 `RE_RECORDED_FROM_TREE` |
| 新 `scripts/vnext/historical_model_egress.py` | 300 行：`_Transport.send`、`execute_historical_semantic`、`register_from_slots` |
| 新 `tests/vnext/test_historical_model_egress.py` | 616 行：离线验证套件 |

不在补丁里、已在仓库的：`scripts/vnext/historical_model_calls.py`（许可、请求、计划、账本——不碰传输工厂、出口令牌或服务商主机名，所以出口扫描器在仓库里通过）与它在未打补丁状态下的用例。

## 一次调用绑定什么（按检查顺序）

1. **#47 自己的许可**（`config/issue47_historical_model_calls_v1.json`，不存在）：与 SEC 许可同样三层——字段逐个定型；按摘要读出批准评论正文并重算哈希，且评论须是本仓库议题 47 上、由批准人发的；评论须复述上限、账本根、scope、传输与重试政策，许可不能比批准宽。实时路径从 GitHub 取回评论并要求逐字节相同。模型许可特有的规则：一次调用＝一次服务商调用＋一次付费调用，**不含任何 SEC 请求**（上限第三项必须为 0）；传输必须是固定那一个（服务商主机名与适配器的常量比较，不写在本模块里）；scope 只能点名已接线的指标（今天只有 D04），用途只有一个；信封恰好是授予之并；账本根不与 #28 的根、本检出、#47 的 SEC 账本根重叠或嵌套。
2. **请求**：由钉定期间的来源在准备时一次建成（内容寻址）；每次校验重算来源身份、逐单元重哈希、重新证明所读的每份保存文件，并要求请求是来源分出的请求之一、服务商请求体与 schema 逐字节不变——与 #28 的请求在同样位置做的检查相同，而不是每次重新解析申报。
3. **授权对象**：控制器从许可文件造出；文件表＝本世代执行授权＋调用路径的两个模块＋许可文件＋保存的批准，每次检查都重算哈希，任何一个中途改变即拒。调用方传入的许可映射必须与授权对象绑定的三个决策哈希相同，否则 `ISSUE_47_MODEL_ALLOWANCE_IS_NOT_THE_ONE_THE_AUTHORITY_BOUND`——一个更宽的映射不是许可。
4. **WB-3 计划与执行**：`build_successor_ai_invocation_plan` 与 `execute_successor_invocation`，控制器已要求的预约、所有者令牌与出口标记；`_Transport.send` 在打开任何东西之前再核一遍这三样，实时路径还在 socket 前从 GitHub 重验批准、从保存字节重验请求。
5. **账本槽位**：在 socket 之前写入 [1,1,0] 的意图，永不删除。

## 计数、停止与恢复

- **计数**：每次认领计一次服务商、一次付费调用，失败也计；累计数每次从账本目录重读，跨进程、跨会话成立；进程锁防同机并发。
- **不重抽**：同一请求摘要只能认领一次（`ISSUE_47_MODEL_REQUEST_ALREADY_CLAIMED_NO_REDRAW`）。控制器本身对后继计划零自动重试。
- **停止**（与 `issue_28_v14` 账本相同的集合）：没有终态的槽位（可能已到达端点，按全额计并停）、`HTTP_402`、`UNKNOWN_REMOTE_OUTCOME`/超时、`USAGE_UNKNOWN`、`SOURCE_AUTHENTICITY_FAILED`、`CONTEXT_REFERENCE_MISMATCH`（服务商报告的输入令牌数与固定参考分词器不一致）。停止后任何认领都按名拒绝。
- **恢复**：补丁**不实现**恢复入口。停止后恢复是所有者的决定，要有新的书面批准（如 #28 对 110、172 的受限恢复授权），不是重试。

## 离线验证的做法

在一棵带 `issue_47_v1` 注册补丁的运行树副本里应用本补丁并 mint，然后 `python3 docs/evidence/issue47_history/model-egress/verify.py`：

1. 确认本补丁就是这里应用的那一份（`git apply -R --check`），snapshot 为这些字节 mint 过；
2. 出口扫描器通过，且两份 #47 模块里恰好只有 `_Transport.send` 一处调用传输工厂、一处引用出口令牌；
3. 跑完整套件：全程拒绝 DNS、原始 socket 与 SEC；唯一的服务商连接器换成受控的一个，它断言 URL、请求体、超时后返回录制字节，或抛出 402、连接重置、超时；
4. 逐个注错，按"快类在前、遇错即停"跑套件，记录每个注错**首先**被哪条用例抓到（不是全部抓到它的用例），连同它抛出的那一行。两种"看起来抓到、其实没有用例看见"的情形被关掉：注错后的文本必须能编译（语法错误会让套件在任何用例运行之前失败）；注错落在 snapshot 按字节记录的文件（三个边界文件）上时，先 mint 再跑套件——字节绑定对任何改动都拒绝，有害无害都一样，在那里被拒只说明文件被绑定，不说明有用例断言了注错破坏的那条性质。跑完恢复原字节、再 mint，snapshot 必须逐字节回到原样，否则整次验证停下。只在类夹具（`setUpClass`）里失败的记为 `CAUGHT_AT_FIXTURE`，如实记为钝的捕获；
5. 从各世代自己的清单读出哪些世代按字节记录了三个边界文件，因而会被应用补丁移动——是读出来的，不是推出来的；
6. 树回到起点：补丁仍可反向应用，snapshot 仍一致，每个绑定文件的字节与验证前相同。

全部成立才封存 `offline-verification.json`。它绑定调用路径两个模块、三个边界文件、mint 工具、套件、`verify.py` 与补丁本身；`historical_model_calls.live_model_ledger` 要求它对当前树逐字节成立，所以实时路径不能在验证过的代码之外运行。在今天的仓库里它不成立（补丁未应用），这由仓库用例断言。

**受控的**是什么要说清：许可与批准评论是测试夹具，写入临时副本、跑完删除，评论正文自带 `"fixture": "RECORDED_TEST_ONLY_NOT_AN_APPROVAL"`；模型输出是语义路线套件的合成夹具（冻结检查器自己推出的关系），所以登记出来的东西证明的是"一次计数的调用到创建者日志"这条路，**不证明任何申报的内容**。

**第一次运行有三处缺陷，在封存之前停下、没有产出收据**：(1) `UNKNOWN_USAGE_DOES_NOT_STOP` 删掉了一个 `if` 的唯一语句，注错后的文件是 `IndentationError`，套件在任何用例之前失败，却按"返回码非零"记成了抓到、`first_caught_by` 为空——够不到目标代码的注错不是证据；改为用 `pass` 占位，且每个注错先编译。(2) `THE_ADAPTER_MATCHES_THE_CLASS_NAME_ONLY` "首先被 `setUpClass` 抓到"，那是控制器的字节绑定（`ai_adapter.py` 在 `issue_47_v1` 里被重记）拒绝了任何改动，不是 `test_the_adapter_hands_bytes_only_to_the_named_type` 看见了按类名放行；改为对被记录文件先 mint。(3) 门禁注错的目标串在 `check_provider_egress.py` 里出现两次（两个精确集合各一次），脚本会在那一项断言失败中止；拆成两个注错，各破坏一个集合，所以只查一个集合的门禁也会被看见。

**第二次运行也在封存前停下**：修好上面三处后，它跑在一棵**落后于仓库**的运行树里——合并 base 带来的 #28 快照与 B03 接线都还没同步进去。被验证的边界文件、套件与调用模块与"当前 HEAD + 补丁"逐字节相同，但铸造工具与各世代清单是旧的：封存出来的收据会绑定旧的铸造工具，在真正的目标树上对不上，"会移动哪些世代"也是按旧快照量的。改为先把运行树同步到当前 HEAD、重新打补丁并 mint，逐文件核对它等于"HEAD + 两个补丁"，再运行；收据另记下它读过的每个世代清单的哈希（`generation_manifests_measured`），读者可以核对量的是哪一份快照。

结果见 `offline-verification.json`（套件、注错、扫描器输出、会被移动的世代）。**第三次运行全部成立并已封存**；随后 base 合并到 `38732ea6`，D04 与出口套件会加载的五个语义模块随之变化，于是在同步到合并后 HEAD 的树上**再跑了一次、结果完全相同**，现在的收据是那一次的（`sha256:5ac39a6c…`，运行树逐文件核对过等于"HEAD + 注册补丁 + 出口补丁"）：出口扫描器通过，且只多出 `historical_model_egress._Transport.send` 这一个调用方；完整套件 27 例全部通过（850 秒，全程拒绝 DNS、原始 socket 与 SEC）；17 个注错全部被抓——**16 个由对应的用例抓到**（例如去掉 402 停止由 `test_http_402_stops_the_channel` 抓到、适配器只比类名由 `test_the_adapter_hands_bytes_only_to_the_named_type` 抓到，后者先 mint 过，所以抓住它的是用例而不是字节绑定），**1 个只在类夹具里被抓**：去掉控制器的 `issue_47_v1` 分支，各类的 `setUpClass` 在造授权对象时就被控制器拒绝（`Scoped R4 invocation requires a registered R4 revision`）——这正是被破坏的性质，但它不是某条具名用例，如实记为钝的捕获；收尾核对补丁、snapshot 与全部绑定文件回到起点。

收据放进本仓库后，`tests/vnext/test_historical_model_calls.py` 走"有收据"分支：它描述的是打了补丁的树，在未打补丁的仓库里实时路径仍按名拒绝（只有调用模块、`verify.py` 与补丁本身三个绑定文件与仓库相同）。

## 应用补丁的代价——需要决定，不是副作用

三个边界文件被 `issue_28_v2` 至 `issue_28_v14` 共 13 个世代按字节记录（从各世代自己的清单读出，`offline-verification.json` 的 `generations_that_record_the_boundary_files` 逐个列出；第三次运行在同步到当前 HEAD 的树上重新量过，结果相同，读过的 17 份世代清单的哈希记在 `generation_manifests_measured`）。在应用了补丁的树里，这些世代的执行授权不再成立，也就是说**补丁不能原样应用在 #28 仍在用这些世代的同一检出里**。选项：

- (a) 与 #28 的维护者协调，由一个新世代同时携带两边的注册；
- (b) 像 `issue_47_v1` 的注册补丁一样，只在 #47 的运行树里应用，真实调用只从那里发出；
- (c) 暂不应用。

推荐 (b)：它与 #47 今天运行历史 Run 的方式相同，不移动 #28 的任何东西；代价是真实调用必须在所有者本机的运行树里进行（账本根与密钥本来就只在那里）。选哪个、以及是否授予调用，都是所有者的决定。

## 真实调用需求（背景，不是申请）

今天能量的往年 D04 请求：Marriott 2023 年 4 个、2024 年 4 个，Paramount 前身 FY2024 8 个，共 16 个；其余往年期间先要原件（SEC 获取计划 A 类）。最新年份 D04 与 #28 的请求普查逐个相等，那里的问题不是额度，而是 #47 要不要复审 #28 已在审的内容。B13 在范围内分支与 D03 仍未接线（理由见 `../semantic-route-wiring/`），本补丁不为它们开路。

## 给安全审阅者：建议逐处核对的地方与复现步骤

这一节是为独立审阅写的清单，不是结论。每处都写了它要成立的性质、以及如果它不成立会发生什么：

1. **控制器的 `issue_47_v1` 分支**（补丁里 `invocation_control._prepare_successor_invocation_authority_from_requirement`）：授权对象仍只由控制器的私有工厂创建；字段只来自 `historical_model_calls.invocation_authority_fields`，而它在描述字段之前先完整验证 #47 自己的许可。不成立时：一个伪造或过宽的许可能造出可用的授权对象。
2. **适配器按类型交出字节**（补丁里 `ai_adapter._scoped_transport_payload`）：只认 `vnext.historical_model_calls` 模块里的 `HistoricalSemanticRequest`（模块名与类名都比对），交字节前调它的 `transport_payload` 从保存的申报字节重验请求。不成立时：同名的仿冒类型能拿到服务商请求体。
3. **出口扫描器的两个精确集合**（补丁里 `tools/check_provider_egress.py`）：各多一项，都是 `historical_model_egress._Transport.send`，没有别的新调用方。不成立时：第二个传输调用方可以绕过预约与令牌。
4. **唯一的发送点**（新模块 `historical_model_egress._Transport.send`，第 69 行起）：在打开任何连接之前再核预约、所有者令牌与出口标记；实时路径在 socket 前从 GitHub 重取批准评论并要求与本地记录逐字节相同，并从保存字节重验请求；只经控制器那个唯一的服务商 opener。
5. **账本**（仓库里 `historical_model_calls.HistoricalModelLedger`，`claim` 第 565 行、`finish` 第 594 行）：每次认领在 socket 之前写 [1,1,0] 的意图、永不删除；同一请求摘要只能认领一次；累计数每次从账本目录重读；停止集合与 `issue_28_v14` 相同；没有终态的槽位按全额计并停。
6. **许可本身**（`historical_model_calls.model_allowance`，第 207 行）：批准评论须在本仓库议题 47、由批准人发出，正文复述上限、账本根、scope、传输与重试政策；上限第三项（SEC）必须为 0；账本根不与 #28 的根、本检出、#47 的 SEC 账本根重叠或嵌套。

**复现**：在当前 HEAD 的一份副本里依次 `git apply docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch`（`issue_47_v1` 的注册补丁：六个继承文件，只在运行树里应用；已核对它应用到 HEAD 后与验证所用运行树里的六个文件逐字节相同）、`git apply docs/evidence/issue47_history/model-egress/egress-registration.patch`、`python3 tools/vnext_mint_historical_requirement.py`，然后 `python3 docs/evidence/issue47_history/model-egress/verify.py`。收据绑定的文件哈希（`bound_files`）与世代清单哈希（`generation_manifests_measured`）可用来确认复现的是同一棵树。

## 不覆盖

真实网络行为（只有受控连接器）；模型语义正确性；恢复入口；跨机器共用同一账本根（锁只在本机）；B13/D03。
