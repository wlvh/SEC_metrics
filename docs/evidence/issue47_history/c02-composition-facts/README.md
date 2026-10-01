# C02 按"构成事实"口径选取：规则、双向核对与裁定

## 口径与改动

2026-09-27 所有者决定（原文摘录见 `../owner-decisions-2026-09-27/decisions.json`）：C02 取**构成事实**——董事会规模、独立董事人数、委员会设置、成员、主席，以及相关独立性和资格认定；不扩展到一般治理流程或委员会工作描述；实现要包含委员会页面的结构化读取和漏选/误选双向检查。

冻结选择器（`text_business_candidates.board_composition_candidates`）表达不了这个口径：它只要一个块里任意位置出现委员会名和任意结构词就标成"委员会信息"，又一次只读一个块，读不到委员会页面（名称、标签、每位成员各占一块）。所以新增后继 `scripts/vnext/historical_board_composition.py`（规则文件；合并 `2cc97e3a` 起这个路径保留 #28 绑定的 `546d10d1` 字节，本方的选择器在 `historical_board_composition_v2.py` 继续，Spec 在 `catalog/r6/C02_board_disclosures_historical_v2.md`，见 `../collab-28/README.md`“选择器路径”），由 `historical_text_results.prepare_business_text_sources` 只替换 C02 治理文档的 proposal；冻结准备仍负责全部来源、身份与期间检查，冻结候选构造、Evidence 与记录形状原样复用。条目上限按 D02 同一修订机制放到 192（`catalog/r6/C02_board_disclosures_v2.md`，只改 `max_items`），实测最多 98 条。

## 读什么

结构（一组块合起来陈述一件事）：委员会页面（标题→成员/主席，含"另一栏"排版与零宽块）、报告签名（"Submitted by the Audit Committee … as of …"、"Name, Chair / Name, Member"）、董事卡片（"Committees:" 标签与条目，条目可用申报自己的委员会简称如 NCG、HRC、A；卡片的董事名在条目后或在卡片字段前；两侧都有名字则不猜）、卡片身份字段（"Independent"、"Director Nominee"、"Age: 73 | Director"——只在旁边有年龄/任职年等卡片字段时算）、点名本注册人的头衔行（"Chairman and Chief Executive Officer, Macy's, Inc."；同一句里出现别的机构、或 former/until，则不算）、按类别分组的董事表（"Continuing Class III Directors"，至少两行名字）、表格脚注里的变动（"(2) Retired from the Board effective May 14, 2025." 只与带同一标记的名字一起取）。

逐句（一句话本身陈述一件事）：规模及其变化、独立性、委员会构成与主席、董事会主席/首席独立董事（无"of the Board"的头衔只在句子说明是谁的——our、the company's、本注册人名所有格——时才算；Vice Chair 只有带"of the Board"才算，福特的 Vice Chair 是高管头衔）、成员变动（点名的人加上任职/离任/留任，或"did not elect any new Directors"、"Two New Directors Effective July 2025"这类计数）、委员会设立变化（须带日期，"was established … in accordance with Section 3(a)(58)(A)"是每个审计委员会都引的法条，不算）、关于董事本身的资格认定。薪酬、投票、出席、沟通、股权计划条款整句排除；但**同一句里写明谁担任哪个委员会主席、或非雇员董事人数**，照样取——事实写在哪里就在哪里读。

## 怎么核对（两个方向）

十个位置各由一个未看过选择器规则的新读者（同一模型家族的子代理，不是人）通读：已选块逐块判 FACT/MIXED/NOT，另读一个"池"（所有提到董事/委员会/独立/主席/成员/提名等词的块，以及委员会附近的短名字）并列出其中陈述构成事实的块。判读按块文本 SHA-256 绑定，文本变了就不适用。

`tools/read_c02_composition.py` 在当前代码下经历史路线重新算出选择，然后回答：选了但读者判为非事实的（误选）；读者判为事实、没选、且它引用的等价块一个都没选的（漏选）。池也写进了判读：读者说明里规定"池中判为 NOT 的不列出"，所以**池里、文本未变、未列为事实的块被选中，按该读者判为误选**，而不是"未读"。读者从没拿到过的块被选中，报"未读"，不当作正确。

