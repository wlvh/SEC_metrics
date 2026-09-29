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
| 新 `scripts/vnext/historical_model_egress.py` | 443 行：`_Transport.send`（唯一发送点；发送前从 GitHub 复核批准，失败是具名的停止终态）、`execute_historical_semantic`、按指标选合同的 `_contract`、`register_from_slots`（登记携带回答它的计数调用记录） |
| 新 `tools/vnext_historical_model.py` | 191 行：执行器（`register-approval` / `start` / `run --metric D04\|E01\|D02 --position …` / `status`；2026-09-29 起在执行者虚拟机里用）；导入任何检出代码之前先建本进程私有的字节码缓存 |
| 新 `tests/vnext/test_historical_model_egress.py` | 1,999 行：离线验证套件，90 例（另有 SEC 套件的读取类与仓库里账本、许可、批准登记、开跑与导出的单元类一起跑；各类例数见收据） |

不在补丁里、已在仓库的：`scripts/vnext/historical_model_calls.py`（许可、请求、计划、账本——不碰传输工厂、出口令牌或服务商主机名，所以出口扫描器在仓库里通过）、`scripts/vnext/historical_counted_calls.py`（LIVE 登记必须携带的计数调用记录与所有者登记的批准所授予的账本；规则文件，每个消费登记的 Run 都执行它）与它们在未打补丁状态下的用例。

## 一次调用绑定什么（按检查顺序）

1. **#47 自己的许可**（`config/issue47_historical_model_calls_v1.json`，不存在）：政策与批准正文都按严格 JSON 解析（重复键拒绝）；批准评论须在本仓库议题 47、由批准人发出、**未被编辑**；正文复述上限、账本根、scope（按授予逐项列出，每个授予点名指标、公司、期间与它放行的每个请求的账本摘要）、传输与重试政策，并**点名离线验证收据的编号**——代码变了收据就变，旧批准自动失效。上限第三项（SEC）必须为 0；传输固定；只能点名已接线指标；账本根按真实路径与 #28 的根、本检出、#47 的 SEC 账本根比较，不重叠、不嵌套。实时路径从 GitHub 取回评论并要求与本地记录逐字节相同。
2. **请求**：由钉定期间的来源在准备时一次建成（内容寻址），摘要是**实际发送的请求体字节**的 SHA-256（复审 N5）；每次校验重算来源身份、逐单元重哈希、重新证明所读的每份保存文件，并要求请求是来源分出的请求之一、服务商请求体与 schema 逐字节不变。**请求须被批准点名**：范围检查只接受点名了这个请求摘要的授予，位置落在授予之内而摘要没被点名，按 `ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED` 拒绝。**请求类型绑定指标**：每组授予只能放行本指标的请求（`ISSUE_47_MODEL_REQUEST_TYPE_IS_NOT_THE_METRIC_S`）。
3. **授权对象**：控制器从许可文件造出；文件表＝本世代执行授权＋调用路径模块＋许可文件＋保存的批准，每次检查都重算。调用方传入的许可映射必须与许可文件逐字段相同；账本根与验证收据编号并入控制器绑定的决策哈希；实时账本在加锁（写任何东西之前）与每次认领时从许可文件重推绑定、要求就在文件指定的根上（复审 N2）。
4. **WB-3 计划与执行**：控制器已要求的预约、所有者令牌与出口标记；`_Transport.send` 在打开任何东西之前再核一遍这些（进程、令牌、执行、恰好一个标记、标记的计划与传输种类各自单独核），并要求存在一个已认领的账本槽位；实时路径还在 socket 前从 GitHub 重验批准、从保存字节重验请求。适配器的载荷钩子只在**本线程正在进行的计数发送**期间交出字节，谁直接构造传输都拿不到（复审 L2）。发请求的进程加载的每个检出模块都必须是授权绑定的文件，并编译进本进程新建的私有字节码缓存，从不读检出自己的 `__pycache__`（复审 N3、N4）。
5. **账本槽位**：在 socket 之前写入 [1,1,0] 的意图，永不删除。账本在认领时再核一次：调用方报的授予必须都点名这个摘要（账本的绑定记着每个授予点名的摘要），所以绕过范围检查的调用方也认领不到槽位。
6. **回答**：D04 由冻结的 D04 检查器逐条核验；E01 与 D02 只按形式核验（E01：每个条目恰答一次、三种决定之一、引文是该条目原文的精确子串；D02：每个必答块恰答一次、计入与无法判定带该块原文的精确子串、排除不带、额外计入必须是请求里的其他块）。**形式不合格是一次计数的失败调用，不是登记**；回答或响应包装嵌套过深同样是有终态的失败（复审 N6）。登记只从槽位自己记录的回答写出、取账本的模式。**LIVE 登记必须携带回答它的计数调用记录**（意图、终态、线路日志互相点名，终态按字节哈希过它们），消费它的 Run 还要求这些调用记在所有者登记过的批准所授予的账本里——那份记录只由 `register-approval` 从 GitHub 读回批准后写，测试从不写（复审 N1）。

