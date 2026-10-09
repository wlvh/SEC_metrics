# 已交付基础财务入口的剩余公司消费者

本批只使用实际main f6ef7886的既有B01/B02/B04/B05公司分派、来源准备、共同计算、普通保存与独立results，不新增指标方法/公共模块/runner，不改变接收中的96/114。代码未改；与原Ford/Salesforce/Macy先导不同的公司任务尚未贯通，故执行一次新消费者验证。原先导60位置、酒店/金融/事件及模型批次不重跑。

复用PR52已提交cross-source-read、batch及full-frame的独立原件阅读，保存本批必要子集和原参考SHA；先核所选原件SHA，再核新出口的值/单位/实际期间。旧published/Run/接受数不是本批正确性依据，DIFFERS不当正确参考。输入用既有完整source-inputs只读，不复制整树或重新GET。

| 公司及明确范围 | 首次CLI | 禁原factory复跑 | 独立results | 实际结果 |
|---|---:|---:|---:|---|
| Enphase FY2021–2025，B01/B02/B04/B05 | 98.828s | 6.871s | .576s | 二十项与原参考值/单位/全年窗一致，165结果/pointer字节保持 |
| Lumen FY2021–2025，同四指标 | 110.649s | 7.056s | .585s | 二十项与原参考一致，165文件保持 |
| Pfizer FY2021–2025，B01/B04/B05 | 108.018s | 5.340s | .559s | 十五项与原参考一致，125文件保持；B02单列待核，不推断失败或零 |
| Southwest FY2021–2024，同四指标 | 初五年99.426s/exit2 | 成功子集5.773s | .572s | 十六项数值/单位/期间一致，FY2025四项实现缺口保留；FY2023B02仅尾零字符串不同，Decimal相等，未改输出 |

全过程socket禁止；复跑和独立读禁止原函数调用，结果目录/指针哈希保持，无新增模型/SEC/NativeRun/接受或active。首次运行使用本分支未提交记录，program版本仍f6、has_uncommitted_changes如实保；记录提交不改生产字节。不把运行行数换算成1950整体完成率。

## 精确未完边界

SouthwestFY2025的原primary与amended材料实际存在，当前主体连续，amendment为0000092380-26-000006。main历史statement入口尚未接该修订，四项返回IMPLEMENTATION_GAP/HISTORICAL_STATEMENT_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED；不是缺源/结构NA/正确零。southwest-fy2025-amendment-gap.json给实际所读依赖。前四年已保存结果不抹掉，也不整体重算；最近请求改成功子集后results列十六成功，原五年失败报告单独保留，不能虚称本次还显示二十行。

PfizerB02 FY2021/2023/2024既有独立读数与旧值不同，pfizer-b02-reference-gap.json保两者、申报和源SHA。当前contract明确当前/前期两个accession角色，旧阅读取当前filing的prior context；需要核相同收入范围及合法前期/重述关系，尚不能任选一个当正确。最初材料只读batch漏FY2021，随后找到full-frame；没有因为参考冲突重读全年或新调模型。FY2022/FY2025 B02已有MATCH参考，本轮尚未处理，其责任继续。

驱动首次假定Southwest全成功，保其原失败；子集读又误期待包含过去无结果的FY2025失败行，之后只读取现成CSV按实际十六行及原失败报告核对，没有重算。尾零断言也只改比较为Decimal等值，原文本均保存。仅驱动假设纠正，不放松主体、期间、单位或业务范围。

## 同一入口的可运行命令

检出实际main f6ef7886或包含它的本记录分支。来源已存在时复用；首次来源恢复沿保留历史分支运行原restore并使用返回data_root，不把恢复父目录当根，不GET。

```bash
python3 tools/vnext_company.py run --company enphase_energy --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric B01 --metric B02 --metric B04 --metric B05 \
  --source-root /saved/sec/source-inputs --work-dir /new/enphase/state --output-dir /new/enphase/runs
python3 tools/vnext_company.py results --company enphase_energy \
  --state-root /new/enphase/state --output-root /new/enphase/read-01
```

