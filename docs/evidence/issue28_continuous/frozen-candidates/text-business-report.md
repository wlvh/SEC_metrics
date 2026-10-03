# R6 C02 / D02–D04 原件自动范围与候选：独立交付

本增量已把十家公司保存的原始来源自动转为可定位、可按原字节重放的 C02、D02、D03、D04 候选。实际新增业务调用 provider/paid/SEC = 0/0/0。没有生成原生指标 Result、正式采纳、发布或 active 切换；本报告不把候选发现当成 Issue 最终验收。

## 依据与范围

`02_指标定义_SEC_10公司单年指标.md:434–483` 允许 C02 可靠结构化失败时使用 TEXT_QUAL，D02 记录已披露计提概念和值或文本存在性，D03 输出命中段落与判断，D04 把检查后未披露持续经营疑虑视作正常结果。当前已实施 TEXT_V1 仅有 D01 的 RISK_FACTOR_HEADINGS_V1；SOURCE_EXCERPTS 不能悄然承载 D03 判断或 D04 语义未披露。

普通来源准备复用 normal_annual_input、normal_governance_input._Sources、annual_update.saved_source 和真实 request proof：当前同主体 ordinary 10-K；治理来源选保存 current submissions 的最新同 CIK DEF14A，缺少时保留正常年度输入已有同期间 amendment 候选。Paramount 来源为当前 2041610 的 10-K/A；未拼旧 813828 proxy。仅提供该来源的逐字披露，尚未声称该替代入口有 C02 正式 SourceStrategy 信用。

共 30 个唯一真实 request proof（来源清单、年度原件、治理原件），分类 {'IMMUTABLE_ATTEMPT': 21, 'LEGACY_WORKING_LOCATOR': 9}。每组均经 normal_source_authority.verify_saved_source_proofs 对已固定 10854a9 基线重验 body、headers、原请求绑定。socket 在探针进程被禁用，原始源不变、实际数据根不写入。

## 十家公司实际候选

下表的数目是来源段落/匹配数，不是董事人数、诉讼数量、调查发生数或成功指标数。

| 公司 | C02 原文段 | D02 原文段 | D03 待判断段 | D04 词句 | 审计报告范围 | XBRL 候选 |
|---|---:|---:|---:|---:|---:|---:|
| marriott_international | 29 | 10 | 20 | 0 | 2 | 0 |
| southwest_airlines | 28 | 25 | 61 | 0 | 2 | 1 |
| ford_motor_company | 23 | 53 | 29 | 0 | 1 | 0 |
| pfizer | 24 | 58 | 89 | 1 | 2 | 0 |
| jpmorgan_chase | 39 | 34 | 101 | 0 | 1 | 2 |
| salesforce | 30 | 9 | 52 | 0 | 2 | 0 |
| lumen_technologies | 17 | 15 | 54 | 0 | 2 | 0 |
| macys | 13 | 3 | 42 | 0 | 1 | 0 |
| paramount_skydance_paramount_global | 12 | 16 | 32 | 0 | 2 | 0 |
| enphase_energy | 34 | 18 | 40 | 0 | 2 | 0 |

C02 与 D02 的十公司候选均在当前 TEXT_V1 的 64 项/64,000 字符之内，仍需明确 source/period 语义和新 method 接线。D03 的 Pfizer 有 89 段、87,139 字符；JPM 有 101 段。不能为满足渲染上限删除后续证据，必须把读取上下文与最终文本结果区分。

## 已证明的真实结构与反例