## 计数、停止与恢复

- **计数**：每次认领计一次服务商、一次付费调用，失败也计；累计数每次从账本目录重读。
- **账本不能靠删除重置**（第一次审阅 M1；复审发现同时删掉 `calls/` 与认领日志仍能重置，现在每次认领先追加到**根目录旁边**的日志副本、根内日志必须与它逐行相同）：根目录旁有初始化锚点、根内有绑定文件（绑定到许可）、只追加的认领日志带前驱链、目录锁、拒绝符号链接；删掉一个停止的槽位、删掉整个根、或重封一个去掉停止的终态，都按名拒绝而不是放行。停止由槽位自己的证据重算，不信任自封的终态。
- **不重抽**：同一请求摘要只能认领一次。控制器本身对后继计划零自动重试。
- **停止**（`issue_28_v14` 账本的集合，另加一项）：没有终态的槽位、`HTTP_402`、未知结果/超时、用量未知、来源真实性失败、服务商报告的输入令牌数与固定参考分词器不一致、上下文超限；以及计费之后传输自述与发送字节不符（`TRANSPORT_OBSERVATION_CHANGED`，响应照样保留，复审 N7）。停止后任何认领都按名拒绝。
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
3. 跑完整套件：每个测试模块一个进程（调用路径检查的正是发请求的那个进程，别的套件导入的代码不该出现在里面），全程拒绝 DNS、原始 socket 与 SEC，唯一的服务商连接器换成受控的一个；**套件不全绿就停下、不跑注错也不封存**——一个已经失败的套件“抓到”注错不说明任何事；套件跑完，封存树必须逐文件回到套件之前（副本从这时的树做成，套件留下的东西会被带进每一份）；每个测试进程有自己的临时目录、随进程删掉；
4. 逐个注错：每个注错点名写来抓它的用例类，先只跑那个类（遇失败即停），失败就记为被它抓到；只有它没抓到时才按固定顺序跑整套（同样遇失败即停），在别处被抓到就如实记为别处。最初几版对每个注错都跑整套，按 47 个注错、62 例算要大半天，而答不出更多：抓到就是抓到，点名的预期类让读者能核对抓到它的是不是为它写的那条用例（无论哪种做法，`first_caught_by` 都不是所有能抓到它的用例的全集）。注错编辑必须恰好命中一次、编辑后必须能编译，两样都在跑任何东西之前检查；落在 snapshot 按字节记录的文件上的注错先 mint 再跑，跑完恢复并逐字节核对；只在类夹具里失败的如实记为钝的捕获；注错在封存树的 N 个副本里跑（`--copies N`，默认 3），不在封存树本身里跑：副本在套件之后做成，开始时与最后一个注错之后都要与封存树的同一份清单（每个文件的路径、大小、SHA-256，含 `.git`、不含 `__pycache__`）相同，封存树也不能变；每个注错在空闲的副本里、在自己的进程里跑一次，判定代码与顺序跑时相同，收据记下它在哪个副本、跑了多久；
5. 从各世代自己的清单读出哪些世代按字节记录了三个边界文件；
6. 树回到起点；
7. 创建者日志（`.git/issue47-historical-assessments`）在套件之后、每个注错之后都逐文件回到起点——用例在注错下会写出平时不写的登记，这里是它们留下来时按名停下的地方。

