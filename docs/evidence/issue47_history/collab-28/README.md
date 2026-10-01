# 交给 #28 的材料（COLLAB-28-47-v1）

本目录只放索引，不复制原件、不另造运行环境。所引文件都是已有文件；固定提交写在各节开头，GitHub 上按该提交打开即可。规则见 Issue #47 / #28 正文的“跨 Issue 协作（COLLAB-28-47-v1）”节，本方副本在 `AGENTS.md`。

## 第一轮（2026-10-01）

### B02：两年用了不同概念的防错

固定提交 `48b46a2d742eb3e3b8bd5a6404908745046b5d2f`。

| 内容 | 位置 |
|---|---|
| 实现 | `scripts/vnext/historical_results.py` 第 46–121 行：常量 `PAIRED_MEASURE_REASON`、`_paired_concept_lists`、`_claim_view`、`paired_measure_problem`；历史路线的调用点在同文件 `paired_measure_problem(` 处（约第 336 行） |
| 用例 | `tests/vnext/test_historical_paired_measure.py`（7 例，约 0.2 秒，fast 层；只读检出里已存的 Pfizer Company Facts） |
| 注错 | `docs/evidence/issue47_history/b02-revenue-concept/injections.py` → `injections.json`：4 个（不问两个概念、任何报值都当桥、在上年申报里找桥、把所有概念组都当成对），全部由对应用例抓到 |
| 量测与端到端 | 同目录 `README.md`、`measure.py` → `measured.json`、`targeted-runs.json` |

**哪部分是通用判断。** `paired_measure_problem(route=, claims=, current_claims=, accessions=)` 只用四样东西：指标的目录分支（找出“当年”与“上年”两个分量读同一组已批概念的那一对）、冻结计算图实际用到的 claims、目标 accession 的全部 Company Facts claims、本期与上期两个 accession 号。它不读期间选择、不读文件、没有副作用。普通路线可以在 `_deterministic_metric_graph` 算出图之后、发布结果之前调用它：本期 accession 用选定的最新年报，上期用 `_prior_filing` 选出的那份。依赖只有 `decimal.Decimal`、目录结构（`branches[].components[].approved_concepts / accession_role`）和 claim 的 `locator / attributes / unit / value` 字段。不需要整体导入 `historical_results.py`，拷贝这四个名字或从该模块导入都可以。

**哪部分依赖历史选期。** 调用点里的 `prepared["filing"]`、`filings["prior"]` 是钉定期间的选择。扣留用的 `withheld_metric_result(... reason_code=PAIRED_MEASURE_REASON)`，以及 detail 里的 `MEASURE_NOT_COMPARABLE` / `paired_measure_bridge`，是历史路线自己的记录方式。普通路线按自己的扣留机制接，不必照搬。

**验收目标（建议在普通入口逐项核对）。**
1. 拦住范围混用。两个 claim 落在不同概念上，且目标年报没有用本期概念、以上期 claim 的同一个数报出上年时，按名扣留。历史实例：Pfizer FY2023 用产品收入除以总收入，发布 −49.3%；FY2024 用总收入除以产品收入，发布 +25.0%。
2. 有依据的标签变化不误拒。目标年报用本期概念报出的上年数等于上期 claim 的值时，保留结果并记下这座“桥”。历史实例：Pfizer FY2022，Revenues 与合同收入两个概念对 2021 年都是 812.88 亿美元，+23.4% 保留。
3. 当期原本正确的结果不受损。#47 量过 Pfizer FY2025 两年都用 Revenues，不会触发。其余公司的最新年度需要 #28 在自己的普通入口逐个确认；#47 没有替 #28 跑普通路线。

**边界。** 这是防错，不是收入可比性的证明。两个概念恰好同数、含义却不同时，会被当成同一个量。目标年报对上年的重述不参与判断：分支仍取上期申报的原数，与“当时报告”的口径一致。它不包含、也不批准“两年共有的第一个标签”政策，不切换到最新重述口径。

