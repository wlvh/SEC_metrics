# C02 选择器修复（共用，[shared-with-#28]）

27 个往年位置的双向判读与当前选择对比（`../c02-older-years/comparison.json`）：26 个不一致，49 个误选块、256 个漏选块。这里按"一个边界清楚的问题"逐个修，每个问题一节：问题、成因、改动、用例与注错、在全部 37 份判读上的量测。选择器是 `scripts/vnext/historical_board_composition.py`（#47 规则文件，改动后重铸 `issue_47_v1`）；合并 `2cc97e3a` 起它在 `historical_board_composition_v2.py`，原路径保留 #28 绑定的 `546d10d1` 字节（`../collab-28/README.md`“选择器路径”），之后各节改的都是 `_v2`。

## 量测方法

`measure.py` 对每个有判读的位置，把选择器在 `--base`（修复前的提交）与工作树（修复后）各跑一次，两次的选择都交给 `tools/read_c02_composition.read_position` 按该位置的判读核对，列出每个移动的块及判读对它的结论，以及每个位置修复前后的问题。37 个位置：27 个往年（`../c02-older-years/judgements/`，从获取导出恢复的根读）与 10 个最新（`../c02-composition-facts/judgements/`，从检出读）。治理文档由路线自己的输入准备构建，一次写进 `--documents`（检出之外）重复使用。

一处修复只应移动它针对的那些块。它移动的任何别的块，不论判读读没读过，都列在量测里。

判读的局限照旧：每个位置一位同族子代理读者，不是人工验收；这 27 份判读被用来定位并检查修复，所以对这些修复只算开发与回归材料，不是留出验证。

## 1. 委员会主席句式把小写词当成委员会名

**问题。** Macy's 四个往年代理（2022-01-29、2023-01-28、2024-02-03、2025-02-01 对应的四份）在"首席独立董事的遴选标准"里都有一条 "●Previous service as a Board committee chair"。它说的是挑人的标准，没有说谁在任何委员会任主席，四位读者都判为不是构成事实；选择器却以 `COMMITTEE_COMPOSITION_STATEMENT` 取了它（块 1089、1150、1217、1083）。

**成因。** 匹配 "as <委员会名> committee chair" 的模式用 `[A-Z]` 要求委员会名的每个词大写开头，但整条模式带 `re.I`，于是 `[A-Z]` 也匹配小写字母，"as a Board committee chair" 里的 "a Board" 被当成了委员会名。同一模块里其他需要大写的地方都写成了 `(?-i:[A-Z])`，只有这一处漏了。

**改动。** 这一处改为 `(?-i:[A-Z])`。

**用例与注错。** `tests/vnext/test_historical_board_composition.py` 的 `test_a_criterion_for_choosing_a_chair_seats_no_one`：这条标准不陈述任何事实；"serves as Audit Committee chair"、"appointed as our Compensation Committee chair" 仍按委员会构成读出。只撤回模块改动时该用例失败、其余照旧。注错 `A_LOWER_CASE_WORD_NAMES_A_COMMITTEE`（改回 `[A-Z]`）记在 `../c02-composition-facts/fault-injections.json`，由这条用例抓到。

**量测**（`measured-1-capitalised-committee-name.json`，base `024864d8`）：37 个位置里只有 Macy's 这四个位置有块移动，移动的正是上面四块，全部是判读判为"不是事实"的块，都从选择里去掉了。误选 49 → 45，漏选 256 不变，不一致的位置仍是 26 个（这四个位置都还有别的问题：漏选 48、1+1、3、2）。最新十个位置的选择一块未变。

**对结果的影响。** 这四个坐标的缺陷登记（`../known_result_defects.json`，`C02_MACYS_*_OLDER_YEAR_READING_DISAGREES`）记下这一处已修、其余问题仍在，坐标继续撤回；没有任何结果因此重新获得信用。

**不主张。** 只修了这一条模式。像"遴选标准清单"这样整段在描述标准而不是事实的写法，别的公司可能用别的措辞写，那要另外的问题去处理。

**顺带修的一个工具缺陷。** `../c02-composition-facts/fault_injections.py` 把被改的模块写进临时目录运行，而模块从 2026-09-29 起改为相对自身位置读取 `catalog/r6/C02_board_composition_terms_v1.json`，临时副本找不到它，对照运行一个用例都跑不起来，脚本在对照处停下（没有给出任何错误结论）。现在把临时副本放在 `scripts/vnext/` 的同样层级下并带上这份目录文件，子进程另用新建的字节码目录。重跑：对照 43 例全过，31 个注错全部由点名用例抓到。

## 2. 名单前的项目符号不在选择器认得的字符里

**问题。** 判读里漏选最多的两个位置：Ford 2022-12-31 对应的代理漏 57 块，Macy's 2022-01-29 对应的代理漏 48 块。其中大部分是委员会页面上的成员名单：委员会名、"MEMBERS" 标签、"某某, Chair"、每位成员一块。

**成因。** 这两份代理在名单的每个名字前单独印一个项目符号：Ford 用 "◾"（U+25FE），Macy's 用 "·"（U+00B7）。选择器只把 `_BULLET_CHARS` 里的字符当成可以跨过的符号，这两个都不在里面，于是名单在第一个符号处就结束，一个名字都没读到。37 份文档里单独成块的符号逐个数过：这两个分别出现 282 次和 244 次，别的未收录符号里，"⚫"（78 次，Macy's）与 "○"（8 次）加进去一块都不移动，所以不加；一条没有例子检验的规则不写进来。

**改动。** `_BULLET_CHARS` 加上 "◾" 与 "·"。名单、卡片条目、引导句后的列表都用这一个字符集。

**用例与注错。** `test_historical_board_composition.ACommitteePageIsReadAsAStructure.test_a_roster_marked_with_each_glyph_filings_print`：两个符号各两种版式（带 "MEMBERS" 标签、委员会名后直接是名单），名单都读出、主席标注读成主席。只撤回模块改动时四个子用例全部失败。注错 `THE_SQUARE_BULLET_IS_NOT_A_BULLET`、`THE_MIDDLE_DOT_IS_NOT_A_BULLET` 各去掉一个符号，都由这条用例抓到；注错总数 33/33，对照 44 例。写用例时第一版把名单后的结尾块写成 "Duties"，它是一个大写开头的单词，被读成人名；真实文件里名单后是 "Key Responsibilities" 这类块，改的是用例。

**量测**（`measured-2-bullet-glyphs.json`，base `58641f01`）：只有这两个位置有块移动，全部是新增、全部是判读判为事实的块：Ford 43 块（五个委员会页面的标题、标签、主席与成员），Macy's 24 块（四个委员会页面的标题与成员）。漏选 256 → 175，误选 45 不变；最新十个位置不变。Ford 还漏 17 块（成员矩阵的标题、表头与 "Chair" 格，几张卡片），Macy's 还漏 7 块（卡片上的主席标注等），两个坐标继续撤回。

**不主张。** 选择器有意不重建丢了列位置的成员矩阵（模块说明里写着）；现在 "◾" 是项目符号了，如果某份文件在委员会标题后直接印一个每格只有一个 "◾" 的矩阵，名字那一列会被当成名单读。37 份文档里没有这种排版，所以没有写防护，也没有例子检验它；遇到时要补的是这条防护。

## 3. 写成句子的成员名单整行读不出

**问题。** Marriott 两份往年代理（2021-12-31、2022-12-31 对应）的委员会页面写的是 "Current Members: Frederick A. Henderson (Chair), Debra L. Lee, and Aylwin B. Lewis."：一句话，末尾有句号，最后一个 "and" 前有逗号。选择器认得 "Members:" 行，但这一行整行没读出来，委员会标题也就没取。

**成因。** `name_list` 按逗号、"and"、分号切开后要求每一段都是人名。"and" 前的逗号让最后一段变成 "and Aylwin B. Lewis."：开头的 "and" 是治理用词，末尾的句号又让最后一个词不像名字。两样里任何一样都让整行失败。

**改动。** 切分时把 ", and" 当成一个分隔；整行末尾的一个句号先去掉，但前一个字符是大写字母时不去（"John B." 的句号属于缩写）。名单之外的话仍然读不成名单。

**用例与注错。** `test_historical_board_composition.ACommitteePageIsReadAsAStructure.test_a_members_line_written_as_a_sentence`：这一行读成成员名单、标题读成委员会标题；"Members: see the table on page 12." 仍不是名单。只撤回模块改动时该用例失败。注错 `A_SERIAL_COMMA_ENDS_A_LIST`、`A_FINAL_PERIOD_ENDS_A_LIST` 各去掉一半，都由这条用例抓到；注错总数 35/35，对照 45 例。

**量测**（`measured-3-sentence-member-lists.json`，base `e95dd9a3`）：只有 Marriott 两个往年位置移动，全部新增、全部是判读判为事实的块：2021 年 6 块、2022 年 8 块（各委员会的标题与成员行）。漏选 175 → 160，误选 45 不变，最新十个位置不变。2022 年的卡片字段原来也算漏选，现在由新取的成员行覆盖，所以那一年的漏选从 15 降到 3。两个坐标仍有别的问题（2021：董事长与 CEO 分设、新董事加入、执行委员会名单；2022：董事长与 CEO 分设、两张卡片字段，另有 4 个误选），继续撤回。

**不主张。** Marriott 2021 的执行委员会名单 "J.W. Marriott, Jr. (Chair), ..." 还读不出：逗号把 "Jr." 切成了一段，"J.W." 也不是选择器认得的名字写法。让叠写的首字母算名字，会让 "U.S." 这类缩写组成的词组也被当成人名，这需要单独量过再改，这一处没有做。

## 4. 卡片上没有标签的委员会条目

**问题。** Enphase 的董事卡片在 "Director since May 2010" 之后一行一个委员会（"Audit Committee"、"Nominating and Corporate Governance Committee (Chair)"），前面没有 "Committees:" 标签。选择器只认带标签的卡片，这些条目一条都没取。成员关系多半能从委员会页面的名单读到，读不到的是主席标注：三个往年位置各漏一到两条（谁任提名与治理委员会主席、谁任审计委员会主席）。

**成因。** `_cards` 只从 "Committees:" 标签开始读条目。

**改动。** 新增 `_unlabelled_card_items`：在任期或年龄字段（与 `_designations` 用的同一个 `_CARD_EVIDENCE`）之后，连续的非强调、非链接块，每一块都必须是本文件自己的一个委员会（与带标签卡片的条目同一个判断 `_card_item`），中间只许空白和项目符号；卡片必须能找到它的董事名（与带标签卡片同一个 `_card_name`），找不到就整张不取。委员会页面的标题是强调块，会结束这一串。

**用例与注错。** `test_historical_board_composition.ADirectorCardIsReadOnlyWhenItNamesItsDirector.test_unlabelled_committees_on_the_lines_after_the_tenure`：条目与董事名都读出；强调的委员会标题不算条目；找不到董事名的卡片不取。只撤回模块改动时该用例失败。注错 `AN_EMPHASISED_HEADING_IS_A_CARD_ITEM`、`UNLABELLED_ITEMS_NEED_NO_DIRECTOR`、`UNLABELLED_CARD_ITEMS_UNREAD`，都由这条用例抓到；注错总数 38/38，对照 46 例。

**量测**（`measured-4-unlabelled-card-items.json`，base `77532c65`）：移动的是 Enphase 的四个位置，全部新增、全部是判读判为事实的块：2022、2023 各 15 块，2024 有 19 块，**最新年份 2025 也有 19 块**。漏选 160 → 156（主席标注），误选 45 不变，其余公司不变。