全部成立才封存 `offline-verification.json`。**封存结果**（2026-09-28，按合同变更并行执行；这是虚拟机改动之前的那一次，那之后收据绑定的文件变了，要重封，见下一节）：套件 121 例全过（每个测试模块一个进程，共 3 个），跑完封存树逐文件回到起点；78 个注错全部被抓到，77 个由为它写的类里的具名用例抓到、1 个在类夹具处（`THE_CONTROLLER_BRANCH_IS_ABSENT`，已知的钝捕获）、没有一个退回去跑整套；注错分到 3 个副本，每份做成时与最后一个注错之后都与封存树的同一份清单逐文件相同（12264 个条目），封存树本身未变，创建者日志每次都回到起点；与顺序基线逐个比对 78/78 相同（结果、预期类的结果、抓到它的用例；顺序封存在 66/78 时被容器重启打断，前 66 行所在的那棵树已删除；其余 12 个在一个副本里顺序补跑；按提交计算，基线与封存树之间收据绑定的文件只有 `baseline_manifest.json`、`verify.py` 不同，快照里不同的记录文件为 `capacity_native_assessment.py`、`continuous_semantic_calls.py`）；注错阶段墙钟 102 分钟（各注错时间相加 5.1 小时），全程 183 分钟；补丁会移动的世代 13 个（`issue_28_v2`–`issue_28_v14`）；收据绑定 16 个文件，编号 `sha256:7dd330d2…`，对应提交 `8c1fcf18`。收据绑定本世代快照：base 之后若移动快照，实时路径会拒绝它（失败即关闭），真实调用前重封（2026-09-29 起由执行者在虚拟机里做）。快照其后已经移动：为清掉 base 新增的字面量扫描器报出的日期，四个规则文件的文档字符串改了措辞（行为不变），所以这张收据现在就会被实时路径拒绝；按合同只因快照移动不单独重封。按它生成的批准正文 `approval-comment-body.json` （上限 `[35,35,0]`，9 个授予点名 35 个请求摘要）是预览：重封后用 `propose_model_allowance.py` 重新生成，调用申请里的步骤已包含这两步。

历次运行的教训保留在这里，因为它们决定了上面每一步为什么存在：第一次运行把"返回码非零"当成抓到（一个注错让文件本身 `IndentationError`、边界文件注错被字节绑定"抓到"、门禁注错的目标串出现两次），在封存前停下；第二次运行所在的运行树落后于仓库，收据会绑定旧的铸造工具，也在封存前停下。复审修复之后的第一次封存运行（2026-09-28）套件全过，但在第六个注错 `THE_ANCHOR_IS_INSIDE_THE_ROOT` 处回退到整套：M1 残余的修法（根目录旁的日志副本）让删掉整个根目录单凭副本就被拒绝，锚点挪进根目录因此不再被它的类看见。按顺序跑下去要约八小时才会以没抓到结束，所以停下，改在三份验证树副本里并行预检（`preflight.py`，只跑各注错的预期类，结果 `preflight-2026-09-28.json`）：78 个里 76 个被预期类抓到、1 个在类夹具处被抓（已知的钝捕获）、只有这一个没被抓到；补了"删根与副本、只留根外锚点仍须拒绝"的用例、重生成补丁之后才开始封存运行。预检不封存任何东西，收据仍是 `verify.py` 在一棵树里把每个注错再跑一遍的结果。

那次封存运行又停在套件闸：`test_a_checked_answer_registers_and_the_route_counts_it` 以 `E01_LIVE_CONFIRMATION_WITHOUT_COUNTED_CALLS` 出错。原因是预检留下的状态，不是代码：三个预检副本里有一个就是验证树本身，注错 `A_LIVE_CONFIRMATION_NEEDS_NO_CALLS` 去掉“LIVE 须带计数调用”那一行后，用例真的写出一条 LIVE 登记、在断言处失败（这就是被抓到），而它后面没有清理；创建者日志在 `.git/issue47-historical-assessments`，夹具的清理与本验证的“树回到起点”原先都不看那里。一小时后，封存运行的套件读到了它。预检里凡是由读日志的用例抓到的结果也因此不可信（例如 `A_COUNTED_CALL_NEED_NOT_BE_LIVE` 当时是被残留撞上，修好后由为它写的用例抓到）。现在：每个用例结束时（失败也一样）把日志放回原样，改动了不是自己写的登记就判失败，被信号打断的用例由退出钩子补做；日志里已有该位置的 LIVE 登记时类夹具按名拒绝启动；本验证与 `preflight.py` 在套件之后、每个注错之后核对日志逐文件回到起点（第 7 步），收据记下起点时的日志。读写日志的四个类的 27 个注错在三个干净副本里重新预检：27 个全部被抓到、日志每次都回到起点；其中 12 个换了抓住它的用例——第一次都是被读日志的用例撞上（E01/D02 的“批次默认 LIVE 读不到测试登记”与 D04 的“LIVE 日志为空”），这次由为它写的用例抓到（`preflight-2026-09-28.json` 的 `journal_rerun`）。这些读日志的用例在各自类里最先跑，在干净副本里同一注错下通过，所以第一次的失败来自日志里已有的登记，不来自注错。三个副本都受了影响：验证树本身在 04:56:07 之后（就是找到的那条），另两个副本在第一次预检后已删除，里面有什么、怎么来的已无法确定。没有一个注错变成抓不到；第一次预检的计数作为“抓到了几个”仍成立，作为“由哪条用例抓到”不成立。