### C02：材料索引与共用修复分工

固定提交 `48b46a2d742eb3e3b8bd5a6404908745046b5d2f`；往年位置的缺陷登记在本索引所在的提交里。

| 目录（都在 `docs/evidence/issue47_history/` 下） | 是什么 |
|---|---|
| `c02-board-read/` | 冻结选择器 `text_business_candidates.board_composition_candidates` 的反例与影响范围。该选择器在各世代冻结，普通路线与历史路线共用。读的十个值是**九家公司的最新期间（不含 JPMorgan）加 Paramount 前身 FY2024**，不是十家公司各自的最新期。246 条摘录里有 94 条在任何口径下都不属于董事会构成，其中 87 条是“块里任意位置有委员会名、任意位置有结构词”这条标签放进来的。见 `README.md`、`excerpt-judgements.json`、`deterministic-narrowing.json`（关键词收窄会丢掉对的、留下错的，不可行）、`core-fact-reach.json`（漏选方向的核心事实触达） |
| `c02-composition-facts/` | 后继选择器 `scripts/vnext/historical_board_composition.py`（#47 规则文件；合并 `2cc97e3a` 起为 `historical_board_composition_v2.py`，Spec 为 `C02_board_disclosures_historical_v2.md`，见下文“选择器路径”）。它只替换 C02 治理文档的 proposal，冻结的来源准备、候选构造、Evidence 与记录形状原样复用；条目上限按修订机制放到 192（`catalog/r6/C02_board_disclosures_v2.md`）。在同十份最新材料上双向核对：765 选、0 误选、0 漏选，其中 52 块依赖两条执行者裁定（`adjudication.json`）；30 个注错全部抓到（`fault-injections.json`）。局限：规则就是在这十份申报上写、也在这十份上核对的，属开发/回归材料，不是留出验证；读者是同族子代理，不是人工验收 |
| `c02-older-years/` | 27 个往年位置（41 期批次 21 个，闭包 `ed360ebc`；第三轮 6 个，闭包 `8530710b`）的双向判读，全部读完（`judgements/`）。与当前代码从已存申报算出的选择对比（`comparison.json`）：26 个不一致，共 49 个误选块、256 个漏选块；Pfizer FY2024 一致。读者之间在若干类别上判断相反，需要按类别统一裁定，且裁定同样适用于最新十个位置的判读。读法、池规则、读者提示和答案交叉核对见 `README.md` |

**当前状态。** 最新十个位置（同上口径）由后继选择器产出的新结果已读并接受；冻结选择器的十条缺陷只对这十个新结果释放。27 个往年值一个都没有被接受；不一致的 26 个已按坐标登记为缺陷撤回（`../known_result_defects.json`，`C02_*_OLDER_YEAR_READING_DISAGREES`），一致的 Pfizer FY2024 也还没有对它的结果做接受核对。这 27 份判读已经或将要用于调整规则，所以它们对之后的修复也只算开发/回归材料。“27 份读完”不等于结果被接受。

**对方接收状态（2026-10-01 读到 `3473308b` 为止）。** B02：#28 在 `32faa26d` 把三个函数接入普通路线（逐 AST 与本方 `48b46a2d` 相同，原因码改为普通路线专用），`f2018837` 的限定独立审阅为 PASS_WITH_BOUNDS——**已确认接收**。C02：#28 在 `3473308b` 读了 `c02-board-read/` 并据其中两处判定撤回自己最新年 Marriott、Pfizer 的三个结果身份，后继选择器与上表修复的普通路线接入**尚未开始**，按其记录是下一步。