**最新年份的值会变。** Enphase 2025 的选择多了 19 块。判读把它们都判为事实（原来是"别处已陈述"的冗余事实），所以这个位置仍与判读一致；但值（摘录集合）变了，已接受的那个值只对应旧结果。下一次在新版本下运行时，这个位置要用 `tools/read_c02_composition.py --runs-root … --closure …` 重新核对接受，在那之前它在覆盖表里读作"接受与这个结果不符"，这是如实的状态。#28 若接入这处修复，它最新年度 Enphase 的 C02 值同样会变。

**还剩的。** 这三个往年坐标还有别的问题（各一到两条传记里的加入日期、2023 年审计委员会设立网络安全小组，以及选举议程、分级名单标题、董事薪酬引导句等误选，后几类读者之间判断相反，要先按类裁定），继续撤回。

## 5. 名字中间带引号昵称的董事

**问题。** Lumen 的代理把一位董事印成 "Steven T. “Terry” Clontz"，Marriott 2022 年的执行委员会成员行里有 "Frederick A. “Fritz” Henderson"。这样的名字一个都读不出：他的卡片条目没取，委员会名单读到他就结束，后面的成员也一起漏掉；Marriott 那一行整行读不出。

**成因。** `person_name` 拒绝含引号的块，昵称的引号让整个名字不成立。

**改动。** `_strip_name` 先去掉夹在名字两个词之间的引号单词（`_NICKNAME`：引号里是一个大写开头的词，前后都还有词）。只在两个词之间才算昵称，所以定义词（"“Board” means"）、末尾的引号词（"Recovery “Clawback”"）都不受影响。

**用例与注错。** `test_historical_board_composition.ANameIsTheWholeBlock.test_a_quoted_nickname_between_the_names`：两种引号的昵称名字成立；定义词、末尾引号词、"Definition of “Cause”:" 仍不是名字；带昵称成员的名单整串读出。只撤回模块改动时该用例失败。注错 `NICKNAMES_STAY_IN_THE_NAME`（不去昵称）、`ANY_QUOTED_WORD_IS_A_NICKNAME`（去掉"后面还有词"的条件）都由这条用例抓到；注错总数 40/40，对照 47 例。

**量测**（`measured-5-quoted-nicknames.json`）：Lumen 2021、2022、2023 各 5 块，Marriott 2022 有 2 块，全部新增、全部是判读判为事实的块。漏选 156 → 146，误选 45 不变，最新十个位置不变（Lumen 2025 也有这个名字，但只出现在薪酬表里，带脚注编号，不在任何被读的结构里）。四个坐标还有别的问题，继续撤回。

## 6. 管理层委员会被当成董事会委员会

**问题。** 四份往年代理用描述董事会委员会构成的句式描述管理层委员会：Lumen 的 "Diversity and Inclusion Steering Committee … is made up of senior leaders and executives"（2021、2022 两年），Pfizer 的 PAC Steering Committee "composed of Pfizer employees" 与 Political Contributions Policy Committee "co-chaired by the Chief Corporate Affairs Officer and …"，Marriott 的 Global Operating Committee "which consists of senior Company leaders"。判读都判为不是董事会构成，选择器以 `COMMITTEE_COMPOSITION_STATEMENT` 取了它们。

**成因。** 构成句式（composed of、made up of、consists of、chaired by）不看成员是谁。这些委员会的名字也不能拿来判断：Lumen 的代理把 "Diversity and Inclusion Steering Committee" 印成过标题，选择器从标题收集的委员会名里就有它，所以"不在本文件委员会名单里"这条判据不成立。

**改动。** `_MANAGEMENT_MEMBERS`：构成句的成员列表一开头就是管理层角色（leaders、executives、officer(s)、employees、associates、management），前面只允许限定词、"senior"、公司名或大写的头衔词，整句不算董事会委员会构成。"composed entirely of independent directors who are not officers"、"three directors, none of whom is an officer"、"chaired by the Chairman of the Board" 不受影响。

**用例与注错。** `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_committee_of_management_is_not_the_board_s`：四种原句都不陈述构成事实；三种董事会委员会的写法仍读出。只撤回模块改动时四个原句子用例失败。注错 `MANAGEMENT_SEATS_A_BOARD_COMMITTEE`（去掉这条判断）、`ANY_WORDS_OPEN_THE_MEMBER_LIST`（成员列表开头放宽为任意词）都由这条用例抓到；注错总数 42/42，对照 48 例。

**量测**（`measured-6-management-committees.json`）：只移走这 5 块（Lumen 2021、2022 各 1，Marriott 2021 有 1，Pfizer 2022 有 2），全部是判读判为非事实的块。误选 45 → 40，漏选 146 不变，最新十个位置不变。四个坐标仍有别的问题，继续撤回。

**不主张。** Lumen 的"由董事会主席、各委员会主席与 CEO 组成的临时遴选委员会"（search committee）不属于这一类（成员是董事与 CEO），仍按原样取，判读判为流程描述，属另一个问题。

## 7. 董事长与 CEO 是否分设的陈述

**问题。** "the Board has chosen to separate the roles of Chairman of the Board and CEO"、"Our Chairman and CEO functions currently are performed by a single individual" 这类句子说的是董事会主席与 CEO 是两人还是一人，不点名。往年读者在五家公司 31 块上都判为事实，最新年 Ford、Macy's、Enphase 的读者也取了，最新年 Lumen、Marriott 的读者没取同样的句子。统一裁定（`../c02-composition-facts/adjudicate.py` 的 `CHAIR_CEO_STRUCTURE`）判为事实；选择器只认点名的主席句（"X serves as Chairman"），这类句子一句也没取。

**改动。** `_CHAIR_CEO_STRUCTURE`：句中有分设或合并（separate、split、combine）紧挨着"Chairman/Chair（of the Board）与 CEO/Chief Executive Officer"这一对，或这一对角色后面跟着 separate、combined、single individual、same person 等，标为 `BOARD_LEADERSHIP_STATEMENT`。两种选择都提到的（"separating or combining"）和讲政策或股东提案的不算。规则与裁定的类别定义相同，但写在选择器自己的模块里，裁定不读选择器。

**用例与注错。** `test_historical_board_composition.ALeadershipOrMembershipFactNamesThisBoardAndThePerson.test_whether_the_chair_and_the_chief_executive_are_one_person`（四种原句）与 `test_a_choice_a_policy_or_a_proposal_states_no_structure`（两种选择都提、政策、提案三种不算；三句都不会在前面被当作要求或假设句排除，所以每一句都真正走到这条规则）。只撤回模块改动时四个原句子用例失败。注错 `THE_CHAIR_CEO_STRUCTURE_STATES_NOTHING`、`NAMING_BOTH_CHOICES_STATES_A_STRUCTURE`、`A_POLICY_OR_A_PROPOSAL_STATES_A_STRUCTURE`。

**量测**（`measured-7-chair-ceo-structure.json`，在统一裁定之上）：新增的块全部是判读判为事实、或统一裁定判为事实的块，没有移走任何块。漏选 144 → 118，误选 46 不变，不一致的位置 28 → 26。最新年 Lumen、Marriott 由不一致变为一致；Pfizer FY2022 取了 723 一块（董事会决定继续由 Bourla 兼任主席与 CEO），读者为它列为同一事实的 16 块随之不再算漏选。最新年 Ford、Macy's 的选择也多了一两块（判读本来就判为事实），已接受的值只对应旧结果，下一次运行后要重新读过才接受。

**不主张。** 点名的兼任句（"Bourla, Chairman and CEO"）原来就由点名规则处理，这里不改；只说分设历史的句子（"separated the roles in 2012"）同样被取，与读者一致。

## 8. 分级董事会一级候选人数不是董事会规模

**问题。** Enphase 的董事会分为三级，每年只改选一级。"To elect our three nominees for director"、"Our Board of Directors has nominated three directors to serve for three-year terms"、"Election of our three nominees as Class II directors" 说的是这一级的候选人数，选择器以 `BOARD_SIZE_STATEMENT` 取了它们。往年四位读者判为非事实，最新年读者判为事实；统一裁定（`CLASSIFIED_SLATE_COUNT`）判为非事实：它既不是董事会规模，也不是成员变动。董事全员每年改选的公司，同样的话就是董事会规模，每位读者都取了。

**成因。** 规模句式分两类却混在一张表里：一类直接说规模（"the Board consists of nine directors"），一类说参选人数（"to elect N nominees"）。另外，直接说规模的那一条允许"has"与人数之间隔 30 个字符，"has nominated three directors"也算"has three directors"。

**改动。** 参选人数的句式移到 `_SLATE_SIZE`，只在董事会不分级时算规模；文件里出现"Class II Directors"、"classified board"或"divided into three classes"即为分级。直接说规模的句式不再允许中间夹着 nominate、elect、propose。

**用例与注错。** `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_on_a_classified_board_the_slate_is_not_the_board_s_size`（三种原句在分级时不算规模，不分级时算；"currently has seven members"两种情形都算）与 `test_the_filing_says_whether_its_board_is_classified`（同一句话在出现级别标题的文件里不取、没有时取）。撤回模块改动时这些用例失败。注错 `A_CLASSIFIED_BOARD_STILL_COUNTS_ITS_SLATE`、`NO_FILING_IS_CLASSIFIED`、`HAS_NOMINATED_COUNTS_AS_THE_BOARD_S_SIZE`；注错 48/48，对照 52 例。

**量测**（`measured-8-classified-slate.json`）：只移走 Enphase 五个位置的这 12 块，全部是判读或统一裁定判为非事实的块，其余公司一块不动。误选 46 → 34，漏选 118 不变。最新年 Enphase 的值随之变化（仍有三个级别标题被取，待第 9 项）。

## 9. 董事分组标题不取

**问题。** Enphase 的董事表按级别分组，每组上方印着"Continuing Class III Directors (Until 2027 Annual Meeting of Stockholders)"、"Class II Nominees for Election (Until 2029 …)"；Lumen 2024 的董事薪酬表上方有"Continuing Directors:"。选择器把这些标题连同其下的名字一起取了。读者判断相反（Enphase 2022、2025 与 Lumen 2024、2025 取了，Enphase 2021、2023、2024 与 Macy's 各年没取），统一裁定（`DIRECTOR_GROUP_HEADING`）判为非事实：标题说的是级别、是否参选与任期，与任期年限同类；董事是谁由下面的名字说明。

**改动。** `_director_groups` 仍用标题找到表格，但只取表里的名字，不取标题本身。一个标题下只有一个名字时那是卡片的开头，不是表格，名字照旧留给卡片规则。

**用例与注错。** `test_historical_board_composition.ACardOrTableStatesWhoAndWhat.test_a_table_of_directors_by_class_and_not_a_card_under_a_heading` 改为要求取两个名字、不取两个标题，并补一条：卡片上方标题下的单个名字不算表格成员。撤回模块改动时该用例失败。注错 `THE_GROUP_HEADING_IS_TAKEN_AGAIN`；原有注错 `ONE_NAME_MAKES_A_TABLE` 的目标代码随之改动，已改为针对新代码，并由新补的断言抓到。注错 49/49，对照 52 例。

**量测**（`measured-9-group-headings.json`）：只移走 13 个分组标题（Enphase 四年各 3 个、Lumen 2024 一个），全部是读者或统一裁定判为非事实的块，名字一个不少。误选 34 → 21，漏选 118 不变，不一致位置 26 → 24：Enphase 2024 与最新年 Enphase 恢复一致。

## 10. "每位候选人现为董事"

**问题。** Macy's 每年的代理都写"Each nominee is currently a member of the Board"。它的董事全员每年改选，这句话说的是候选名单就是现任董事会。五份判读里只有 2024 年的读者取了，统一裁定（`NOMINEES_ARE_SITTING_DIRECTORS`）判为事实，理由与"非分级董事会的候选人数即规模"相同。选择器没有取。

**改动。** `_SITTING_SLATE`：每位/全部候选人"现为本董事会成员/现为董事"标为 `BOARD_ROSTER_STATEMENT`；后面接"of <别的机构>"的（"a member of the board of directors of another public company"）不算。

