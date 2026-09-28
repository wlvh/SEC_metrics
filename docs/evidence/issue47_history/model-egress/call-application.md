# #47 模型调用申请（待所有者决定；本文件不是许可）

## 一句话

一份申请、三组互不借用的授予：**D04 16 次**（3 个往年期间的持续经营疑虑披露审阅）、**E01 7 次**（7 个窗口的并购公告内容确认）与 **D02 12 次**（12 份已存年报 Item 8 的诉讼披露审阅，两个方向都覆盖），合计上限 `[35, 35, 0]`，只在所有者本机、用所有者的 API 密钥与账本根执行。本环境没有密钥、没有账本根、没有发出任何调用。

## 两个授予

| 项 | D04 | E01 | D02 |
|---|---|---|---|
| 请求合同 | #28 的 D04 原生解释请求（`d04_native_assessment` / `semantic_review_v4`），由钉定来源分组 | #47 自己的 `E01_CONTENT_CONFIRMATION_V1`（`scripts/vnext/historical_ma_confirmation.py`）：一个窗口一个请求，逐条带候选条目原文与哈希 | #47 自己的 `D02_ITEM_8_LEGAL_REVIEW_V1`（`scripts/vnext/historical_legal_review.py`）：一份申报一个请求，带 Item 8 里 D02 可能取入的每一个块（并入附注、页面装饰、审计报告之外） |
| 位置 | Marriott FY2023、FY2024；Paramount 前身 FY2024 | Ford 2025、Lumen 2025、Macy's FY2025（截至 2026-01-31）、Marriott 2025、Paramount 前身 2024、Pfizer 2025、Southwest 2025 | 12 个已存 D02 位置：Enphase、Ford、Lumen、Pfizer、Southwest 2025；Marriott FY2023–FY2025；Paramount 前身 FY2024 与 FY2025；Macy's、Salesforce（截至 2026-01-31） |
| 请求数 | 4 + 4 + 8 = 16 | 7（每窗口 1 个；共 44 个候选条目） | 12（每份申报 1 个；9,753 个块，其中 318 个必须明确回答） |
| 参考输入 token | 2,571,552（单个 24,858–193,773） | 43,109（单个 1,862–17,601） | 417,576（单个 963–56,802） |
| 计量文件 | `d04-request-measurement.json`（`measure_d04_requests.py`；在当前树上重算，16 个请求摘要逐个相同） | `../e01-content-confirmed/request-measurement.json`（`measure_e01_requests.py`） | `../d02-item-8-review/request-measurement.json`（`measure_d02_requests.py`） |
| 上限 | `[16, 16, 0]` | `[7, 7, 0]` | `[12, 12, 0]` |
| 回答怎么核 | 冻结的 D04 检查器逐条核验来源角色与关系 | 形式核验：每个条目恰答一次、三种决定之一、引文是该条目原文的精确子串 | 形式核验：每个必答块恰答一次、三种决定之一、计入与无法判定必须带该块原文的精确子串、排除不带；额外计入的块必须在请求里、不重复、带引文 |
| 成功后登记 | `register_from_slots`：全部请求成功才登记，按钉定来源作键 | 同一入口：该窗口唯一请求成功即登记，按窗口的确认来源作键 | 同一入口：该申报唯一请求成功即登记，按位置（公司、钉定期间、申报字节）作键 |
| 批准点名的请求 | 16 个请求摘要（分属两个授予） | 7 个请求摘要 | 12 个请求摘要（分属四个授予） |

**请求类型绑定指标**：每组授予只能放行本指标的请求，别的类型按名拒绝（`ISSUE_47_MODEL_REQUEST_TYPE_IS_NOT_THE_METRIC_S`）；只批其中一组时，另外的指标一次也调不出去。