**2026-09-28 合同变更**（[Issue #47 评论 5870869079](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-5870869079)，执行者转录，`../owner-decisions-2026-09-28/decisions.json`）：本验证可以按逐文件相同的清单分到多个副本并行执行；先剖析 LIVE 类再缓存纯计算；只在收据绑定文件中本世代快照以外的文件变化、或审阅者/所有者要求时重封。判定规则、回到起点的核对与零调用不变；实时路径照旧拒绝过期收据，真实调用前重封（2026-09-29 起由执行者在虚拟机里做）。

**对照基准**：顺序封存的前 66 行（`sequential-interrupted-2026-09-28.log`）加上在一个副本里顺序补跑的其余 12 行（`complete_sequential_baseline.py` → `sequential-completion-2026-09-28.json`）。`compare_with_sequential.py <封存提交>` 逐注错比对结果、预期类的结果、是否退回整套与抓到它的用例；三次运行不在同一棵树里（并行版的 `verify.py` 本身是收据绑定的文件，base 合并又移动了快照），所以它还用仓库历史算出基线各部分所在提交与封存提交之间差了什么：收据绑定的文件只许 `verify.py` 与快照不同，差出这两个之外即拒绝（那时比对的就是代码改动而不是并行化）；快照里差的已记录文件逐个列出，快照其余部分不许不同；收据本身必须是在点名的提交上封存的——补丁不拥有的每个绑定文件都要等于该提交里的字节。补跑记下的 `tree_unchanged: false` 不是它改了树：它与第一次并行封存在同一分钟、在同一棵验证树里启动，最后一次读那棵树时，封存的套件夹具正在里面；补跑只读那棵树（一次清单、一次复制），注错跑在它自己的副本里，副本在做成时与最后一个注错之后都等于它所复制的树。前 66 行所在的那棵树已删除，它建自哪个提交是记录，脚本无法再推导。**教训**：两个都检查“树没变”的程序，不要同时指向同一棵树；以及——下午这段原本写“补跑副本的清单摘要必须等于封存收据的”，那只在封存树从未改动时成立，第一次并行封存在最后一步崩溃、`verify.py` 修好重封之后，这条检查必然失败，所以改成按提交计算差异。

## 独立复审

`independent-review-2026-09-27-rereview/`：修复与 E01/D02 扩展之后，另一个全新上下文的同族子代理复审，结论仍是 PASS_WITH_FINDINGS，并写明**只凭所有者决定 M3 不能授予真实调用**：先修 N1、N2，M1 残余、N3、N4 修掉或由所有者接受，再重跑本验证重新封存。每一条的复现、修法、用例与注错逐条列在该目录的 `README.md`；修复后的验证自身又查出四处（验证脚本让非运行器进程发请求、测试进程的导入顺序与运行器不同、两个位置之间的已加载代码、L2 之后两个没跟上的旧用例），也记在那里。只能如实说明或交给所有者的四条限制（M3 其余部分、L5、能写运行树或账本父目录的人、#28 的 `CallLedger` 形状相同）同样在那里。

## 2026-09-29：改在虚拟机执行之后的差异，与第三次限定审阅

所有者决定模型调用也在执行者的云端虚拟机里执行（Issue #47 评论 5882788074，执行者转录）。收据 `8c1fcf18` 之后，调用路径为此变了四样，都是为了让账本和批准在一台会被回收的机器上仍然站得住：

- **开跑标记**（`scripts/vnext/historical_ledger_start.py`，SEC 与模型两本账共用，各用自己的记录类型、拒绝前缀与导出目录）：`start` 在账本根旁写一份本地开跑记录（含一个不公开的随机数），并给出执行者要发到 Issue #47 的标记评论；实时路径在读许可、核收据之后、建账本之前要求：这份批准最早的标记未被编辑、由仓库所有者账号在本 Issue 发出、且等于本机记录。
- **读取器**：虚拟机里没有 `gh`，实时路径与发送前的批准复核都用 `live_github_reader()`（只能读本仓库 Issue #47 的单条评论与评论页）。
- **换行**：网页粘贴的批准正文带 CRLF；门禁与登记只原谅换行与末尾空白，其余任何差异仍是另一份批准。
- **导出与恢复**（`scripts/vnext/historical_model_export.py`，入口 `tools/vnext_historical_model_export.py`，在自己的进程里跑，从不在发请求的进程里加载）：每次运行后把账本导出到分支上本批准自己的目录，恢复出来的是记录，再从它花额度是所有者的决定。

**第三次独立审阅**（`independent-review-2026-09-29-vm/`，全新上下文的同族子代理，不是人；只审这段差异）结论 PASS_WITH_FINDINGS。最重要的一条 **F1 不能在代码里关闭**：在虚拟机里，读回 GitHub 评论用哪个程序、经哪个代理、信任哪个证书都由执行者决定，审阅者用三行的假 `gh` 让门禁接受了一条从未发布的评论；执行者还持有密钥，可以不经这套代码直接调用。所以这些门禁约束的是**执行者的代码路径，不是执行者本人**：它们防事故、让所有者的决定事后可核对；约束执行者的是代码之外的控制——为这次运行单独建的、在服务商侧设了额度上限并在跑完后吊销的密钥，以及用服务商自己的用量记录核对分支上的导出。调用申请、提案工具的 `execution` 说明与 09-29 决定记录已按此更正（后者追加 `corrections`，原文保留）。

其余各条的复现、修法与守它的用例、注错：

| 审阅项 | 审阅复现的问题 | 修法 | 用例 / 注错 |
|---|---|---|---|
| F2 | 标记带着整份开跑记录（含随机数），容器丢失后把标记抄回空根旁就能开跑，同一请求发了两次；实时路径从不看分支上的导出 | 标记只带本地记录的公开视图与它的摘要，随机数只在本地；实时路径在开跑检查之后，拒绝比分支上本批准导出落后的账本（本地认领日志必须以导出绑定的字节开头） | `test_the_marker_does_not_carry_what_the_local_record_needs`、`test_a_ledger_behind_its_export_is_refused`、补丁侧 `test_a_ledger_behind_the_branch_s_export_sends_nothing`；`THE_MARKER_CARRIES_THE_WHOLE_RECORD`、`A_LEDGER_MAY_BE_BEHIND_ITS_EXPORT` |
| F3 | 在账本已丢的主机上导出，会在授予的根上新建一个空账本，并用 `[0,0,0]` 覆盖已花费的导出 | 导出先确认账本在这里开过（绑定、锚点、日志副本都在，在取锁之前查，因为取锁本身会初始化）；只覆盖同一批准、且新日志以旧日志开头的导出 | `test_an_export_of_a_ledger_never_started_here_is_refused`、`test_an_export_only_moves_forward`；`AN_EXPORT_BEGINS_A_LEDGER`、`AN_EXPORT_MAY_GO_BACKWARDS` |
| F4 | 在仍有开跑记录的主机上恢复，恢复出来的账本立刻可花；导出在核验之后又被重读一次 | 有开跑记录就拒绝恢复；写入的是核验过的那份成员，不再重读 | 补丁侧 `test_an_export_blocks_a_later_start_and_restores_only_as_a_record`；`A_RESTORE_MAY_LAND_BESIDE_A_START` |
| F5 | 重新批准（重封之后就会发生）可以把同样 35 个请求从零再发一遍；所有批准共用一个导出路径 | 每个批准导出到自己的目录（批准摘要前 16 位）；另一批准的导出已认领的请求出现在新授予里，开跑拒绝，读不出的导出索引同样拒绝；提案工具也不写出这样的批准 | `test_a_re_approval_cannot_start_over_requests_another_approval_claimed`、`test_each_approval_exports_into_its_own_directory`；`A_RE_APPROVAL_REDRAWS_CLAIMED_REQUESTS`、`ALL_APPROVALS_SHARE_ONE_EXPORT` |
| F6 | 发送前从 GitHub 复核批准失败时，槽位被计数但没有终态，通道记为 UNKNOWN 停止 | 复核失败是一个具名、计数、停止的终态 `APPROVAL_NOT_CONFIRMED_ON_GITHUB`，不打开 socket | 补丁侧复核用例拆成“被改动 / 读不到”两个子用例；`A_FAILED_RECHECK_LEAVES_THE_SLOT_OPEN`，`NO_GITHUB_RECHECK_BEFORE_THE_SOCKET` 改为对准复核调用本身 |
| F7 | 导出在释放锁之后才读账本文件 | 成员与核验它们的快照在同一把锁里读 | 由 F3 的用例覆盖 |
| F8 | 恢复唯一的路径穿越检查在 `historical_source_export.py`，而模型收据不绑定它 | 收据绑定该文件（`BOUND` 16 → 20，另三个是开跑模块、导出模块与导出工具） | — |
| F9 | 标记不核对它是不是发在本 Issue、是不是所有者的数字账号；读取器跟随重定向 | 标记与批准一样核对 `issue_url`、数字账号与账号类型（不查应用标记——标记本来就是执行者经应用发的）；读取器拒绝被重定向的读取 | `test_a_marker_not_from_this_issue_or_account_does_not_count`、`test_a_redirected_read_is_refused`；`A_MARKER_FROM_ANYWHERE_COUNTS`、`A_REDIRECTED_READ_IS_TRUSTED` |
| F10 | 代理对所有主机重新终止 TLS：密钥、提示、回答与 GitHub 读回都经过它；每个进程都能以所有者账号操作 GitHub | 写进调用申请与批准正文的 `execution`；开跑记录记下读取器、代理与证书包摘要 | — |
| F11 | 一个注错只改了拒绝的名字；F2–F4 没有注错；一处断言只查字面常量；模型侧换行用例只有单行正文 | `A_LOST_START_IS_NOT_NOTICED` 改为 `A_STARTED_APPROVAL_STARTS_AGAIN_ON_A_NEW_HOST`，对准“碰到本批准的标记就不再开跑”；上面各条补了注错；换行用例改为多行正文（含内部 CRLF 与单独的 CR）；那条用例改名为它实际验证的事 | — |

**仍然防不住的**：第一次导出推到分支之前，容器丢失而标记评论又被删除（执行者以所有者账号行事，删得掉），就没有东西能发现——这一段只靠外部控制。

**注错**：`verify.py` 由 78 个增到 98 个（开跑、读取器与导出 10 个，审阅修复 10 个），另 3 个因代码改动重新对准；绑定文件 16 → 20。仓库侧：`model_start_injections.py` 16 个、`acquisition-wiring/vm_start_injections.py` 26 个，全部由点名的用例抓到。这一轮的教训之一：审阅修复让导出模块里 `state = ledger.snapshot()` 出现了两次，原来对准它的注错命中两处，脚本在运行任何东西之前按名停下（`INJECTION_DID_NOT_APPLY … 2`）；改为连同上一行注释一起对准核验函数里的那一处。

## 应用补丁的代价——需要决定，不是副作用

三个边界文件被 `issue_28_v2` 至 `issue_28_v14` 共 13 个世代按字节记录（`offline-verification.json` 的 `generations_that_record_the_boundary_files` 逐个列出，读过的世代清单哈希记在 `generation_manifests_measured`）。在应用了补丁的树里，这些世代的执行授权不再成立，所以**补丁不能原样应用在 #28 仍在用这些世代的同一检出里**。推荐只在 #47 的运行树里应用（与 #47 今天运行历史 Run 的方式相同）；按 2026-09-29 的决定，真实调用在执行者虚拟机里的 #47 运行树进行。

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

**复现**：在当前 HEAD 的一份副本里依次 `git apply docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch`、`git apply docs/evidence/issue47_history/model-egress/egress-registration.patch`、`python3 tools/vnext_mint_historical_requirement.py`，然后 `python3 docs/evidence/issue47_history/model-egress/verify.py --copies 3`（副本放在运行树旁边，每份与运行树一样大，约 3.3 GB；`--copies 1` 就是顺序跑）。收据的 `bound_files` 与 `generation_manifests_measured` 可用来确认复现的是同一棵树。

## 不覆盖

真实网络行为（只有受控连接器）；模型语义正确性（E01、D02 的形式检查挡得住答非所问与编造引文，挡不住读错意思，那是内容验收的事）；恢复入口；跨机器共用同一账本根（锁只在本机）；B13/D03；C02 的模型辅助判断——C02 已按"构成事实"口径用确定性规则重写，不需要模型。补丁通过审阅、某个指标有可信的请求合同、某个具体请求获得调用许可是三件分开的事；语义路线请求普查的 193 个是计量，不是可执行清单。
