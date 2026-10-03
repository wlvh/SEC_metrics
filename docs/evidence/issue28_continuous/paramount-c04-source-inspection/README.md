# Paramount C04：当前原件与同主体比较限制

本项只读恢复当前剩余坐标，没有改运行代码或规则、没有重跑340、没有发SEC/provider请求。`inspect_current.py`实际执行当前`prepare_saved_governance_input`、`auditor_document_views`、`_governance_resolution`；当前结果仍为`C04_COMPARABLE_AUDITOR_FACTS_MISSING`、value=None，result_id仍`sha256:f6616f6a8f7d985a8092c76a7895649c8b010d3e9b7758c3ceb0c224ebdf1ef5`。这是当前源重建及resolver复验，不是新增完整Run或390完成信用。

## 已核对的事实

- 当前主体CIK2041610，来源政策为SUCCESSOR_REGISTRANT_ONLY；CIK813828是登记的相关前身，cross_entity_combination_authorized=false。
- 完整已保存2041610 submissions中只有一份10-K：2025年度、0002041610-26-000011；无同CIK前期普通年报、无history shards。2026-04-24的10-K/A为同2025年修订，不能充当前期年报。
- 原生审计师事实：当前10-K找到PricewaterhouseCoopers LLP；10-K/A未提供对应AuditorName，现有同期间原件fallback正确选回10-K，并没有把当前审计师漏掉。
- 完整当前年报Item9明确`None.`。当前审计报告说明Successor报表期间为2025-08-07至2025-12-31；另份报告明确2024年度及2025-01-01至08-06报表属于Paramount Global and its subsidiaries (Predecessor)。审计报告还明确公司或前身自1970年由其审计。
- 没有同CIK DEF14A，但10-K/A已给PartIII。Item14说明PwC提供2025/2024服务，费用脚注明确2024为Predecessor期间；不能把这个2024数字或同一审计事务所名称当成同registrant前期AuditorName。proxy不是C04必需替代材料，不能因为没有DEF14A就把C04归为缺proxy。

原件完整SHA、原文块及字节范围见`source-anchors.json`；机器当前来源证明、清单及resolver输出见`current.json`。

## 另有具体来源路线遗漏，不能只写“真实缺资料”

当前元数据选择器及C04 v2 Spec均仅列8-K、8-K/A。当前完整清单另外给出：

| 形式 | accession | 日期 | 已保存清单中的Item字段 |
| --- | --- | --- | --- |
| 8-K12B | 0001193125-25-175046 | 2025-08-07 | 1.01,1.02,2.01,2.03,3.01,3.02,3.03,5.01,5.02,5.03,5.05,7.01,9.01 |
| 8-K12B/A | 0002041610-25-000029 | 2025-10-23 | 7.01,9.01 |

这两份没有进入当前4份普通8-K集合。清单Item字段未列4.01只提供线索，不能替代原件/头文件检查。通过实际本地`_Sources.read`核对，两份primary及header共4个URL都明确SAVED_SOURCE_MISSING，详见`variant-local-availability.json`，未触发获取。这不是声称原文含4.01；在读到原件前，该内容未知。

因此，“四份已检查事件没有4.01”只能按当前明确支持的8-K/8-K/A范围解释，不能扩写为所有实际8-K相关申报已完整覆盖。新注册发行人的8-K12B变体是来源发现/读取路线的具体开发责任；旧Spec和历史结果不能被悄悄重解释为已覆盖这些形式。

## 当前结论与下一责任

本坐标有两个独立层次：

1. **已证明的主体/比较事实限制**：同registrant前期10-K不存在于完整保存清单；2024比较财务和审计费属于前身。不能换CIK凑齐，不能直接改结构性不适用。
2. **尚未解决的实现/验证责任**：当前规则没有覆盖8-K12B家族，且对应原件未保存；现有明确Item9 None及连续审计原文也没有当前C04 v2批准的替代接受路径。

不把整个问题归成披露不足：原文对会计师变化及审计连续性有明确陈述。也不据此擅自输出0：v2当前否定路径要求同registrant当前/前期AuditorName相同并具有完整支持形式事件集合；以Item9 None替代前期比较，或跨前身比较，会改变现有接受条件，不能在这次有限来源调查中静默完成。

建议后续先登记并处理通用8-K12B/8-K12B/A来源形式（保留旧版本语义），在现有总授权下集中安排缺少的4个有限SEC原件/头文件来源；这不是新增预算请求。其后仍须明确新注册人没有前期同CIK年报时，是否已有授权的接受规则可以采用原件明确否定陈述；没有则作为具体规则决策与其他必要决策集中处理。不得把缺前期文件自动等同于无审计师变化。此时其他无依赖开发继续，C04保持未完成。

新增完整真实坐标0、新增provider/paid/SEC=0/0/0；无生产或采纳信用。首个调查脚本误名inspect.py遮蔽了Python标准库，已改名，初次日志保留；不是业务来源失败。
