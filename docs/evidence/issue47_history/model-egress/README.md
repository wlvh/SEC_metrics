# #47 模型出口：限定差异、离线验证、独立审阅与调用申请

**这是什么**：让 #47 的历史语义路线在所有者另行批准后能发出受限模型调用所需的最小改动（`egress-registration.patch`，7 个文件），在一棵应用了补丁的临时副本里做的离线验证（`verify.py` → `offline-verification.json`），两次独立安全审阅（`independent-review-2026-09-27/`、`independent-review-2026-09-27-rereview/`），以及一份调用申请（`call-application.md`）。补丁现在承载三种请求：D04 的原生解释请求（#28 的合同）、E01 的内容确认请求（#47 自己的合同 `historical_ma_confirmation.py`，所有者 2026-09-27 采用"经内容确认的并购公告"之后新增）与 D02 的 Item 8 审阅请求（#47 自己的合同 `historical_legal_review.py`，关键词代理三次确定性替代都失败之后新增，两个方向都覆盖，见 `../d02-item-8-review/`）。

**不是什么**：不是调用许可，也没有发出任何调用；补丁在仓库里**没有应用**。今天的仓库：控制器不给 `issue_47_v1` 造授权对象，适配器不把字节交给 #47 的请求类型，出口扫描器通过——这三点由 `tests/vnext/test_historical_model_calls.py` 在未打补丁的树上断言。#28 的工作现场、额度、账本和旧评估都不读、不借、不复用。

## 为什么必须改冻结文件

一次模型调用要过三道门，三个文件都被此前的世代按字节记录：

| 门 | 今天的行为 | 补丁做什么 |
|---|---|---|
| `invocation_control._prepare_successor_invocation_authority_from_requirement` | 按 requirement_id 登记世代，其余一律拒绝 | 加 `issue_47_v1` 分支：字段由 `historical_model_calls.invocation_authority_fields` 在验证 #47 自己的许可后描述，**授权对象仍只由控制器的私有工厂创建** |
| `ai_adapter._scoped_transport_payload` | 只把字节交给 #28 的 `SemanticRequest` 或 LiveScopedReaderRequest | 加一种类型：`historical_model_calls.HistoricalSemanticRequest`（模块名与类名都比对），交字节前从保存的申报字节重验请求 |
| `tools/check_provider_egress.py` | 固定传输调用方与出口令牌引用的精确集合 | 把同一个 `historical_model_egress._Transport.send` 加进两个集合 |

另两处是量出来的：控制器只对 `issue_28_v14` 容忍"价格未知"，#47 的计划否则在建计划时就被拒，所以 `_continuous_observations` 也要认 `issue_47_v1`；三个文件都在 `issue_47_v1` 的执行授权里，不重记就在建授权时以 `Successor execution authority bytes differ` 拒绝，所以铸造工具要把三者加进 `RE_RECORDED_FROM_TREE`。

## 补丁的全部内容（7 个文件，`git apply --check` 对当前 HEAD 通过）

| 文件 | 改动 |
|---|---|
| `scripts/vnext/invocation_control.py` | +11 −1：`issue_47_v1` 分支；`_continuous_observations` 认它 |
| `scripts/vnext/ai_adapter.py` | +4：认 `HistoricalSemanticRequest` 并调用它的 `transport_payload` |
| `tools/check_provider_egress.py` | +2：同一个 `_Transport.send` 进两个精确集合 |
| `tools/vnext_mint_historical_requirement.py` | +9：三文件进 `RE_RECORDED_FROM_TREE` |
| 新 `scripts/vnext/historical_model_egress.py` | 363 行：`_Transport.send`（唯一发送点）、`execute_historical_semantic`、按指标选合同的 `_contract`、`register_from_slots` |
| 新 `tools/vnext_historical_model.py` | 174 行：所有者本机用的执行器（`register-approval` / `run --metric D04\|E01\|D02 --position …` / `status`） |
| 新 `tests/vnext/test_historical_model_egress.py` | 1,276 行：离线验证套件，62 例 |

不在补丁里、已在仓库的：`scripts/vnext/historical_model_calls.py`（许可、请求、计划、账本——不碰传输工厂、出口令牌或服务商主机名，所以出口扫描器在仓库里通过）与它在未打补丁状态下的用例。

## 一次调用绑定什么（按检查顺序）