## 结果

| 位置 | 之前 选/误选/漏选 | 现在 选/误选/漏选 | 依赖裁定的块 |
|---|---|---|---|
| Enphase 2025 | 16 / 0 / 8 | 35 / 0 / 0 | 0 |
| Ford 2025 | 77 / 0 / 0 | 80 / 0 / 0 | 2 |
| Lumen 2025 | 63 / 4 / 19 | 98 / 0 / 0 | 9 |
| Macy's 2026 | 46 / 0 / 11 | 97 / 0 / 0 | 9 |
| Marriott 2025 | 85 / 0 / 14 | 96 / 0 / 0 | 1 |
| Paramount 前身 2024 | 58 / 3 / 3 | 68 / 0 / 0 | 0 |
| Paramount 2025 | 40 / 0 / 8 | 54 / 0 / 0 | 10 |
| Pfizer 2025 | 70 / 0 / 12 | 79 / 0 / 0 | 0 |
| Salesforce 2026 | 43 / 1 / 6 | 63 / 0 / 0 | 21 |
| Southwest 2025 | 60 / 0 / 21 | 95 / 0 / 0 | 0 |
| 合计 | 558 / 8 / 102 | 765 / 0 / 0 | 52 |

"之前"是本目录判读时的选择（同一后继模块的第一版）；十份判读正是对它做的。

## 裁定（`adjudication.json`，由 `adjudicate.py` 生成）

读者之间对同一类块判断相反时，用一条规则决定这一类，并对全部 37 份判读（最新十份、往年 27 份）里该类的**每一个**块适用。类别只按文字界定，不看路线选没选；只在判读与规则不同处写一条裁定，读者原来的判断和理由留在旁边。判为事实的裁定列出同一文档里陈述同一事实的块（`redundant_with`），其中任一块被选就不算漏选。

