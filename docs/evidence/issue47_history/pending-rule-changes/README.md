# 曾等收据提交后再应用的规则改动（已落地）

模型出口离线验证的收据绑定本世代快照（`requirements/issue_47_v1/baseline_manifest.json`），规则文件一改，快照就移动。所以 10-02 夜到 10-03 凌晨，规则文件的改动先存成补丁放在这里（推到远端，不随容器丢失），打算等收据与批准正文提交之后再应用。

10-03 约 04:47 UTC 虚拟机重启，打断了在 `562128fc` 上进行的重封：98 个注错只跑完 10 个，没有产出收据。重封要从头再跑，所以顺序反过来：四份补丁按下表顺序应用、重铸快照、跑相关测试，作为一个正式提交落地（本提交）；重封改在落地后的 HEAD 上进行。补丁文件已从分支删除，原字节在 `20497f4d`（四份都在）。#28 在 `31beeab5` 里读的 `d01-running-header.patch` 是 `af29ab2f` 那一版，与这里应用的字节相同。

| 补丁 | 内容 | 状态 |
|---|---|---|
| `c02-repair-49.patch` | C02 共用修复 49：职责从句里的状态词不算成员资格认定（`historical_board_composition_v3.py`、测试、注错与 `c02-selector-repairs/` 第 49 节、两份量测）。37 份判读与 12 个未判读位置一块不动，Southwest 两个块的标签改对；注错 161/161。 | 已应用（本提交） |
| `d01-running-header.patch` | D01 跳过跨两部分的运行页眉（JPMorgan “Parts I and II”）：`historical_risk_results.py` 改用冻结选择器与冻结推导的后继，各一处替换；新用例模块 `test_historical_running_header.py` 登记进 saved-source 层；`d01-risk-headings/running-header/` 的量测、来源记录、注错。50 份 D01 申报只移动 JPMorgan FY2021/23/24/25 四份、各少这一行；注错 6/6。 | 已应用（本提交） |
| `b06-fallback-forms.patch` | B06 回退解析器认两种往年写法：债务表里的转递证书（pass-through certificates）算债务工具，养老金义务（`DefinedBenefitPlanBenefitObligation`）算性质不同。`historical_debt_results.py` 的最后一级改用三个后继（`b06_disclosure.verify` 两处替换，`b06_disclosure_v2.verify` 与 `normal_candidates._b06_resolution` 各一处改为调用后继）；新用例模块 `test_historical_debt_fallback_forms.py` 登记进 saved-source 层；`b06-older-years/fallback-forms/` 的来源记录、注错与说明。Southwest FY2022 由扣留变为 0.7568（8,088/10,687 百万美元），全帧对比（50 期间、冻结对后继）只移动 Southwest 三年：FY2022 出数，FY2021、FY2023 仍扣留、停在下一级，已有数值一个都没变；注错 5/5。 | 已应用（本提交） |
| `jpm-proxy-image-name.patch` | JPMorgan FY2021 的 C02/C03：2022 年代理的封面名称是 logo 图片，名称改取封面之后第一块，仍须等于 SEC 记录在申报日的名称；认 Wingdings 的 `þ`/`o`。薪酬汇总表认带节号和 "(SCT)" 的标题；独立单元格里的脚注编号只在整行按原样不满足合计、去掉后满足时才去掉；"CEO CIB" 这类业务单元 CEO 不算注册人的 CEO。改 `historical_proxy_identity.py`、`historical_proxy_compensation.py` 与两份测试，`proxy-image-name/` 放量测、路线探针与注错。九份无 inline XBRL 的代理里只有 JPMorgan 移动（C03 84,428,145，与其 2023 年代理的标注一致；C02 51 条摘录），原八份的封面、人员行与 C03 答案逐个相同；注错 14/14。 | 已应用（本提交） |

应用方式：逐个 `git apply`（四份不碰同一处，按表中顺序），然后 `python3 tools/vnext_mint_historical_requirement.py` 与 `--check`。落地后各自的定向重跑、阅读与缺陷释放写在各补丁对应的证据目录里，还没有做。

2026-10-06现行H6接续：四份补丁均已落地，不再应用。上面“还没有做”是当时记录。后续`3fba0e84`轮已重跑并从原件阅读JPM FY2021/23/24/25 D01，四条运行页眉缺陷均为`RULE_FIXED_RESULT_RECOMPUTED_AND_READ`；FY2022原未受影响，保留`500ddf5f`原接受。JPM FY2021 C03已在同轮从代理原件核对84428145，Southwest FY2022 B06已核对8088/10687百万、比率0.7568073360157200336857864695；相应记录均在`accepted_result_content.json`绑定原结果及阅读文件，不因本轮代码变化重写或全量重跑。JPM FY2021 C02仍有独立布局/成员遗漏内容缺陷，修复49之后的Ford/Lumen等不一致继续H5；这些未完成不表示四份补丁未应用。现行剩余来源/内容/入口状态按#47 H6逐项接续，不重新造一次完整批次或重封。