**对方接收状态（读到 `2cc97e3a` 为止）。** C02：#28 在 `e17cf333` 按本方 `877793e9` 把共用选择器接入普通路线的显式后继（选择器字节等于本方 `546d10d1`，即下表修复 1–6；它自己的 Spec v2 上限 64，Marriott、Pfizer 超过 64 条时按名失败、不截断），旧的冻结默认路线不变——修复 1–6 **已接收**。`2cc97e3a` 按本方统一裁定撤回它 Enphase 2025 的两个私有结果，点名六块（57、210、212、232、243、2338）；这六块正是下表修复 8、9 移走的块。修复 7–12 **尚未接收**；它对最新年各值的影响见下文“选择器路径”。修复 13 在其后提交，最新年只移动 Paramount 2025（新增 8 块）。

**分工。** 共用选择器修复默认由 #47 继续实现，#28 负责普通路线接入和独立检查。修复按“一个明确的误选或漏选问题”为单位提交，提交标 `[shared-with-#28]`，并在本目录登记问题、提交、用例与历史侧验证结果。#28 现在的普通路线用的仍是冻结选择器，所以它最新年度的 C02 结果与 `c02-board-read/` 读的十个值同属一类问题；这部分的核对与接入由 #28 在自己的记录里处置，#47 不代为宣布普通路线已通过。

### C02 共用修复登记

每一项是一个边界清楚的误选或漏选问题，提交标 `[shared-with-#28]`。可复用位置都是选择器在该提交的版本：第 1–12 项提交时它在 `scripts/vnext/historical_board_composition.py`，合并 `2cc97e3a` 起在 `scripts/vnext/historical_board_composition_v2.py`（见下文“选择器路径”）；问题、成因、用例、注错与历史侧量测见 `../c02-selector-repairs/README.md` 对应一节。量测把修复前后的选择器在全部 37 份判读（27 个往年、10 个最新）上各跑一次，列出移动的每一块。

