# 等收据提交后再应用的规则改动

模型出口离线验证的收据绑定本世代快照（`requirements/issue_47_v1/baseline_manifest.json`）。任何规则文件一改，快照就移动，正在重封的收据就对不上它要描述的树。所以在收据与批准正文提交之前，规则文件的改动先存成补丁放在这里，保证改动已推到远端、不随容器丢失；收据提交之后按序 `git apply`、重新铸造快照、跑相关测试，再作为正式提交推送，并删掉这里对应的补丁。

| 补丁 | 内容 | 状态 |
|---|---|---|
| `c02-repair-49.patch` | C02 共用修复 49：职责从句里的状态词不算成员资格认定（`historical_board_composition_v3.py`、测试、注错与 `c02-selector-repairs/` 第 49 节、两份量测）。37 份判读与 12 个未判读位置一块不动，Southwest 两个块的标签改对；注错 161/161。 | 待应用 |
| `d01-running-header.patch` | D01 跳过跨两部分的运行页眉（JPMorgan “Parts I and II”）：`historical_risk_results.py` 改用冻结选择器与冻结推导的后继，各一处替换；新用例模块 `test_historical_running_header.py` 登记进 saved-source 层；`d01-risk-headings/running-header/` 的量测、来源记录、注错。50 份 D01 申报只移动 JPMorgan FY2021/23/24/25 四份、各少这一行；注错 6/6。 | 待应用 |
| `b06-fallback-forms.patch` | B06 回退解析器认两种往年写法：债务表里的转递证书（pass-through certificates）算债务工具，养老金义务（`DefinedBenefitPlanBenefitObligation`）算性质不同。`historical_debt_results.py` 的最后一级改用三个后继（`b06_disclosure.verify` 两处替换，`b06_disclosure_v2.verify` 与 `normal_candidates._b06_resolution` 各一处改为调用后继）；新用例模块 `test_historical_debt_fallback_forms.py` 登记进 saved-source 层；`b06-older-years/fallback-forms/` 的来源记录、注错与说明。Southwest FY2022 由扣留变为 0.7568（8,088/10,687 百万美元），全帧对比（50 期间、冻结对后继）只移动 Southwest 三年：FY2022 出数，FY2021、FY2023 仍扣留、停在下一级，已有数值一个都没变；注错 5/5。 | 待应用 |

应用：逐个 `git apply docs/evidence/issue47_history/pending-rule-changes/<补丁>`（三份不碰同一处，已按表中顺序依次应用核对过），然后 `python3 tools/vnext_mint_historical_requirement.py` 与 `--check`。