**用例与注错。** `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_slate_of_sitting_directors_says_who_the_members_are`（两种原句取；同意参选、别家董事会、任期句不取）。撤回模块改动时该用例失败。注错 `A_SITTING_SLATE_STATES_NOTHING`、`ANOTHER_BOARD_SEATS_THE_SLATE`；注错 51/51，对照 53 例。写用例时自己举的反例（别家公司的董事会）暴露了第一版会把它也读成本董事会，已收紧后再量。

**量测**（`measured-10-sitting-slate.json`）：只在 Macy's 五个位置各新增这一块，漏选 118 → 113，误选 21 不变，最新年 Macy's 恢复一致。

## 11. 由具名董事组成的董事会工作组

**问题。** Macy's 2022、2023 年代理在委员会一节里有"Digital Innovation Task Force"及"The Digital Innovation Task Force is made up of three directors, Torrence Boone, Ashley Buchanan and Tracey Zhen, and senior members of our digital … teams"。2022 年读者判为事实，2023 年读者没取同样两块；统一裁定（`BOARD_TASK_FORCE`）判为事实：由具名董事组成的董事会机构，属委员会设置与成员。选择器只认"committee"，没有取。

**改动。** `_TASK_FORCE_MEMBERS`：工作组"由 N 名董事组成"且句中写出人名，标为委员会构成陈述；只有管理层成员的工作组（"made up of senior leaders"）没有董事人数，不算。`_task_force_titles`：只有当上方三块内的标题正是这句话里的工作组名时才取标题。

**用例与注错。** `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_task_force_of_named_directors_is_a_body_of_the_board`（原句取；管理层工作组不取；标题取；别的工作组标题不取）。撤回模块改动时该用例失败。注错 `A_TASK_FORCE_STATES_NOTHING`、`A_TASK_FORCE_TITLE_IS_NOT_TAKEN`、`ANY_TASK_FORCE_TITLE_HEADS_THE_MEMBERS`；注错 54/54，对照 54 例。

**量测**（`measured-11-task-force.json`）：只在 Macy's 2022、2023 各新增标题与成员句两块，漏选 113 → 109，误选 21 不变。

## 12. 出席情况里给出的上年董事会人数

**问题。** Ford 2021、2022 年代理写"Last year, of the twelve then current members of the Board, twelve attended the virtual annual meeting"。它给出上年股东会时董事会的人数。2021 年读者取了，2022 年读者没取同样的句子；统一裁定（`DIRECTOR_COUNT_ON_A_DATE`）判为事实：某日的董事人数，不论印在哪里。选择器把讲出席的句子整句排除了（出席不是构成事实）。

**改动。** `_THEN_CURRENT_MEMBERS`："of the N then-current members of the Board / directors"标为规模陈述，与股权计划资格里的非雇员董事人数一样，在排除话题之前判断。没有人数的"All then current directors attended"不算。

**用例与注错。** `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_the_board_s_size_on_a_past_date_wherever_it_is_printed`。撤回模块改动时该用例失败。注错 `A_PAST_COUNT_IS_SET_ASIDE_WITH_ATTENDANCE`；注错 55/55，对照 55 例。

**量测**（`measured-12-past-board-size.json`）：只在 Ford 2021、2022 各新增这一块，漏选 109 → 107。

## 13. 董事加入日期按目标年度判断

**问题。** 有些句子写了董事何时加入董事会："who joined our Board in February 2020"、"has served as Chief Executive Officer and a director of the Company since February 2021"、"who joined our Board on February 25, 2021"。选择器原来不看日期：凡是 "joined our board" 都当成员变动取，凡是 "has served as … director since …" 都不取。统一裁定按目标年度分成两类。加入日期在目标年度之前，是任期的另一种说法，与卡片上的 "Director since" 同类（JOIN_BEFORE_THE_YEAR，非事实）。加入日期在目标年度之内或之后，是该年度董事会成员的变动（JOIN_IN_THE_YEAR，事实）。按这个口径，有三块误取、两块漏取：
- 误取：Enphase 2021、2022 的董事薪酬段（Malchow 2020 年加入）；Lumen 2022 的持股指引例外（Allen 2021 年、Jones 2020 年加入）。
- 漏取：Marriott 2021 的 CEO 在 2021 年 2 月加入董事会；Goren 在 2022 年 3 月加入。

**成因。** 选择器的输入只有治理文件本身，不知道目标年度。代理文件的 reportDate 有时是股东会日期，有时为空，不能代替目标年度。

**改动。**
- `board_composition_facts` 增加必填参数 `period_start`，即目标年度第一天，ISO 日期。路线传 target 的 `period_start`；提案里记下 `join_dates_judged_from`。
- `_DATED_JOIN` 识别带日期的加入句式。日期只印月份时按该月月末算，只印年份时按年末算：文件没说加入早于年度，就不当作早于。
- 加入日期在年度第一天之前：这一段不再让成员变动规则成立，句中其他变动照常算。
- 加入日期在年度之内或之后：标为成员变动。这项判断放在排除话题之前，与上年人数一样，所以写在薪酬段落里也取。
- 日期不合法时按名拒绝（`C02_COMPOSITION_PERIOD_START_INVALID`）。
- **接口变化**：调用方必须传目标年度。#28 若接这一版，需要在它的 `_prepared` 里传 `target["period_start"]`。

**用例与注错。** `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard` 的四条用例：
- `test_a_join_dated_before_the_year_is_tenure`：两种原句在加入之后的年度不取，在加入当年取；同句另有变动时照取；不带日期的加入照旧取。
- `test_a_join_dated_in_the_year_is_a_change`：CEO 原句当年取、次年不取；薪酬句里的当年加入取；别家董事会不算。
- `test_a_join_is_dated_as_precisely_as_it_is_printed`：52/53 周年度从 1 月 30 日开始，印了 1 月 15 日算年度前，只印 1 月算年度内。
- `test_the_target_year_is_a_date_and_the_proposal_names_it`：四种坏日期按名拒绝；提案记下目标年度。

六个注错都由为它写的用例抓到：`A_DATED_JOIN_COUNTS_IN_ANY_YEAR`、`AN_IN_YEAR_JOIN_STATES_NOTHING`、`A_JOIN_IN_A_PAY_SENTENCE_IS_SET_ASIDE`、`A_PRINTED_DAY_IS_IGNORED`、`A_MONTH_ALONE_IS_PLACED_AT_ITS_START`、`ANY_TARGET_YEAR_IS_ACCEPTED`。注错 61/61，对照 59 例。

**量测**（`measured-13-joins-by-period.json`）：
- 移走 Enphase 2021、2022 与 Lumen 2022 三块，统一裁定都判为非事实。
- 新增 Marriott 2021 两块：613 由统一裁定判为事实，842 由读者判为事实。
- 误选 21→18，漏选 107→105。
- **最新年 Paramount 2025 新增 8 块**：都是 "Ms. Byrne has served as a member of our Board since August 2025" 这类履历块，即 2025 年组成的新董事会成员，读者都判为含事实的混合块。该位置的选择仍与判读一致，但值会变；重算之后要重读，才能接受。

**这次顺带修正了量测工具。** `measure.py` 的 `base_matches_route` 拿 `--base` 的选择去比缓存里路线当时的选择。缓存是在更早的选择器版本上建的，所以第 1–12 节的量测文件里，有 26 个位置这一项是 false，退出码因此是 1。原因是比较对象过时，不是规则不符。现在缓存记下建它时选择器的哈希：与 `--base` 相同才比较，否则记为 null；只有真比出差别时，退出码才是 1。

**不主张。** 选择器识别加入日期的句式，与统一裁定 JOIN 规则的句式写法相同。所以在这些句式上两者一致是写法相同造成的，不是独立验证；主要依据仍是读者的原判。

## 14. 写成名词的加入日期

**问题。** #28 在 `9f8b855f` 核对它自己 Salesforce FY2026 的 C02 结果，发现第 4300 块被取了。这一块讲的是关联方雇员，唯一与本董事会有关的话是"prior to Mr. Munoz's appointment to the Board in January 2022"。对 FY2026 来说，这是年度之前的加入，属于换了说法的任期（JOIN_BEFORE_THE_YEAR）。本方已接受的 Salesforce FY2026 值发布的是同样 63 块，也带着这一块。

**成因。** 统一裁定的 JOIN 句式和第 13 节的 `_DATED_JOIN` 只认动词写法（"was appointed to the Board in …"），没有认名词写法。所以统一裁定从没判到 4300，读者的"混合（含事实）"就一直成立；选择器则按"X’s appointment to the Board"把它当成员变动取。

**改动。** 选择器与统一裁定都补上同一个名词写法："appointment/election to the Board in/on/effective <日期>"。统一裁定重跑后只多一条：Salesforce 2026 第 4300 块，非事实（`../c02-composition-facts/adjudication.json`）。

**用例与注错。** `test_a_join_written_as_a_noun_is_dated_too` 覆盖四种情形：原句在 FY2026 不取、在 2021 年度取；薪酬句里的年度内名词加入取；不带日期的名词照旧取。注错 `A_NOUN_FORM_JOIN_IS_NOT_DATED` 由这条用例抓到；注错 62/62，对照 60 例。

**量测**（`measured-14-noun-form-joins.json`，用的是新的统一裁定）：只有 Salesforce 2026 一个位置移动，其余 36 个位置一块不动。
- 移走 4300。
- 新增 919："upon their appointment to the Board in July 2025, Ms. Chang and Mr. Kirk each received a prorated RSU grant"，是年度内的加入，读者判为含事实。
- 误选 19→18，不一致位置 24→23。

**还没修的。** #28 指出的另一处是第 933 块："On March 21, 2025, Mr. Donald assumed the role of Lead Independent Director, and Mr. Roos assumed the role of Chair of the Governance Committee"。它没被取，读者又把它算作已被现任主席名单（773）、Donald 的月份（665）和费用季度（964）覆盖。这些块都没有说 Roos 何时接任，所以量测仍报这个位置"一致"——这正是 #28 指出的错。坐标继续撤回，这一处留给下一节。

## 15. 带日期的职务接任，以及什么才算"已覆盖"

**问题。** 第 14 节留下的第 933 块写在董事薪酬表的说明里："On March 21, 2025, Mr. Donald assumed the role of Lead Independent Director, and Mr. Roos assumed the role of Chair of the Governance Committee."。它是 Salesforce FY2026 唯一写明 Roos 何时接任治理委员会主席的一块。选择器不认 "assumed the role of"，没有取。读者判它含事实，但记为已被 665、962、964、3091 覆盖，而这四块都没有说出这次变动：
- 665 只给 Donald 接任的月份；
- 962 只讲 Donald；
- 964 是 Roos 按季度领取的费用；
- 3091 讲的是 Washington 卸任。

量测原来的规则是"读者引用的块里有一块被选中就算覆盖"，所以一直报这个位置一致。

**改动（量测一侧）。** 统一裁定新增一类 `DATED_ROLE_CHANGE`（事实）。一句话写明某位董事在目标年度内或之后的某天，接任董事长、首席独立（主持）董事或某委员会主席，就是一次职务变动。只有写明同一人、同一职务、同一次变动，且日期至少一样精确的块，才算覆盖它；以下几种都不算：只写现任者，写另一人的变动，本句给了日而另一块只给月份，讲费用对应的季度。读者已判为事实、却引用了不覆盖它的块时，裁定替换读者的引用，`read_position` 按裁定判断是否覆盖。

在 37 份判读上，统一裁定只多两条：
- Salesforce FY2026 第 933 块：没有任何块覆盖它。
- Macy's FY2024 第 2358 块（"Mr. Spring was appointed Chairman in April 2024"）：读者引用了 18 块，裁定只认第 1044 块（"On April 10, 2024, … Mr. Spring began serving as Chairman of the Board"）。1044 已被选中，所以 2358 不算漏选。

