# 历史流动性指标开发接收

独立接续PR75/5272797e，B08流动比率、B09现金储备使用已选财年对应的实际余额日期；保留发行人财年作为年度容器。公共控制器、保存器、读取器、公式及测试运行器不另实现，PR71/75候选不扩。此分支尚未创建下一份Draft PR，也未入main；仅已保存、未修订、连续主体，在线来源发现、修订/继承接收未含。

同一公司命令Macy’s FY2021–FY2025两指标10位置，首57.243秒，值/单位/余额日期与已有原件阅读零差异；禁止选源/计算复跑1.749秒计算0，70文件未变，独立读0.075秒。FY2023余额时点为2024-02-03，B08=1.374492099322799097065462754 ratio、B09=1,034,000,000 USD，CSV仍标FY2023，不把余额当53周期间流量，也不按日期年份标FY2024。JPM FY2021两指标根据既定non_financial行业规则为N_A_STRUCTURAL、余额日2021-12-31，不用零替代，不假称未取得来源；真实选源耗时96.948秒。

后续增加计算来源缺口的具名扣留，调用现有Calculator，不吞未知异常或宣称原件没披露。完整来源的构造控制5.501秒验证WITHHELD/null与明确SOURCE_OR_IMPLEMENTATION_UNRESOLVED；人为制造的缺口不是Macy’s财报结论。补此分支后只重验受影响FY2023的真实两个位置，首/禁止计算复跑/另进程读取见verification.json；没有盲目重跑十个位置。12项短测试0.017秒过，包括同一控制器分派、原酒店/收入factory保持及未接修订/继承前置拒绝。

主要实际记录在[verification.json](verification.json)，原样CLI、控制驱动、CSV/出处与普通结果在[consumer-materials.tar.gz](consumer-materials.tar.gz)，不复制整棵来源/程序。新增provider/paid/SEC=0，无新旧式Run或接受。年度选择与正值已验证；最终扣留复跑/来源变化/真实混合复用和更广公司接收继续做，完成前不写为最终交付。已验证阅读直接复用，其他期间/主体/单位/缺件要求保持。

后续接收成立，准备独立Draft候选：Ford FY2021–FY2025两指标10位置首62.537秒，原业务阅读的值/单位/余额日零差异；禁止选源/计算复跑1.825秒、计算0、70结果/指针未变，独立读耗时见verification.json。最终共享控制器的构造小状态接收：只给B08增加明确的测试处理依赖并制造计算源缺口，4.838秒当前B08具名扣留，B09原值复用；同输入复跑0.329秒、selector0、无新结果目录；后续只请求B09，独立读B08仍null/WITHHELD且requested=False，旧成功保存文件留存。这是构造控制，不是财报缺披露。

真实Macy’s FY2023同CLI混合B04/B08/B09 9.040秒：两余额指标新算，B04直接复用、原选源0、65旧B04结果/指针文件不变。共同控制器现有源/配置变化、期间隔离与恢复反例连同本历史case/分派共36项0.100秒、零skip；未写第二个控制器或复制整棵来源。能力合同结构检查通过、两个副产物恢复。原代码测试边界保持；下一个Draft只接这段B08/B09流动性范围，不借此声称main、全部五年或在线取源已完成。

使用同一入口，最多五个发行人财年：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company ford_motor_company --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2025 --metric B08 --metric B09 \
  --source-root /saved/sec/source-inputs \
  --work-dir /writable/ford-state --output-dir /writable/ford-csv
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company ford_motor_company --state-root /writable/ford-state \
  --output-root /writable/daily-csv
```

Macy’s改为macys、仍2021–2025；余额时点以原件年度末日为准，实际年度容器和来源URL/申报/单位留在CSV与出处。当前模式分派保持，其他家族的原factory/处理依赖未改；旧Run仍由原版本读取。两家公司20位置没有重新阅读或重建旧native Run，只验证新公司消费者。其余公司接收、修订/继承及在线历史来源准备继续是实际缺口，原完整目标不缩小。

## 同家族的修订与主体边界接续

实际其他公司验证发现原接收守卫将所有10-K/A或继任主体拒绝，形成了Southwest FY2025和Paramount FY2025的接入缺口。既有共同catalog已经允许B08/B09的current/current_instant/ALLOW，因此历史消费者改为直接向同一inspect_instant_balance_amendment提供所选申报原件，不调用latest准备，不另写修订核心，也不改政策/公式。范围限所选CIK的年末余额，原年报收入August7/August8冲突与短期流量、旧拒绝记录保留，不推为可比年度或跨主体拼接。

共同检查Paramount25实际返回INPUT_PROPERTY_PROVEN/issues为空；同公司两项最终13.120秒得到原1.256722332295499575431644495 ratio与3,274,000,000 USD、2025-12-31时点，原阅读值/单位/日期相同。成功scope检查、CIK及annual_continuity_proven=false保存为既有input-assessments侧车；禁止选源/计算复跑0.543秒、16文件不变，独立读取保留。Southwest25初次两项实现拒绝保留，接后两项9.421秒得到0.5168940573207581723285413424 ratio及3,231,000,000 USD。构造未决修订检查4.880秒验证计算调用0、WITHHELD/null及具名AMENDMENT_INPUT_UNRESOLVED，不冒充真实财报结论。

Paramount前身21–23六项同年自身CIK已成功，24两项仍具名扣留：共同annual._note把原说明的10-K等内联font文本拆成独立块，95到108共13块触发旧8块界限。完整说明三段与原始跨度已保存，明确只补PartIII10–14而无其他改动；这属于公共解析缺口，已交#28，不将计数界限改大、删块、改原文或复制检查器放行。元数据未决不等于真实金额变化，也不取消后续修复责任。[定向主要接收摘要](amendment-receiving.json)及[完整有限材料](amendment-receiving-materials.tar.gz)保留正反证据。

公共提供的PR76最小短CI patch已原样接收：既有类共19项0.018秒、零skip；36项受影响状态/期间/历史case控制0.106秒过。原580九项CI已全部SUCCESS；后继提交独立核新CI，不借旧绿灯。当前case接收修订/选定继任主体的即期范围，原文开头的“未修订连续主体”只解释首个开发版本，不能用于描述此后继现行边界。main仍未接入，在线来源准备、Paramount24解析和其他业务责任继续。
