# B06 新旧内容阻断与范围

金额为来源USD；对受阻坐标，机器debt只是未采纳候选，不表示总债务。原始来源及精确期间见coverage.json、原生Run、source_composition_evidence。生产权限所有坐标均为无。

| 公司 | 原候选 → 新候选 | 新原生值/状态 | 债务 / 权益 | 本轮结论及剩余最小决定 |
|---|---|---|---|---|
| Marriott International | NOT_MEANINGFUL → NOT_MEANINGFUL | NOT_MEANINGFUL | 16204000000（已证小计16204000000） / -3771000000 | 16204百万账面已含商业票据1177、融资租赁120。负权益，NOT_MEANINGFUL；新集合未重复加。 |
| Southwest Airlines | OK → OK | 0.6140834481894499436160882095 | 4901000000（已证小计4901000000） / 7981000000 | 4901百万已包含financelease78；按4919−18=324+4577对账，修订结论沿用原确切证据。 |
| Ford Motor Company | NEEDS_REVIEW → NEEDS_REVIEW | NEEDS_REVIEW | None（已证小计None） / None | 工业债务21919百万含租赁890。补充资产130934−负债109758=21176净资产，但归母工业权益缺NCI分配，不能作为分母；无完整比值。 |
| Pfizer | NEEDS_REVIEW → NEEDS_REVIEW | NEEDS_REVIEW | None（已证小计64795000000） / 86476000000 | 3154短债已含当前长期2997及其他短借157，加61641非流动=64795百万已证明借款小计。融资租赁不存在/已包含尚未证明，完整比值拒绝；不将无标签当零。 |
| JPMorgan Chase | NEEDS_REVIEW → NEEDS_REVIEW | NEEDS_REVIEW | None（已证小计970329000000） / 362438000000 | 435206长期已含current42589；64776短债、442396证券融资、27951合并VIE融资四行互不重复，小计970329百万。租赁完整性未证明；仅保存已证明小计，银行范围单列，不输出完整比值。 |
| Salesforce | NEEDS_REVIEW → OK | 0.2531872442595786412363464205 | 14974000000（已证小计14974000000） / 59142000000 | 14439借款+535另列financelease（275+260）=14974百万；经营租赁排除。 |
| Lumen Technologies | NOT_MEANINGFUL → NOT_MEANINGFUL | NOT_MEANINGFUL | 17441000000（已证小计17441000000） / -1117000000 | 17815−223−151=17441百万，已含financelease202（在lease/other220内），负权益−1117；不重复加。 |
| Macy's | NEEDS_REVIEW → OK | 0.5030864197530864197530864198 | 2445000000（已证小计2445000000） / 4860000000 | 2441本金+10溢价−19成本=账面2432，再加另列financelease13=2445百万；13内已确认非租赁1不剥离。 |
| Paramount Skydance / Paramount Global | OK → OK | 1.168049260241169930727785855 | 13658000000（已证小计13658000000） / 11693000000 | 13658百万successor账面已含financelease3；credit/CP/Miramax期末无余额，不改用14980本金。 |
| Enphase Energy | OK → OK | 1.107959077222837051285943352 | 1204377000（已证小计1204377000） / 1087023000 | 632.183当前+572.194非流动=1204.377百万；完整租赁政策明确无financelease，旧比值保持。 |