**批准点名到具体请求**：每个授予列出它放行的每个请求的账本摘要，共 35 个。三种合同的摘要都是**实际发送的请求体字节**（模型、消息、解码设置，按发出去的样子）的 SHA-256（`ledger_digest`）；独立复审发现 D04 原先用的是 #28 的语义摘要，漏掉了实际发送的若干字段，批准点名它并不能钉住发出去的内容。摘要由 `planned_request_digests` 算出——钉定来源、它分出的请求与 `ledger_digest`，正是认领时用的同一组函数——并且必须等于三份计量文件记下的摘要，否则提案工具不写出批准正文。落在授予的位置之内但没被点名的请求（例如提示词、合同或来源字节变了，请求就是另一个摘要）在两处被拒：发送前的范围检查（`ISSUE_47_MODEL_REQUEST_DIGEST_NOT_GRANTED:<指标>:<公司>:<期末>:<摘要>`）与账本自己的认领（同名理由，只带摘要），所以绕过其中一处也花不出额度。这样批准的是"这 35 个请求"，不是"这些位置上将来建出的任何请求"。

两个授予共用：传输 deepseek / deepseek-flash / Chat Completions（temperature 0、thinking 关闭、max_tokens 4096、零自动重试）、一个账本根（提案 `/Users/lyuhongwang/.local/state/sec_metrics/issue47-historical-model-v1`，与 #28、#47 SEC 的根都不重叠、不嵌套，由门禁核对）、一个累计上限。仓库不做金额预检或金额上限（D-36）；按上面的 token 量由所有者在账户侧核算。

## 为什么是这些，不是更多

- **193** 是语义路线的请求普查（含 B13、D03 与最新年份），是计量，不是可执行清单。E01 的 7 个请求不在那 193 里：E01 在那次普查时还是条目规则口径。
- **最新年份 D04 的 66 个请求**是 #28 已在自己的账本里对同一份申报发过的；#47 自己再发等于为同一份申报再付一次费。它们进入五年框架的方式——等 #28 的结果被采纳后引用，还是 #47 自己复审——是跨 Issue 的信用决定，不在本申请里。E01 没有这个问题：普通路线仍按已批条目规则计数，从不做内容确认。
- **其余 37 个往年期间**要先有原件（SEC 获取计划 A 类）。请求从原件建，今天量不出；原件到位后按实测另行申请。
- **D02 在本申请里，是因为确定性规则已经三次失败**：关键词代理在 11 份申报上准入 24 个 Item 8 块、错 5 个，三条替代规则各在一份真实申报上失败；四个位置按既有要求撤回。D02 的请求合同是 #47 自己的新合同，两个方向都覆盖（见下），不借 D04 或 E01 的合同。
- **B13 适用分支、D03、C02 不在本申请里**：B13 的请求合同 #28 还在修订；D03 在普通链路里没有原生 Run 路线可移植；C02 已按"构成事实"口径用确定性规则重写并双向核对，不需要模型。

## E01 要预先说清楚的两点

1. **不是每个窗口都能判定**。44 个候选里 36 个的文字引用附件，而附件一份都没保存。多数短条目自己写明了主题（季度销量新闻稿、首席会计官任命、票据发行、要约收购、股东年会日期），可以按自身文字判定；但 Paramount 2024-04-29 那条 8.01 只有 "issued the press release filed herewith as Exhibit 99"，按合同应答 `CANNOT_TELL_FROM_THE_ITEM_TEXT`，该窗口就会按名扣留 `HISTORICAL_E01_ITEM_TEXT_DOES_NOT_SETTLE_IT`。这是正确的拒绝，不是失败，也不是交付。读附件需要取回 EX-99，那不在拟议的 SEC 授予里，是另一个范围决定。
2. **计数只数被确认的条目**，被否定的候选对匹配器不存在；有任一条目无法判定，整个窗口扣留，不把下界报成计数。

## D02 要预先说清楚的几点

