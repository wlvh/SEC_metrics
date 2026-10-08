# H4 后续：历史收入期间冲突与 B03 普通 case 接收

接续已交付 PR71，不扩大该酒店/公共测试收口 PR。本次代码在原历史分支开发，尚未 main；主记录为 [verification.json](verification.json)。两份完整源组件以逐字节可还原的gzip归档保存，原始SHA/大小及归档SHA见[component-archives.json](component-archives.json)，源内容未裁剪；case测试一次解码共享准备。复用公共 adee3036 的收入期间检查、原件准备及保存/读取函数；没有新增计算器、controller、runner、来源获取或模型试验。

## Paramount FY2025 的实际影响

原历史 `_successor_income_input` 未消费公共可见期间检查，并在建立 Result 之前调用当前收入准备。旧“Aug8已确认、仅146天年度长度不适用”不能解释当前来源。已接同一公共检查，且先核当前 accession 等于指定历史 accession，再允许当前输入或失败用于历史目标，避免把当前报告的冲突赋给其他年度。

实际选中 `0002041610-26-000011`：原生 context 起日2025-08-08，可见 `table_000060` 第2行/第24列的表头为 `Period From August 7 - December 31,`，年份由同列第3行2025证明。历史B01/B03现为 `ORDINARY_INCOME_VISIBLE_PERIOD_CONFLICT`、WITHHELD/null，保留表格/格定位、原始文字、source reference及两种日期。年度容器仍2025-01-01至2025-12-31，不选择Aug7/Aug8，也不年化、拼前身财务或修改旧Run。

两组件经公共 `save_calculated_case` 保存/读取0.448秒；保存器被禁止重选最新输入仍通过。另一进程读取0.254秒，14个文件不变，原ResultID、两日期及原因保持。必要的B03→B01依赖也扣留，不制造缺失依赖或旧成功补数。原记录器把公共证据dict误当list的失败保存在 `first-record-error.log`，B01已保存组件直接复用，仅补B03和记录检查8.713秒；不编造未保存的最初两项总耗时。

## B03 通过同一公司入口

```bash
python tools/vnext_company.py run --company marriott_international \
  --source-root /absolute/saved-source-root \
  --work-dir /absolute/company-state --output-dir /absolute/company-outputs \
  --metric B03 --period fiscal-years \
  --fiscal-year-start 2024 --fiscal-year-end 2025
python tools/vnext_company.py results --company marriott_international \
  --state-root /absolute/company-state --output-root /absolute/daily-export
```

薄 `historical_saved_case` 将已有历史源组件转换为公共case：只检查MetricResult/Trace、依赖集合、Spec闭包、公司与实际期间，保留输入/结果身份和原件证明。历史选年与原有Calculator仍负责计算。源目录不需要catalog/程序/计算配置；规则来自程序目录。IO仅定向接公共 `_save_case`/`read_saved_result` 的input-assessments支持，旧当前case准备函数未替换。酒店请求继续原factory和原处理依赖，旧native任务继续原入口；混合B03/酒店单次请求暂明确拒绝。

Marriott两年实际原件支撑及数值：

| FY | 经营利润m | 折旧m | 摊销m | 收入m | B03 ratio |
|---|---:|---:|---:|---:|---:|
| 2024 | 3767 | 128 | 255 | 25100 | 0.1653386454183266932270916335 |
| 2025 | 4141 | 145 | 313 | 26186 | 0.1756281982738868097456656229 |

两年原件D&A检查为KEEP/批准组成；原生ordinal、主体、USD、期间及既有合同摊销/减值检查保持。B01依赖位于原记录中，不要求先执行其他公司或手工拼接。公司CLI首跑6.309秒、禁止resolver计算的复跑0.431秒、独立读0.210秒，18个Result/指针文件字节不变；没有复制源树或程序树，也没有重跑酒店或原Macy两年B01。此前case/API接点探针6.258秒与CLI场景分别记录，不混成一个耗时。

同任务请求2025–2026：2025复用不计算，2026明确SOURCE_UNAVAILABLE且命令退出2；请求0.394秒，随后读取0.207秒，2024/2025旧值均保留、2026无值，18个旧文件不变。

只补测已恢复来源中的2021–2023（未重算2024/2025）：公司范围处理13.411秒，三年B03均ALL_BRANCHES_REJECTED，Trace明确D&A两个结构化分支MISSING_CANDIDATE；B01依赖分别13,857m/20,773m/23,713m。没有批准CompanyFacts候选不证明财报没有D&A。已知2021原件138m折旧和带类别165m/62m摊销的限制承接前轮记录；后续需要原件范围与包含关系适配，不能猜总额或把本次case保存算作五年B03业务接受。

## 验证与剩余边界

39项受影响小例0.209秒通过，包含历史收入跨accession拒用、冲突证据/依赖、case重复/缺依赖/错公司/期间/Spec、B03分派、原酒店factory、旧native分流、历史D&A共享检查及状态复用。五项真实Paramount源检查8.873秒通过；旧实际日期成功断言转为同来源负例，XML与原生同值不能覆盖可见表头矛盾。未把机械格式/来源case保存提升为语义完整接受。