- `ford_motor_company`：原件 `evidence/request_attempts/3b/3bbda349b5831cfb9a2686dbdb7d87614bcdbe2d195aa8ecd9b39215945361f9/f-20251231.htm`；附注范围（半开 block 序号）`[('Note 24', [(3955, 3992, 'EXACT_NOTE')])]`；审计报告范围 `[(2131, 2167)]`。
- `jpmorgan_chase`：原件 `evidence/request_attempts/4d/4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/jpm-20251231.htm`；附注范围（半开 block 序号）`[('Note 30', [(10159, 10196, 'EXACT_NOTE')])]`；审计报告范围 `[(5181, 5219)]`。
- `pfizer`：原件 `evidence/request_attempts/17/175e07c21ee258eddd9952e443d34df2a297d0c38e2d1312dff0a64a31c401ab/pfe-20251231.htm`；附注范围（半开 block 序号）`[('Note 16A', [(3819, 3954, 'WIDER_PARENT_NOTE')])]`；审计报告范围 `[(1857, 1891), (4191, 4223)]`。
- `salesforce`：原件 `evidence/request_attempts/d6/d606b8cc64176cbfa8c75355a9c935ec83f6b8374a87f94f3747941633fa8d25/crm-20260131.htm`；附注范围（半开 block 序号）`[('Note 14', [(2091, 2109, 'EXACT_NOTE')])]`；审计报告范围 `[(1003, 1035), (1035, 1054)]`。
- `paramount_skydance_paramount_global`：原件 `evidence/request_attempts/4c/4cf3d42c0ba1129dadd58d9c1ffdc4f35e2a81cec7bab3763e2a3bbecfea135d/psky-20251231.htm`；附注范围（半开 block 序号）`[('Note 18', [(3199, 3267, 'EXACT_NOTE')])]`；审计报告范围 `[(1357, 1389), (1389, 1411)]`。
- `macys`：原件 `evidence/request_attempts/47/47e1df1c9e94a3e0de3def3d714f16496c25f6461504899e4476b203bb91f4c7/m-20260131.htm`；附注范围（半开 block 序号）`[]`；审计报告范围 `[(781, 810)]`。

- Ford 与 JPM 的物理 Item 8 只有“见附后财报”指针。全文结构导航找到 Item 编号之后的实际审计报告及 Item 3 引用的 Note 24 / Note 30；只有 Item 8 LOCATED 不足以支持完整检查。
- Pfizer 的 Note 16A 引用找不到独立编号标题时，明确扩展到完整父 Note 16，范围一直到下一完整 Note；内部的“1. …”不被当作 Note 17。Paramount 的标题是“18) …”，也能一般化定位。Salesforce 最后 Note 14 在所属 Item 8 的结束边界闭合。
- Macy 审计报告有分页后的普通续段以 “consolidated financial statements, taken as a whole” 开头。旧候选边界曾误截于 block 798；现在要求财报结束标题具有标题强调结构，正确延续到 block 810。此真实反例已加入测试。
- Pfizer 全文唯一 going-concern 词句讨论 Seagen 收购商誉包含的既有业务持续经营元素，不能判定持续经营疑虑；所有公司无命中也不产生“未披露”结论。
- 同一年度原件可同时收录当期及前身/比较期间审计报告（Paramount）。source CIK 验证通过不等于每个报告段落都审计同一当期主体；报告范围保留 subject/period review_required。
- Southwest 唯一计提候选是 us-gaap:LossContingencyAccrualProvision，107,000,000 USD，原 context 为 2023-10-01 至 2023-12-31。JPM 两个候选是 LossContingencyRangeOfPossibleLossPortionNotAccrued、2025-12-31、Minimum/Maximum 维度值 0 与 1,200,000,000 USD；它们既非当期计提总额，也不能支持“无诉讼”。全部原 concept/context/unit/ordinal 被保留而未投成指标值。

## 交付入口与可复用接线

- `scripts/vnext/text_business_candidates.py:324`：`prepare_business_candidates(raw_bytes, raw_blob, source_reference, company_id, cik, filing)` 从原字节重建候选；`:346` `replay_business_candidates(bundle, **source_arguments)` 精确比对。逐条原文附 native source_reference_id / raw_asset_id / UTF-8 byte span / span SHA256。
- `:76 / :126`：治理来源文档与 C02 原文陈述。保留 source filing，不赋予董事统计 as-of，不把 nominees/election 自动当在任董事。
- `:163 / :213`：Item 3 前向附注导航与 D02/D03 候选；范围状态仅为 LOCAL_REQUESTED_RANGES_SCANNED，semantic_scope_completeness_asserted=false。
- `:254`：全本地文档词句和审计报告边界，not_disclosed_confirmed/going_concern_doubt_asserted/clean_opinion_used_as_absence 均为 false。
- `:295`：原始 XBRL concept/value/context 候选，metric_role_interpretation_required=true；无合计或最终数值。
- 业务词、段落识别与附注/报告导航词全部来自 `catalog/r6/text_business_candidates_v1.json`；每个 proposal 绑定 policy_hash。未修改共享 TEXT_V1、text_coverage、Run、冻结 Spec 或 Requirement。