| # | 问题 | 提交 | 用例 | 历史侧量测 |
|---|---|---|---|---|
| 1 | 匹配 "as <委员会名> committee chair" 的模式带 `re.I`，`[A-Z]` 也匹配小写，把遴选标准 "Previous service as a Board committee chair" 读成有人任委员会主席 | `5f803852` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_criterion_for_choosing_a_chair_seats_no_one`；注错 `A_LOWER_CASE_WORD_NAMES_A_COMMITTEE` | 只移动 Macy's 四个往年位置的这四块（都是判读判为非事实的块）；误选 49→45，漏选 256 不变，最新十个位置不变（`../c02-selector-repairs/measured-1-capitalised-committee-name.json`） |
| 2 | 委员会名单在每个名字前单独印项目符号，"◾" 与 "·" 不在选择器的符号集里，名单在第一个符号处结束，一个名字都没读到 | `9b7465ab` | `test_historical_board_composition.ACommitteePageIsReadAsAStructure.test_a_roster_marked_with_each_glyph_filings_print`；注错 `THE_SQUARE_BULLET_IS_NOT_A_BULLET`、`THE_MIDDLE_DOT_IS_NOT_A_BULLET` | 只在 Ford、Macy's 各一个往年位置新增 43 + 24 块，全部是判读判为事实的块；漏选 256→175，误选不变，最新十个位置不变（`../c02-selector-repairs/measured-2-bullet-glyphs.json`） |
| 3 | 委员会成员行写成句子（末尾句号、最后一个 "and" 前有逗号），`name_list` 整行失败，成员行与委员会标题都没取 | `a88147a4` | `test_historical_board_composition.ACommitteePageIsReadAsAStructure.test_a_members_line_written_as_a_sentence`；注错 `A_SERIAL_COMMA_ENDS_A_LIST`、`A_FINAL_PERIOD_ENDS_A_LIST` | 只在 Marriott 两个往年位置新增 6 + 8 块，全部是判读判为事实的块；漏选 175→160，误选不变，最新十个位置不变（`../c02-selector-repairs/measured-3-sentence-member-lists.json`） |
| 4 | 卡片在 "Director since …" 之后一行一个委员会、没有 "Committees:" 标签，选择器只认带标签的卡片，漏掉主席标注 | `a6975a47` | `test_historical_board_composition.ADirectorCardIsReadOnlyWhenItNamesItsDirector.test_unlabelled_committees_on_the_lines_after_the_tenure`；注错 `AN_EMPHASISED_HEADING_IS_A_CARD_ITEM`、`UNLABELLED_ITEMS_NEED_NO_DIRECTOR`、`UNLABELLED_CARD_ITEMS_UNREAD` | Enphase 三个往年位置新增 15 + 15 + 19 块，全部是判读判为事实的块，漏选 160→156，误选不变。**最新年份 Enphase 2025 也新增 19 块**（判读同样判为事实），已接受的值只对应旧结果，要重新核对接受；普通路线接入后最新年度 Enphase 的值同样会变（`../c02-selector-repairs/measured-4-unlabelled-card-items.json`） |
| 5 | 名字中间印着引号昵称（"Steven T. “Terry” Clontz"），`person_name` 拒绝含引号的块，卡片读不出、名单读到他就断 | `5c595159` | `test_historical_board_composition.ANameIsTheWholeBlock.test_a_quoted_nickname_between_the_names`；注错 `NICKNAMES_STAY_IN_THE_NAME`、`ANY_QUOTED_WORD_IS_A_NICKNAME` | Lumen 三个往年位置各 5 块、Marriott 一个往年位置 2 块，全部新增、全部是判读判为事实的块；漏选 156→146，误选不变，最新十个位置不变（`../c02-selector-repairs/measured-5-quoted-nicknames.json`） |
| 6 | 管理层委员会（成员是高管、员工，或由某某 Officer 主持）被构成句式当成董事会委员会 | `546d10d1` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_committee_of_management_is_not_the_board_s`；注错 `MANAGEMENT_SEATS_A_BOARD_COMMITTEE`、`ANY_WORDS_OPEN_THE_MEMBER_LIST` | 只移走 Lumen、Marriott、Pfizer 四个往年位置的 5 个误选块（都是判读判为非事实的块）；误选 45→40，漏选不变，最新十个位置不变（`../c02-selector-repairs/measured-6-management-committees.json`） |
| 7 | 董事长与 CEO 分设或合一的陈述（不点名）一句都没取；统一裁定判为事实 | `852a6e90` | `test_historical_board_composition.ALeadershipOrMembershipFactNamesThisBoardAndThePerson.test_whether_the_chair_and_the_chief_executive_are_one_person`、`test_a_choice_a_policy_or_a_proposal_states_no_structure`；注错 `THE_CHAIR_CEO_STRUCTURE_STATES_NOTHING`、`NAMING_BOTH_CHOICES_STATES_A_STRUCTURE`、`A_POLICY_OR_A_PROPOSAL_STATES_A_STRUCTURE` | 新增块全是判读或统一裁定判为事实的块，未移走任何块；漏选 144→118，误选 46 不变，不一致位置 28→26；最新年 Lumen、Marriott 恢复一致；最新年 Ford、Macy's 的值随之变化，需重读后才接受（`../c02-selector-repairs/measured-7-chair-ceo-structure.json`） |
| 8 | 分级董事会每年只改选一级，"To elect our three nominees" 这类一级候选人数被当成董事会规模；"has nominated three directors" 也被当成 "has three directors" | `bed088ee` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_on_a_classified_board_the_slate_is_not_the_board_s_size`、`test_the_filing_says_whether_its_board_is_classified`；注错 `A_CLASSIFIED_BOARD_STILL_COUNTS_ITS_SLATE`、`NO_FILING_IS_CLASSIFIED`、`HAS_NOMINATED_COUNTS_AS_THE_BOARD_S_SIZE` | 只移走 Enphase 五个位置的 12 块，全部是读者或统一裁定判为非事实的块；误选 46→34。最新年 Enphase 2025 移走 57、210、2338（`../c02-selector-repairs/measured-8-classified-slate.json`） |
| 9 | 董事分组标题（"Continuing Class III Directors (Until 2027 …)"）连同其下的名字一起被取 | `bd181df0` | `test_historical_board_composition.ACardOrTableStatesWhoAndWhat.test_a_table_of_directors_by_class_and_not_a_card_under_a_heading`；注错 `THE_GROUP_HEADING_IS_TAKEN_AGAIN`、`ONE_NAME_MAKES_A_TABLE` | 只移走 13 个分组标题（Enphase 四年各 3 个、Lumen 2024 一个），名字一个不少；误选 34→21，不一致位置 26→24。Enphase 2025 移走 212、232、243，修复 8、9 之后该位置的选择与读者判读、统一裁定一致（`../c02-selector-repairs/measured-9-group-headings.json`） |
| 10 | 全员每年改选的董事会写 "Each nominee is currently a member of the Board"，没取 | `16c4821e` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_slate_of_sitting_directors_says_who_the_members_are`；注错 `A_SITTING_SLATE_STATES_NOTHING`、`ANOTHER_BOARD_SEATS_THE_SLATE` | 只在 Macy's 五个位置各新增这一块；漏选 118→113，最新年 Macy's 恢复一致（`../c02-selector-repairs/measured-10-sitting-slate.json`） |
| 11 | 由具名董事组成的董事会工作组（Macy's "Digital Innovation Task Force"）没取，选择器只认 committee | `35b93187` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_task_force_of_named_directors_is_a_body_of_the_board`；注错 `A_TASK_FORCE_STATES_NOTHING`、`A_TASK_FORCE_TITLE_IS_NOT_TAKEN`、`ANY_TASK_FORCE_TITLE_HEADS_THE_MEMBERS` | 只在 Macy's 2022、2023 各新增标题与成员句两块；漏选 113→109，最新十个位置不变（`../c02-selector-repairs/measured-11-task-force.json`） |
| 12 | 出席情况句里的上年董事人数（"of the twelve then current members of the Board"）随出席话题被整句排除 | `60aa9f7b` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_the_board_s_size_on_a_past_date_wherever_it_is_printed`；注错 `A_PAST_COUNT_IS_SET_ASIDE_WITH_ATTENDANCE` | 只在 Ford 2021、2022 各新增这一块；漏选 109→107，最新十个位置不变（`../c02-selector-repairs/measured-12-past-board-size.json`） |
| 13 | 董事加入日期不看目标年度：年度之前加入的（"who joined our Board in February 2020"）被当成成员变动取，年度之内加入的（"has served as … a director of the Company since February 2021"）没取 | `2926b7d0` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard` 的 `test_a_join_dated_before_the_year_is_tenure`、`test_a_join_dated_in_the_year_is_a_change`、`test_a_join_is_dated_as_precisely_as_it_is_printed`、`test_the_target_year_is_a_date_and_the_proposal_names_it`；注错 `A_DATED_JOIN_COUNTS_IN_ANY_YEAR`、`AN_IN_YEAR_JOIN_STATES_NOTHING`、`A_JOIN_IN_A_PAY_SENTENCE_IS_SET_ASIDE`、`A_PRINTED_DAY_IS_IGNORED`、`A_MONTH_ALONE_IS_PLACED_AT_ITS_START`、`ANY_TARGET_YEAR_IS_ACCEPTED` | 移走 Enphase 2021、2022、Lumen 2022 三块，新增 Marriott 2021 两块；误选 21→18，漏选 107→105。最新年 Paramount 2025 新增 8 块 2025 年加入的董事履历（读者判为含事实），该位置仍一致，但值会变。**接口变化**：`board_composition_facts` 必须收到 `period_start`（目标年度第一天），接这一版时请传 `target["period_start"]`（`../c02-selector-repairs/measured-13-joins-by-period.json`） |
| 14 | 写成名词的加入日期没被认出（"prior to Mr. Munoz's appointment to the Board in January 2022"），Salesforce FY2026 第 4300 块被当成员变动取（#28 `9f8b855f` 的内容核对发现） | `84627bed` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_join_written_as_a_noun_is_dated_too`；注错 `A_NOUN_FORM_JOIN_IS_NOT_DATED` | 统一裁定的 JOIN 句式同时补名词写法，多一条裁定（4300 非事实）；只移动 Salesforce 2026：去掉 4300，新增年度内名词加入的 919；误选 19→18（`../c02-selector-repairs/measured-14-noun-form-joins.json`） |
| 15 | 带日期的职务接任没被取（Salesforce FY2026 第 933 块，Roos 2025 年 3 月 21 日接任治理委员会主席），量测又把读者"已被覆盖"的说法照单全收（#28 同一核对发现） | `43f07e94` | `test_taking_over_a_chair_or_the_lead_role`；`test_historical_board_composition_filings.ADatedRoleChangeIsCoveredOnlyByTheSameChange`；注错 `TAKING_OVER_A_COMMITTEE_CHAIR_IS_NOT_READ`、`TAKING_OVER_THE_LEAD_ROLE_IS_NOT_READ`、`A_READER_CITATION_STANDS_OVER_THE_ADJUDICATION`、`A_YEAR_COVERS_A_DAY`、`ANOTHER_PERSONS_CHANGE_COVERS`、`A_CHANGE_BEFORE_THE_YEAR_IS_DECIDED` | 统一裁定新增 `DATED_ROLE_CHANGE`，37 份判读上多两条（Salesforce 933 无覆盖、Macy's FY2024 2358 由已选的 1044 覆盖）；只移动 Salesforce 2026（新增 933），漏选 106→105；该位置的选择现与判读一致（`../c02-selector-repairs/measured-15-dated-role-changes.json`） |
| 16 | 年度内加入的董事履历（"has served as a member of our Board since August 2025"）没取，量测又把读者引用的名单（第 84 块）当成覆盖（#28 `3a661897` 对 Paramount FY2025 的内容核对发现） | `006795dd` | `test_a_long_title_before_the_join`；`test_historical_board_composition_filings.AJoinInTheYearIsCoveredOnlyByTheSamePersonsJoin`；注错 `THE_JOIN_REACH_IS_SIXTY`、`A_ROSTER_COVERS_A_JOIN`、`A_JOINER_IS_ANY_NAME_BEFORE_THE_PRONOUN`、`ANOTHER_PERSONS_JOIN_COVERS` | 统一裁定的 `JOIN_IN_THE_YEAR` 改为只由同一人、日期至少一样精确的加入覆盖；选择器 "has served as … a member of our Board since" 中间长度 60→80 字符。只移动 Paramount 2025（新增第 100 块），漏选 106→105；该位置的选择现与判读、裁定一致。第 168 块（提名理由）是否算资格认定，两边口径不同，记为待对齐（`../c02-selector-repairs/measured-16-join-coverage.json`） |

