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
| `c02-composition-facts/` | 后继选择器 `scripts/vnext/historical_board_composition.py`（#47 规则文件）。它只替换 C02 治理文档的 proposal，冻结的来源准备、候选构造、Evidence 与记录形状原样复用；条目上限按修订机制放到 192（`catalog/r6/C02_board_disclosures_v2.md`）。在同十份最新材料上双向核对：765 选、0 误选、0 漏选，其中 52 块依赖两条执行者裁定（`adjudication.json`）；30 个注错全部抓到（`fault-injections.json`）。局限：规则就是在这十份申报上写、也在这十份上核对的，属开发/回归材料，不是留出验证；读者是同族子代理，不是人工验收 |
| `c02-older-years/` | 27 个往年位置（41 期批次 21 个，闭包 `ed360ebc`；第三轮 6 个，闭包 `8530710b`）的双向判读，全部读完（`judgements/`）。与当前代码从已存申报算出的选择对比（`comparison.json`）：26 个不一致，共 49 个误选块、256 个漏选块；Pfizer FY2024 一致。读者之间在若干类别上判断相反，需要按类别统一裁定，且裁定同样适用于最新十个位置的判读。读法、池规则、读者提示和答案交叉核对见 `README.md` |

**当前状态。** 最新十个位置（同上口径）由后继选择器产出的新结果已读并接受；冻结选择器的十条缺陷只对这十个新结果释放。27 个往年值一个都没有被接受；不一致的 26 个已按坐标登记为缺陷撤回（`../known_result_defects.json`，`C02_*_OLDER_YEAR_READING_DISAGREES`），一致的 Pfizer FY2024 也还没有对它的结果做接受核对。这 27 份判读已经或将要用于调整规则，所以它们对之后的修复也只算开发/回归材料。“27 份读完”不等于结果被接受。

**分工。** 共用选择器修复默认由 #47 继续实现，#28 负责普通路线接入和独立检查。修复按“一个明确的误选或漏选问题”为单位提交，提交标 `[shared-with-#28]`，并在本目录登记问题、提交、用例与历史侧验证结果。#28 现在的普通路线用的仍是冻结选择器，所以它最新年度的 C02 结果与 `c02-board-read/` 读的十个值同属一类问题；这部分的核对与接入由 #28 在自己的记录里处置，#47 不代为宣布普通路线已通过。

### C02 共用修复登记

每一项是一个边界清楚的误选或漏选问题，提交标 `[shared-with-#28]`。可复用位置都是后继选择器 `scripts/vnext/historical_board_composition.py` 在该提交的版本；问题、成因、用例、注错与历史侧量测见 `../c02-selector-repairs/README.md` 对应一节。量测把修复前后的选择器在全部 37 份判读（27 个往年、10 个最新）上各跑一次，列出移动的每一块。

| # | 问题 | 提交 | 用例 | 历史侧量测 |
|---|---|---|---|---|
| 1 | 匹配 "as <委员会名> committee chair" 的模式带 `re.I`，`[A-Z]` 也匹配小写，把遴选标准 "Previous service as a Board committee chair" 读成有人任委员会主席 | `5f803852` | `test_historical_board_composition.AProseFactIsAStatementAboutThisBoard.test_a_criterion_for_choosing_a_chair_seats_no_one`；注错 `A_LOWER_CASE_WORD_NAMES_A_COMMITTEE` | 只移动 Macy's 四个往年位置的这四块（都是判读判为非事实的块）；误选 49→45，漏选 256 不变，最新十个位置不变（`../c02-selector-repairs/measured-1-capitalised-committee-name.json`） |
| 2 | 委员会名单在每个名字前单独印项目符号，"◾" 与 "·" 不在选择器的符号集里，名单在第一个符号处结束，一个名字都没读到 | `9b7465ab` | `test_historical_board_composition.ACommitteePageIsReadAsAStructure.test_a_roster_marked_with_each_glyph_filings_print`；注错 `THE_SQUARE_BULLET_IS_NOT_A_BULLET`、`THE_MIDDLE_DOT_IS_NOT_A_BULLET` | 只在 Ford、Macy's 各一个往年位置新增 43 + 24 块，全部是判读判为事实的块；漏选 256→175，误选不变，最新十个位置不变（`../c02-selector-repairs/measured-2-bullet-glyphs.json`） |
| 3 | 委员会成员行写成句子（末尾句号、最后一个 "and" 前有逗号），`name_list` 整行失败，成员行与委员会标题都没取 | `a88147a4` | `test_historical_board_composition.ACommitteePageIsReadAsAStructure.test_a_members_line_written_as_a_sentence`；注错 `A_SERIAL_COMMA_ENDS_A_LIST`、`A_FINAL_PERIOD_ENDS_A_LIST` | 只在 Marriott 两个往年位置新增 6 + 8 块，全部是判读判为事实的块；漏选 175→160，误选不变，最新十个位置不变（`../c02-selector-repairs/measured-3-sentence-member-lists.json`） |
| 4 | 卡片在 "Director since …" 之后一行一个委员会、没有 "Committees:" 标签，选择器只认带标签的卡片，漏掉主席标注 | `a6975a47` | `test_historical_board_composition.ADirectorCardIsReadOnlyWhenItNamesItsDirector.test_unlabelled_committees_on_the_lines_after_the_tenure`；注错 `AN_EMPHASISED_HEADING_IS_A_CARD_ITEM`、`UNLABELLED_ITEMS_NEED_NO_DIRECTOR`、`UNLABELLED_CARD_ITEMS_UNREAD` | Enphase 三个往年位置新增 15 + 15 + 19 块，全部是判读判为事实的块，漏选 160→156，误选不变。**最新年份 Enphase 2025 也新增 19 块**（判读同样判为事实），已接受的值只对应旧结果，要重新核对接受；普通路线接入后最新年度 Enphase 的值同样会变（`../c02-selector-repairs/measured-4-unlabelled-card-items.json`） |
| 5 | 名字中间印着引号昵称（"Steven T. “Terry” Clontz"），`person_name` 拒绝含引号的块，卡片读不出、名单读到他就断 | `5c595159` | `test_historical_board_composition.ANameIsTheWholeBlock.test_a_quoted_nickname_between_the_names`；注错 `NICKNAMES_STAY_IN_THE_NAME`、`ANY_QUOTED_WORD_IS_A_NICKNAME` | Lumen 三个往年位置各 5 块、Marriott 一个往年位置 2 块，全部新增、全部是判读判为事实的块；漏选 156→146，误选不变，最新十个位置不变（`../c02-selector-repairs/measured-5-quoted-nicknames.json`） |

这些修复都不让任何往年坐标重新获得信用：每个坐标的选择只要还和判读不一致，就继续撤回。#28 的普通路线目前用冻结选择器，后继选择器及这些修复是否、何时接入由 #28 自己处置；#47 不代为宣布普通路线已通过。