1. **两个方向**：请求带的是 Item 8 里 D02 可能取入的**全部**块，不只是关键词准入的那些。带法律程序词汇的块（含关键词的全部准入）必须逐块明确回答；其余任何块都可以作为"额外计入"列出，所以关键词从未放进来的披露也到得了。词汇只决定哪些必须被明确回答，不限定能计入什么。
2. **只改 Item 8**：Item 3 与 Item 3 点名并入的附注照原样；登记之后 Item 8 的关键词准入被审阅计入的块替换。没有登记的位置逐字节不变——今天已接受的 8 个 D02 值不会因为这段代码移动；审阅之后它们会成为新结果、新结果编号，要重新阅读才能接受（已有接受不自动继承）。
3. **无法判定就扣留**：任一必答块答 CANNOT_TELL_FROM_THE_TEXT，整份申报按名扣留 `HISTORICAL_D02_ITEM_8_REVIEW_DOES_NOT_SETTLE_IT`，不发布已判定的部分。
4. **输出预算是量出来的**（同一参考分词器，合成回答）：全部必答块排除时，回答 13–1,574 token（最多的是 Pfizer，65 个必答块）；每把一个必答块改成计入并带最长引文（300 字符或整块），另加 2–80 token。所以在 4,096 的输出上限内，Pfizer 最多能有 45 个必答块被计入，其余 11 份申报即使全部必答块都计入也放得下；已读出的 Item 8 计入块最多的是 Southwest 的 5 个。额外计入的块同样按条计 token，由同一上限约束。
5. **边界是判断题**：定义里"顺路提到诉讼"（估计的不确定性、法律费用政策、应收催收、交易或融资成本、债务契约）的例子来自已读出的误取；模型会在边界上出错，形式检查挡不住读错意思，审阅登记之后要按已批定义两个方向重读原文才计入第三层。

## 调用路径已经做到什么（离线，受控连接器）

- **两次独立安全审阅**（全新上下文的同族子代理，不是人）。第一次（`independent-review-2026-09-27/`）结论 PASS_WITH_FINDINGS，要求授予任何模型许可之前修好 M1–M3：M1、M2、L1–L4、L6、L7 已修，每一条都有用例与注错；M3 中代码能承载的部分已实现，其余是下面的决定 2。修复与 E01、D02 扩展之后的复审（`independent-review-2026-09-27-rereview/`）结论仍是 PASS_WITH_FINDINGS，并写明只凭所有者决定 M3 不能授予真实调用：先修 N1、N2，M1 残余、N3、N4 修掉或由所有者接受。**全部已修**，没有一条留给所有者接受：N1（调用方传 `mode="LIVE"` 就能写出 LIVE 登记）现在要求 LIVE 登记携带回答它的计数调用记录、且记在所有者登记的批准所授予的账本里；N2（换账本根绕过上限）现在许可映射须与许可文件逐字段相同、账本根并入决策哈希；N3/N4 发请求的进程只能加载被授权绑定、编译进本进程私有字节码缓存的检出代码；N5 批准点名实际发送字节的摘要；N6/N7 与 M1 残余各有终态或日志副本。每条一个具名用例、一个注错；N1 另有仓库侧 8 例与 13 个注错（CI 跑得到）。
- **离线验证收据** `offline-verification.json`：2026-09-28 封存，套件 121 例全过（每个测试模块一个进程，共 3 个），跑完封存树逐文件回到起点；78 个注错全部被抓到，77 个由为它写的类里的具名用例抓到、1 个在类夹具处（`THE_CONTROLLER_BRANCH_IS_ABSENT`，已知的钝捕获）、没有一个退回去跑整套；注错分到 3 个副本，每份做成时与最后一个注错之后都与封存树的同一份清单逐文件相同（12264 个条目），封存树本身未变，创建者日志每次都回到起点；与顺序基线逐个比对 78/78 相同（结果、预期类的结果、抓到它的用例；顺序封存在 66/78 时被容器重启打断，前 66 行所在的那棵树已删除；其余 12 个在一个副本里顺序补跑；按提交计算，基线与封存树之间收据绑定的文件只有 `baseline_manifest.json`、`verify.py` 不同，快照里不同的记录文件为 `capacity_native_assessment.py`、`continuous_semantic_calls.py`）；注错阶段墙钟 102 分钟（各注错时间相加 5.1 小时），全程 183 分钟；补丁会移动的世代 13 个（`issue_28_v2`–`issue_28_v14`）；收据绑定 16 个文件，编号 `sha256:7dd330d2…`，对应提交 `8c1fcf18`。批准正文点名这个编号；代码、本世代快照或任何规则文件再变，实时路径都会拒绝它，所有者真实调用前在本机重封（`verify.py --copies N`），批准点名新编号。**快照其后已经移动**：为清掉 base 新增的字面量扫描器报出的日期，四个规则文件的文档字符串改了措辞（行为不变），快照随之移动，所以这张收据现在就会被实时路径拒绝（失败即关闭）；按合同只因快照移动不单独重封。已按这张收据生成的批准正文 `approval-comment-body.json` 是预览：授予、上限 `[35,35,0]` 与 35 个请求摘要不随重封改变（提案脚本每次都用当前代码重算摘要并要求等于三份计量），只有收据编号会变——所有者在本机重封后用 `propose_model_allowance.py` 重新生成再发布，下面的步骤已包含这两步。
- **执行器** `tools/vnext_historical_model.py`（补丁内）：`--metric D04|E01|D02`；导入任何检出代码之前先建本进程私有的字节码缓存；只循环调用既有闸门，遇停止即停、不绕过；某个请求失败但未触发停止时，该位置不登记、其余照跑；已认领的请求不再发。

