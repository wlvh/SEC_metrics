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
