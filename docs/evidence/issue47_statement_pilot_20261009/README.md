# B01/B02/B04/B05 历史公司入口接收

状态为分支已验证、尚未入 main。三家公司各五个财年、四个指标通过同一 `tools/vnext_company.py run` 计算、复跑、独立读取并导出 CSV/出处；复用既有原件阅读确认的60个值、单位和实际期间，全部零差异。不新增模型/SEC调用，不新增旧式原生Run或业务接受登记；本先导不代表十公司×39指标的完整五年交付。

本候选从 PR71 `2b289bf6` 接续，保留酒店接收范围。唯一公共改动是原样消费 PR74 `5a0352d1` 的18行每指标函数/依赖映射；`company_current_records.py` 整文件 SHA为 `838fd65cb240e9a3bacb65d399fea8684b6d37c812bcd4364e0ba0d20969bbf0`，与公共提交逐字节相同。没有第二套控制器、结果保存器、读取器或runner。公司入口使用本方薄适配选择实际年度与当前/前期申报，再调用现有CompanyFacts解析、共同期间/范围比较和Calculator。来源根只供原件/请求记录及公司身份；Spec、公式、政策与处理代码从程序根读取。

代码组合可从本候选分支完整取得，依赖 PR71 的历史选择/年度准备及公共 PR67/74；这些公共/历史候选尚未获准合入main。当前main为 `8588ccbb`，相同命令名称不表示main已经具备本历史能力。PR58和PR62分别独立依赖PR61，2026-10-09核到各13项CI全部SUCCESS；不将它们写成PR67已经接入。

| 公司与发行人财年 | 首次计算 | 处理依赖补齐后的重新处理 | 禁止选源/计算的复跑 | 另进程禁止更新的读取 | 值/单位/期间差异 |
|---|---:|---:|---:|---:|---:|
| Ford FY2021–FY2025 | 129.835s | 139.666s | 4.058s | 0.176s | 0/20 |
| Salesforce FY2022–FY2026 | 100.806s | 107.275s | 4.666s | 0.172s | 0/20 |
| Macy’s FY2021–FY2025 | 116.656s | 122.522s | 3.980s | 0.171s | 0/20 |

每家公司最终复跑均为20个 `NO_SOURCE_CONTENT_CHANGE`，选源及计算调用0、无新结果目录；读取不更新或计算，每家260个已有结果/指针文件保持不变，包括早期版本。这里不是为了CI全绿重复整批：首轮发现实际共享计算与选源代码未全部列入本历史消费者的程序依赖，补齐四个实际文件后，公共控制器正确把配置变化作为重新处理条件；旧结果目录保留。未改变公式、原件或任何旧失败。原件解析在单次公司调用中由现有公共缓存共享，没有逐位置复制来源/程序目录；记录与CSV的读口只读已存结果。

发行人财年与报告末日明确对应：Salesforce五年末日为2022-01-31至2026-01-31；Macy’s为2022-01-29、2023-01-28、2024-02-03、2025-02-01、2026-01-31。Macy’s FY2023是2023-01-29至2024-02-03的53周年度，B02为 `-0.0552327960068734146141886916` ratio、B04为105,000,000 USD、B05为674,000,000 USD，不替换为自然年或年化数值。旧内容阅读身份与引用在 [previous-business-readings.json](previous-business-readings.json)，原始阅读和旧Run留在 [PR52历史分支](https://github.com/wlvh/SEC_metrics/tree/task/sec-history-five-year/docs/evidence/issue47_history/content-acceptance)，不以本次相同数值自动增发接受信用。

真实Marriott FY2024一次混合调用 B04/B10/B11耗时4.650s：新增B04由真实来源计算，B10/B11直接复用且酒店准备函数调用0，28个酒店保存文件不变。未重跑两年B01或酒店原文/全帧验证。另有明确标记的构造控制：人为使Macy’s FY2023前期输入失败，只扣留B02；B04=105m、B05=674m仍保存可读。扣留相同输入复跑0.499s，准备调用0，返回 `PREVIOUS_INPUT_WITHHELD`，21文件未变，独立读B02仍null。该人为缺源不是真实Macy’s财报结论。

40项小测试0.107s、零skip：现有普通状态/恢复反例、同入口分派及酒店原函数/依赖保持、历史列表错主体/未声明/错范围/重复行拒绝、未接修订/继承主体在计算前具名拒绝。它们与真实来源公司CLI接收共同验证；没有为每个小反例安装整家公司。旧保存器第一次适配曾报 `ORDINARY_PROJECTION_SELECTED_CLAIM_MISSING`；已补传实际原件的current/prior claim清单，未注入人工参考操作数；后续实际60位置和构造扣留经过同一writer。

使用命令（`--source-root`为已经恢复的保存来源根；工作/输出目录独立于源码与来源）：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company ford_motor_company --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric B01 --metric B02 --metric B04 --metric B05 \
  --source-root /saved/sec/source-inputs \
  --work-dir /writable/ford-state --output-dir /writable/ford-csv
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company ford_motor_company --state-root /writable/ford-state \
  --output-root /writable/ford-read-csv
```

Salesforce改公司和财年范围为 `salesforce` /2022–2026；Macy’s为 `macys` /2021–2025。相同run命令复用未变输入；结果按指标和发行人财年独立保存。输出 `metrics_matrix.csv` 和 `metric_evidence.csv` 保留真实申报、期间、单位及出处。程序内部的 `PUBLISHED` 是该普通记录的成功结论，仍作为公司候选，没有正式发布或active权限。

实际材料见 [verification.json](verification.json) 与 [consumer-results.tar.gz](consumer-results.tar.gz)：原样CLI输出、控制驱动、CSV/出处、当前与早期普通记录，816成员、338,812字节；只归档消费者结果，没有复制整棵来源/程序。归档驱动只是本轮开发检查，不建立另一套历史测试平台。正式小测试命令为：

```bash
PYTHONPATH=scripts:. python -m unittest \
  tests.vnext.test_historical_statement_cases \
  tests.vnext.test_historical_filing_inventory_small \
  tests.vnext.test_history_company_dispatch \
  tests.vnext.test_ordinary_current_update
```

剩余边界：目前只接已保存、未修订、连续主体的B01/B02/B04/B05，以及原酒店范围；历史在线来源发现/补齐未接入。本批不含B03、收入主体继承、目标/前期修订、AI家族与不成熟债务计算。Marriott FY2020的10-K/A实际只更正审计意见的内控交叉引用，但完整表格与指标依赖接收尚需共同来源接口；FY2021 B02保持具名扣留，不能因“有修订”推断收入重述，也不能因四张收入表逐格相同就自动放行全部指标。旧任务/旧Run读取复用PR71已完成的42文件保护验证；本批不更改旧记录格式或重放那些未变材料。普通来源变化、补齐依赖和局部失败由同一公共控制器处理，公共采集迁移与指定EX-99另在原H6推进。

后续公共测试接收：原样应用#28固定3e0d7064提供的9行patch，只登记已有三class和一条单进程CI步骤。StatementScope2＋inventory5＋dispatch9共16项0.018s通过、零skip，v2 runner全部函数AST不变；原46c30d29的9项CI已全部SUCCESS，新提交CI独立看终态，不缓存旧绿灯。历史计算与60份公司材料不重跑，归档与生产代码原字节保持。[实际16项日志](ci-short-tests.log)。