这些修复都不让任何坐标重新获得信用：选择仍与判读不一致的坐标继续撤回；已经一致的坐标，其已发布结果是旧版本算的，要等重算、重读后按结果编号释放。修复 7–12 是否、何时接入 #28 的普通路线由 #28 自己处置；#47 不代为宣布普通路线已通过。

### 选择器路径（自合并 `2cc97e3a` 起）

#28 的 issue_28_v13 现在按字节记录 `scripts/vnext/historical_board_composition.py`（本方 `546d10d1` 的字节）与 `catalog/r6/C02_board_composition_terms_v1.json`，并在 `catalog/r6/C02_board_disclosures_v2.md` 新建了它自己的普通路线 Spec（上限 64）——本方的历史 C02 Spec（上限 192）原来就在这个路径。两个世代都按字节绑定同一路径时，一棵代码树只能满足其中一个：本方若继续在原路径上修，#28 的普通 Run 在本分支的合并树上会因执行字节不符而失败，它断言 Enphase 2025 选 54 块、含 210 的用例也会失败；反过来本方的修复会停在 `546d10d1`。所以合并时：

* 两个共用路径保留 #28 绑定的字节，issue_47_v1 从父代权威继承它们；
* 本方的选择器从此在 `scripts/vnext/historical_board_composition_v2.py` 继续（合并时等于 `60aa9f7b` 的字节，只加一段说明），历史 C02 Spec 改为 `catalog/r6/C02_board_disclosures_historical_v2.md`（字节不变；Spec 闭包哈希只由内容决定，不随路径变）；
* 约定：本方不改 #28 世代绑定的路径。#28 接新版本时，把 `_v2` 在某个固定提交的字节复制到它自己的路径（例如原路径）再记录；若直接绑定 `_v2`，本方下一次修复时同样的冲突会再出现。#28 若更愿意直接绑定 `_v2`，请在双方记录里说明，本方届时另起后继文件。

