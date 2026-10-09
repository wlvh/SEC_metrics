# D02 原文事实核验修正检查点

D02 继续表示诉讼披露，不新增总诉讼负债、年末计提总额或案件数。已批准原定义要求有合格 XBRL 事实时记录概念和值；旧 MIXED/79 是跨指标行数，不是 D02 金额。原实现、当前矩阵与 12 份历史 publication 均没有数值 D02 Result，详见同目录 D02_FACT_MEANING_AUDIT.md、d02_legacy_numeric_audit.json。

本次移除了“仅因找到当期 accrual 就整项要求新 typed Result”的过度阻断。支持事实现在沿原覆盖范围、Evidence 和同一可读 ReviewUnit 保留 namespace、concept、原始文本、单位 QName、CIK、期间、显式维度 QName、原数字属性与可重算金额；仅对原件能证明的支持格式给出 VERIFIED_AS_REPORTED_MONETARY_FACT。它们各自保留原始期间和主体，不求和、不把金额填成总负债 Result，也不把生成的解释伪装成原文摘录。

namespace、numeric tag、unit/context、nil、transform 或数字词法不支持时，仅标为 SOURCE_LITERAL_ONLY，value_normalized=null，并在 Review 展示原文和具体原因。现阶段规范化支持 USD/EUR，不换币；其他币种只表示未支持，不声称币种非法。无 format 必须是 decimal 词法；支持的 dot-decimal transform 使用严格三位逗号分组子集。特殊纯 fact 而没有合法文本段落的来源仍不在 SOURCE_EXCERPTS 的支持范围内，程序不会造一句引用；本次十公司及当期反例均有合法原文。

只修改未冻结的四文件。V12、旧治理 helper、正常输入函数、来源证明集合、记录 schema 与共享 Run 文件未由本子任务修改。没有新 AI attempt、HUMAN 身份或 Run 冻结；SYSTEM Review 使用已有 D-06 实现。所有检查 provider/paid/SEC=0/0/0。

## 稳定字节

| 文件 | SHA256 |
| --- | --- |
| scripts/vnext/text_results_v2.py | 26a0fe518cdbb76377d6afcfde82e0a886eb7e9fc730254abd875012ecf1cc93 |
| catalog/r6/D02_legal_disclosures_v1.md | 66e25bccd5235d13d5c5edc03a8eb52f20fd65875a2eadaef961915a192b188f |
| catalog/r6/text_results_v2_policy.json | 16d9b7e46aa73d61f678ff06b0b9b24c1bedb9849840e2d84e90fd3919ce7d3c |
| tests/vnext/test_text_results_v2.py | 61f96cfd8dbbf7883d21e6ef632fed69224391ac220b9ea736b2f82ee32fa487 |

## 验证与首轮证据

- 20 项组件测试 PASS：d02_fact_fix_review_repairs_tests_first.log。包括真实 JSON 落盘、Review 重建、事实重哈希篡改、缺 unit、假 context namespace、nil、旧期间/别主体、无 format 的 1,23、dot-decimal 的 1,23、unsupported comma-decimal、USD/EUR 和未支持币种。语义扫描 d02_fact_fix_semantic_scan.json=[]。
- 独立审阅的原始 12 个反例：../r4-route/d02-fact-review/probe-result.json 及各原始 TEST_ONLY_source.htm。首轮发现 ZZZ 被误核验和无 format 逗号被移除；失败保留，未覆盖。
- 独立审阅对相同原件修后重放：../r4-route/d02-fact-review/recheck-originals-v2/probe-result.json，12/12 PASS，四文件前后 hash 一致；所有例均继续得到 TEXT_V1。USD/EUR 正例保留自身币种；不支持数字 Review/context 均无错误的 123000000。独立真实 JPM helper 检查也通过；总报告 ../r4-route/d02-fact-review/REVIEW.md。
- 修前当期 107M 失败保留于 d02_fact_semantics_audit.json。修前/修后原始 bytes 一致（sha256:47fac924f1ed5370f5e22d35f99b276ddbe4ede652dc04150a80fbb50a151449），精确对照 d02_fact_fix_before_after_identity.json。修后当期反例生成 TEXT_V1，107M 只在其独立事实证据中，不是总额 Result。
- 真实 10 公司 × C02/D02 共 20 坐标，加上述 TEST_ONLY 当期反例，共 21 组原生候选、Evidence、SYSTEM Review、Result、Trace 和 495 Observations 已 JSON 落盘（真实20为490条，合成5条）。见 d02_fact_fix_native/create-summary.json、各公司 records.json/review.md/review_context.json、d02_fact_fix_native_create_first.log。
- 实际20均从 portable-normal-text-minimal（83文件、无Git）正常准备；prepared_input、input_binding、records、SourceReference、source_proofs/admission 及选中的逐字摘录与最小输入首轮逐字段相同。C02 每公司4证明、D02每公司3证明；9份 proxy 的 LEGACY 分类照实保留。
- 实际事实：Southwest 107000000 USD，2023-10-01→2023-12-31；JPM 0/1200000000 USD、2025-12-31 instant，未计提损失区间 min/max 与诉讼事项维度完整保留。其余8家公司没有此受支持集合中的事实，不能由此推断无诉讼。

原字节新进程重放已完成：21/21 PASS，495 Observations、Evidence、Review、Result 和 Trace 全部按 JSON 原记录重建一致。证据为 d02_fact_fix_native/cold-summary.json 与 d02_fact_fix_native_cold_first.log；生成、独立审阅、冷重放及交付时的四文件 SHA256 一致。