年度之前的变动按任期处理，不作裁定，例如 Lumen FY2021 的 "Effective May 20, 2020, Mr Glenn became … Chairman"。

**改动（选择器一侧）。** "assumed / took over / took on the role (position) of" 后面接董事长、首席独立董事或主持董事的，标为领导职务陈述；接某委员会主席的，标为委员会构成陈述。

**用例与注错。**
- 选择器：`test_taking_over_a_chair_or_the_lead_role`。933 原句两种标签都有；别家公司的委员会、非董事会的职务都不算。注错 `TAKING_OVER_A_COMMITTEE_CHAIR_IS_NOT_READ`、`TAKING_OVER_THE_LEAD_ROLE_IS_NOT_READ` 都被这条用例抓到；注错 64/64，对照 61 例。
- 统一裁定与判读工具：`test_historical_board_composition_filings.ADatedRoleChangeIsCoveredOnlyByTheSameChange`。它检查规则对每一块的覆盖判断：读者的引用被裁定拒绝后，该块算漏选；选中后不算。注错 `A_READER_CITATION_STANDS_OVER_THE_ADJUDICATION`、`A_YEAR_COVERS_A_DAY`、`ANOTHER_PERSONS_CHANGE_COVERS`、`A_CHANGE_BEFORE_THE_YEAR_IS_DECIDED`。

**量测**（`measured-15-dated-role-changes.json`）：只有 Salesforce 2026 一个位置移动，新增 933。漏选 106→105（新裁定下，933 原本算漏选），不一致位置 24→23。至此，Salesforce 2026 的选择与判读、统一裁定一致。

**这个位置还剩什么。**
- #28 提到的第 4301 块（"prior to the dates that Oscar Munoz and Craig Conway joined the Audit Committee"，没有日期）按读者的判断保留：含事实，已由成员名单 743 覆盖。
- 第 962、3091 块讲的是同一次交接，933 被选中后由它覆盖。
- 坐标仍然撤回：已发布的结果是旧版本算的，要重算、重读之后，才能按结果编号释放。

**不主张。**
- 这两类问题是 #28 在一个位置上发现的；本节把它们写成规则，在全部 37 份判读上量，只在两个位置起作用。
- 读者是同族子代理，统一裁定由执行者按文字写成，两者都不是人工验收。
- 规则是看过这些材料之后写的，属于开发/回归材料，不是留出验证。

## 16. 年度内的加入也只由同一人的加入覆盖

**问题。** #28 在 `3a661897` 核对它自己 Paramount FY2025 的结果，发现 10-K/A 董事履历里写的本董事会任职起点没有入选，例如 "Ms. Byrne has served as a member of our Board since August 2025"、"Mr. Campion … since January 2026"。本方已接受的值（54 块）同样缺这些块。读者判它们含事实，但都记为已被第 84 块覆盖；84 是"董事会现有十人"的名单，没有写任何人何时加入。这与第 15 节是同一个缺口：读者的引用没有经过核对。

**改动（量测一侧）。** `JOIN_IN_THE_YEAR` 采用与 `DATED_ROLE_CHANGE` 相同的覆盖规则：只有写明同一人加入、日期至少一样精确的块才覆盖；读者引用了不覆盖的块时，裁定替换引用。加入的人取紧挨着加入短语之前的姓名（60 字符内）。加入短语前是 their、his、her 这类代词时，取它后面的姓名，例如 "upon their appointment to the Board in July 2025, Ms. Chang and Mr. Kirk …"。在 37 份判读上，新增的覆盖裁定都落在两个位置：Paramount 2025 的九块履历，和 Salesforce 2026 的第 919 块；其他位置没有新裁定。

**改动（选择器一侧）。** "has served as … a member of our Board since" 中间允许的长度由 60 字符放到 80，与统一裁定的 JOIN 句式一致。第 100 块中间夹着 "our Chief Strategy Officer and Chief Operating Officer and as"，共 62 字符，原来认不出。

**用例与注错。**
- 选择器：`test_a_long_title_before_the_join`；注错 `THE_JOIN_REACH_IS_SIXTY`。
- 统一裁定与判读工具：`test_historical_board_composition_filings.AJoinInTheYearIsCoveredOnlyByTheSamePersonsJoin`，覆盖三种情形：同一人、日期更精确的加入可以覆盖；名单不能覆盖；代词后面的人才是加入者。注错 `A_ROSTER_COVERS_A_JOIN`、`A_JOINER_IS_ANY_NAME_BEFORE_THE_PRONOUN`、`ANOTHER_PERSONS_JOIN_COVERS`。

**量测**（`measured-16-join-coverage.json`）：只有 Paramount 2025 一个位置移动，新增第 100 块；漏选 106→105（按新裁定，100 原本算漏选）。其余八块已在第 13 节取到，919 在第 14 节取到。这个位置的选择现与判读、统一裁定一致；坐标仍撤回，要等重算、重读。

**没有跟着改的。** #28 还把提名理由（"We believe Mr. Thornton is qualified to serve as a member of our Board because …"，第 168 块）算作董事资格认定。两份 C02 Spec 列举的资格认定是 financially literate、audit committee financial expert、non-employee director、没有成员是高管或雇员，并写明提名与评估程序不在口径内；本方读者也判它不是事实。这是含义问题，已在登记里记为待对齐，没有改选择器。

## 17. 具名董事的任期在年会上结束，是一次离任

**问题。** Lumen 2024 往年判读的漏选有 11 块，都挂在第 1506 块上："(6)The terms of Mr. Brown, Mr. Clontz and Ms. Siegel will end in connection with the election of directors at the 2025 annual meeting."。它是全文唯一点名三人离任的块；读者把离任时间线里的名字（565–570）、"Retiring Directors:" 标题（1494）和其下三行薪酬（1495–1497）都记为由它覆盖。选择器没取它，原因有两个：
- 离任句式只认 "term on the Board will end" 这种写法，不认 "X’s term ended …" 和 "The terms of X … will end …"。
- Lumen 2021、2022 的脚注把编号直接贴在称谓前（"6Ms. Boulet’s term ended …"）。"6Ms" 不构成一个词，"Ms." 的句点被当成句末，句子在人名前断开，选择器看不到这个人。

**改动（选择器一侧）。**
- 成员变动多一种句式：某人的任期（所有格、代词或 "terms of" 加称谓姓名）在年会或董事选举时已结束或将结束。
- 分句前，在贴着称谓的一两位数字后补一个空格。前面是 `$`、小数点、逗号或另一位数字时不补，所以金额和年份不受影响。

**改动（量测一侧）。** 统一裁定新增规则 `TERM_END_AT_A_MEETING`（事实），现共 17 条（AGENTS.md 与协作索引曾把第 15 节之后的 16 条误记为 17 类，已改正）。凡是看到过这类脚注的读者都判为事实，读者之间没有分歧。这一类是为没人看过的块写的：Lumen 2022 第 1315 块、2023 第 1644、1645 块，这三块不含所有者的词汇，不在判读池里，选择器取了它们之后量测会报"未读"。覆盖规则与第 15、16 节相同：只有写明同一批人离开、且年份相同（如果写了年份）的句子才算覆盖。不点名的"以下三位将退休"、"Retiring Directors" 标题和薪酬行都不算。
- 第一版把 Marriott 五年的 "Each of the following director nominees … their term of office will expire at the Annual Meeting" 也判成离任，读者都判它不是事实。这是整批候选人照常改选，没有人离开。现在提到候选人或提名的句子不在本类；只用代词、句中又没有恰好一人具名的，也不在本类。
- 裁定判"同一离任"按句子看，不按整块看。Lumen 2025 第 537 块先写 Glenn、Jones 在年会退休，后一句写 Fowler 2025 年 12 月辞职；按整块看，"2025" 会被误当成与 2026 年会冲突。

**用例与注错。**
- 选择器：`test_a_named_director_s_term_ending_at_a_meeting`、`test_a_footnote_number_printed_against_the_honorific`。注错 `A_TERM_ENDING_IS_NOT_READ`、`A_TERM_OF_ANYTHING_IS_A_PERSONS`、`A_GLUED_MARK_HIDES_THE_PERSON`、`AN_AMOUNT_IS_A_MARK`。第一版的第二个注错（在所有格一支里加 "the|a"）没有被抓到：它根本碰不到反例 "The term of the Amended Plan will end …"，因为那句在 term 和 will end 之间隔着 "of the Amended Plan"。真正挡住这句的是 "terms of" 之后必须跟称谓，改为去掉这一条件后被抓到。原注错 `LET_A_TITLE_S_PERIOD_END_THE_SENTENCE` 的目标行随之改写，测的性质不变。
- 统一裁定与判读工具：`test_historical_board_composition_filings.ATermEndingIsCoveredOnlyByTheSameDeparture`。注错 `A_HEADING_COVERS_A_DEPARTURE`、`ANOTHER_YEARS_DEPARTURE_COVERS`、`A_NOMINEES_TERM_IS_A_DEPARTURE`、`A_PRONOUN_TERM_IS_ANYONES`、`A_POSSESSIVE_NEED_NOT_BE_A_PERSON`。

**量测**（`measured-17-term-endings.json`）：只移动 Lumen 五年，新增的块读者都判为事实，或由新类判为事实。
- Lumen 2021：新增 1210、1211。1210 是贴编号的年度内加入句，同一处改动让它也被认出。
- Lumen 2022：新增 1315。
- Lumen 2023：新增 1644、1645。
- Lumen 2024：新增 1506、1507，11 块漏选全部消失，这个位置的选择现与判读、裁定一致。
- Lumen 2025：新增 1370、1373。两块原本就由已选的块覆盖，问题集不变。

合计漏选 105→91，误选 18 不变，不一致位置 23→22。Lumen 2025 是最新年度，值会变，但原值不缺事实，所以不撤回；重算后要重读。

**没有跟着改的。** 读者把在目标年度之前的离任（如 FY2024 判读中"At the 2021 annual meeting, Virginia Boulet retired from the Board"）也判为事实，选择器也取。这与 `JOIN_BEFORE_THE_YEAR`（年度之前的加入是任期，不是事实）看起来不对称。区别在于：加入日期说的是一位在任董事任职多久；离任说的是一位已不在任的人。所有者的口径只写"成员变动，写明人或日期"，没有限定期间，读者之间也没有分歧，所以本节不改。是否只计年度内的离任，是口径问题。

## 18. 带交叉引用链接的陈述仍按正文读取

**问题。** Ford 2024 往年判读有 21 块漏选，其中 18 块（九位独立董事在汇总表里的 "Independent" 和卡片上的 "Independent Director Since: …"）都引用同一个覆盖块：第 1590 块 "the Board determined that none of the following directors had any material relationship with the Company and, thus, are independent: Kimberly A. Casiano, …"。这是董事会对全部独立董事的认定，选择器给它打得出两个标签，却没有取。原因是这一块带链接：句末 "Our committee membership is as noted on page 9" 里的 "page 9" 是超链接，而正文循环跳过所有带链接的块。跳过链接块是为了排除目录这类导航行，但一句陈述里夹着交叉引用，并不会因此变成导航。D02 的 Pfizer Item 3 超链接句是同一种情形。

**先量后改。** 在 37 份文档里，带链接、又能得到标签的块只有四块，读者都判为事实或含事实：Ford 2024 第 1590 块、Marriott 2023 第 6851 块（"FOR the election of each of the 12 director nominees (see Item 1 on page 12)"，全员改选的董事会，候选人数即规模）、Pfizer 2022 第 3068 块（薪酬委员会全由独立董事组成）、Pfizer 2025 第 4015 块（独立董事选 Narayen 续任首席独立董事）。目录行一块都得不到标签，因为标签规则本身要求完整陈述：具名的人、人数或认定。所以正文循环不再看链接标志；卡片、名单等其他读法仍按原样跳过链接。