新普通B03 factory目前只接已保存、未修订、连续主体，修订/继承主体和其他族的普通适配明确IMPLEMENTATION_GAP。原历史组件对同一最新继承主体的日期冲突修复已完成，但不等于继承主体的普通公司B03接入。历史在线发现/补齐、模型验证和完整五年业务继续未完。公开公司结果仍为开发候选，不是正式采纳；原源码/原回答/旧Run/失败和固定模型运行包不改。新SEC/provider/paid调用均0，账本仍1547行＋224保守计数＝1771/1867。

能力结构检查在实现提交后通过，16.873秒，两个检查器副产物按检查前字节还原。提交前因HEAD仍为旧测试字节的失败保存在capability-alignment-before-commit.log；不把结构检查当业务或模型接受。

当前历史PR52原CI37788307281快测FAILURE，191入口中8个非零，见[精确摘要](legacy-fast-ci-summary.json)。五项旧authority加载被normal_source_authority祖先字节先挡；其余为历史exact变更集合、旧enrollment/resign拒绝和parser字节断言。没有新H4业务断言失败由这个日志证明，也不能把本地39＋5通过写成全CI通过。公共runner/CI一方集成，旧来源/Run/快照不重签。

## 旧年度来源缺口的最小适配需求

后续只读原件普查11.463秒，未重建公司或Run。原生事实和完整必要段落证明：FY2021/22/23摊销165/197/226m分别已包含62/83/122m费用报销项；折旧138/114/122m已包含49/35/37m报销项。不能将这些子项再加一次。2021跨页折旧段紧邻续句明确所述减值年份2020/2019，完整续文单独保存；不据此扩大为本次已审核所有减值。资本化取得合同成本另有75/89/88m候选及收入/费用位置说明，仍需按既有Scope核对，不盲目相加。

这里证明有来源，并未证明全批准D&A集合。完整原生候选/维度/QName/单位/context、原段跨度/SHA和接口预期见[b03-source-adapter-request.json](b03-source-adapter-request.json)、[候选普查](older-native-da-census.json)及[全部相关段落](older-da-wording.json)。已交#28共用普通源实现负责人：输入已选认证原件/实体/实际期间/明确namespace政策，输出有源候选与包含/子集关系或准确未决；不接调用者金额、不暴露正则或公司/年度特判，不因此生成新完整B03信用。本方只维护历史选择和消费者，没有另写D&A内核。旧年度三个null保持。

公共c56旧独立journal兼容已只读核对：build_company_view/候选枚举AST及ordinary controller/store均与adee相同，company-task H4路由优先；本方暂不消费、不重开已经通过的H4验证。新c56自身CI由其实际终态解释，不继承adee绿灯。

## 已保存来源的B02/B04/B05消费者接续

后续增量只改历史选源和薄case分派，公共normal_companyfacts_results、Calculator、controller、writer和runner均未改。历史CompanyFacts适配可从程序根读规则、从来源根读原件，并限定本次指标；B04/B05不再为另一个指标准备无关前期。新ordinary slice限定未修订连续主体，旧默认历史路径保留。B01与B02/B04/B05可同一范围命令选择；B03已有独立适配/结果继续承接，跨酒店/收入族混合与修订仍未接收。此项留在PR52，不扩已通过PR71的首个酒店slice。

真实Macy's FY2023为53周：2023-01-29至2024-02-03。当前原accession0001628280-24-012734，前期0001628280-23-009154；23092m/24442m−1得到B02=-0.0552327960068734146141886916 ratio，B04=105m USD，经营现金1305m−资本支出631m得到B05=674m USD。原生数值/期间、两来源accession和计算记录保留；不年化53周或改用最新申报的前期值。完整已计算组件以Macy-FY2023-companyfacts-component.json.gz保存，短例按类共享解包。

同一公司CLI三项首跑15.333秒、禁止选源/计算的复跑0.969秒、另一进程读取0.214秒，24结果/指针文件逐字节不变，CSV及证据均由公共writer/reader导出。明确构造的前期源读取失败仅扣留B02，B04/B05正确值仍保存；同输入扣留复跑0.864秒，B02为PREVIOUS_INPUT_WITHHELD、另两项NO_SOURCE_CONTENT_CHANGE，24文件不变。这个故障替身不是Macy's真实缺披露或缺件结论。

41项受影响短例0.371秒通过，包含保存53周/两accession、金额/单位/公式、错主体/期间、缺记录、Spec和未接修订/继承主体分类，以及已有真实paired-measure正反例。单独B04来源隔离核对5.944秒，禁止读取来源包所有程序/规则目录（仅允许公司registry），仍取得同一个105m结果，无复制程序或来源树。三公司60位置、已有两年B01及酒店全帧没有重算。[同CLI主结果](catalog-cli-verification.json)、[短测试](catalog-affected-short-tests.log)、[来源隔离](catalog-source-only-check.json)，复现命令：

```bash
PYTHONPATH=scripts:. python docs/evidence/issue47_history/historical-income-receiving-2026-10-08/check_historical_catalog_cli.py \
  --source-root <已保存原件根> --state-parent <源码与来源树外的开发状态父目录>
```

源发现/在线补齐尚未接同一公司入口，也没有将全部历史能力接入main；本次新增SEC/provider/paid=0/0/0、无新native Run或完整五年接受。Marriott三年B03原件位置、XML的SOURCE_REFERENCE/请求proof已补[b03-source-locations.json](b03-source-locations.json)，供#28从实际已选原件实现共用源适配；本方三个null保持。
