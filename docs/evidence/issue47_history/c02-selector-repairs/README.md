# C02 选择器修复（共用，[shared-with-#28]）

27 个往年位置的双向判读与当前选择对比（`../c02-older-years/comparison.json`）：26 个不一致，49 个误选块、256 个漏选块。这里按"一个边界清楚的问题"逐个修，每个问题一节：问题、成因、改动、用例与注错、在全部 37 份判读上的量测。选择器是 `scripts/vnext/historical_board_composition.py`（#47 规则文件，改动后重铸 `issue_47_v1`）。

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
