# 等收据提交后再应用的规则改动

模型出口离线验证的收据绑定本世代快照（`requirements/issue_47_v1/baseline_manifest.json`）。任何规则文件一改，快照就移动，正在重封的收据就对不上它要描述的树。所以在收据与批准正文提交之前，规则文件的改动先存成补丁放在这里，保证改动已推到远端、不随容器丢失；收据提交之后按序 `git apply`、重新铸造快照、跑相关测试，再作为正式提交推送，并删掉这里对应的补丁。

| 补丁 | 内容 | 状态 |
|---|---|---|
| `c02-repair-49.patch` | C02 共用修复 49：职责从句里的状态词不算成员资格认定（`historical_board_composition_v3.py`、测试、注错与 `c02-selector-repairs/` 第 49 节、两份量测）。37 份判读与 12 个未判读位置一块不动，Southwest 两个块的标签改对；注错 161/161。 | 待应用 |

应用：`git apply docs/evidence/issue47_history/pending-rule-changes/c02-repair-49.patch`，然后 `python3 tools/vnext_mint_historical_requirement.py` 与 `--check`。