Lumen仅改company为lumen_technologies。Pfizer本轮只选B01/B04/B05；Southwest完整五年会显示上述修订缺口，不能把其退出码2视为所有结果失败。已有任务读取自己的原state；输出目录须新。各company.json保本轮实际状态/目录/比较和调用边界，原件参考不修改。完整历史在线发现/补齐、修订适配、其他指标及五年业务责任继续。

## 后继：有限原财务数值修订接收

SouthwestFY25阻塞已定位为消费者未接已成立公共证明：修订只更正Exhibit3.2公司章程超链接，并增加规定的认证；公共annual_amendment_scope_v2严格验证相同封面/Item15、限用途note/链接/签名、无非DEI财务事实和期间不变，实际分类EXHIBIT_LINK_CORRECTION_WITH_IDENTICAL_ORIGINAL_ITEM15，明确允许ORIGINAL_STATEMENT_VALUES。southwest-amendment-scope.json保完整所读说明文字、原件与修订SHA/分类及policy scopeID。首摘要取错rawblob字段KeyError保本地，校正后仅读取scope，不运行财务。

本方薄适配只为B01/B02/B04/B05连续主体消费这一现有证明，不改共享checker/policy/计算或任意关键词。全部修订须有明确原数值许可、无issue/期间不变、further-review=false，否则在金额选择前拒；PartIII仅事件许可不接财务，B07、其他指标、继任主体、前期修订等原边界保持。处理依赖列实际四文件/政策；保存精确scopeID/分类及原修订proof，展示不嵌整份文档。

新20scope例.028s，含无修订不读源、原数值许可、事件-only/期变/issue/待审拒、第二份修订失败拒全部；受影响历史分派/状态及公共paragraph解析联合54例.175s零skip。仅在原Southwesttask补FY25四指标，首20.724s全部READY，原16位132文件字节保持；禁factory复2.039s0、另进程读.576s保五年二十值/单位/实际日期/168结果pointer文件。原四失败日志保持、不重算邻居；源码在提交前已同字节验证，如实标uncommitted。新源/模型/Run/正式接受0。

该修补尚在本短分支，不在main。它将一个具体“来源齐但消费者不支持”缺口变为同公司CLI可用；不证明所有修订、PartIII、PfizerB02冲突或完整1950已解决。本记录以前SouthwestFY25未完段保原时间边界，现本段为后继终态。

公共方提供f79固定tree最小workflow patch已接：只加statement测试路径和原Historical步骤的四个新修订方法，原金融三模块/dispatch/state保持；同实际步骤63例.176s零skip，新四方法实际加载。statement-workflow.json/log。真实FY25公司结果不重跑，新head远端执行另核，不造新runner或无意义触发提交。

后继原件范围核对纠正一个业务判断：PfizerFY2023 B01新结果与原reference同50,914m，仅证明选定事实的数值一致；原table113明确它是Product revenues，另有Alliance7,582m，Total58,496m，因此该位置不再列作完整营业收入正确值。原比较JSON/Result保留，新精确缺陷及原表/native ordinal/重列说明在[后继固定证据](https://github.com/wlvh/SEC_metrics/blob/0dc5de75/docs/evidence/issue47_growth_reference_20261010/README.md)。使用现有optional defect列表独立read已将该一Result扣留，默认公共缺陷登记/收入scope修补待#28，不改共享内核或扩大PR116。Southwest有限链接修订证明及实测不受该发现影响；旧MATCH不能替代业务范围核对。

生产de192公司workflow37983406969/job113999286264实际SUCCESS；原Historical步骤63方法.312s零skip，新四个修订方法逐项已加载/ok，ci-de192-company.log/json保实际执行而非登记名。后继040624只说明Pfizer范围新发现，不改此生产代码，按自身CI读终态；不因纯记录再次计算财报。