## 结果怎么用、怎么验收

1. 登记之后按普通历史 Run 建原生 Run、冻结、冷读、公共行；E01 的端到端（记录模式、合成回答）已在运行树实测过（`../e01-content-confirmed/recorded-e01-run-*.json`），公共行与收据都标明"记录测试回答、无真实调用信用"。
2. 这只到"路线交付"层。**内容验收**要独立阅读：D04 两个方向读与持续经营相关的原文；E01 逐个条目读其原文（必要时读附件），核对确认与否定。没有这一步，不计入第三层。
3. **预期要说清楚**：D04 是稀有事件指标，这三个期间很可能答"定义范围内无疑虑披露"，这 16 次调用的作用是按已批方法把"无"证明出来；E01 的 7 个窗口里，已知至少 Paramount 前身 2024 有一笔真实交易（2024-07 的合并协议，另有 2024-11 出售 Viacom 18 股权的完成公告），其余多为融资与经营事项。值不值得，是所有者的判断。

## 已知风险与未解决项

- **M3（批准人身份）**：GitHub 评论只能证明"由 wlvh 账号发出"，执行代理在本环境里也能以该账号发评论。缓解：批准正文点名验证收据 id（代码变了就要新批准；收据绑定本世代的快照，所以任何规则文件变了也要新批准）、逐个点名 35 个请求摘要（请求字节变了就不在批准里）；登记批准时要求评论由数字账号 30534800、类型 `User`、关联 `OWNER` 发出，且**不是经 GitHub App 代发**（`performed_via_github_app` 为空；本环境的代理经 App 发评论），否则以 `ISSUE_47_MODEL_APPROVAL_WAS_POSTED_THROUGH_AN_APP` 拒绝；真实调用只能在所有者本机、用所有者的密钥、由所有者运行命令发出——本环境既无密钥也无账本根，代理即使发出一条"批准"也发不出调用。更强的做法是离线签名（固定公钥、代理拿不到私钥），需要另外实现与密钥管理。
- **L5（既有）**：出口扫描器只按名字匹配调用方；由"唯一发送点在打开连接前再核预约、令牌与标记"兜住，不由扫描器兜住。
- **合同的语义正确性**：D04 用的是 #28 的请求合同，#28 登记了语义未验收，同样的限制适用于这里。E01 的合同是新的，从没被真实模型回答过；它的形式检查挡得住答非所问与编造引文，挡不住"读错了意思"——那是内容验收的事。
- **截断与失败**：输出上限 4096；#28 的 B13 请求曾在 4096 处截断。E01 最大的请求（Lumen，15 个条目）按每条引文上限 600 字符算，回答不超过约 2,700 token。任何失败都是计数的终态、不重抽；修复后要另行申请修后补验，不是重试。

