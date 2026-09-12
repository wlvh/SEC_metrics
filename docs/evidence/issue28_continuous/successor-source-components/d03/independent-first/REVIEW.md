# D03 独立只读审阅：源文事实的错误确定性标记

结论：发现 3 项 P2，已有真实反例，不建议把当前 SOURCE_REPORTED_FACT / authority_to_action_relation_proven / current_status_asserted 作为后继自动批准依据。它们是尚未接入生产的事实分类问题，不是 FROZEN Run、最终 Result 或发布的错误接受：所有受测候选仍 requires_semantic_review=true，semantic_scope_completeness_asserted=false、native_result_created=false，未发现一句支持事实把整段变为已完整解决。

本轮只读作者 3 文件、现有原件和原材料；全部新增复现文件在本目录。没有修改生产文件、V13、CI、历史证据，没有调用 SEC / provider、没有 Run 或 freeze。provider / paid / SEC = 0 / 0 / 0。

## P2-1：历史、第三方和条件引用被当作当前注册人的事实

位置：[regulatory_investigation_candidates.py:144](/Users/lyuhongwang/Developer/SEC_metrics/scripts/vnext/regulatory_investigation_candidates.py:144)，以及 79–118 行。facts 只接收当前块；前后上下文直到 facts 完成后才保存到 context_excerpts，既不参与主体判断，也不参与 current 状态判断。`we` 一律是 SOURCE_AUTHOR_FIRST_PERSON，HTML 引用容器的归属没有验证。

独立完整 HTML 反例：

- historical_quoted_paragraph：前一段明确“quotation ... 2018 annual report; ... closed in 2019”，随后 blockquote 内是 `We are cooperating with the DOJ inquiry.`。输出 supported_fact_count=1、CURRENT_COOPERATION、SOURCE_REPORTED_FACT、current_status_asserted=true。
- third_party_quoted_paragraph：前段明确是供应商 Delta 对自己调查的发言，后一段明确其不关联注册人；引用内同一句仍被归于注册人的 `we`。
- conditional_quoted_paragraph：前段明确是假设 DOJ 开始询问后的假设回答；后一段明确没有该询问。引用内仍得到当前确定事实。
- adjacent_closed_status：同一句当前配合后紧邻 `This inquiry was closed in January 2021.`；当前标记仍 true，尽管该矛盾正是作者同块 mixed-resolution 规则试图处理的情形。

上述限定实际存在于输出 context_excerpts；不是输入缺失。每份独立 HTML、完整 bundle、精确原始字节 span 和 source SHA 均在 index.json 对应条目，首次结果未重写。

最小修复建议：在允许事实等级之前，按引用容器/引介语和所指事项核对源作者、时态与条件；无法机械绑定时保留摘录和 SEMANTIC_REVIEW_REQUIRED，清除 current/asserted 与 proven 信用。先不要对所有邻段出现 closed/if 就全面拒绝：另存的 unrelated_closed_control 明确是 separate unrelated private contract lawsuit，当前 DOJ 配合应继续保留，原九条真实事实也应逐条回归。

## P2-2：机构在句首只负责“报告/否认”，仍被视为发出程序材料的主语

位置：[policy:29](/Users/lyuhongwang/Developer/SEC_metrics/catalog/r6/regulatory_investigation_candidates_v1.json:29)，以及 [regulatory_investigation_candidates.py:102](/Users/lyuhongwang/Developer/SEC_metrics/scripts/vnext/regulatory_investigation_candidates.py:102)。ISSUED_PROCESS_TO_NAMED_ENTITY 在机构与 issued/served 中间允许任意 0–80 个非句末字符；它没有独立 authority_relations 条目，代码将 relation is None 直接当 authority_related=true。

实际反例：

- sec_reports_private_actor：`The SEC reported that private plaintiff Delta issued a subpoena to Example Incorporated in a contract dispute.` 实际发出方是私人原告 Delta；程序仍得到 REPORTED_REGULATORY_PROCESS_ADDRESSED_TO_ENTITY / SOURCE_REPORTED_FACT / authority_to_action_relation_proven=true。
- sec_denies_action：`The SEC denied that it issued a subpoena to Example Incorporated.` 实际否认发生该行为；仍得到完全相同的确定事实。现有 negated_action 仅 no/not/never/without，不能弥补任意叙述动词跨越造成的主谓关系丢失。

这两例 current_status_asserted=false，所以错误是“机关曾发出材料”的事实，不是自动声称当前案件开放。建议把发行机关主语+有限官方下属单位+直接肯定 issued/served 作为完整关系绑定；转述、否认、声称和内嵌其他主语不能越过后取动词。保留真实 Lumen FCC Enforcement Bureau 直接发函正例，未证明的复杂句转语义候选。

