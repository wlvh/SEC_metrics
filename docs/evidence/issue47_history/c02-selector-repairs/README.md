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
