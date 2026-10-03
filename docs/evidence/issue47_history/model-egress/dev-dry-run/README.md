# E01 / D02 / D04 请求的开发演练（付费调用之前）

按 #28 §5.8（#47 正文 v1.2 第 3.1 节采用）：付费调用之前，先让一个只看得到模型输入包的独立上下文回答真实请求，回答经合同自己的检查，再与从原件做的开发参照比对。开发失败先解决，再进入付费验收。

**这些回答是开发材料，不是 DeepSeek 的回答，不是 LIVE，不占调用额度，也不给任何结果验收信用。** 零 SEC / provider / paid 调用。

## 输入：就是付费调用会发出的字节

- `dump_requests.py` 在封存运行包上（演练时是提交 `7cf3992e` 加注册补丁与出口补丁、重铸快照；改发 D04 编号变体后的运行包 `5640c367` 上重跑，19 个输入文件逐字节相同）用路线自己的构造函数重建 E01 的 7 个、D02 的 12 个请求，用固定传输政策算出发给服务商的请求体，再从请求体字节里读回消息。每个请求的账本摘要都必须等于计量文件记下的摘要（`e01-content-confirmed/request-measurement.json`、`d02-item-8-review/request-measurement.json`），不等就停下。`requests-index.json` 列出 19 个请求的摘要；它们就是批准正文要点名的 19 个摘要。
- 每个开发上下文只读一个文件：系统提示加用户消息（`render_input`；用户消息按键排序缩进显示，每个键和字符串值都是发出的原样）。`inputs-index.json` 记下这 19 个文件的摘要，在运行包上重跑 `dump_requests.py` 可逐字节重现。

## 开发上下文怎么答的

每个请求一个全新上下文的同族子代理（不是人，不是 DeepSeek），提示只有这几条：

> You are standing in for a language-model API in a test. A separate program will check your answer automatically, so follow the format exactly. Read the whole file `<该请求的输入文件>` (read it in consecutive chunks until the end). It contains a SYSTEM PROMPT and a USER MESSAGE exactly as the model would receive them. Do what the system prompt asks, using only what is in that file. Rules: read only that one file — no other files, no git, no shell, no web; produce exactly the response the system prompt asks for, one JSON object and nothing else, quotes copied character for character; write it to `<回答文件>`; then reply only DONE.

回答原样在 `answers/`。

## 合同检查（`check_answers.py`，结果在 `check.json`）

用合同自己的 `validate_answer` 和计数检查每份回答，输出长度用钉定的参考分词器计：

- **19/19 通过合同检查**（格式、每块恰好一条决定、引文是该块原文的精确子串且长度合规、E01 的计数）。
- 输出 13–1,743 个 token，都在 4,096 的上限之内（D02 最长是 Pfizer 的 1,743；E01 最长是 Lumen 的 1,024）。

## 与开发参照比对

**E01**（`e01-reference.json`，44 个条目；8.01 用 09-26 读过的逐份判断，其余条目 10-03 按请求里的定义读原文）：44/44 一致，7 个窗口的计数全部等于参照（Paramount 前身 2024 那个只写“随附新闻稿”的 8.01 两边都答“无法判定”，窗口按合同扣留）。

**D02**（`d02-reference.json`）：参照由执行者在打开开发回答之前写成——12 个请求的 318 个必答块逐块读全文，再读每个判为在范围内或待判的块前后两块；`in` 是定义算的，`out` 是不算的，`boundary` 是定义原文留给判断的（不计入漏选或误取）。执行者自己的两条 D02 裁定（`d02-older-years/adjudication.json` 的 `SPECIFIC_LEGAL_MATTER_IS_DISCLOSURE`、`CLAIMS_ACCRUAL_IS_DISCLOSURE`）决定它们点名的类别。

比对之后参照改了两处，都写在 `_notes` 里：

- **Macy's**：开发回答在 `also_in_scope` 里列出了工伤与一般责任准备金的表格行（b1424、b1429、b1432–b1436）。参照只看了必答块的前后两块，没看到这张表；按 `CLAIMS_ACCRUAL_IS_DISCLOSURE` 它们在范围内，所以补进参照。这是演练找到参照漏掉的东西，方向是对的。
- **Lumen b2102**：参照起初只读了前 900 字，判为政府补助会计（不算）；块的最后一句写着合规审计后可能追回补助或罚款、按 ASC 450 计提负债。合规审计算不算定义里的“调查”，原文留给判断，改为待判。