## P2-3：名称含 Government 的私人法人被当作机关

位置：[policy:9](/Users/lyuhongwang/Developer/SEC_metrics/catalog/r6/regulatory_investigation_candidates_v1.json:9)、[policy:32](/Users/lyuhongwang/Developer/SEC_metrics/catalog/r6/regulatory_investigation_candidates_v1.json:32)。裸 government 的词边界允许其只是专有实体名的首词，from 关系不验证后续完整机构名称和角色。

`We received a subpoena from Government Employees Insurance Company, a private insurer, in its contract lawsuit.` 得到 REPORTED_RECEIPT_OF_REGULATORY_PROCESS / SOURCE_REPORTED_FACT / authority_to_action_relation_proven=true。句内已明确是 private insurer；不需要外部公司信息就可以知道不能仅凭 government 字首证明政府机关。

建议来源机关关系覆盖完整名词短语及其同句定义，不能把裸 government 的前缀命中当认证。明确的私人角色或无法闭合的机关名称需要退回语义候选；这是类别规则，不应维护这个示例公司的例外表。

## 额外边界观察与正确结果

conference_background：`We are cooperating with the SEC on its conference about enforcement practices.` 也得到 EXPLICIT_CURRENT_RESPONSE_TO_AUTHORITY。原文的合作确实存在，但并未说明调查或执法程序发生；当前规则只需要句中另有 enforcement 词。若此事实仅表示“与机关合作”且始终留待 D03 语义判断，这不能自动升级为“被调查”。若后继准备把它直接作为 D03 实际监管行为，则必须增加动作与合作关系绑定。此条与以上 7 个明确错误接受分开记录，不扩大当前证据结论。

正确控制：实际当前 DOJ inquiry 配合有 1 条支持；私人原告发材料仅背景提 SEC 被正确退回；同句 if 条件正确退回；相邻明确无关私人诉讼结案不抹掉 DOJ 当前陈述。这些控制用于避免只增加关键词拒绝表。

## 真实十公司原件复核与范围

重新验证作者 checkpoint 中十公司的真实 source_proofs 对当前已保存基线的准入，并从实际 raw_blob.storage_uri 读取原文，调用 replay_regulatory_investigation_candidates 对整个 bundle 精确重建。10/10 PASS；原有 9 条支持事实保持：Southwest 1、Pfizer 4、JPM 1、Salesforce 1、Lumen 1、Paramount 1。具体 statement_text、原始块字节、source SHA、相邻文本和准入结果保存在 actual-replay.json。这里是独立原字节重算，未依赖作者的 PASS 标签。

独立阅读未把这些九条事实当九起当前调查：Pfizer 三条是 2019/2023 收件事实，current=false；Lumen 是向注册人发函，current=false；JPM 是集团及关联实体在总括程序清单中，未映射每一案件/每个实体；其余当前参与/配合仍无案件数和被调查主体推定。全段 semantic review 标志正确保留。没有测试新 Run、正式 Review、后继预算或发布接线，也没有声称该组件已满足最终 D03。

## 可复跑材料

```text
python3 /tmp/sec_metrics_issue28_continuous/pr43-review/d03-independent-review-20260912b/reproduce.py
python3 /tmp/sec_metrics_issue28_continuous/pr43-review/d03-independent-review-20260912b/replay_actual.py
```

脚本保护首次结果不覆盖；修后复跑时复制脚本与保留 HTML 到新目录或编写只读原 HTML 的后继脚本。不得重新生成不同反例后宣称修掉原反例。

本目录 index.json 保存第一批 11 场景，additional-control.json 另存“无关结案”控制，共 12 个隔离场景；actual-replay.json 是 10 个真实来源重建。受审三文件前后 SHA 与作者最终 checkpoint 相同：

- `scripts/vnext/regulatory_investigation_candidates.py`: `76c3fb71eab453c2ae662ec9957f646c2d078869eef89dc9a122d37906817eb5`
- `catalog/r6/regulatory_investigation_candidates_v1.json`: `ce8ca7978797ededca8cea77303cd78a257622fd564b2fa70e6b04c88f2c7c63`
- `tests/vnext/test_regulatory_investigation_candidates.py`: `9e11ae5e03b4cd2bae59d3eb5f4ebe4790ba5b8c6737d602cb638ccbe195ac18`

此报告是独立只读审阅。建议先修上述事实等级再继续将 D03 接入后继 native TEXT；完整开发委托继续，不需要因本报告停止无依赖的离线工作。
