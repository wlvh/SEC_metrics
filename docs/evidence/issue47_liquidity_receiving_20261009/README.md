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

## 其他公司同家族接收

未重做已有业务阅读。Salesforce、Marriott、Pfizer、Lumen、Enphase各五年10位置同公司命令成功，现行值/单位/余额时点与原阅读零差异；首次分别49.010、39.261、68.320、52.025、47.552秒。Salesforce、Marriott、Pfizer未变输入复跑分别2.186、1.934、1.905秒，计算0、70文件不变；随后新增修订scope元数据不用于重开这些无修订年度批次。Southwest首47.602秒，前四年8位置成功且0差异，25两项初拒绝后以共同即期检查定向接收成功，见上一节。

JPM22–25补8个已选年度位置真实读取234.356秒，按同一既定行业规则N_A_STRUCTURAL；连此前21共五年10位置，独立公司读取保持无数值。Paramount21–23来自813828自身申报的六个余额值，25来自2041610两余额值，各与旧阅读同一；24两项因共同说明解析缺口具名扣留，不以状态行数宣称完整交付。该家族十家公司年度均已触达，不能当作100个位置全部业务完成或1950完成；仍须修复Paramount24、接入main和历史在线来源准备。阶段版本、旧拒绝、结果及正常CSV出处保存在[接收摘要](broader-company-receiving.json)与[完整消费者材料](broader-company-materials.tar.gz)，只结果/日志而非来源/程序整树。原35模型调用、SEC账本、旧Run及接受登记没有改写。

## Paramount FY2024公司消费者接收（后继PR79依赖）

公共PR79/1cc80525的限定修复已交付，本文前述“FY24仍扣留”描述此前真实终态，原结果和失败继续保留。消费其main→候选的三源模块差异，保留本分支既有rules_root可选适配；没有整支合入公共开发或拷新控制器。历史余额适配明确传note_layout=inline-paragraphs-v2并登记三个实际处理依赖；公共默认blocks-v1未变，不按公司/年份写特例。16个公共完整API/排版小例0.099s和36个受影响消费者/状态/期间小例0.118s通过，零skip。

只对原公司任务FY2024 B08/B09重新处理，首16.820s，得到流动比率1.302253140899179732115045167 ratio和现金储备2,661,000,000 USD，2024-12-31时点；所选CIK为813828，两值/单位/测量期和原primary bytes与已保存原阅读一致。新版INPUT_PROPERTY_PROVEN说明、原13块和实际段落/原始跨度、条件补偿说明及原件身份通过共同input-assessments保存。它仅证明这一余额输入范围，annual_continuity_proven=false、debt_completeness_proven=false；August7/August8年度流量冲突没有解决。

复跑0.628s，源准备/graph调用0、86保存文件不变；另一进程公司results/CSV0.075s。原FY2024两份WITHHELD/null普通结果仍可读；未请求的FY2021–23及FY2025八个当前结果的ID/保存根/值/单位/窗口与前次公司读一致，未重算其他98位置。已成功的FY2025继任主体最终任务按原版本保留，本轮只更新原FY2024所在任务，不跨任务手工拼结果。

[本次主要增量记录](paramount2024-paragraph-receiving.json)和[实际新旧普通结果、CSV/出处及检查日志](paramount2024-paragraph-receiving-materials.tar.gz)已保存。仍为分支接收、未main、无正式接受或新Run；新provider/paid/SEC=0。实际main接续需公共PR79源码和PR76本消费者组合，不用来源属性评估代替公司数值，也不借用公共方接受信用。