两个版本在同 37 份文档上的差别逐块列在 `selector-path-split.json`：差别正好是修复 7–12。最新年：Enphase 54→48（移走上面六块，不新增），Ford 80→82，Lumen 98→99，Macy's 97→99，Marriott 96→98，Paramount、Pfizer、Salesforce、Southwest 不变。这里只量了本方的文档；#28 的普通文档经同一冻结准备生成，是否逐块相同由 #28 在自己的链路里核对。Marriott（98）、Pfizer（79）在两个版本下都超过普通路线的 64 条上限；本方历史路线用 `historical_spec_revision.py` 与 `historical_text_protocol.py` 把上限放到 192，是可供参考的现成实现，不是对 #28 Spec 的要求。

### C02 读者分歧的统一裁定（[shared-with-#28]）

`../c02-composition-facts/adjudicate.py` 把读者判断相反的类别各用一条规则决定（16 条，按文字界定、不看路线是否选取），对全部 37 份判读适用，表格与两处取舍的说明见 `../c02-composition-facts/README.md`。用今天的选择器：误选 40→46，漏选 146→144，一致位置 11→9；对路线有利与不利的裁定大致相当。**影响 #28 普通路线的部分**：这些是"什么算构成事实"的判定，与选择器实现无关；#28 用自己的读法核对最新年度时，若读到同类块（董事长/CEO 分设句、分级董事会一级候选人数、分组标题、"每位候选人现为董事"等）可以直接引用这些规则，也可以不同意并说明。最新年 Enphase、Lumen、Macy's、Marriott 的值按新裁定与读者判读不一致，#47 已撤回这四个值（`C02_*_UNIFIED_ADJUDICATION_DISAGREES`）；后续选择器修复按类别逐项提交，仍标 `[shared-with-#28]` 并在上表登记。

**#28 的内容核对引出的两处补充（读到 `34338e4e` 之后）。** #28 对它自己 Salesforce FY2026 结果的核对指出两处错，本方的量测也有同样的缺口：一是 JOIN 句式只认动词，没认名词写法（"prior to Mr. Munoz's appointment to the Board in January 2022"）；二是读者把一块记为"已被覆盖"，量测就照单全收，而被引用的块只写了现任主席、另一人的月份和费用季度。补上之后统一裁定共 16 条规则（原文误记为 17 类）：JOIN 增加名词写法，新增 `DATED_ROLE_CHANGE`（带日期的职务接任，只由写明同一变动的块覆盖，读者的引用被拒时由裁定替换）。在全部 37 份判读上只多三条裁定（Salesforce FY2026 第 4300、933 块，Macy's FY2024 第 2358 块），只移动 Salesforce FY2026 一个位置（见下表第 14、15 行）。