1. **#47 自己的许可**（`config/issue47_historical_model_calls_v1.json`，不存在）：政策与批准正文都按严格 JSON 解析（重复键拒绝）；批准评论须在本仓库议题 47、由批准人发出、**未被编辑**；正文复述上限、账本根、scope（按授予逐项列出，每个授予点名指标、公司、期间与它放行的每个请求的账本摘要）、传输与重试政策，并**点名离线验证收据的编号**——代码变了收据就变，旧批准自动失效。上限第三项（SEC）必须为 0；传输固定；只能点名已接线指标；账本根按真实路径与 #28 的根、本检出、#47 的 SEC 账本根比较，不重叠、不嵌套。实时路径从 GitHub 取回评论并要求与本地记录逐字节相同。
2. **请求**：由钉定期间的来源在准备时一次建成（内容寻址）；每次校验重算来源身份、逐单元重哈希、重新证明所读的每份保存文件，并要求请求是来源分出的请求之一、服务商请求体与 schema 逐字节不变。**请求须被批准点名**：范围检查只接受点名了这个请求摘要的授予，位置落在授予之内而摘要没被点名，按 `ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED` 拒绝。**请求类型绑定指标**：每组授予只能放行本指标的请求（`ISSUE_47_MODEL_REQUEST_TYPE_IS_NOT_THE_METRIC_S`）。
3. **授权对象**：控制器从许可文件造出；文件表＝本世代执行授权＋调用路径两个模块＋许可文件＋保存的批准，每次检查都重算。调用方传入的许可映射必须与授权对象绑定的三个决策哈希相同。
4. **WB-3 计划与执行**：控制器已要求的预约、所有者令牌与出口标记；`_Transport.send` 在打开任何东西之前再核一遍这三样，并要求存在一个已认领的账本槽位；实时路径还在 socket 前从 GitHub 重验批准、从保存字节重验请求。
5. **账本槽位**：在 socket 之前写入 [1,1,0] 的意图，永不删除。账本在认领时再核一次：调用方报的授予必须都点名这个摘要（账本的绑定记着每个授予点名的摘要），所以绕过范围检查的调用方也认领不到槽位。
6. **回答**：D04 由冻结的 D04 检查器逐条核验；E01 与 D02 只按形式核验（E01：每个条目恰答一次、三种决定之一、引文是该条目原文的精确子串；D02：每个必答块恰答一次、计入与无法判定带该块原文的精确子串、排除不带、额外计入必须是请求里的其他块）。**形式不合格是一次计数的失败调用，不是登记**。登记只从槽位自己记录的回答写出、取账本的模式。

## 计数、停止与恢复

- **计数**：每次认领计一次服务商、一次付费调用，失败也计；累计数每次从账本目录重读。
- **账本不能靠删除重置**（第一次审阅 M1）：根目录旁有初始化锚点、根内有绑定文件（绑定到许可）、只追加的认领日志带前驱链、目录锁、拒绝符号链接；删掉一个停止的槽位、删掉整个根、或重封一个去掉停止的终态，都按名拒绝而不是放行。停止由槽位自己的证据重算，不信任自封的终态。
- **不重抽**：同一请求摘要只能认领一次。控制器本身对后继计划零自动重试。
- **停止**（与 `issue_28_v14` 账本相同的集合）：没有终态的槽位、`HTTP_402`、未知结果/超时、用量未知、来源真实性失败、服务商报告的输入令牌数与固定参考分词器不一致、上下文超限。停止后任何认领都按名拒绝。
- **恢复**：补丁**不实现**恢复入口。停止后恢复是所有者的决定，要有新的书面批准，不是重试。

## 第一次独立安全审阅与处理

`independent-review-2026-09-27/`：全新上下文的同族子代理（不是人），对 `92da6f2f` 加补丁的结论是 PASS_WITH_FINDINGS，**在 M1–M3 修好之前不能授予任何模型额度**。逐条处理：