**用例与注错。** `test_a_statement_carrying_a_cross_reference_is_read`：带链接的认定句要取，带链接的目录行不取。注错 `A_LINKED_STATEMENT_IS_NAVIGATION`（把链接标志放回正文循环）。

**量测**（`measured-18-linked-statements.json`）：只新增上面四块。漏选 91→73，误选 18 不变，不一致位置 22 不变。
- Ford 2024 剩 942、2489、2499 三块。942 是被 `_POLICY` 里 "family members" 挡住的句子；2489、2499 是 Farley 卡片上的 "Committees: N/A"，见第 19 节。
- 另外三个位置新增的块原本就被覆盖，问题集不变。
- Pfizer 2025 是最新年度，值会变，但原值不缺事实，所以不撤回。

## 19. 委员会标签的就近范围按印出的块计

**问题。** Ford 2021、2023、2024 往年判读都漏了 Farley 卡片上的两块：姓名 "James D. Farley, Jr." 和 "Committees: N/A"（他不在任何委员会）。卡片读法从标签往前找姓名，最多看 8 块。Ford 的卡片在字段之间插了零宽空白块和单独的项目符号块，从 "Committees: N/A" 到姓名隔了 10 个原始块，其中只有 4 块印了东西，所以永远找不到姓名。

**改动。** 委员会标签找姓名时，范围只数印出内容的块，空白块和单独的项目符号不占名额。其他读法（身份标注、无标签的卡片条目）仍按原始块计：
- 先在 37 份文档上把新算法套到所有读法上试过。除了 Ford 三年，它还会去掉 Macy's 2025、2026 的三处 "Independent"（读者判为事实），并在 Marriott 2024、2025 取进 "GE Aerospace" 这类别家公司名（读者判为非事实）。
- 原因是身份标注可以越过本卡片的标签和委员会条目继续往下，一旦数的是印出的块，就会够到下一张卡片的姓名。两边都有姓名时按规则不取，于是掉了。
- 只用于委员会标签时，移动的正好是 Ford 三年这 6 块。

**用例与注错。**
- `test_spacer_blocks_do_not_carry_a_committee_label_out_of_reach`：Ford 式卡片，注错 `SPACERS_COUNT_FOR_A_COMMITTEE_LABEL`。
- `test_a_designation_s_reach_still_counts_every_block`：Macy's 式卡片，防止把新算法推广到身份标注，注错 `SPACERS_ARE_FREE_FOR_A_DESIGNATION`。
- 注错 72/72。

**量测**（`measured-19-card-reach.json`）：Ford 2021、2023、2024 各新增两块，都是读者判为事实的块；漏选 73→69，误选 18 不变，不一致位置 22 不变。
- Ford 2024 剩 942，即被 `_POLICY` 的 "family members" 挡住的句子。
- Ford 2023 剩 749。
- Ford 2021 剩 626、760、3096、4055，其中委员会改名的几块是另一类问题。

## 20. 在章程句里一并点名的委员会，说明设有哪些委员会

**问题。** Ford 2022 往年判读还剩 17 块漏选，其中 14 块（"Standing Board Committees" 行和 Board Committees 矩阵的标题与表头）都把第 474 块列为覆盖块："the charter of each of the Audit Committee, Compensation, Talent and Culture Committee, Finance Committee, Nominating and Governance Committee, and Sustainability, Innovation and Policy Committee of the Board"。统一裁定早已把这一类判为事实（`COMMITTEES_NAMED_AS_A_SET`，即说明设有哪些委员会），选择器却没有对应句式。

**先量后改。** 在 37 份文档里，一句章程句点名三个以上委员会的，共有七块：Ford 五年各一块（2021 第 910、2022 第 474、2023 第 873、2024 第 1079、2025 第 438 块），Salesforce 两年各一块（2025 第 619、2026 第 602 块）。它们都由读者判为事实，或由统一裁定判为事实。只点名一个委员会的章程句不算，例如 Macy's 的 "The charter for the CMD Committee is available …"，或 Ford 的 "The Charter of the Audit Committee provides that …"。

**改动。** 新增规则：章程句里至少有三个**不同的**大写委员会名，就给出 "设有哪些委员会" 的标签。
- 第一版数的是 "committee" 这个词。"The Charter of the Audit Committee provides that a member of the Audit Committee … audit committee …" 有三次这个词，却只说了一个委员会；当时的反例能通过，只是因为 "may not" 碰巧触发了政策否决。改为数不同的名字后，反例换成一句不含政策词的句子。
- 第二版又把 Ford 2021 第 3096 块当成一组委员会。那一句是改名："update the name of the CTC Committee from the “Compensation Committee” to the “Compensation, Talent and Culture Committee”"，一个委员会被叫了三种名字。读者判它为事实，理由是改名，不是"设有哪些委员会"。现在含 "name … from … to" 的句子不算一组委员会，改名在第 21 节单独处理。

**用例与注错。** `test_the_committees_named_together_on_their_charters`。注错：
- `A_CHARTER_SET_IS_NOT_READ`；
- `COMMITTEE_WORDS_COUNT_AS_COMMITTEES`（数词而不数名字）；
- `A_RENAME_COUNTS_AS_A_SET`。

共 75/75。

**量测**（`measured-20-committee-set.json`）：新增的正好是上面七块；漏选 69→55，误选 18 不变，不一致位置 22 不变。Ford 2022 只剩 406（"family member" 句）、1255（Farley 卡片姓名）、4535（股东提案人的原话）。最新年度两处：Ford 2025 新增 438，原值已覆盖这一事实，值会变；Salesforce 2026 新增 602，这个坐标本来就因第 14、15 节撤回，重算时一并计入。

## 21. 委员会改名是委员会设置的变动

**问题。** Ford 2021 往年判读漏了同一次改名的三块：第 626、4055 块 "The Compensation Committee changed its name to the Compensation, Talent and Culture Committee"，以及第 3096 块 "the Charter of the CTC Committee was amended to update the name of the CTC Committee from the “Compensation Committee” to the “Compensation, Talent and Culture Committee”"。读者判三块都含事实（委员会更名，属于设有哪些委员会），并互相列为覆盖。选择器原有的改名句式只认 "committee … was renamed … <年份>"。

**先量后改。** 在 37 份文档里搜 "changed its name"、"renamed"、"name of … committee … from"：
- 委员会改名只出现在 Ford 2021 这三块。
- 其余命中都是薪酬计划或政策被改名（Ford 2023 的奖金计划、Ford 2023–2025 的追回政策、Pfizer 2025 的计划修订），读者都判为非事实。

所以新句式要求被改名的是委员会：要么 "X Committee changed its name to the Y Committee"，要么 "the name of the X Committee from the A Committee to the B Committee"。第 20 节的"一组委员会"规则不把改名句算成一组；改名句由本节按改名取，标签同为"设有哪些委员会"。

**用例与注错。**
- 用例 `test_a_committee_that_changed_its_name`：两种委员会改名要取；计划改名、政策改名不取。
- 第 20 节的反例改为直接检查一组规则（`_committee_set`），不再检查标签，因为改名句现在凭改名得到同一个标签。
- 注错 `A_RENAME_IS_NOT_READ`、`A_RENAMED_PLAN_IS_A_COMMITTEE`。共 77/77。

**量测**（`measured-21-committee-rename.json`）：只有 Ford 2021 新增这三块；漏选 55→52，误选 18 不变，不一致位置 22 不变。Ford 2021 只剩第 760 块，即 "family member" 那句。

## 量过而未采用：按就近找卡片姓名把头衔行与人连起来

**来由。** #28 在 `137ecb24` 审它自己的 Macy's FY2025 结果，指出董事长兼首席执行官的头衔行（第 821 块）被单独取出，紧挨着的姓名（第 820 块 Tony Spring）没有跟着。#47 的选择同样单独取了 821、826、453。不过 #47 的值里有第 839 块 "Mr. Spring … currently serves as Chairman and Chief Executive Officer"，这件事本身是陈述了的。

**试过的做法。** 仿照委员会标签和身份标注的读法，头衔行也按就近找卡片姓名，找到就一起取（`rejected-title-name/probe.py`，只在内存里改，不写文件）。

**量出来的结果。** 37 份文档里新增 12 个姓名块。其中 7 个是对的：Macy's 历年的 Gennette、Spring，以及 Marriott 2024、2025 的 David S. Marriott。另外 5 个连错了人（`rejected-title-name/probe.log`）。Macy's 的提名人汇总表一行是"姓名、年龄、技能……、任职年份、头衔"。第 480 块的头衔属于上一行（Spring），往下最近的姓名却是下一行的 Varga（Macy's 2022、2023 是 Granoff），读者把这些姓名判为非事实。就近规则在卡片里成立，在表格里会把董事长头衔安到另一位董事身上；这个错比头衔单独出现更糟。

**结论。** 不采用。要把头衔和人连起来，需要读出表格的行结构，不能靠距离。在此之前，头衔行照旧单独取；人与头衔的关系由同一份值里写明二者的句子（Macy's 2026 的 839）承担。这个口径问题也已告诉 #28。

## 22. 点名了人的 "family member" 不是独立性标准

**问题。** Ford 2021 只剩第 760 块漏选："In addition, having a Ford family member, William Clay Ford, Jr., as our Executive Chair …, while Alexandra Ford English and Henry Ford III, who were first elected to the Board at the 2021 Annual Meeting, provide fresh perspectives …"。对 FY2021 来说，2021 年年会上的加入属于年度内的成员变动，读者判为含事实。选择器的政策否决词里有 "family member(s)"，整句因此被搁置。这个词本来是为独立性标准设的，例如 "the director or a family member is … employed by"。

**先量后改。** 把这个词从否决里整个拿掉（只在内存里试），37 份文档会多出 10 块：其中 9 块是读者判为非事实的独立性标准条款（Marriott 五年、Paramount 四年），只有这 1 块是事实。这 9 块都不点名任何人；第 760 块点名了 Ford 家族的几位董事。

**改动。** "family member" 只在句子不点名任何人时才算标准。点名了人的句子说的是具体的人，不是规则。那 9 块条款仍被否决；用例直接用其中两条原文作反例，它们离开这个词会被读成委员会组成，所以反例能证明否决仍在起作用。

**用例与注错。** `test_a_named_family_member_is_not_an_independence_standard`。注错：
- `A_NAMED_FAMILY_MEMBER_IS_A_STANDARD`（恢复无条件否决）；
- `A_FAMILY_MEMBER_IS_NEVER_A_STANDARD`（完全取消否决）。

共 79/79。

**量测**（`measured-22-named-family-member.json`）：只新增 Ford 2021 第 760 块；漏选 52→51，不一致位置 22→21，Ford 2021 恢复一致。

**仍开放的同句。** Ford 2022 第 406、2023 第 749、2024 第 942 块是同一句。对这三个年度，2021 年的加入在目标年度之前，按统一裁定属于任期，不算事实。句中另有 "William Clay Ford, Jr., as our Executive Chair" 这一主席事实，所以裁定把这三块留给读者；读者判为含事实，理由却只写了 2021 年的加入，也没有列出覆盖块。这三块是真漏选，还是读者理由与统一规则冲突，要看主席事实是否已由其他被选中的块写明，需要为主席事实写覆盖核对，本节没有处理。

## 量过而暂缓：列表项不是卡片姓名

**问题。** 剩下 18 块误选中有 3 块是别家公司名，被当成了董事姓名：Marriott 2022 的 "■ DICK’S Sporting Goods"、"■ Alignment Healthcare"，Marriott 2023 的 "⯀ Alignment Healthcare"。`person_name` 先去掉开头的项目符号再判断，于是带项目符号的列表项也能算姓名。

**试过的做法。** 卡片找姓名时（`_full_name`），以项目符号开头的块不算姓名。只在内存里试，脚本与输出见 `pending-bulleted-card-names/`。