| 规则 | 判定 | 内容与理由 |
|---|---|---|
| `CARD_TENURE_FIELD` | 非事实 | 卡片上的"Director since: 2017"。在任多久不在所有者列出的事实里 |
| `CARD_SUBJECT_NAME` | 事实 | 卡片或表格行在构成字段前印的名字。字段不写是谁就什么也没说；字段自己写出了人名的不需要 |
| `NOMINEE_CARD_NO_COMMITTEE` | 非事实 | 尚未任董事的候选人卡片上的 "Committees: N/A"（紧挨在它前面的是本卡片的 "Director since: N/A"）。候选人不在任何委员会，是因为还不在董事会，这说明不了本董事会委员会的成员。Paramount FY2024 的读者三处都没取，FY2022 的读者取了一处（第 819 块，Ostroff）。在任董事的 "N/A" 说明此人不在任何委员会，不在本类。37 份文档里四处候选人卡片都是这个顺序，所以只认紧挨在前的字段，不另设窗口。只产生一条裁定：Paramount 2022 第 819 块由事实改为非事实，该位置漏选 [819] 消失、与判读一致（`adjudication-effect-nominee-card.json`：漏选 29→28，一致的位置 21→22） |
| `CHAIR_CEO_STRUCTURE` | 事实 | 董事长与 CEO 分设还是由一人担任。往年读者在五家公司 31 块上都取了；最新 Lumen、Marriott 的读者没取同样的句子 |
| `CLASSIFIED_SLATE_COUNT` | 非事实 | 分级董事会里一级的候选人数。不是董事会规模，也不是成员变动 |
| `DIRECTOR_GROUP_HEADING` | 非事实 | 董事分组标题（级别、候选或留任、任期），表格上方与卡片上方同样处理。级别与任期与任期年限同类 |
| `DIRECTOR_TABLE_NAME` | 事实 | 带独立性列的董事表里的每个名字。标了或没标，该行都承载这张表对此人的认定 |
| `DIRECTOR_COUNT_ON_A_DATE` | 事实 | 某日的董事人数或非雇员董事人数，不论印在股权计划资格还是出席情况里 |
| `COMPENSATION_COMMITTEE_INTERLOCKS` | 事实 | 薪酬委员会成员无人是或曾是高管或雇员：对委员会成员的认定 |
| `MEMBERSHIP_CRITERIA_DETERMINATION` | 事实 | 董事会认定董事符合任职标准：资格认定 |
| `PRESIDING_DUTY` | 非事实 | 某个职位主持独立董事会议。这是该职位的职责；谁担任这个职位才是构成事实，在写出担任者处读。14 份判读里 9 份没取、5 份取了。块里另写出担任者的留给判读 |
| `BOARD_TASK_FORCE` | 事实 | 由具名董事组成的董事会工作组及其标题：委员会设置与成员 |
| `NOMINEES_ARE_SITTING_DIRECTORS` | 事实 | "Each nominee is currently a member of the Board"：候选名单就是现任董事会 |
| `COMMITTEES_NAMED_AS_A_SET` | 事实 | 把三个以上董事会委员会一并列出的句子（如章程句）：委员会设置。由判读里写出全部这些委员会的块覆盖 |
| `JOIN_BEFORE_THE_YEAR` / `JOIN_IN_THE_YEAR` | 非事实 / 事实 | 写明某人何时加入董事会的句子。目标年度之前的日期是换了说法的任期，与 `CARD_TENURE_FIELD` 同；目标年度及以后的是期间内的成员变动。同一块里还写了别的构成事实（主席、委员会、离任）的留给判读。名词写法（"prior to Mr. Munoz's appointment to the Board in January 2022"）原先没有被句式识别，是 #28 对 Salesforce FY2026 的内容核对发现的；补上后多一条裁定（Salesforce 2026 第 4300 块，非事实）。年度内的加入与 `DATED_ROLE_CHANGE` 一样，只由写明同一人加入、日期至少一样精确的块覆盖，读者引用的名单（如 Paramount FY2025 第 84 块）不算，由 #28 对 Paramount FY2025 的核对引出 |
| `DATED_ROLE_CHANGE` | 事实（只由同一变动覆盖） | 写明某位董事在目标年度内或之后某天接任董事长、首席独立（主持）董事或某委员会主席的句子：一次职务变动。只有写明同一人在同一职务上同一变动、日期至少一样精确的块才算覆盖；写现任者、另一人的变动、只给月份或费用季度的不算。读者判为事实但引用了不覆盖它的块时，裁定替换读者的引用，`read_position` 按裁定判断。由 #28 对 Salesforce FY2026 的内容核对（第 933 块）引出，见 `../c02-selector-repairs/README.md` 第 15 节 |
| `TERM_END_AT_A_MEETING` | 事实（只由同一离任覆盖） | 写明某位具名董事的任期在某次年会上已结束或将结束的句子（Lumen 董事薪酬表的脚注："The terms of Mr. Brown, Mr. Clontz and Ms. Siegel will end in connection with the election of directors at the 2025 annual meeting"）：一次离任。看到过这类句子的读者都判为事实，与各种日期的退休句同样处理，读者之间没有分歧；本类是为没有读者看过的块写的（脚注不含所有者词汇，不在判读池里，Lumen 2022 一块、2023 两块）。只有写明同一批人离开、且（如写了年份）年份相同的块才算覆盖；不点名的"以下三位将退休"、"Retiring Directors" 标题和其下的薪酬行都不算。整批候选人改选时"their term of office will expire at the Annual Meeting"没有人离开，不在本类；只用代词、句中没有恰好一人具名的，也不在本类。见 `../c02-selector-repairs/README.md` 第 17 节 |

**两处是执行者的取舍，不是多数读者的意见**：`PRESIDING_DUTY` 与多数读者一致（9 比 5），`NOMINEES_ARE_SITTING_DIRECTORS` 与多数相反（Macy's 五份判读里 1 份取、4 份没取），理由是非分级董事会全员改选，候选名单即董事会，与每位读者都取了的"非分级董事会候选人数即规模"同理。