| 发现 | 处理 | 守住它的用例 |
|---|---|---|
| M1 删账本文件可重置上限与停止 | 移植 #28 账本的绑定、锚点、追加日志、前驱链、目录锁、拒绝符号链接；停止从证据重算 | `TheLedgerCannotBeResetByDeletingIt`（5 例） |
| M2 重复键取最后值、编辑过的评论被接受 | 严格 JSON；评论须未编辑 | `TheApprovalIsReadStrictly` 的重复键两例与 `test_an_edited_approval_comment_is_refused` |
| M3 "批准人"只证明"由 wlvh 账号发出" | 代码能承载的部分：批准正文点名验证收据编号，代码变了旧批准失效（`test_a_verification_the_approval_does_not_name_is_refused`）；收据绑定本世代快照，任何规则文件变了也失效；批准逐个点名请求摘要，请求变了就不在批准里（见下一节）；其余是批准方式的决定，写进调用申请 | `OnlyTheRequestsTheApprovalNamesAreClaimed`（4 例） |
| L1 账本根按字符串比较 | 按真实路径双向比较 | `test_a_ledger_root_reached_through_a_symlink_is_refused`、`test_the_sec_ledger_root_respelt_is_still_the_sec_ledger_root` |
| L2 传输无已计数槽位也能到达连接器 | 发送点要求已认领的槽位，并在 WB-3 之外拒绝 | `test_the_transport_refuses_outside_wb3` |
| L3 校验不从申报重推请求文字 | 每次校验重推来源并逐单元比对 | `test_a_source_edited_and_resealed_does_not_rebuild_from_the_filing` |
| L4 令牌计数大幅不一致不停止 | 计数不一致在上下文超限之前判定，二者都是停止 | `test_a_count_disagreement_is_the_stop_named_even_past_the_limit`、`test_a_context_overrun_stops_the_channel` |
| L5 出口扫描器只按名字匹配（既有） | 不由扫描器兜住，由唯一发送点在连接前再核预约、令牌与标记兜住 | `test_the_send_rechecks_the_reservation_and_its_marker` |
| L6 套件会覆盖并删除所在树的许可文件 | 夹具只动自己写的文件，旁边有真实许可就拒绝运行 | `TheFixturesNeverTouchAnAllowanceTheyDidNotWrite`（2 例） |
| L7 `gh` 复核继承完整环境（含服务商密钥） | 只传 `gh` 需要的变量 | SEC 套件的 `TheGithubReaderPassesGhOnlyWhatItNeeds`（验证脚本一并运行） |
| 三处检查没有用例覆盖（发送时重核、实时账本根、账本与许可绑定） | 各补用例 | `test_the_send_rechecks_the_reservation_and_its_marker`、`test_a_live_ledger_outside_the_granted_root_is_refused`、`test_a_ledger_for_another_allowance_is_refused_before_a_slot` |

M1、M2、L1 同样描述 SEC 路径，在所有者花 SEC 额度之前已先在 SEC 侧修好（`../acquisition-wiring/`）。

## 复审前自查补上的两处

修完上表之后，逐项问"批准到底绑定了什么"，查出两处审阅没有点名、但同属 M3 的缺口：

1. **收据不绑定本世代快照**。`verify_model_wiring` 只重算调用路径几个模块的哈希；E01 的回答检查与它继承的 D04 检查器都是规则文件，改弱其中一个再重铸快照，收据照样成立，旧批准照样放行。现在 `CALL_PATH_FILES` 含 `requirements/issue_47_v1/baseline_manifest.json`：快照记录每个规则文件的字节，任何规则文件变了收据就不成立（`test_a_receipt_that_does_not_bind_the_snapshot_is_refused`）。
2. **批准只点名位置，不点名请求**。授予放行"某指标 × 某公司 × 某期间"之内建出的任何请求，于是提示词或合同变了、只要位置不变照样花额度。现在每个授予列出它放行的请求摘要，范围检查与账本认领各自要求被点名（`test_a_request_the_approval_does_not_name_claims_nothing`、`test_the_ledger_refuses_an_unnamed_request_whatever_grants_a_caller_passes`；两层各有只有它能答的用例，靠拒绝消息的格式区分，否则两层并存时破坏任何一层都读成"没抓到"）。提案工具用同一组函数算出摘要，并要求等于三份计量文件记下的摘要（`test_the_planned_digests_are_the_ones_a_claim_computes`）。

## 离线验证

在一棵逐文件核对过等于"HEAD + 注册补丁 + 出口补丁"的运行树里（HEAD 之外的差异恰好是这两个补丁、未提交的模型调用改动与重铸的快照），`python3 docs/evidence/issue47_history/model-egress/verify.py`：

1. 本补丁就是这里应用的那一份（`git apply -R --check`），snapshot 为这些字节 mint 过；
2. 出口扫描器通过，且两份 #47 模块里恰好只有 `_Transport.send` 一处调用传输工厂、一处引用出口令牌；
3. 跑完整套件：全程拒绝 DNS、原始 socket 与 SEC；唯一的服务商连接器换成受控的一个；
4. 逐个注错：每个注错点名写来抓它的用例类，先只跑那个类（遇失败即停），失败就记为被它抓到；只有它没抓到时才按固定顺序跑整套（同样遇失败即停），在别处被抓到就如实记为别处。最初几版对每个注错都跑整套，按 47 个注错、62 例算要大半天，而答不出更多：抓到就是抓到，点名的预期类让读者能核对抓到它的是不是为它写的那条用例（无论哪种做法，`first_caught_by` 都不是所有能抓到它的用例的全集）。注错文本必须能编译；落在 snapshot 按字节记录的文件上的注错先 mint 再跑，跑完恢复并逐字节核对；只在类夹具里失败的如实记为钝的捕获；
5. 从各世代自己的清单读出哪些世代按字节记录了三个边界文件；
6. 树回到起点。