**量出来的结果。**
- 这 3 块错的公司名被去掉，没有别的影响。
- 但同时去掉了 3 块 "Independent Director" 标注，读者判为事实（Marriott 2022 第 819、915 块，2023 第 1529 块）。原来这些标注一直挂在错的"姓名"上。
- 原因在版式：Marriott 把卡片姓名印在委员会和外部董事会列表之后。以第 819 块为例，名字 Lauren R. Hobart 在第 829 块，超出标注的就近范围；范围内能找到的"姓名"只有那个公司名。

**结论。** 暂不采用。直接改会把 3 块误选换成 3 块漏选，而这 3 块标注此前被量测算作"选对了"，其实一直挂在错的人名上，量测看不出这一层。正确的做法是让标注找到排在列表之后的卡片姓名，同时不重犯第 19 节里 Macy's 那种越界到下一张卡片的问题，需要单独设计。

**第二次量测（第 36 处之后）。** 试了"标注往后找姓名时，带项目符号的列表项不算姓名、也不计入就近范围"（`pending-bulleted-card-names/probe-skip-list-items.py`，只在内存里改；输出 `probe-skip-list-items.log`）：
- 列表项按"单独项目符号块之后的行"也算时，Marriott 各年新增 60 多个判为事实的标注与姓名，但 Macy's 2024–2026 的四处 "Independent"（含最新年）被丢：标注在姓名之后，往后跳过整段经历列表找到了下一张卡片的姓名，前后都有姓名就按规则放弃；
- 只算自带项目符号的块时，Macy's 2025、2026 仍丢三处，还新增把未加符号的公司名当姓名的误选（Marriott 2024 "GE Aerospace"、"Alignment Healthcare"，2025 "GE Aerospace"）；
- Marriott 2022 第 915 块另有原因：姓名写作 "Margaret M. (Meg) McCarthy"，括号里的昵称使它不被认作人名，往后搜不到。

所以仍暂缓。要做的是：认出"其他上市公司董事会 / 董事职务"列表段落（标题加其后的列表项）并整段排除在姓名之外，括号昵称按第 5 节的引号昵称同样处理，再量 Macy's 那种姓名在前、标注在后的卡片。

## 23. 董事会或其委员会设立的、名字夹在冠词和 "Committee" 之间的委员会

**问题。** Enphase 2023 第 447 块 "the Audit Committee established a cybersecurity subcommittee, which includes a board member with cybersecurity expertise"，Lumen 2022 第 1879 块 "In early 2022, the Board formed a special CEO Succession Committee"、第 1281 块同一件事，读者都判为含事实（设立了委员会），都没取。选择器设立委员会的句式只允许冠词和 "committee" 之间出现 new、separate、special、standing、ad hoc 这几个修饰词；委员会自己的名字（"cybersecurity"、"CEO Succession"）一出现就不匹配。Lumen 2022 的第 958 块是同一事实，读者把它列为由 1281、1879 覆盖。

**先量后改。** 允许名字出现后，37 份文档里匹配的句子共五句：
- 上面三块，加上 Southwest 2025 第 1225 块 "the Board also established an ad hoc Fleet Oversight Committee"（该块已因同块另一句被选中）；
- Lumen 2021 第 68 块 "We have also established a Lumen Sustainability Management committee which is responsible for driving our sustainability agenda with the Board and senior leaders…"，读者判为非事实：这是公司的管理层委员会，不是董事会的。

名字可以是任何词，所以只靠名字分不出谁的委员会。这五句里，是董事会的委员会的那四句，设立者都是董事会或它的某个委员会；第 68 块的设立者是 "We"。

**改动。** 新增一个设立句式：名字可以夹在冠词和 "committee" 之间，但设立者必须是董事会或某个委员会；名字只能是词，不能是从句（"formed a working group with the Audit Committee" 不算设立委员会）。原来不带名字的句式不变（它不要求设立者；Enphase 2024、2025 的 "has established a subcommittee" 由它取到）。

**用例与注错。** `test_a_committee_the_board_set_up_under_its_own_name`：三条原文正例；反例是第 68 块原文和一条构造的 "working group" 句子。注错：
- `A_NAMED_SETUP_IS_NOT_READ`；
- `ANY_SUBJECT_SETS_UP_A_NAMED_COMMITTEE`（去掉设立者要求）；
- `A_CLAUSE_IS_A_NAME`（名字里允许介词、冠词等虚词）。

共 82/82，对照 71 个用例。

**量测**（`measured-23-named-committee-setup.json`）：只新增 Enphase 2023 第 447 块、Lumen 2022 第 1281、1879 块，都是读者判为含事实的块；漏选 51→47（含由 1281、1879 覆盖的 958），误选 18 不变，不一致位置 21 不变，最新年不变。

## 24. 每次物色董事时才组成的遴选委员会是一个步骤，不是委员会构成

**问题。** Lumen 2022 第 842 块、2023 第 1085 块是同一句："The NCG Committee forms a search committee that is comprised of the Chairman of the Board, the HRCC and NCG Committee chairs, and the CEO who will request to interview with a diverse slate of candidates…"。读者都判为非事实：这是物色董事的流程，每次物色时才组成这个委员会，句中列的是职务，不是某个现有委员会的成员。选择器按 "committee … is comprised of" 当成委员会构成取了。2024、2025 年同一句没被取，只是因为那两年写成 "who will seek to interview"，"seeks to" 碰巧触发了政策否决，并不是规则把它判对了。

**先量后改。** 在 37 份文档里找"现在时或 will/may/would 加 forms/convenes/creates/establishes/appoints 一个委员会"的句子，只有 Lumen 这一句（2022–2025 四年），读者都判为非事实。过去时的设立（"the Board formed a special CEO Succession Committee"）说的是一个已经存在的委员会，不受影响。

**改动。** 句子说某个委员会是"每次组成"的，就不按委员会构成取。

**用例与注错。** `test_a_committee_formed_for_each_search_is_a_step`：反例是第 1085 块原文；正例是同一句改成过去时的构造句，仍按构成取。注错：
- `A_SEARCH_STEP_IS_COMPOSITION`（去掉这条判断）；
- `A_PAST_FORMATION_IS_A_STEP`（过去时 "formed" 也算每次组成）。

第 6 项的注错 `MANAGEMENT_SEATS_A_BOARD_COMMITTEE` 改的正是这一行，所以改为只去掉管理层判断、保留本条。共 84/84，对照 72 个用例。

**量测**（`measured-24-search-committee-step.json`）：只移走 Lumen 2022 第 842 块、2023 第 1085 块；误选 18→16，漏选 47 不变，不一致位置 21 不变，最新年不变。

## 25. 用 "became" 接任的职务

**问题。** Lumen 2021 第 897 块 "Effective May 20, 2020, Mr. Glenn became Lumen’s independent, non-executive Chairman, with Mr. Hanks continuing his role as Vice Chairman" 没取。选择器认的职务动词都要带 "as"（"serves as"、"was appointed as"），或是第 15 项的 "assumed the role of"；"became" 直接接职务名，不带 "as"。读者把同年的五块漏选（第 695、732 块卡片上的 "Chairman of the Board"、"Vice Chairman of the Board"，第 1049 块 "Independent Chairman named at 2020 annual meeting"，第 1223、2651 块董事酬金和关联交易里的副主席）都列为由 897 覆盖，所以这一块关系到六个块。

**日期。** 2020 年早于目标年度 2021。加入日期早于年度是任期，统一裁定判为非事实（`JOIN_BEFORE_THE_YEAR`）；职务不一样。读者对"谁担任某职务"的带日期陈述，不论日期在年度前后，都判为事实（"Lead Independent Director since 2022"、"Chair of the Board since January 1999"、"non-executive chairman since 2009"），因为它说的是现在谁担任，没有别的块更新它。加入日期只是重复了名单已经写明的"谁在董事会"，职务陈述却是唯一说明谁是主席的地方。所以这里不按日期筛。

**先量后改。** 37 份文档里 "became" 后 80 字符内出现主席、首席董事、副主席的句子共六句：
- 第 897 块是唯一没取的事实；
- Ford 2021 第 2381 块、Macy's 2024 第 2736 块、Salesforce 2025 第 1887 块已因同块其他句子被选中；
- Paramount 2021 第 932 块是董事酬金句（因薪酬话题排除）；
- Paramount 2021 第 728 块 "became the first woman to chair a major New York law firm" 说的是别的机构，读者判为非事实。

**改动。** 只加语料里实际出现的两种写法：
- "became <本公司>’s … Chairman"（与 "served as <本公司>’s Chairman" 同一规则，名字必须是本公司）；
- "became Chair of the … Committee"（加入委员会主席句式的动词表，Salesforce 第 1887 块的句子由此得到标签，但该块原已入选）。

"became Lead Independent Director"、"became Chairman of the Board" 这类不带所有格的写法，37 份文档里一句都没有，先不加：一条没有例子检验的规则不加。

**用例与注错。** `test_a_role_taken_up_with_became`：第 897、1887 块原文两条正例；反例是构造的 "she became Acme’s Chairman" 和第 728 块原文。注错：
- `BECAME_TAKES_NO_ROLE`；
- `BECAME_ANY_OWNERS_CHAIR`（所有格不核对是不是本公司）；
- `BECAME_A_COMMITTEE_CHAIR_IS_NOT_READ`。

共 87/87，对照 73 个用例。

**量测**（`measured-25-became.json`）：只新增 Lumen 2021 第 897 块；漏选 47→42（695、732、1049、1223、2651 由它覆盖），误选 16 不变，不一致位置 21 不变，最新年不变。

## 26. 年度内带日期的离任，无论印在哪里都算

**问题。** Macy's 2024 第 1982 块 "(5)Mr. Bryant and Ms. Hale ceased serving on the Board following our annual meeting of shareholders on May 19, 2023"，Macy's 2025 第 1814、1816 块 "(5)Mr. Buchanan ceased serving on the Board on November 25, 2024 and forfeited the RSUs granted in May 2024" 等，读者都判为含事实（离开董事会，别处没有写），都没取。原因有两个：选择器的离任句式不认 "ceased serving on the Board"；而且这几块是薪酬表的脚注，提到 RSU，整句先被薪酬话题排除。

**规则来自加入日期那一条。** 第 13 项起，年度内的加入"无论印在哪里都算，薪酬段落也不例外"：它是董事会成员的变化，统一裁定在年度之前的才判为任期。离任是同一种变化的另一面，所以照同样处理：带日期的离任，日期在年度内或之后，就在薪酬话题排除之前读；早于年度的不算年度内的变化。"ceased serving as EVP" 是高管离开职位，不是董事会，必须是 "on the Board"。

**先量后改。** 37 份文档里 "ceased serving / ceased to serve / ceased to be" 的句子，说董事离开董事会且带日期的只有 Macy's 这五块（2024 第 1981、1982 块，2025 第 1813、1814、1816 块），读者都判为事实；其余是高管离职（Lumen、Enphase）、股权计划条款，或已因别的句子入选（Lumen 2024 第 1516 块、Paramount 2023 第 936 块）。

**用例与注错。** `test_a_departure_dated_in_the_year_is_a_change_wherever_printed`：第 1814、1982 块原文两条正例；同一条 1814 放到日期之后开始的年度，不算；Lumen 2023 第 2324 块原文（高管离职）不算。注错：
- `A_DATED_DEPARTURE_IS_NOT_READ`；
- `A_DEPARTURE_BEFORE_THE_YEAR_COUNTS`（不看日期）；
- `AN_OFFICER_S_DEPARTURE_IS_THE_BOARD_S`（不要求 "on the Board"）。

共 90/90，对照 74 个用例。

**量测**（`measured-26-dated-departures.json`）：只新增上面五块；漏选 42→39，不一致位置 21→20（Macy's 2025 现与判读一致），误选 16 不变，最新年不变。