**上一版裁定只有两类，而且其中一类是单边的**：卡片名只在"路线取了这个名字"时才裁定为事实，于是只会替路线已取的名字解围，从不把路线漏掉的名字算作漏选。现在按文字找名字（字段前最近的、由两个以上词组成或分两块印的人名，信件结尾的"Sincerely,"不算），上一版的 52 条全部原样保留。

**效果**（`adjudication-effect.json`，用今天的选择器）：误选 40→46，漏选 146→144，一致的位置 11→9。对路线不利和有利的裁定大致相当：新不一致的是最新年 Enphase（3 个级别标题、3 处分级候选人数被取）、Lumen（分设句未取）、Macy's（候选人现为董事未取）、Marriott（两处分设句未取），以及若干往年块；新一致的是 Paramount FY2021、FY2023。这四个最新位置已按坐标登记缺陷（`C02_*_UNIFIED_ADJUDICATION_DISAGREES`，带逐块的 `selection_problems`），此前接受的值在修好的选择被重新读过之前一律撤回。

用例：`test_historical_board_composition_filings` 要求最新十个位置的裁定**正好**是规则在该文档与判读上得出的结果（多一条少一条都不行），往年裁定都绑在读者看过的文本上，每个位置要么一致、要么与登记的缺陷逐块相同。`adjudication_injections.py`（结果在 `adjudication-injections.json`）在内存里逐处改读法与裁定，随规则增加到 20 处（`NOMINEE_CARD_NO_COMMITTEE` 加了 3 处），20 处都被各自点名的用例抓到，对照运行干净。

**局限**：每一类的识别式是在这 37 份判读上写的，只找得到这些申报里的写法；换一种写法的同类块不会被裁定，仍按判读处理。用来定规则的判读对后续修复只算回归材料。

## 故障注入

`fault_injections.py` 逐条破坏规则，每次在子进程里让 `vnext` 包先找只含被改模块的临时目录（其余模块与数据文件都用检出里的），并要求**对照运行先干净跑完整个套件**。最初 30 条、对照 40 例，30/30 由各自具名用例抓到；往年修复（`../c02-selector-repairs/`）每处加一条，现为 31 条、对照 43 例，31/31（`fault-injections.json`）。2026-09-29 起模块改为相对自身位置读取 `catalog/r6/` 里的目录文件，临时副本找不到它，对照运行跑不起来，脚本在对照处停下；现在临时副本按 `scripts/vnext/` 的层级放置并带上该文件，子进程另用新建的字节码目录。第一版把整个包复制到临时目录，包在那里找不到数据文件、套件一例都没跑，于是 30 条全报"漏掉"——不是规则的问题，是注错够不到目标；现在对照必须报告完整用例数，否则直接退出。第二版有 3 条漏掉，原因都在用例：职责引导句的用例里没有"committee"一词，根本到不了被测规则；"former"用例已被另一条检查拒掉；人名判断没有直接用例。三处都改了用例而不是规则。

## 局限

- **规则是在这十份申报上写的，也在这十份上核对**：这是拟合，不是留出验证。本仓库每家只存了一份代理材料（全部 2026 年申报）；SEC 获取计划里的 36 份往年代理到位后，就是第一批留出材料——那时要先读、再比，不先改规则。
- 读者是同一模型家族的子代理；判读质量本身没有被人工抽检。
- 没读的结构：没有委员会名、只写"Respectfully submitted,"的签名（Macy's 两处；其事实由委员会页面覆盖）；没有"Committees:"标签的卡片（Enphase；由签名与页面覆盖）；成员矩阵里失去列位置的圆点（按设计不重建）。
- 漏选判断接受"读者引用的等价块中任一已选"即视为覆盖（读者常把几处互为替代的块一起列出），只被部分覆盖的另列在 `covered_by_some_citations_only`。

## 还没做的

选择器按已裁定的类别逐项修复（分设句、分级候选人数、分组标题、候选人现为董事、工作组、某日人数、按日期区分加入），每项单独提交并标 `[shared-with-#28]`；修好后四个最新位置重跑、重读、按新结果释放。
