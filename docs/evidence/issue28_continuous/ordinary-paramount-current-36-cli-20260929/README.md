# Paramount FY2025：35项正常候选继续，C04按同主体证据扣留

本目录使用产品代码 `c88ed896`、当前V14需求闭包和已经认证的#28来源处理副本 `sha256:cd1cc2feff4cfa3347fac80c7b23248ed5026d71b87a0f240c563287ffdef228`。`run.py`在禁网、禁用116个旧语义生产导出的条件下，从默认 `tools/vnext_normal_update.py --process --company paramount_skydance_paramount_global` 进入36项普通更新，状态根为 `/private/tmp/issue28-paramount_skydance_paramount_global-current-36-cli-20260929`。不是再次运行既有D04大材料或线上新财报获取。

实际CLI返回码2，整体 **`UPDATES_PARTIAL`**：35项`CANDIDATE_READY`、C04一项`CANDIDATE_WITHHELD`。外层`run.exit=0`表示如实保存了这一部分完成状态，并非36项全成功。C04原生Result为`WITHHELD/null/C04_COMPARABLE_AUDITOR_FACTS_MISSING`，当前成功指针为空；缺同一注册主体前期可比审计师事实时，没有给“未更换”的0。其余35项独立继续。创建的实际进程约运行77分钟。

`cold.py`在另一个Python进程重新认证同一来源，从盘重放35条成功Run的Result及公开行，并核对C04扣留Run、输入描述、行字节和无成功指针。首次冷读的A01—C03共28项已经逐项重放，随后证据脚本错误地要求正常CLI的扣留摘要包含`result_reason`；该摘要没有成功候选，因此字段为`null`。`cold-first.exit=1`与`cold-first.log`保留原失败。修正脚本后先重放C04，再完成全部36项：`cold.exit=0`、`cold.json` **36/36**，没有修改产品代码、来源或原生结果。最终理由分布为13项`PASS`、16项`TRAIT_NOT_APPLICABLE`、2项`ANNUAL_DURATION_OUT_OF_RANGE`、4项`ENTITY_CONTINUITY_NOT_COMPARABLE`和C04一项有证据扣留。此前第一次仅用shell后台启动未获得可跟踪进程和退出收据，空的`cold-launcher.log`保留；成功冷读由随后跟踪的进程完成。

`compare.py`对保留390索引的36个普通坐标作**角色明确**的对照：值、单位、理由、质量、适用性及相应期间角色36/36相符；Result ID 33项相同，B10/B11/C04三项不同。C01和E01—E05的旧索引`source_period`从2025-01-01开始，当前相同Result ID的`period_start`从2024-01-01开始：前者是FY2025报告坐标，后者是两年事件回看窗口。初版`comparison.json`将两种字段直接比较而报六项差异，最终脚本分别记录原值、相同Result ID与窗口关系，`same_result_event_lookback_count=6`。这并非证明所有事件语义正确，也不改写旧索引或原Result；当前E01的“条目代码线索”与“原文确认并购公告”口径仍待决定。

创建及冷读前后，#28真实`claims.jsonl`、来源请求日志与正式active指针哈希均不变，新增真实provider/paid/SEC调用 **0/0/0**。本次证明的是保存FY2025来源下，C04一个局部扣留不会阻断其他35项正常更新，而且36条状态能从盘重现；没有新增完整39指标公司或390业务坐标。它不证明真实下一财年在线来源发现与获取、C04否定业务规则、正式旧入口退出或生产采纳。#47分支、账本、快照、Run根和PR52未被操作。