## 27. 与职务一起被任命为董事

**问题。** 三块读者判为含事实（董事会成员变化）的句子没取：
- Marriott 2021 第 1144 块 "Following Mr. Sorenson’s passing, the Board elected Anthony Capuano to serve as CEO of the Company and as a member of the Board."；
- Macy's 2023 第 40 块 "Tony Spring was appointed by the Board of Directors as Macy’s, Inc. president and CEO-elect, and a member of the Board of Directors."；
- Macy's 2024 第 2737 块 "in March 2023, the Board appointed Mr. Spring as Macy’s President and CEO-elect and a member of the Board."。

选择器的任命句式要 "to the Board"（"appointed X to the Board"），或带日期的加入要日期跟在 "a member of the Board" 之后；这三句是 "as …, and a member of the Board"，日期要么没有，要么在动词前面。

**日期。** 与加入日期同一规则（统一裁定 `JOIN_BEFORE_THE_YEAR`）：任命只在年度之前的，是任期。这里日期可能在动词前，所以读句子里所有的日期：没有日期，或有一个在年度内或之后，才算变化。

**先量后改。** 37 份文档里 "appointed/elected/named … and/as a member of the Board" 的句子共八句：上面三句；Enphase 2021–2025 五句 "before being appointed President and CEO and a member of the Board in September 2017"，对这五个年度都是任期（统一裁定把 2021–2024 四块判为非事实，2025 年那块读者判为非事实），新规则也不取。

**用例与注错。** `test_appointed_with_an_office_and_as_a_member_of_the_board`：第 1144、2737 块原文两条正例；第 2737 块放到下一年度不算；Enphase 2022 第 382 块原文不算。注错：
- `AN_APPOINTMENT_WITH_AN_OFFICE_IS_NOT_READ`；
- `AN_APPOINTMENT_BEFORE_THE_YEAR_COUNTS`（不看日期）；
- `ANY_DATED_APPOINTMENT_IS_TENURE`（有日期就不算）。

第一版只读去掉带日期加入之后的句子；规则既然要读句子里所有日期，去不去掉没有区别，也没有任何用例能区分，所以改为直接读整句。共 93/93，对照 75 个用例。

**量测**（`measured-27-appointed-a-member.json`）：只新增上面三块；漏选 39→36，不一致位置 20→19（Macy's 2024 现与判读一致），误选 16 不变，最新年不变。

## 28. 在另一家公司的年会上不再连任，不是本董事会的变化

**问题。** Pfizer 2022 第 446、547 块是同一条脚注："* Mr. Echevarria has informed Pfizer that he will not be standing for re-election at the Xerox Holdings Corporation’s Annual Meeting of Shareholders to be held on May 25, 2023."。说的是他不再在施乐的董事会连任，读者都判为非事实，选择器按 "not standing for re-election" 当成本董事会的离任取了。选择器的"别的机构"检查认 "the board of Acme"、"on the Acme board"、"At Acme, …" 等写法，不认"某公司的年会"。

**先量后改。** 37 份文档里所有格的 "X’s Annual/Special Meeting" 中，X 除了这一条的 Xerox，都是本公司自己（"Ford’s"、"Pfizer’s"、"the Company’s"）。

**改动。** "<名字>’s Annual Meeting / Special Meeting" 中的名字不是本公司的名字词、也不是 "Company" 时，算别的机构。句首的冠词不算名字："The Company’s Annual Meeting …" 是本公司的。

**用例与注错。** `test_standing_down_at_another_company_s_meeting`：第 446 块原文为反例；本公司自己的年会三条构造正例（"the Company’s"、"Pfizer’s"、句首 "The Company’s"）。注错：
- `ANOTHER_COMPANY_S_MEETING_IS_THIS_BOARD_S`（去掉这条检查）；
- `THE_REGISTRANT_S_OWN_MEETING_IS_ANOTHER_S`（本公司名字也算别的机构）；
- `THE_ARTICLE_NAMES_THE_COMPANY`（句首冠词当名字）。

第三个注错第一次没被抓：正例只有小写的 "the Company’s"，去掉冠词跳过也不影响。句首大写冠词这种写法语料里没有，但不跳过它就会把 "The Company’s Annual Meeting" 读成别的公司，所以补了一条构造的句首正例，而不是删掉这段处理。共 96/96，对照 76 个用例。

**量测**（`measured-28-another-company-meeting.json`）：只移走 Pfizer 2022 第 446、547 块；误选 16→14，漏选 36 不变，不一致位置 19 不变，最新年不变。

## 29. 年度内委员会构成没有变化

**问题。** Pfizer 2022 第 799 块、2023 第 884 块都以一句 "There were no changes to Committee compositions in 2022."（2023 年那份写 2023）结尾。这句说的是那一年各委员会的成员就是原来那些人，读者两份都判为含事实（MIXED，块里其余文字是委员会调整的程序），选择器没有对应句式，两块都没取。

**先量后改。** 37 份文档里写 "no change(s) to/in … committee/board composition" 的只有 Pfizer 三句：上面两句，和 2025 年第 1095 块的 "No changes to Committee compositions occurred in 2025 other than the election of Dr. Desmond-Hellman as Chair of the Science and Technology Committee and to reflect the retirement of Dr. Hobbs."。最后这句已经因为点名了委员会主席的任命而入选，不靠新规则。

**改动。** "no change(s) to Committee composition(s) in <年份>"，且年份不早于目标年度（与加入日期同一规则：早于年度的稳定不说明本年度）时，算委员会构成陈述。只收语料里出现的写法：不收 "during"、"occurred in" 这类中间插词的写法，也不收董事会构成——这些在 37 份文档里都没有例子，2025 年那句也不需要它。

**用例与注错。** `test_no_change_to_the_committees_in_the_year`：第 799、884 块那句原文为正例；把 2022 年那句放到 FY2023 的文件里不算（构造）。注错：
- `NO_CHANGE_TO_THE_COMMITTEES_IS_NOT_READ`（去掉这条规则）；
- `AN_EARLIER_YEAR_S_STABILITY_COUNTS`（不看年份）。

共 98/98，对照 77 个用例。

**量测**（`measured-29-no-committee-change.json`）：只新增 Pfizer 2022 第 799 块、2023 第 884 块；漏选 36→34，不一致位置 19→18（Pfizer 2023 现与判读一致），误选 14 不变，最新年不变。

## 30. 名单里的 "J.W. Marriott, Jr."：连写的两个首字母和逗号后的 Jr.

**问题。** Marriott 2021 第 991 块 "Current Members: J.W. Marriott, Jr. (Chair), Anthony G. Capuano, Lawrence W. Kellner, and Debra L. Lee." 是执行委员会的成员名单，读者判为事实，第 990 块是它的委员会标题。这一行整行读不出，原因有两个，缺一个都不行：
- 名字词规则只认一个首字母（"J."），两个首字母连写不带空格（"J.W."）不算名字词；
- 名单按逗号切开后，"Jr." 成了单独一项，它不是名字，整行就不算名单。

**先量后改。** 用内存补丁在 37 份文档上分别量两条机制：
- 只放开连写首字母、不限位置：会把 "U.S. Federal Income Tax Consequences"、"Orange, S.A."、"Telefonica S.A."、"M.B.A., Harvard University"、"B.A., Cornell University"、"U.S." 这些块都读成人名（选择不变，但名字判断变松）。限定为"恰好两个首字母、紧挨在最后一个词（姓）前"之后，名字判断只在真人名上变："J.W. Marriott, Jr."、"Andrew P.C. Wright"（Marriott 各年的签名与履历）。
- 只把 "Jr." 并回前一项、不限前一项：Paramount 三年的 "Phillips, Jr., Charles E."（姓在前的一个名字）会被读成两个人的名单。限定为前一项至少有两个词（名和姓）之后，这一块不变。
- 两条机制单独都不移动任何选择；两条一起只新增第 990、991 块。

**改动。** 名字词：恰好两个连写首字母、且是倒数第二个词时，当作首字母。名单：逗号后单独的 "Jr." 并入前一项，前提是前一项至少两个词。"Sr."、"II"、"III" 这类后缀在 37 份文档的名单里没有出现，没有加。

**用例与注错。** `test_two_initials_printed_together_before_the_surname`：两个真人名为正例，上面六个缩写块原文为反例；`test_a_suffix_after_a_comma_ends_the_name_before_it`：第 991 块的名单为正例，"Phillips, Jr., Charles E." 为反例；`test_a_members_line_written_as_a_sentence` 补上第 990、991 块。注错：
- `JOINED_INITIALS_ARE_NOT_A_NAME`（去掉连写首字母规则）；
- `JOINED_INITIALS_ANYWHERE`（不限位置）；
- `A_SUFFIX_IS_A_NAME_OF_ITS_OWN`（不并入）；
- `A_SUFFIX_JOINS_A_SURNAME_ALONE`（前一项只有姓也并入）。

共 102/102，对照 79 个用例。

"恰好两个"字母没有单独的注错：语料里三个首字母的块（"M.B.A., Harvard University"）不在倒数第二个位置，放宽到三个也不会被任何真实块区分。

**量测**（`measured-30-joined-initials-and-suffix.json`）：只新增 Marriott 2021 第 990、991 块；漏选 34→32，不一致位置 18→17（Marriott 2021 现与判读一致），误选 14 不变，最新年不变。

## 31. 单独一行的 "Chair:"，主席名在下一行

**问题。** Pfizer 2022 的五个委员会页都把 "Chair:" 单独印成一块，主席名在下一块（"Suzanne Nora Johnson"、"James C. Smith"、"Joseph J. Echevarria"、"Scott Gottlieb, M.D."），科学技术委员会的主席名还拆成 "Helen H." 和 "Hobbs, M.D." 两块。选择器只认同一块里的 "Chair: 名字"，这五处都没取。前四位主席另在别处被选中的块里写明（读者记为同一事实），所以不算漏选；Hobbs 任科学技术委员会主席这件事没有别的块写，第 875–877 块是漏选。

**先量后改。** 37 份文档里单独成块的 "Chair:" 只有 Pfizer 2022 这五处。

**改动。** 委员会页内单独一块 "Chair:"，其后紧跟名字时，取这一块和其后的名字，名字标为主席名；后面没有名字的标签不取。只收语料里的写法 "Chair:"，不收 "Chairman:"、"Committee Chair:" 等没有出现的写法。

**用例与注错。** `test_a_chair_label_on_a_line_of_its_own`：第 874–878 块原文为正例；标签后接职责说明而没有名字时不取（构造，用第 807 块的原文接在标签后）。注错：
- `A_CHAIR_LABEL_ALONE_IS_NOT_READ`（去掉这条规则）；
- `A_CHAIR_LABEL_WITH_NO_NAME_COUNTS`（不要求后接名字）；
- `THE_LABELLED_CHAIR_IS_A_MEMBER`（名字不标为主席）。

共 105/105，对照 80 个用例。

**量测**（`measured-31-chair-label-line.json`）：只在 Pfizer 2022 新增 11 块（五个标签和其后的主席名，读者都判为事实）；漏选 32→29，不一致位置 17→16（Pfizer 2022 现与判读一致），误选 14 不变，最新年不变。

## 32. "Our Board has a Lead Independent Director, Mr. Gomo"

**问题。** Enphase 2021 第 216 块第一句 "Our Board has a Lead Independent Director, Mr. Gomo, who has authority, among other things, to call and preside over Board meetings, …"。读者判为含事实（Gomo 任首席独立董事，别处没有写），选择器没取。现有句式认 "our/the + 职务 + , + 人名"（"the Lead Independent Director, Mr. X"），这里是不定冠词 "a"。