建议下一个正式增量：C02 的来源语义及 D02 使用明确的逐字陈述 method，沿既有 Observation→Evidence→整组 Review→Calculator→Trace/Result 接线；先保留报告期与源披露时点的区别。D03/D04 增加明确语义解释的结果类型和可重验完整检查记录，依旧复用同一原生执行链。不要把新解释塞进 SOURCE_EXCERPTS，也不要给缺少结果的坐标假造“未披露”。C02 的 Part III fallback 作为明确后继 SourceStrategy 登记，不改旧 DEF14A 入口的历史含义。

## 资源规模与需要集中的决定

C02/D02 的原文摘录可继续零模型完成必要原生接线。D03/D04 共有 20 个公司×指标的普通语义判定任务；这是集中费用申请的任务规模依据，不是已批准调用数、最终 provider request 数或 qualification 数。可否同源合并请求要服从现有任务/Review 边界；新 qualification、重试、真实 SEC 刷新仍须另列，不能复活旧额度。

| 公司 | 年报可见字符 | 法律/风险所查范围字符 | 审计报告范围字符 | 治理全文字符 |
|---|---:|---:|---:|---:|
| marriott_international | 271,428 | 157,283 | 11,516 | 277,658 |
| southwest_airlines | 536,271 | 281,611 | 9,909 | 285,423 |
| ford_motor_company | 630,830 | 111,966 | 15,676 | 319,642 |
| pfizer | 629,666 | 349,468 | 17,285 | 481,317 |
| jpmorgan_chase | 1,153,348 | 126,242 | 12,728 | 353,818 |
| salesforce | 403,488 | 242,055 | 12,890 | 625,505 |
| lumen_technologies | 474,832 | 286,427 | 11,627 | 789,665 |
| macys | 290,303 | 165,055 | 8,375 | 421,547 |
| paramount_skydance_paramount_global | 506,057 | 305,995 | 20,287 | 157,538 |
| enphase_energy | 454,845 | 296,520 | 11,003 | 370,347 |

字符数用于请求设计，不能当 provider-reported tokens。D04 的语言阴性结论不能只读搜索命中段落；全文/适当完整语义范围的可承载性还需在明确 frozen request 上核实。当前最大的年度可见文本为 JPM 1,153,348 字符。这是具体上下文规模问题，不能把无匹配偷换成零风险。

本轮没有发现必须新增业务选择才能继续开发的阻断：C02 已允许逐字治理披露，D03 的判断与 D04 检查后的未披露含义也已有定义。先按这些含义实现正式类型、来源范围与验证。只有若新增固定董事人数时点、改变调查判断含义或降低未披露证明标准，才属于需要集中对齐的业务改变。

## 验证与证据文件

- `text_business_tests.log`：13 项必要反例 PASS；涵盖原文字符/字节、源修改重放拒绝、跨主体、断截、TOC、前向附注、内部编号、括号编号、审计续段、未来董事、委员会薪酬噪声、假设/否定调查、商誉词句与无匹配不冒充未披露。
- `text_business_semantics_scan.log`：针对新增 Python 的现有语义扫描，0 项问题。
- `text_business_replay_inputs.json`：20 个正常自动来源文档的完整原生输入绑定、30 唯一真实 proof、policy hash、原字节派生 bundle 与上下文规模。
- `text_business_cold_replay.json` / `.log`：独立新进程按原字节和 source proof 重建 20 个 bundle；以此最终日志为准。
- `text_business_final_summary.json`：最终数目、字符范围和源路径。早期探针结果继续保留，不能视作修复后当前结论。

代码仍在原主 PR 分支的独立未提交文件，未执行 commit/push。本子任务完成来源可行性调查及第一层可重放业务候选；父代理继续正式结果、独立审阅和 Issue 级交付。