改后结果（`check.json` 的 `missed`、`wrongly_taken`）：

| 请求 | 结果 |
|---|---|
| 11 份（Enphase、Ford、Lumen、Macy's、Marriott 三年、Paramount 两年、Pfizer、Salesforce） | 参照算的每一块都取了，参照不算的一块都没取 |
| Southwest 2025 | 漏 3 块：`Insurance Reserves` 标题与其下的保险准备金政策（b1510、b1511），以及税率调节表里的 `DOT settlement` 一行（b2176） |

待判块上开发回答偏宽：附注总标题、Paramount 的交易相关事项与其他公司事项小标题、Pfizer Seagen 的或有事项引言都取了；资产负债表上的“Commitments and contingencies (Note N)”一行都没取。

## 怎么处理 Southwest 那 3 块

不改这一批的 D02 合同，理由：

1. 两类都是定义原文没有写明、由执行者裁定的类别。`CLAIMS_ACCRUAL_IS_DISCLOSURE` 本身就有读者判反（Macy's FY2021 第二位读者）；把执行者的裁定写进给模型的定义，付费结果与执行者一致就会是循环论证。定义保持已批原样，付费结果按两向阅读独立验收。
2. 开发回答在同一类上前后不一：Macy's、Marriott 的自保准备金都取了，Southwest 的没取。这是回答一致性的问题，不是合同格式或请求缺陷；改提示也不能保证 DeepSeek 就一致。
3. 改合同会改 D02 的 12 个请求摘要，正在跑的封存要作废重跑，批准正文推后。

付费结果验收时专门看这两类：每份 D02 结果都两向读，自保或保险准备金段落、其他表格里点名具体和解或诉讼金额的行，各自按裁定判断。不一致的位置照常撤回，不因为“模型这么答”而接受。如果付费结果在这两类上同样前后不一，再按 #47 第 3.1 节的“初测加一次实质修正”给 D02 定义写后继版本，下一批再用。

## D04

先按原来的基础形式演练了最小的一个请求（Marriott 2023 第 4 个，1 个单元），开发回答通过了冻结检查。随后查 #28 的真实调用记录时发现，基础形式的回答合同在 #28 真实调用 71 失败过（模型抄错单元编号，见 `../call-application.md` 的 10-03 说明），#47 因此改发编号变体，16 个请求随之全变。基础形式的那次演练作废，材料没有提交。

编号形式在新运行包（`5640c367` 加两份补丁、重铸快照）上重建：16 个请求的摘要逐个等于 `../d04-request-measurement.json`（`d04-requests-index.json`、`d04-inputs-index.json`）。演练了两个：

| 请求 | 单元 | 开发回答 | 冻结检查 |
|---|---|---|---|
| Marriott FY2023 第 4 个 | 1 个（原生 XBRL 补充对象） | 26 个 token，单元已审、无发现 | 通过（`restore_response` 按位置还原后走 `validate_response`） |
| Marriott FY2024 第 4 个 | 3 个（原生 XBRL 补充对象） | 68 个 token，三个单元各按位置作答、无发现 | 通过 |

回答原样在 `answers-d04/`，检查结果在 `check-d04.json`。参照：两个请求的四个单元都是财务数据的 XBRL 补充对象，逐单元查原文，没有持续经营、重大疑虑、持续经营能力或流动性的任何措辞，也没有必评候选；空发现就是对的答案。这只验证回答格式与冻结检查，不验证模型在有疑虑披露时的判断（这三个期间的已存申报里没有这样的披露）。

其余 14 个没有演练：每个 7.8 万到 19.4 万参考 token，开发上下文能否读完说明不了 DeepSeek 能否读完；内容方面，#28 的真实 D04 结果也没有经过语义验收（`semantic_correctness_verified: false`），#47 的 D04 往年结果付费后同样要两向阅读，不因为合同检查通过就接受。

## 没做的

- 这只是一个开发上下文、一次回答；没有测同一请求多次回答是否稳定。
- 参照是执行者一个人读的，不是独立人工验收。
