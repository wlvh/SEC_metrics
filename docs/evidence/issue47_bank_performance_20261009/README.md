# 历史银行盈利与信用指标开发接收

从PR77/e333独立接续，原候选不扩大。A05 ROA、A06 ROE、A07净利润变动、A08非利息/净利息收入、A10贷款损失准备使用现有catalog、Calculator和paired_measure_v1；历史薄case只选择实际current/prior来源及期间，再交公共公司控制器保存/读取/CSV。不写竞争计算、采集、保存或runner，不手工给运行器金额。

实际JPM五FY2021–2025共25位置由同一公司范围CLI处理，FY21首241.165s、其余四年612.244s。未变输入复跑27.940s，source selector/graph/prior准备调用0、175保存结果/指针不变，独立进程读25位置0.148s。时限实数如实报告，不声称均已达普通PR5分钟目标；没有将旧快测绿灯或旧接受数当新业务完成率。

其中24个位置的值/单位/实际测量窗口与已保存原件阅读相同；A05 FY2021旧接受记录没有该项，本次新候选0.01355861265326514473806383999 ratio单独核原件：2021全年净利润48,334m USD、2021年末资产3,743,567m、2020年末资产3,386,071m，各自来自0000019617-22-000272/0000019617-21-000236自身原件。独立lxml读原QName/context/单位/无维度、数字scale/sign，两个期末平均作分母得到该值。旧read_statement_facts未把Assets列入NEEDED、另一个初脚本未规范CIK前导零，开发失败保留并纠正；不把缺输出说成缺披露，不改期望值或灌人工操作数。没有新增正式内容接受。

A05/A06只用全年净利润与两期末平均，不用季度/年度平均；A07比较两份各自原申报年度，别名不同时仍经同一paired_measure guard，不能借当前重述替代前期原值。A10在2021-12-31等实际期末，A05–A08为全年窗口，年度容器/测量期分别保留。

构造的前期缺源仅影响A05/A06/A07，实际控制157.282s：三项当前WITHHELD/null，A08/A10仍NO_SOURCE_CONTENT_CHANGE正确值。稳定扣留复跑8.242s准备0、保存文件不变、旧成功留存，独立读仍扣留。这是人为控制，不是真实JPM缺源结论；只复制已完成FY21的小状态，没有复制整树来源/程序或读取在途年度写入。38短例0.099s/零skip，包含公共控制器源/配置变化、恢复、期间隔离和历史分派，能力结构检查PASS/副产物恢复。

本分支尚未新建Draft PR，main仍未接，金融修订/继任主体拒绝及更多反例/真实混合接收继续。现有公司命令选择五年或单年与指标即可，无需先跑其他公司或手工拼内部结果；示例：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company jpmorgan_chase --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric A05 --metric A06 --metric A07 --metric A08 --metric A10 \
  --source-root /saved/sec/source-inputs --work-dir /writable/jpm-state --output-dir /writable/jpm-csv
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company jpmorgan_chase --state-root /writable/jpm-state --output-root /writable/jpm-read
```

[主要记录](verification.json)、[原样CLI/控制驱动/原件操作数/CSV/出处及普通结果](consumer-materials.tar.gz)已提交。新provider/paid/SEC=0，无新native Run/接受，原35模型、SEC账本、失败与旧Run保持。此25位置不替代全部1950或正式采纳，Goal完整目标继续。
