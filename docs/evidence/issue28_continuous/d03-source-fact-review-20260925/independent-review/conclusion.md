# D03 来源事实模块：6e5a85bf 限定独立审阅

**结论：限定审阅未通过；发现一项会错误证明“当前调查涉入”的阻断问题。**这不否定 JPM 原句的肯定含义，也不表示已经发现真实公司结果错误。修复并复核本问题前，不能将本模块的 `SOURCE_REPORTED_FACT` 普遍视为已证明的当前行动事实。

## 审阅身份与范围

- 精确补丁：`6e5a85bf96d9086d51fbddeb0ab38f446d3fc19e`。当前 `scripts/vnext/regulatory_statement_facts.py`、`tests/vnext/test_regulatory_statement_facts.py` 与该提交的 Git blob 一致，分别为 `ed33ce653f3f8417017547e37169cca05e930cef`、`d10c811efd4fc742a39e82a2710d5dd5ec8a69aa`；SHA-256 分别为 `3dda5cded82a471f1d5559654f44f50701439942f833f18526986409594057b2`、`5e27b11206dac52e2cabdd898418abb727e6d49fc5555434fa3732caa5334541`。工作树对该提交的这两文件及所给 `d03-source-fact-final.json` 无差异。
- 审阅该模块对肯定、假设、否定、主体、期间的来源事实判定，以及 JPM 原句的证据与样本角色。当前已变化的 `r6_regulatory_semantics.py` 接线不在本报告的审阅范围。

## 阻断发现：后置限定词仍被标为当前肯定事实

`regulatory_statement_facts.py:59-69` 只枚举少量否定、情态及结束用语；同一句在政府调查短语**之后**明确说调查已完成、未来才可能发生或不涉及本公司时，规则仍落入 `:70-84` 的 `AFFIRMATIVE`、`CURRENT_AS_REPORTED`、`SOURCE_REPORTED_FACT`。`check_aggregate_classification` 又在 `:89-95` 把这种标记当作已证明事实，拒绝非 `CURRENT_REGULATORY_ACTION / ONGOING_AS_REPORTED` 分类。

隔离构造的反例及实际输出见 [probes.log](probes.log)：

| 来源句中的调查限定 | 实际输出 | 应保留的边界 |
| --- | --- | --- |
| `all of which were completed in 2020` 或 `all of which have concluded` | `SOURCE_REPORTED_FACT`、`CURRENT_AS_REPORTED`，无原因码 | 调查当前仍在进行并未被证明 |
| `that can arise in the future` | 同上 | 未来可能性不能算当前事实 |
| `none of which involve us`、`that are hypothetical` | 同上 | 否定或假设不能算本公司当前涉入 |

同一探针的对照句用 `resolved` 或 `may` 时正确转入 `SEMANTIC_REVIEW_REQUIRED`；这说明问题在限定表达的覆盖与作用域，不在测试环境。对 `completed in 2020` 的错误标记调用 `check_aggregate_classification`，会实际抛出 `D03_AFFIRMATIVE_AGGREGATE_FACT_CLASSIFICATION_CONFLICT`，拒绝更谨慎的分类。这里证明的是模块可能误标并误拦截；未运行模型或原生 Run，不能据此宣称已发生生产错误接受。

建议修复时按政府行动短语后的实际从句判断其时间、条件与主体；无法确定作用域时降为 `SEMANTIC_REVIEW_REQUIRED`。仅补几个同义词不足以封住开放式限定表达。保留 JPM 肯定原句的正例，并加入上述过去、未来、假设、否定及对照反例，再复核修复差异。

## 已核实的正向事实及限制

JPM FY2025 保存原件 `evidence/request_attempts/4d/4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23/jpm-20251231.htm` 的完整 SHA-256 与路径中的 `4d9feb...` 一致。`d03-source-fact-final.json` 中第339块原始字节范围 `1419062:1419419` 的 SHA-256 是 `185199a46f8e4dae32972a61de6118cb249d2487a1fa89159a3872b03ed67d6c`；第140块别名定义范围 `1282800:1283589` 的 SHA-256 是 `34a66111476bf80709b2aea8879fe0453b2b9fc41c09f7729aa3bf56cd055ab5`。两段均从保存原件重算相符。别名段明确把 `JPMorganChase` 绑定到 `JPMorgan Chase & Co.`。

第339块的完整首句以现在时说公司被列为被告或以其他方式涉及多项民事和政府法律程序，并明确列入美国及非美国政府机关的调查与执法；它是**肯定的总体涉入陈述**。原句没有案名、准确案件数或具体事件日期；不能从 `many` 推出数量，也不能推断违法、有罪或每项调查的被调查对象。保存事实的 `case_identity`、`case_count` 为 null，`event_dates` 为空，`whole_source_coverage_proven=false`、`native_result_created=false`，与这一边界相符。JPM 已用于此前修复，这次只算回归样本，不是未见留出。

规定短测试 `PYTHONPATH=scripts python3 -m unittest tests.vnext.test_regulatory_statement_facts.RegulatoryStatementFactsTest -q` 通过：6 项、0.001 秒，见 [short-test.log](short-test.log)。它覆盖原 JPM 回归、简单的情态/否定/过去时/主体替换及分类冲突，但没有覆盖上述行动短语后的限定从句。未重跑约 135 秒的 JPM 大材料测试；其旧成功日志只能作为历史记录，不能替代本次完整材料复验。

本报告没有审阅已变化的请求/响应接线、完整原件覆盖、模型内容判断、D03 原生接受或生产发布；没有真实 provider/SEC 调用、账户操作、提交、推送或归档包。Issue #28 当前执行范围与权限已实时读取；本次审阅不增加调用或生产权限。

工具调用统计：19 次 `functions.exec`，其中 37 次内部 `exec_command`，另有 1 次 `apply_patch`；若两层均计，共 57 次，低于 80 次上限。普通消息为开工说明与最终报告两条，无提问；耗时低于 90 分钟。
