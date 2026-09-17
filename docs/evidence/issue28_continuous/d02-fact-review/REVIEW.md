# D02 事实核验修正：独立复核完成

结论：初轮两类过宽核验已修复。直接读取初轮保存的12份原HTML副本重放，12/12通过；补充实际保存JPM原件独立helper核对通过。作者4文件新hash与两次审阅始末hash完全一致。本轮不修改仓库，不安装输入、不创建/冻结Run、无V13整图或正式采纳信用；调用0/0/0。

## 原问题及修后行为

- 任意3大写字母曾获得已核验货币标识。现在政策明确目前只支持USD/EUR；ZZZ等其他声明保留原文+SOURCE_LITERAL_ONLY+D02_FACT_CURRENCY_NOT_SUPPORTED，不称币种本身无效、不转换USD。
- 无format的1,23曾错误去掉逗号成为123000000。现在无format仅支持明确XML decimal子集，未支持文字保留原文，无normalized值。
- numdotdecimal的支持子集明确限制分组语法。1,23在该子集之外只保留原文；这是程序支持边界，不把其他transform格式自动宣称为源数据错误。
- 明确numcommadecimal的1,23继续只保留原文；修后上述3个逗号变体的Evidence、review_context和可读Review均没有123000000。

初轮原证据保留于 probe-result.json、FIRST_FINDINGS.md 及各原例目录。修后输出放入 recheck-originals-v2/，没有覆盖原例；其文件源摘要可逐项对照。

## 其余通过边界

USD、EUR、本期同实体107M继续作为原报告补充事实核验并显示；最终仍TEXT_V1文字Result，未成为总诉讼负债。假transform URI、假ISO4217 namespace、坏CIKscheme保留literal并给理由；伪fasb/us-gaap URI不成为合法候选。2023期间保持2023，另一CIK保持OTHER_ENTITY_AS_REPORTED，两者都不进入本公司本期accrual候选。12例合法文字都继续PUBLISHED TEXT_V1（仅测试原生记录状态，无正式发布信用）。

可读Review逐事实显示namespace、concept、原文字、归一值、单位、原context和维度、verified_context、locator、数字属性、核验状态及理由。Evidence重建重新运行原件parser与新helper，不能仅重签事实金额来改变判断。

## 实际保存原件

JPM 2025 10-K，source SHA4d9febdbc2038dcdca8726053286df4cbbfd48885051cbd781efcc3becb66a23。新helper核对两项原生 LossContingencyRangeOfPossibleLossPortionNotAccrued：原文字0和1.2、USD、2025-12-31时点，分别MinimumMember和MaximumMember，归一值0/1200000000。完整ThreatenedOrPendingLitigationMember维度及CIK0000019617均保留，均明确aggregate_or_target_period_value_asserted=false；没有把零下限、未计提损失范围或最大值变成诉讼总负债。完整输出在 actual-jpm-v2/result.json。

此项仅独立运行保存原件的候选parser与新事实helper，不重复作者正在做的10公司完整原生文字重建，也不称已通过当前V13 Run验证。作者20项测试与21例实际原生材料另有其自己的执行证据，本报告只认领上述12原副本+1真实源独立helper检查。
