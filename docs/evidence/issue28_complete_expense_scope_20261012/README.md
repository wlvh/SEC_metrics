# 完整费用损益表的收入范围：公共接入与公司结果

本批复用 #47 固定250be450的两文件实现及原件材料。它解决主干只识别 cost-of-revenue/cost-of-sales、不能消费完整 CostsAndExpenses 损益表的问题。仅显式单收入路线扩展，V1和V2默认不变；没有重建收入选择器、变更B02原件首次报告口径或引入模型。

## 来源与业务边界

准入需要同一完整合并损益表中的单一收入行、完整费用组/总额、经营损益；主体、全年实际期间、列、USD/可见单位/scale以及primary/XML均一致。收入减完整费用须等于经营损益；额外收入、非零或未标记中间项、错误主体/期间/单位、范围限定仍拒绝。原件明示同一DEI注册人与合并子公司的别名定义只用于绑定表头，保留原文跨度；不删Global等名称后缀，不按公司名特判。原fixed-zero/dash处置收益仅记录其同context/USD的中性零，不授新数值概念。

Root独立从两原primary重新读SHA、原生金额文本/sign/scale、CIK813828、实际年度无维度context、USD及别名原文跨度。2024原收入29,213m、完整费用34,482m、经营损失−5,269m；2023原收入29,652m、费用30,103m、经营损失−451m。完整原件/表范围仍由共享读取器证明；只核金额一致不能给完整范围信用。verify_originals.py、original-witnesses.json记录执行。两源各自准入，不借本期的前期比较数替代原件。费用中的减值不变成B03加回。

原独立驱动误用parsedfact的concept键（实际qualified_name），后遇MappingProxy序列化，失败日志保留；只修驱动，不动生产。初独立比值用current/prior−1，Decimal运算次序丢最后一位；按已批准growth的(current−prior)/prior重新记录精确−0.01480507217051126399568325914。不是修改指标或重跑业务来迁就预期。

## 本方确认并修复的有限误拦

Root初测确认P2：合法发行人财年2026、原DEI2025的完整费用源，主函数已解column_year2026，但子函数仍按原2025检查费用列，拒绝COLUMN_PERIOD_UNPROVEN（fiscal-label-before.log）。仅把既有column_year传给费用子检查；默认None保持子函数旧行为，原actualdates、DEI、引用和范围不改。新小回归同时保合法冲突与错误源/列拒绝。

120来源/单行/V1/历史控制0.978s、55当前consumer/计算/dispatch控制0.342s，errors/failures/skips均0。上条给peer的消息误写116，实际required日志120为准。peer原115控制和真实公司/源执行按精确旧版本保留，不以其绿灯代替本方差异验证。

## 正式公司入口闭环

Root在独立新空状态执行正式公司run：Paramount FY2024单B02，真实保存SEC源→当期和前期来源/输入检查→共享收入范围→配对/Calculator→保存→CSV，17.780822s得到ratio−0.01480507217051126399568325914、原3a8ca984 Result、完整2024。模型/SEC网络禁止，未mock来源选择、Calculator或写入。

禁止历史case/range、两Calculator及paired reader的同输入复跑0.332584s，NO_SOURCE_CONTENT_CHANGE，零计算/新Result；七结果文件保持。独立results进程0.128417s得到同值/ratio/CIK/年度/日期/ID，18状态文件不改。first/repeat计时仅CLI main，read含解释器/导入，不能拼成提速比例。verify_company.py用显式source-root/work-dir/output-root，新状态在本方issue28-development-evidence，不写peer旧状态。actual-company.json保参数、来源、结果与计时。

这证明一家公司/年度完整B02路径及本批公共源结构，非全部28缺口、当前全部十家公司、390、模型验收或正式采纳。原Macy FY22不完整总收入真负例及同额度/失败记录保留。成功历史证据不改签，任何未核范围不填值。

## 组合与复用

