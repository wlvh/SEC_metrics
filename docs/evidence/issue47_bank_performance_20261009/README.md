# 历史银行盈利与信用指标开发接收

从PR77/e333独立接续，原候选不扩大。A05 ROA、A06 ROE、A07净利润变动、A08非利息/净利息收入、A10贷款损失准备使用现有catalog、Calculator和paired_measure_v1；历史薄case只选择实际current/prior来源及期间，再交公共公司控制器保存/读取/CSV。不写竞争计算、采集、保存或runner，不手工给运行器金额。

实际JPM五FY2021–2025共25位置由同一公司范围CLI处理，FY21首241.165s、其余四年612.244s。未变输入复跑27.940s，source selector/graph/prior准备调用0、175保存结果/指针不变，独立进程读25位置0.148s。时限实数如实报告，不声称均已达普通PR5分钟目标；没有将旧快测绿灯或旧接受数当新业务完成率。

其中24个位置的值/单位/实际测量窗口与已保存原件阅读相同；A05 FY2021旧接受记录没有该项，本次新候选0.01355861265326514473806383999 ratio单独核原件：2021全年净利润48,334m USD、2021年末资产3,743,567m、2020年末资产3,386,071m，各自来自0000019617-22-000272/0000019617-21-000236自身原件。独立lxml读原QName/context/单位/无维度、数字scale/sign，两个期末平均作分母得到该值。旧read_statement_facts未把Assets列入NEEDED、另一个初脚本未规范CIK前导零，开发失败保留并纠正；不把缺输出说成缺披露，不改期望值或灌人工操作数。没有新增正式内容接受。

A05/A06只用全年净利润与两期末平均，不用季度/年度平均；A07比较两份各自原申报年度，别名不同时仍经同一paired_measure guard，不能借当前重述替代前期原值。A10在2021-12-31等实际期末，A05–A08为全年窗口，年度容器/测量期分别保留。

构造的前期缺源仅影响A05/A06/A07，实际控制157.282s：三项当前WITHHELD/null，A08/A10仍NO_SOURCE_CONTENT_CHANGE正确值。稳定扣留复跑8.242s准备0、保存文件不变、旧成功留存，独立读仍扣留。这是人为控制，不是真实JPM缺源结论；只复制已完成FY21的小状态，没有复制整树来源/程序或读取在途年度写入。38短例0.099s/零skip，包含公共控制器源/配置变化、恢复、期间隔离和历史分派，能力结构检查PASS/副产物恢复。

本分支形成独立Draft候选，base为PR77资本分支，main仍未接。金融修订/继任主体继续明确拒绝，不扩PR71/75/76/77。现有公司命令选择五年或单年与指标即可，无需先跑其他公司或手工拼内部结果；示例：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company jpmorgan_chase --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric A05 --metric A06 --metric A07 --metric A08 --metric A10 \
  --source-root /saved/sec/source-inputs --work-dir /writable/jpm-state --output-dir /writable/jpm-csv
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company jpmorgan_chase --state-root /writable/jpm-state --output-root /writable/jpm-read
```

[主要记录](verification.json)、[原样CLI/控制驱动/原件操作数/CSV/出处及普通结果](consumer-materials.tar.gz)已提交。新provider/paid/SEC=0，无新native Run/接受，原35模型、SEC账本、失败与旧Run保持。此25位置不替代全部1950或正式采纳，Goal完整目标继续。

真实混合接收在已有资本公司任务只新增FY2025 A08，15.775s：原A01/A02准备与计算均0、80结果文件不变；整体稳定复跑1.416s，银行准备/graph0、三项结果文件不变。另一进程同一公司results读取0.100s，FY2025资本0.155/0.146 ratio、A08=0.9115807340506899405928145595 ratio和原银行B08结构NA共存，未请求其他年度/指标仍可读。当前模式代码和factory未改，已有真实当期结果复用；当前分派短例仍过，没有重跑两年B01或酒店。

四项构造口径反例通过真实shared paired_measure：无目标申报桥接、前期重述金额改变、单位/窗口/申报错误和桥接冲突都拒绝；完整原前期值在当前概念下报告才可桥接。连同原两source-role、历史分派与公共状态42项0.100s，零skip。另对已保存JPM FY2025 A07原件作一次明确构造guard失败，case→共同writer已完成，当前WITHHELD/null、MEASURE_NOT_COMPARABLE保留。驱动在JSON输出CSV bytes时报TypeError，初错误log保留，修驱动后只从已保存结果恢复读取0.001s，不重复准备/计算；首段耗时未成功保存，不补造。该测试不宣称JPM真的有口径冲突，也不修改原成功任务。

能力结构检查对实际main和父PR77均PASS。按旧b06大分支作base的检查FAIL因公共简化已移除的无关CAPABILITY anchors，原失败log保存；不重铸旧快照或扩大本批以满足旧分支门禁。副产物已恢复。本候选的新bank短class初时待公共selector，后继已按下述固定补丁接收；本地42通过与新CI终态分别记录。上述新增混合/构造原始结果、驱动、CSV和出处在[增量材料](mixed-and-measure-materials.tar.gz)，不重新打包原175成员或复制来源/程序整树。

公共c459422d固定a457补丁已接收，前置合入PR77的bfeea6b1短CI登记。bank2+4新增class同时进入v2和显式CI，原dispatch整class自然执行12例；全部32例实测0.026s通过，runner函数/类AST未改。原25银行计算不重跑。原a457 CI状态保留，新head终态待核。[实际短测试log](public-short-selectors-received.log)。