## 需要所有者决定的

1. 是否批准 D04 `[16, 16, 0]`（D04 × {Marriott FY2023–FY2024；Paramount 前身 FY2024}）、E01 `[7, 7, 0]`（E01 × 上表 7 个窗口）与 D02 `[12, 12, 0]`（D02 × 上表 12 个位置），合计 `[35, 35, 0]`；也可以只批其中一组或两组。
2. 批准方式：GitHub 评论（推荐，理由见上：执行只在所有者本机），由所有者本人用 `gh`（本人登录）或网页发布——经 GitHub App 代发的评论会被拒；还是离线签名。
3. 最新年份 D04：等 #28 采纳后引用（推荐，不重复付费），还是 #47 自己复审（+66 次）。
4. 出口补丁只在所有者本机的 #47 运行树应用（推荐；应用在同一检出会让 13 个 #28 世代的执行授权失效）。
5. E01 读附件：只按条目自身文字确认（推荐先这样跑，已知至少一个窗口会按名扣留），还是另行申请取回相关 8-K 的 EX-99 附件。

## 批准后所有者在本机做的事

（以验证时的 HEAD 为准；运行树即带注册补丁的 #47 运行树）

```
git apply docs/evidence/issue47_history/native-run-2026-09-18/0001-register-issue47-v1.patch
git apply docs/evidence/issue47_history/model-egress/egress-registration.patch
python3 tools/vnext_mint_historical_requirement.py
python3 docs/evidence/issue47_history/model-egress/verify.py --copies 3      # 本机重封：收据绑定快照
python3 docs/evidence/issue47_history/model-egress/propose_model_allowance.py  # 按新收据编号重新生成批准正文
gh issue comment 47 --repo wlvh/SEC_metrics \
  --body-file docs/evidence/issue47_history/model-egress/approval-comment-body.json
python3 tools/vnext_historical_model.py register-approval --approval-url <gh 打印的 URL>
DEEPSEEK_API_KEY=... python3 tools/vnext_historical_model.py run --metric D04 \
  --position marriott_international:2023-12-31 --position marriott_international:2024-12-31 \
  --position paramount_skydance_paramount_global:2024-12-31
DEEPSEEK_API_KEY=... python3 tools/vnext_historical_model.py run --metric E01 \
  --position ford_motor_company:2025-12-31 --position lumen_technologies:2025-12-31 \
  --position macys:2026-01-31 --position marriott_international:2025-12-31 \
  --position paramount_skydance_paramount_global:2024-12-31 --position pfizer:2025-12-31 \
  --position southwest_airlines:2025-12-31
DEEPSEEK_API_KEY=... python3 tools/vnext_historical_model.py run --metric D02 \
  --position enphase_energy:2025-12-31 --position ford_motor_company:2025-12-31 \
  --position lumen_technologies:2025-12-31 --position macys:2026-01-31 \
  --position marriott_international:2023-12-31 --position marriott_international:2024-12-31 \
  --position marriott_international:2025-12-31 \
  --position paramount_skydance_paramount_global:2024-12-31 \
  --position paramount_skydance_paramount_global:2025-12-31 --position pfizer:2025-12-31 \
  --position salesforce:2026-01-31 --position southwest_airlines:2025-12-31
```

`gh issue comment` 必须由所有者本人登录的 `gh` 发出（或在网页上粘贴同一正文）；`register-approval` 从 GitHub 读回评论，核对作者、未编辑、未经 App 代发与正文摘要，然后写出许可、批准记录与 `granted-model-ledger.json`——只有记在这份记录所授予账本里的计数调用，其 LIVE 登记才会被 Run 读取。

`run` 遇停止以退出码 3 结束并说明原因；再次运行从账本继续，已认领的请求不会再发。