本地源代码先正常结合actualmain dbfea的完整同树428d99与fixed250be，再执行本方P2/公司验证。源码/测试为实际未提交树，原HEAD14e7与被测改动在tested-tree.json记录；后来的公开SHA不倒称已执行。main114/302新E01未消费本次B02路径，必要公共组合随后按实际差异核验，已收到/未收到范围分开。原peer独立新task17.135/复.976/读.077、首次迁移outer错误及同原件scope的记录只引用[原记录](https://github.com/wlvh/SEC_metrics/blob/250be450d59143be3ba70f1555d15df080c08444/docs/evidence/issue47_b02_scope_receiving_20261011/complete-expense-consumer/README.md)，不再重包/重跑。

Root单写publiccore及本批适配；#47拥有历史consumer，提供原件/执行边界。无新SEC/provider/paid、账户操作、机会重置、Ready、作者merge/采纳/deploy/active。后续现行接收顺序和Goal保持。

## 最终交付范围与既有main

已正常承接接收者main302074f4（E01/113/114）。Root财务验证在main dbfea＋本两文件改动执行，E01不被本次B02选择/处理；未改C04/A13/记录控制器。四个祖先元数据引起的本地冲突文件全部恢复为实际main302字节，随后176来源/当前consumer/历史dispatch控制1.254s零skip。不是接收者的50格E01重跑。原main已接收内容保持，代码差异只两收入文件及必要CI注册。

Root用Macy原SHA876f真实FY22源再验证仍NO_REPORTED_TOTAL_PROVEN，源/原期间保持，不放错误数值。现行PfizerFY25的实际原件consumer得到与已核179相同b1d89/value/unit/actualperiod。外层驱动猜错完整小数，原失败log保；只读完整已返回Result与原source-checked记录核相等后保存recovered.json，不重跑为修补预期。

不把peer大生成JSON/全部来源assessment重新作为本候选大diff搬入。它们在固定250be原记录保留，本方磁盘副本保留；本PR只链接出处和本次小验证记录。original-probe-plan.json仅保本方已读两原件的原生序号/金额/context/定义跨度，用于独立核对原始字节；不是生产来源包、模型输入或隐藏必带答案。公司入口仍只读取真正Source和规则。

## 接收退回6119475258：新增证明与旧处理隔离

接收者的完整原件对照发现：FY2021/22完整费用后有非零Gains on dispositions，新证明不成立却直接抛错，阻断了原B01/B03处理。本方原green不解除退回。本修补仅将SELECTED_REPORTED_REVENUE_COMPLETE_EXPENSE_*这条新增证明的不成立记为complete_expense_rejections，不准入行，让旧V1/caller继续自己的规则；不吞其他IncomeSourceError/来源身份错误，不改变费用数学关系或给失败证明信用。默认没有新增证明失败时不增加字段。

先补失败回归复现异常；修后完整新增proof控43/.608和联合179/1.284零skip。包含非零/未标金额不授完整scope、actual B01 adapter/Calculator回到V1 NO_DEMONSTRATED_SPLIT原值、真正来源身份错误仍拒。原expect-raise测试改为精确不准入/原因检查，没有改成接受错误表。

独立actualmain302与候选两个新任务/同保存来源，精确只跑受影响FY21/22 B01/B03四行。主干首跑完成后，外驱动误把输出前缀当实际输出目录，报FileNotFound；原错误保，按官方run_summary只读续接原已保存结果，未重基线、elapsed/exit未保存诚实null。候选首42.723807s恢复四正确结果；before/after每行value、unit、actualperiod、fiscalyear、status和完整ResultID全部相同，four-row-comparison.json记录。B01为28,586m/30,154m；B03为0.2339256978940740222486531869/0.09109902500497446441599787756。

before/after禁case/range/两Calculator复1.063964/1.051056s，全部NO_SOURCE_CONTENT_CHANGE/calculationfalse/结果字节保持；独立results .133978/.135073s不写状态。此为实际生产接缝，未把processor mock成功。已有FY24成功代码路径未变，原两原件/scope/17.781公司成功证据复用，合法小正例仍通过；接收者将按其范围亲复十家公司当期与历史，未由本方声称该广泛复核通过。newcalls0/0/0，旧回答/状态不改。
