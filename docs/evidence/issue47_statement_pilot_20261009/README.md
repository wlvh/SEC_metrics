# B01/B02/B04/B05 历史公司入口接收

状态为分支已验证、尚未入 main。三家公司各五个财年、四个指标通过同一 `tools/vnext_company.py run` 计算、复跑、独立读取并导出 CSV/出处；复用既有原件阅读确认的60个值、单位和实际期间，全部零差异。不新增模型/SEC调用，不新增旧式原生Run或业务接受登记；本先导不代表十公司×39指标的完整五年交付。

本候选从 PR71 `2b289bf6` 接续，保留酒店接收范围。唯一公共改动是原样消费 PR74 `5a0352d1` 的18行每指标函数/依赖映射；`company_current_records.py` 整文件 SHA为 `838fd65cb240e9a3bacb65d399fea8684b6d37c812bcd4364e0ba0d20969bbf0`，与公共提交逐字节相同。没有第二套控制器、结果保存器、读取器或runner。公司入口使用本方薄适配选择实际年度与当前/前期申报，再调用现有CompanyFacts解析、共同期间/范围比较和Calculator。来源根只供原件/请求记录及公司身份；Spec、公式、政策与处理代码从程序根读取。

原527验证组合依赖 PR71 的历史选择/年度准备及公共 PR67/74；原验证时main为 `8588ccbb`。2026-10-09接收方已将61/58/62/67/71合入main/e2d6784c，本PR后续接这个实际main，酒店历史已有可用入口；本方B01/B02/B04/B05四指标先导仍候选未main。公共每指标工厂/依赖映射来自PR74，不将相同CLI名称或main酒店交付写成四指标已接收。

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

2026-10-09接实际main的消费者增量：业务源/四指标计算文件未改，原60位置计算证据复用；合并工作树51定向例7.083s零skip，含历史分派、稳定成功/扣留、来源变化与子集读口及受影响公共记录。当期真实短源三例使用既有共享夹具，不重跑两年B01或酒店历史全帧。唯一合并冲突在公共v2测试清单，已按#28精确补丁保留双方选择器与显式步骤，runner函数AST同main；实际46项0.038s零skip。合并代码与本项增量提交后，以本PR的main base审查，不借其他候选的未提交文件。原 `consumer-results.tar.gz` 的60普通结果在新目录恢复，实际 `read_saved_result` 逐一读取0.044s通过，未读取来源或计算。审查可直接恢复这个现有包，不需要新的审查包或私人未提交文件。

B01同族接缝：本PR仅接公共PR85/541b的已选收入原件模块与原样namespace helper。B01观察值必须与已选primary/XML原生金额、主体、申报、单位和实际期间相符；不准备当期B06，不更改旧计算公式或修订/继承拒绝。Ford FY2021 136341m、Salesforce FY2022 26492m、Macy FY2023 23092m USD，三定向原件样本实测9.153/6.511/5.681s，值/单位/期间/Result ID与包内旧结果逐字段相同；不是重跑原60位置。新增解析依赖仅分配B01，其他三指标不消费收入接口。29项含新接口的小例0.183s过，详见[本次接收检查](main-receiving.json)。

审查材料恢复：`consumer-results.tar.gz` 是现有普通记录/CSV包，解包到新目录后，可对 `<新目录>/<ford|salesforce|macys>/saved-results/FY<年>/B<指标>` 调用 `read_saved_result(output_root=...)`；本次60条均实读成功。重新计算所需完整原件来自PR52已提交 `evidence/issue47_acquired`，按[历史使用指南](../../historical_company_usage.md)的既有restore入口恢复，使用返回的实际source-inputs根。本PR未添加在线获取；归档中的绝对旧开发路径只作日志，审查命令应替换为自己恢复的根和新状态目录。

实际main随后到d4b0db79：PR74每指标公共映射及PR85原件接口已经合入，现有75与main的公共保存器/原件接口/namespace逐字节相同，不需要新公共实现或额外依赖PR。再接实际main后，现有历史步骤与main收入步骤的相邻插入冲突由公共侧提供解法；双方步骤均保留。最新54选择器小例0.076s、30消费者/接口小例0.179s零skip；新增构造控制故意用13m计算观察值对应12m原件，由实际共享原件核对拒绝，不把机械成功当金额支持，也不将替身当真实财报。原三真实B01样本消费的相关源/解析/计算文件未被main增量改变，复用它们，不重复整组。

15个旧B01观察值进一步直接过新原件检查（不重新计算），14个支持、Salesforce FY2026暴露DEI字面2025与已解析发行人FY2026不相等，原拒绝保留在[原检查](main-receiving-saved-b01-originals-before.json)。既有发行人定义规则已证明FY2026，实际日期2025-02-01→2026-01-31不变；修复只把原件读者指向prepared中保留的`original_input`，输出/观察值仍使用解析后的发行人标签，并显式拒绝原始/实际日期变化。没有改公共API、用答案覆盖原件或放宽单位/主体/期间检查。实际受影响FY2026重新过入口，B01=41525000000 USD、Result ID和值/单位/期间与原包相同，4.020s；原标签冲突及定义依据保存[修复核对](main-receiving-salesforce-label-fixed.json)。

FY2026真正进入同一公司CLI并保存/导出：首跑内部4.368s，观察原工厂但禁止调用的复跑0.399s，独立读取外部0.348s，CSV为FY2026/2025-02-01→2026-01-31/41525000000 USD，9结果与pointer文件读取前后保持；见[CLI核对](main-receiving-salesforce-label-cli.json)。初次开发验证误用MagicMock替换工厂，改变了程序身份而报TypeError，修正为保留函数身份的只读调用观察；另一次记录器误取不存在的read status键失败，均保留日志。完成记录直接消费已经写出的结果并只重做读取，不抹掉失败或补造计时；first/repeat为CLI内部耗时，final read为外部wall。

## 2026-10-10 总收入范围订正

新公共范围接入亲核原件发现：Macy FY2023 原损益表明确 NetSales23092m＋OtherRevenue774m＝TotalRevenue23866m。本记录原 same-concept金额/期间MATCH与CLI机械链不能据此证明完整B01。确切旧B01 `5f17ec97…` 及其增长B02 `db609edd…` 当前正确值信用停止；原Result/Run/CSV及早期验证不改写。FY2022 `a4237cca…`/`bf5f4bdc…` 暂为范围待核线索而非已确诊错误，后期FY2023比较列不回填原FY2022。其他指标/公司/年份不因本条被推断为错误。具体原件表格、字节SHA、关系及精确四ID见[同一来源核对记录](https://github.com/wlvh/SEC_metrics/blob/26f34c39/docs/evidence/issue47_macys_revenue_scope_20261010/README.md)。后继共用核心与准确默认缺陷扣留由公共#28接收，不手工注入数值、重算60位置或恢复调用。
