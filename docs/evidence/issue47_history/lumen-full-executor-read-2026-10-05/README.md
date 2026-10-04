# Lumen FY2021：完整供应文字参考及旧开发答比较

执行者先读完精确请求供应的全部 **5219 文字块**，再固定来源参考，最后读取旧开发回答。这里的 FY2021 是年度容器；代理声明日期为 2022-04-07，提交于 2022-04-08，accession `0000018926-22-000013`。没有把文件中的“当前”改成年末快照。

原件与请求来自已提交的 `evidence/issue47_local_inputs/c02-table-context-v2.tar.gz`。原 HTML SHA 为 `f3c138a9411eaeeb7272b6da5be398dd79e9c92d1fbdf42fea8f72f25b1067d8`；原精确请求 SHA 为 `c6c224c5d73152b7a2712114d4715053934b2318cebf397d63c37193256b67a5`。全部 5219 原块的字节跨度及输入 metadata 的 artifact 哈希再次核对通过。

22 个阅读分包覆盖 B0–B5218，连续、不重叠，没有关键词删源。执行者实读每包并写下范围判断；绑定脚本只验证字节与坐标，不自动判断业务语义。四份必要完整表保留原格、空白、跨度、表头与 raw text：table87（Audit/HRCC）、table90（NCG/Risk）、table116（现任及前董事的报酬表，仅用具名身份/明确状态/脚注）、table255（HRCC 签名）。四个常设委员会的 **19 个正向具名成员关系**有正文和这些原表支持。其余表格、技能图表和图片未全部作语义解释。

参考有 41 个整理单元，包含原引用块及必要格子。它们是执行者手工组织的参考，单元数不是接受指标数，也不是独立回答的事实数。参考写入并记录 SHA `ba811d27e6a4568ea579919346dab04ee0415f3c273f1500faf35dd5a852f703` 后，才读取旧开发答；两个实际时间记录也在包内。没有把这次原件阅读称作独立输入测试或新留出测试。

旧回答 34 项、230 个引用位置全部绑定原件。十一名当前提名人的身份与任期、十名独立董事、四个常设委员会和十九个成员关系、Audit 专家资格、Board Chair/Vice Chair、Allen/Jones 加入与 Boulet 离任、NCG 主席轮换均已支持，不能再次描述为遗漏。旧答本来就保留了 NCG 轮换未具名前后任、Jones 加入时宣布的未具名退休两项未决。

新发现的具体遗漏是 **B972 已存在的 Risk 子委员会**。正文说 Risk and Security 通过一个子委员会监督涉密活动及设施；这是职责段落里的实际机构关系。旧答四个常设委员会事实与 Risk 成员事实都没有保留它，未决也没有记录该关系。后续完整提取应保留其存在，同时让未具名的成员、主席与正式名称继续未决；不能补造第五个常设委员会或改写旧答补信用。

时间、主体和资格边界逐项保留：

- B259 默认信息为代理声明日期；B2756 的会后十一名董事是未来安排。B452 的任期还取决于当选及继任者当选并具备资格，不能预先写成选举已完成。
- B2870 说明年报附录摘录 Items 5/7/8，来自 2022-02-24 提交的 FY2021 10-K，且未更新。该附录与四月代理正文不共用一个隐含“当前”。
- Allen 的加入日明确为 2021-02-25；Boulet 任期结束于 2021 年股东年会。邻近 May20 股票授予日没有被用来补造她的离任日。Jones 加入日为 2020-01-01。
- Audit 五位成员的原文字面为 “audit committee financial expert”；独立性评估实际说明 SEC、NYSE 和公司治理指引。HRCC 的非雇员声明也覆盖 subsidiaries，旧答较短的 Company 表述不是完整原句。没有凭惯例追加另一条未说明的法规归因。
- 原文对具名董事的经验、技能及角色作了发行人评价，原块保留；它们是否属于 #28 要求的资格/角色评价仍待评论 `5969862604` 的回复。不会自动计接受，也不会把未决政策计成已确认缺陷。
- 年报附录 B4730 的 “Compensation Committee” 出现在股权激励授权机制，代理正文定义 HRCC。保留称呼差异，不能据此额外算一个委员会；固定任务本来就排除股权计划机制作为组成事实。
- 其他发行人董事会、管理层 Sustainability/Security Privacy Council、Customer Advisory Board、养老金资格及顾问/审计师独立性保持各自主体；董事会分红、回购工作和未具名诉讼被告不补成成员变化。

原单请求仍为 **216976 输入 + 4096 预留 = 221072**，超过原 200000 上限。此前三种有界完整表示的最小值 204549 也保留失败含义。两个全表责任输入分别为 193573/193102 输入，各自 fits；联合可重建全部文字/629 表格，但合计 386675 输入及跨包语义、去重和完整性仍未独立验证。本目录不增加压缩尝试、不裁源、不提高上限、不接入运行。

`reference-materials.tar.gz` 的逐成员字节与 SHA 见 `manifest.json`。它包含阅读分包/index、手工记录、冻结参考、首次读旧答时间、比较收据和绑定日志；原件与旧答仍引用已提交的各自原文件。

可复现（从已校验原输入解包后）：

```bash
mkdir -p work/lumen-reference-replay
tar -xzf docs/evidence/issue47_history/lumen-full-executor-read-2026-10-05/reference-materials.tar.gz \
  -C work/lumen-reference-replay
python3 docs/evidence/issue47_history/lumen-full-executor-read-2026-10-05/bind_reference.py \
  --input work/issue47-inputs/c02/lumen_technologies-2021-12-31 \
  --reading-notes work/lumen-reference-replay/lumen2021-c02-reader-notes.json \
  --out work/lumen-reference-replay/reference-rebuilt.json
cmp work/lumen-reference-replay/reference-rebuilt.json \
  work/lumen-reference-replay/lumen2021-c02-executor-reference.json
python3 docs/evidence/issue47_history/lumen-full-executor-read-2026-10-05/compare_old_development_answer.py \
  --document work/issue47-inputs/c02/lumen_technologies-2021-12-31/document.json \
  --answer docs/evidence/issue47_history/c02-model-method/answers/lumen_technologies-2021-12-31.json \
  --reference work/lumen-reference-replay/reference-rebuilt.json \
  --out work/lumen-reference-replay/comparison-rebuilt.json
cmp work/lumen-reference-replay/comparison-rebuilt.json \
  work/lumen-reference-replay/lumen2021-c02-old-answer-comparison.json
```

原回答、原 Result、失败、模型包及接受登记不改。新增 DeepSeek/paid/SEC 为 `[0,0,0]`，新 Run/接受均 0，完整 C02 接受没有因本比较授予。