**先量后改。** 37 份文档里 "a/an + 董事长或首席独立董事 + 逗号" 的句子：这一句之后紧跟大写人名；Enphase 2022–2025 的 "an independent Chair of the Board, separate from the CEO"、Macy's 五年的 "the use of a lead independent director, and the other elements …"、Pfizer 2023/2025 的 "the election of a Lead Independent Director, establish …" 逗号后都是小写词，不是担任者。

**改动。** 冠词加上 "a"；逗号后仍须是大写开头的人名（原有的大小写敏感条件）。"an" 在语料里没有逗号后接人名的例子，没有加。

**用例与注错。** `test_a_board_that_has_a_lead_director_names_the_holder`：第 216 块那句原文为正例，Pfizer 2023 第 3546 块原文为反例。注错：
- `A_LEAD_DIRECTOR_INTRODUCED_WITH_A_IS_NOT_READ`（去掉 "a"）；
- `A_LOWER_CASE_WORD_AFTER_THE_COMMA_IS_A_HOLDER`（逗号后不要求大写，Pfizer 那句会被读成担任者）。

共 107/107，对照 81 个用例。

**量测**（`measured-32-has-a-lead-director.json`）：只新增 Enphase 2021 第 216 块；漏选 28→27，误选 14 不变，不一致位置 15 不变（Enphase 2021 还有表格脚注的主席标记和一处董事薪酬句），最新年不变。

## 33. 表格里带脚注标记的名字，和表下写明委员会职务的注释

**问题。** Enphase 2021 的董事表（第 144–156 块）在名字后印脚注标记（"Steven J. Gomo(2)"、"Benjamin Kortlang(1)(5)"），表下第 157–162 块逐条写明标记的含义（"(1)Chair of the Nominating and Corporate Governance Committee"、"(2)Chair of the Audit Committee"、"(5)Member of the Audit Committee" 等）。读者把带标记的名字和六条注释都判为事实。选择器没有这种读法，其中 Gomo 任审计委员会主席（第 146、158 块）和第 157 块别处没有写，是漏选。

**先量后改。** 37 份文档里 "(n)Chair/Member of the … Committee" 这种注释只在 Enphase 2021 出现。

**改动。** 与已有的"脚注写明变动"读法（`_footnoted_changes`）同样处理：表下一条 "(n)Chair/Member of the … Committee" 注释，和它之前 80 块内名字带 "(n)" 标记的块一起取；没有名字引用它的注释不取，带别的标记的名字不算这条注释的。

**用例与注错。** `test_a_table_s_names_and_the_notes_that_give_their_committee_roles`：第 144–162 块节选原文为正例；没有名字引用的注释不取（构造）；带别的标记的名字不算（构造，"标记须对应"沿用自脚注变动读法，语料里所有标记都有注释，所以用构造块行使它）。注错：
- `A_ROLE_NOTE_IS_NOT_READ`（不调用这一读法）；
- `A_ROLE_NOTE_WITHOUT_NAMES_IS_TAKEN`（没有名字也取注释）；
- `A_NAME_CITING_ANOTHER_MARK_IS_THE_NOTE_S`（任何带标记的名字都算）。

两个旧注错因这次改动失效，第一次运行在它们那里停下（`EDIT_DOES_NOT_APPLY`）：`A_FOOTNOTE_WITHOUT_ITS_NAMES` 的目标行在新读法里又出现一次，改为连同下一行（变动注释自己的标签）一起作目标；`A_TASK_FORCE_TITLE_IS_NOT_TAKEN` 的目标行被拆成两行，改为新的行。两者针对的仍是原来的规则。

共 110/110，对照 82 个用例。

**量测**（`measured-33-footnoted-committee-roles.json`）：只在 Enphase 2021 新增 11 块（5 个带标记的名字、6 条注释，读者都判为事实）；漏选 27→24，误选 14 不变，最新年不变。Enphase 2021 剩下一处误选（第 943 块，董事薪酬资格的引导句）。

## 34. 谁有资格领取董事薪酬，不是任职资格认定

**问题。** Enphase 2021 第 943 块、2022 第 531 块、2023 第 515 块都是董事现金薪酬表的引导句："Under the Non-Employee Director Compensation Policy, each member of the Board who is not our employee was eligible for the following cash compensation for Board services."。读者三份都判为非事实（董事薪酬）。选择器把它读成"委员会成员资格认定"：政策名里的 "Non-Employee Director" 碰上资格词，"each member" 碰上成员指称，"was" 碰上状态动词。

**先量后改。** 37 份文档里写 "eligible for … compensation" 的句子只有这三句；Enphase 2024 第 534 块同一句没写政策名，本来就没被取。"eligible to receive … compensation"（Enphase 2022 第 547 块）所在的块没被取、也不因这条变化，所以不收。

**改动。** "eligible for … compensation" 归入已有的薪酬话题排除（与 retainer、fees、RSU 同处理：句子讲的是薪酬，就不按构成读）。

**用例与注错。** `test_who_is_eligible_for_pay_is_not_a_qualification`：第 943、531 块原文为反例。注错 `PAY_ELIGIBILITY_IS_A_QUALIFICATION`（去掉这一排除）。共 111/111，对照 83 个用例。

**量测**（`measured-34-pay-eligibility.json`）：只移走这三块；误选 14→11，不一致位置 15→12（Enphase 2021、2022、2023 现与判读一致），漏选 24 不变，最新年不变。

## 35. "…, where he served on the board of directors" 说的是逗号前那个机构的董事会

**问题。** Marriott 2022 第 959 块、2023 第 1583 块是董事 Grant Reid 的履历："… and the Consumer Goods Forum, where he served on the board of directors, co-chaired the governance committee, and co-led the Forest Positive Coalition."。读者都判为非事实（Consumer Goods Forum 的董事会和治理委员会，不是本公司的）。选择器的"别的机构"检查认 "the board of Acme"、"At Acme, …"，不认"Acme, where he served on the board"，于是按委员会构成取了。

**先量后改。** 37 份文档里 "<机构>, where he/she served … board" 只有三处：上面两块，和 Paramount 2024 第 802 块（"the Council on Foreign Relations, where she served on the Board of Directors from 2010 to …"，本来就没被取，改后也不取）。

**改动。** "where he/she/they" 从句前紧挨着的大写名字不是本公司或本公司委员会的名字时，算别的机构。本公司名字不算别的机构，这一点沿用其余几条检查的做法，语料里没有本公司 + "where" 的句子，用构造句行使。

**用例与注错。** `test_a_board_a_where_clause_is_about_is_that_body_s`：第 959 块那句原文为反例；"Example Corporation, where he served on the Audit Committee" 为构造正例。注错：
- `A_WHERE_CLAUSE_BODY_IS_THIS_BOARD`（去掉这条检查）；
- `THE_REGISTRANT_BEFORE_WHERE_IS_ANOTHER_BODY`（本公司名字也算别的机构）。

这条检查插在第 28 处那条检查之后，那条的注错 `THE_REGISTRANT_S_OWN_MEETING_IS_ANOTHER_S` 原目标文本跨到了下一行，第一次核对时在它那里对不上，已改目标，针对的仍是原规则。共 113/113，对照 84 个用例。

**量测**（`measured-35-where-clause-body.json`）：只移走这两块；误选 11→9，漏选 24 不变，不一致位置 12 不变（两个位置各还有一处把别家公司名当人名的误选），最新年不变。

## 36. 公司名后面括号里写的委员会职务，是那家公司的

**问题。** Lumen 2023 第 790 块 "Cineverse Corporation (Chairman of the Audit Committee, and serves on the Compensation and Nominating Committees)" 是一位董事在别家上市公司的职务列表中的一项。读者判为非事实，选择器按 "serves on the … Committees" 读成本董事会委员会构成。

**先量后改。** 37 份文档里"名字 + 括号里写着委员会"的整块只有这一块；Lumen 2025 第 700 块 "•Ally Financial since May 2025 (Audit committee member)" 和 Pfizer 2025 两块职责条目都以项目符号开头，不在本条范围，也都没被取。

**改动。** 一句话整句是"以大写名字开头 + 括号里写着委员会"的形状，且开头的名字不是本公司或本公司委员会的名字时，括号里的职务算那家机构的。

第一版写成区分大小写的 "committee"，而这块写的是 "Committee"，规则没有生效，量测显示什么都没动、新用例失败；改为认首字母大写。

**用例与注错。** `test_a_company_named_with_the_roles_held_there`：第 790 块原文为反例；"Example Corporation (serves on the Audit Committee)" 为构造正例。注错：
- `A_COMPANY_S_ROLES_ARE_THIS_BOARD_S`（去掉这条检查）；
- `THE_REGISTRANT_WITH_ROLES_IS_ANOTHER_BODY`（本公司名字也算别的机构）。

新检查与第 35 处的检查结尾相同，第 35 处两个注错的目标文本会落到新检查上，已改为以新检查的注释行结尾，针对的仍是第 35 处的规则。

共 115/115，对照 85 个用例。

**量测**（`measured-36-company-roles-in-parentheses.json`）：只移走这一块；误选 9→8，漏选 24 不变，最新年不变。

## 37. 出席情况里写出的董事人数

**问题。** Marriott 的代理在出席情况里写出当时的董事人数：
- 2022 第 1039 块："All 14 directors then serving attended the Company’s 2022 annual meeting"；
- 2024 第 1264 块："All 12 directors nominated for election in 2024 attended the Company’s 2024 annual meeting"（2023 第 1685 块、2025 第 1199 块同样写法）。

读者都判为含事实（当时董事会的人数），选择器因出席话题整句排除。2021 第 842 块被取，只是因为同一块另写了一个带日期的加入。2024 年只有第 1264 块写出 12 人，读者没列覆盖块，所以算漏选；另外三年的人数另有 "reduced its size from X to Y" 的块写出，且已被取。

**先量后改。** 37 份文档里同时写出董事人数与出席的句子只有 7 句：
- Ford 2021 "of the twelve then current members of the Board, twelve attended"（第 12 处已读）；
- Marriott 五年的上述 5 句；
- Enphase 2021 "all but two of the other members of our board of directors attended"：没写董事会人数，读者没取。

**改动。** 与第 12 处一样，在出席话题排除之前读：
- "All N directors then serving" 并入已有的 `_THEN_CURRENT_MEMBERS`（某日在任董事的人数）；
- "All N directors nominated for election" 新增 `_ALL_NOMINATED_DIRECTORS`，只在董事会不分级时算规模。分级董事会上候选人只是其中一级，按统一裁定 `CLASSIFIED_SLATE_COUNT` 不算，与第 8 处同一判断。

只认语料里的这两种写法。

**用例与注错。** `test_the_board_s_size_where_attendance_at_its_meeting_is_reported`：Marriott 2022、2024 的两句原文为正例；同一句放在分级董事会上为构造反例；Enphase 2021 "all but two" 原文为反例。注错：
- `A_THEN_SERVING_COUNT_IS_SET_ASIDE`（去掉 then serving 写法）；
- `A_NOMINATED_COUNT_IS_SET_ASIDE`（去掉 nominated 写法）；
- `A_CLASS_S_NOMINEES_ARE_THE_BOARD`（不看是否分级）；
- `ANY_COUNT_AFTER_ALL_IS_A_SIZE`（把 then serving 写法放宽成 "all … 数字 … directors/members"，由 Enphase 反例抓到）。

共 119/119，对照 86 个用例。

**量测**（`measured-37-board-size-at-attendance.json`）：只在 Marriott 2022–2025 各新增一块，都是读者判为含事实的块；漏选 24→23，误选 7 不变，Marriott 2024 现与判读一致。最新年 Marriott 2025 的选择多了第 1199 块（读者判为含事实，列为由已取的第 491 块覆盖）。已接受的值只对应旧结果，下一次运行后要重读。

**局限。** 两种写法都不看句中年份。"nominated for election" 的人数在不分级的董事会上按当时在任的人数读，与读者一致；若句中年份早于目标年度，本条照样取，没有例子检验。
