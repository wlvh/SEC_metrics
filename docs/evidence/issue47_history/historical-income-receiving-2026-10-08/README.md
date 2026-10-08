# H4 后续：历史收入期间冲突与 B03 普通 case 接收

接续已交付 PR71，不扩大该酒店/公共测试收口 PR。本次代码在原历史分支开发，尚未 main；主记录为 [verification.json](verification.json)。复用公共 adee3036 的收入期间检查、原件准备及保存/读取函数；没有新增计算器、controller、runner、来源获取或模型试验。

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