全部成立才封存 `offline-verification.json`。{VERIFY_RESULT}

历次运行的教训保留在这里，因为它们决定了上面每一步为什么存在：第一次运行把"返回码非零"当成抓到（一个注错让文件本身 `IndentationError`、边界文件注错被字节绑定"抓到"、门禁注错的目标串出现两次），在封存前停下；第二次运行所在的运行树落后于仓库，收据会绑定旧的铸造工具，也在封存前停下。

## 独立复审

{REREVIEW_RESULT}

## 应用补丁的代价——需要决定，不是副作用

三个边界文件被 `issue_28_v2` 至 `issue_28_v14` 共 13 个世代按字节记录（`offline-verification.json` 的 `generations_that_record_the_boundary_files` 逐个列出，读过的世代清单哈希记在 `generation_manifests_measured`）。在应用了补丁的树里，这些世代的执行授权不再成立，所以**补丁不能原样应用在 #28 仍在用这些世代的同一检出里**。推荐只在 #47 的运行树里应用（与 #47 今天运行历史 Run 的方式相同）；真实调用只在所有者本机的运行树里进行（账本根与密钥本来就只在那里）。

## 调用申请

`call-application.md`：D04 16 次（3 个往年期间）、E01 7 次（7 个有候选的窗口）与 D02 12 次（12 份已存年报的 Item 8），合计上限 `[35, 35, 0]`，三组授予互不借用；请求逐个计量（`d04-request-measurement.json`；`../e01-content-confirmed/request-measurement.json`；`../d02-item-8-review/request-measurement.json`，含输出 token 的实测）。需要所有者决定的事写在申请末尾。

## 给安全审阅者：建议逐处核对的地方与复现步骤

1. **控制器的 `issue_47_v1` 分支**（补丁里 `invocation_control.py`）：授权对象仍只由控制器的私有工厂创建；字段只来自 `historical_model_calls.invocation_authority_fields`，它先完整验证 #47 自己的许可。
2. **适配器按类型交出字节**（补丁里 `ai_adapter._scoped_transport_payload`）：只认 `vnext.historical_model_calls.HistoricalSemanticRequest`，交字节前从保存字节重验请求。
3. **出口扫描器的两个精确集合**（补丁里 `tools/check_provider_egress.py`）：各多一项，都是 `historical_model_egress._Transport.send`。
4. **唯一的发送点**（`historical_model_egress._Transport.send`）：连接前再核预约、所有者令牌、出口标记与已认领槽位；实时路径在 socket 前从 GitHub 重取批准、从保存字节重验请求。
5. **按指标的合同**（`historical_model_egress._contract`）：D04 用冻结检查器、E01 用 `historical_ma_confirmation`、D02 用 `historical_legal_review`；请求类型绑定指标；登记分支按指标（`register_from_slots`）。
6. **账本**（`historical_model_calls.HistoricalModelLedger`）：认领在 socket 之前写意图、永不删除；不能靠删除重置；停止从证据重算。
7. **许可本身**（`historical_model_calls.model_allowance`）：严格 JSON、未编辑的评论、按授予的 scope、收据编号、真实路径比较的账本根。

**复现**：在当前 HEAD 的一份副本里依次 `git apply docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch`、`git apply docs/evidence/issue47_history/model-egress/egress-registration.patch`、`python3 tools/vnext_mint_historical_requirement.py`，然后 `python3 docs/evidence/issue47_history/model-egress/verify.py`。收据的 `bound_files` 与 `generation_manifests_measured` 可用来确认复现的是同一棵树。

## 不覆盖

真实网络行为（只有受控连接器）；模型语义正确性（E01、D02 的形式检查挡得住答非所问与编造引文，挡不住读错意思，那是内容验收的事）；恢复入口；跨机器共用同一账本根（锁只在本机）；B13/D03；C02 的模型辅助判断——C02 已按"构成事实"口径用确定性规则重写，不需要模型。补丁通过审阅、某个指标有可信的请求合同、某个具体请求获得调用许可是三件分开的事；语义路线请求普查的 193 个是计量，不是可执行清单。
