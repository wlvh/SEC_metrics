# 当前年度收益族的历史公司接收

独立接续固定PR78/7b6803c6，原PR71/75/76/77/78范围和head保持。historical_statement现有case核心由两个受控入口共用：原四指标入口保持B01/B02/B04/B05及签名；新当前年度入口接B04净利润、B05自由现金流、B07利息覆盖率。公司CLI只新增B07分派，原B04/B05仍原factory，公共catalog、概念优先级、公式、Calculator、controller/writer/reader/runner不改。没有把B04净利润当B07经营利润分子。

同一公司命令Ford/Macy’s/Lumen FY2021–2025各5位置初次34.975/31.198/27.984s。初版Ford24出现No deterministic catalog branch is complete，旧异常留存；新入口把已知来源错误保存为明确SOURCE_OR_IMPLEMENTATION_UNRESOLVED/WITHHELD，原四指标默认异常含义保持、未知RuntimeError仍抛出。处理代码/配置实际变化后，本新增族接受一次最终版本处理29.466/31.703/28.622s（Ford24已复用刚完成的稳定扣留），其他已验证家族不重跑。

最终15位置为11个数值、3个旧业务规则成立的NOT_MEANINGFUL/null（Ford25/Lumen23/25，保留原计算负ratio及RATIO_NUMERATOR_NOT_POSITIVE）、Ford24一个未决source gap。旧原件阅读数值/单位/测量窗口无差异；比较使用Decimal语义，canonical新文本可去尾随零，不假报原字符串字节相同。源日期和发行人FY分别保持，Macy FY2023是53周2023-01-29→2024-02-03。正确业务空值、未决抽取和未披露不混同，不给旧阅读增发接受。

最终同输入复跑Ford/Macy/Lumen1.140/1.123/1.131s，source准备/graph0、59/65/65保存文件不变；真正另进程只读0.173/0.172/0.173s，禁止selection/update、CSV/出处及五位置保持。Macy FY23同入口混合B04/B05/B07 9.778s只准备两新指标，B07不重算/65旧文件未变。两受影响原MacyFY23 B04（53周）与LumenFY23 B05（负值）旧/新/共用入口整个case对象相同38.766s，不重跑先导全体。43短例0.154s零skip，能力结构对实际父分支过，副产物恢复。

Ford24资料已保存且有原native行。批准三利息概念在目标accn/年度无CF行；原件us-gaap:InterestExpenseOther/c-1/无维度/USD/scale6=1115m，完整行明确排除Ford Credit。另us-gaap:InterestExpense/c-333=7583m有FordCredit分部维度，不能泛加concept、相加或用其他scope金额。只读原件/context/CF census和完整行已交#28公共方；本方不改定义/概念表、不把诊断操作数送Calc，Ford24继续null并保留修复责任。资料足够但当前批准接入不足，不写成没有披露。

[唯一主要验证记录](verification.json)、[实际普通结果/CSV/出处/驱动与原错误](consumer-materials.tar.gz)已提交；仅结果和最小诊断，不复制源码/来源整树、不新建runner。分支验证、尚未main；在线历史来源、修订/继任年度、其余指标和完整1950目标继续。新SEC/模型/paid、native Run及完整接受0，旧35响应/失败/费用归属保持，无Ready/merge/部署/active。

示例：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run --company macys \
  --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 --metric B07 \
  --source-root /saved/source-inputs --work-dir /writable/macys-state --output-dir /writable/macys-csv
python /path/to/SEC_metrics/tools/vnext_company.py results --company macys \
  --state-root /writable/macys-state --output-root /writable/macys-read
```

后续固定efee代码接收Salesforce FY2022–2026和Marriott/Pfizer/Enphase FY2021–2025各五B07位置，首26.546/21.412/36.593/25.527s；19数值与原读取值/单位/实际窗口一致，Salesforce24一个批准来源gap明确扣留，资料未证明缺披露。Pfizer五项维持既定APPROX重建分支，不提升EXACT；Salesforce非自然年保原1月末及发行人FY。稳定复跑1.210/1.087/1.156/1.088s准备/计算0，各35保存文件未变；另进程读均约0.141s，update0。无生产代码改动、原三公司不重做。[补充接收记录](broader-company-receiving.json)及[实际结果/日志材料](broader-company-materials.tar.gz)补入同一主目录，原208成员包保留；20行不等于20全部数值接受，原完整Goal继续。
