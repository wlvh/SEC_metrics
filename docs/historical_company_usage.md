# 历史公司使用指南

截至2026-10-09，main `4a03f223` 已包含 PR61/58/62/67/71/74/75/76/79/83/86、PR77/78/81/82/84/88，以及事件接收提交 `44719c7e` / `408e89e2`。同一 `tools/vnext_company.py`、公共更新器、保存器和结果读口支持保存来源的历史 B10/B11，以及未修订、连续主体的 B01/B02/B04/B05和所选CIK余额的B08/B09。酒店共用计算与四指标历史适配已 main；PR58 合入的是机械 D02 引文检查，D02 公司模型链和完整五年业务验收仍未完成。

A01/A02资本、A05/A06/A07/A08/A10银行指标和B07年度计算也已main。C01/E02–E05普通历史适配及公共事件源/宽窗接口已在main；[PR90](https://github.com/wlvh/SEC_metrics/pull/90)和[PR89](https://github.com/wlvh/SEC_metrics/pull/89)已由接收方合入；后续消费者记录继续按本记录的执行版本解释，不改旧运行记录。PR83 的普通在线接续不等于历史模式已能在线发现与补齐来源；本指南的 `fiscal-years` 仍需已保存来源根。代码合入不表示正式采纳、发布或 active 切换。

## 取得代码和已保存输入

审查者在已有仓库创建自己的新目录和新分支，名称被占用时另选，不覆盖已有任务：

```bash
git fetch origin main
git worktree add -b review/issue47-hotel-history ../SEC_metrics-history-review \
  4a03f223
cd ../SEC_metrics-history-review
python3 tools/vnext_company.py run --help
```

这一 main 版本已经携带 Marriott FY2024/FY2025 的完整保存原件、HTTP headers、请求日志及公司登记，来源根可以直接是该检出根。规则、指标定义和程序从代码根读取；所有状态和输出写检出根之外的新目录。无需取得开发者的私人来源目录，也不要求审查者建立信任库或修改原任务。本指南的两年命令已在被 main 接收的同一实现上使用这些提交材料实际运行；合并未改变这些处理文件，复用原计算验证；对应[主要验证记录](evidence/issue47_history/simplification-closeout-2026-10-08/README.md)。

其他既有历史材料仍由 PR52 的已提交 `evidence/issue47_acquired/` 承接。若已经有恢复结果，复用它的实际 `source-inputs` 根，不重新恢复整树。确实需要首次恢复时，使用保留的 `task/sec-history-five-year` 入口：`python tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out <不存在的新目录>`，并读取返回的 `data_root`；父目录本身不是来源根。恢复不发出 SEC GET，不给未成熟指标授予计算能力。它是既有材料恢复步骤，尚未统一到新公司历史来源准备流程。

## 同一公司命令的历史模式

从上述代码目录运行以下命令。`$PWD` 是可取得的已保存来源根，`$HOME/sec-metrics-review-20261009` 可替换为自己的新外部目录：

```bash
python3 tools/vnext_company.py run \
  --company marriott_international --period fiscal-years \
  --fiscal-year-start 2024 --fiscal-year-end 2025 \
  --metric B10 --metric B11 --source-root "$PWD" \
  --work-dir "$HOME/sec-metrics-review-20261009/state" \
  --output-dir "$HOME/sec-metrics-review-20261009/runs"

# 同样的run可复跑；从同一state读取时不再准备来源或计算。
python3 tools/vnext_company.py results \
  --company marriott_international \
  --state-root "$HOME/sec-metrics-review-20261009/state" \
  --output-root "$HOME/sec-metrics-review-20261009/read-01"
```

财年起止为包含端点的发行人财年标签，一次最多五年；实际日期来自所选申报 DEI，不能把报告截止日期的公历年份当成财年。例中两年实际各为1月1日至12月31日；Macy’s FY2024 的截止日期是2025-02-01。这只是标签解释，当前 main 的四指标历史模式已经支持 Macy’s，需采用下方已保存来源流程。

上述保存输入的两年值为 B10 69.8% / 69.3%，B11 128.23 / 128.8 USD。内部 B10 计算值仍为 0.698 / 0.693 ratio，CSV 明确转换成 percent；不能把69.8当成原始比率。出处保留原申报、原表、原格文字及位置，不把展示值代替证据。

`run` 的 JSON 指明本次 `output_root`，CSV 位于该根的 `metrics_matrix.csv` / `metric_evidence.csv`，不要到输出父目录或旧运行目录找本次文件。`results --state-root` 指向原 `work-dir`，无需附加 `historical-company-state`、`company-state` 或 trust；`--output-root` 必须是新的读取目录。两种命令都不修改原件，不执行在线发现、SEC获取或模型调用。

## 四指标五年模式

以下代码已经随 PR75 进入上述 main。完整保存输入来自原 PR52 的 `evidence/issue47_acquired/`；首次恢复使用上节保留分支的 `restore` 命令，直接采用返回的 `data_root`，它才是实际 `source-inputs` 根。不要把源码根、导出目录或恢复父目录误当成这个根。

```bash
python3 tools/vnext_company.py run \
  --company ford_motor_company --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric B01 --metric B02 --metric B04 --metric B05 \
  --source-root /saved/sec/source-inputs \
  --work-dir "$HOME/sec-metrics-ford/state" \
  --output-dir "$HOME/sec-metrics-ford/runs"
python3 tools/vnext_company.py results \
  --company ford_motor_company --state-root "$HOME/sec-metrics-ford/state" \
  --output-root "$HOME/sec-metrics-ford/read-01"
```

Salesforce 使用 `--company salesforce`、FY2022–FY2026；Macy’s 使用 `--company macys`、FY2021–FY2025。这些命令与三家公司60位置的原实际运行、复跑和独立读取可在[四指标主要记录](evidence/issue47_statement_pilot_20261009/README.md)核对；main 接收未改变其计算/读取实现，不为了说明变化重跑60位置。

B01 为营业收入、B02 为收入同比增长率、B04 为净利润、B05 为自由现金流（经营活动现金流减资本支出）。B02需要同主体且实际相邻的前期申报；不以任意重述值或错误年份代替。目标或前期修订尚未完成该族适配时，显示具名缺口/扣留，其他项继续保存。Salesforce FY2026 原 DEI 字面标签为2025，发行人定义明确解析FY2026，实际日期2025-02-01→2026-01-31；两种标签与冲突依据保留，不改写原件或日期。

B01源核对同时读取所选primary/XML的金额、单位、主体及实际期间；main此次接收的边界仍是连续主体、未修订输入。它不解除 Paramount 收入的 August7/August8 冲突，也不接 B03、继任收入范围或所有39指标；B08/B09的年末余额接收见下节。

## 年末余额指标

B08流动比率和B09现金储备已随PR76进入main。沿用上节命令，指标改为 `--metric B08 --metric B09`；可与已接收的四指标/酒店指标同次选择，按各自既有工厂与处理依赖保存。余额实际期间为年度末日的单日，财年字段仍使用发行人标签。Macy’s FY2023的余额日是2024-02-03，不把它称作FY2024或53周流量。

原十公司五年100位置的来源、计算与限制验证见[余额主要记录](evidence/issue47_liquidity_receiving_20261009/README.md)，main接收未改计算。结构性不适用保留N_A_STRUCTURAL依据与空值，不当作零或缺源。修订仅经已有共享输入属性核对后用于指定余额指标，未决类别仍扣留；继任主体只取所选CIK期末余额，不拼前身、不据此证明可比完整年度或债务完整性。Paramount FY2024两项明确采用原申报年末余额；收入August7/August8冲突仍另行保留。

## 资本、银行和利息保障倍数

main `73ead3b4` 已包含 A01/A02（Tier1、CET1资本比率）、A05/A06（ROA、ROE）、A07（净利润变动）、A08（非利息/净利息收入）、A10（贷款损失准备）和 B07（利息保障倍数：营业利润除以利息费用）的历史分派。仍使用上面的 `run --period fiscal-years` / `results`，以 `--metric` 明确选择；例如 JPM 五年资本使用 `--company jpmorgan_chase --fiscal-year-start 2021 --fiscal-year-end 2025 --metric A01 --metric A02`。来源、工作目录和输出参数都保留，不先运行其他公司。

资本与A10按实际年末时点输出；A05/A06用同主体全年净利润和两个相邻年末的平均分母，A07需要自身前期申报，A08与B07保留年度流量窗口。不能把单日期末余额当作全年流量，也不能拿当前重述金额替代原前期。既有[资本验证](evidence/issue47_capital_receiving_20261009/README.md)、[银行验证](evidence/issue47_bank_performance_20261009/README.md)和[年度盈利验证](evidence/issue47_annual_earnings_20261009/README.md)按保存版本复用；其中原“未main”文字是当时记录，本节说明今日接收状态，不改写原记录。

行业不适用、主体不可比和程序未完成分开：JPM B07为 `N_A_STRUCTURAL/null/TRAIT_NOT_APPLICABLE`；Paramount FY2025的B02/B04/B05/B07保留 `NOT_MEANINGFUL/null/ENTITY_CONTINUITY_NOT_COMPARABLE`，不拼接前身或提取金额。这不解决其B01范围及日期冲突。金融修订和继任主体的金额适配仍未完成，按[主体结论记录](evidence/issue47_successor_outcomes_20261009/README.md)解释，不把这些空值改成零。

## 已保存来源的历史事件模式

main `4a03f223` 已包含所选事件源、历史分派和普通宽窗保存接口，处理文件与本方已验证的 `65471ee1` / `b7640660` / `da873af8` 相同。后续公司验证记录沿本主要记录的接收分支可取得，原件仍从PR52恢复；无需两个会话未提交的文件。采用同一命令，例如已恢复Macy’s来源后：

```bash
python3 tools/vnext_company.py run \
  --company macys --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric C01 --metric E02 --metric E03 --metric E04 --metric E05 \
  --source-root /saved/sec/source-inputs \
  --work-dir "$HOME/sec-metrics-macys-events/state" \
  --output-dir "$HOME/sec-metrics-macys-events/runs"
python3 tools/vnext_company.py results \
  --company macys --state-root "$HOME/sec-metrics-macys-events/state" \
  --output-root "$HOME/sec-metrics-macys-events/read-01"
```

实际事件来源窗口、申报、原header条目和出处都经同一保存/读取出口。C01/E03按现行Item5.02披露计数，不把相同集合解释为已经区分任命与离任事件。Paramount FY2025仍有2025全年年报容器及目录批准的2024-01-01至2025-12-31事件测量宽窗；只对这几个事件指标成立，财务及E01不能借用。验证和具体运行版本见[事件主要记录](evidence/issue47_events_receiving_20261009/README.md)。E01内容确认、在线历史发现和缺件补齐不在此已实现范围，完整交付责任继续。

## A13 国际净收入：候选分支的有限接收

审查此能力需明确检出该候选，前面的 main 酒店命令不会取得 A13 适配。使用已有仓库的新目录，例如：

```bash
git fetch origin task/issue47-geography-history-20261009
git worktree add -b review/issue47-a13 ../SEC_metrics-a13-review \
  origin/task/issue47-geography-history-20261009
cd ../SEC_metrics-a13-review
```

分支已包含其需要的公共 PR104 接缝；无需另外复制未提交文件。来源恢复需在保留历史分支执行上节命令，随后把返回的实际 `source-inputs` 根传入此候选。若分支名或目录已占用，选择新名字，不能覆盖现有任务。

`task/issue47-geography-history-20261009` 在实际 main `6e51f416` 上消费公共 PR104 的显式旧标记版本解析及 A13 公司更新接缝。该分支尚未入 main；当前已实际验证 JPMorgan FY2021–FY2025 的选源、共用检查和计算、同公司首跑／复用、独立 CSV 与出处读取。A13 为源表披露的全年国际净收入金额，使用原表国际合计、收入定义、USD 单位和实际全年窗口。

```bash
python3 tools/vnext_company.py run --company jpmorgan_chase \
  --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 --metric A13 \
  --source-root /saved/sec/source-inputs --work-dir /new/a13/state --output-dir /new/a13/runs
python3 tools/vnext_company.py results --company jpmorgan_chase \
  --state-root /new/a13/state --output-root /new/a13/read-01
```

来源使用上面的已提交 SEC 导出恢复根；所有状态和输出写新外部目录。实测五年结果依次为 28,971,000,000、31,968,000,000、34,873,000,000、38,233,000,000、42,758,000,000 USD，各年实际1月1日至12月31日、CIK 19617。修订、接续主体及未决范围分别保留具名限制；其他金融指标、当期 A13 默认入口、其他公司与完整五年业务还待接续。主要记录见 [A13 历史消费者验证](evidence/issue47_geography_receiving_20261009/README.md)。公共接缝允许的是明确传入的历史 A13 工厂，没有默认打开 39 项计算或自动取得来源。
## A03/A12：候选分支的历史测量期
`task/issue47-average-risk-history-20261010` 在 main `6e51f416` 上消费公共 PR107 的受控旧 DEI 版本、显式历史工厂及季度保存接口，尚未进入 main。本候选只添加 A03/A12 和三项既有历史措辞适配，不要求先运行其他公司，也不复制公共控制器/保存器。
git fetch origin task/issue47-average-risk-history-20261010
git worktree add -b review/issue47-average-risk ../SEC_metrics-average-risk-review \
  origin/task/issue47-average-risk-history-20261010
cd ../SEC_metrics-average-risk-review
  --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2025 \
  --metric A03 --metric A12 --source-root /saved/sec/source-inputs \
  --work-dir /new/average-risk/state --output-dir /new/average-risk/runs
  --state-root /new/average-risk/state --output-root /new/average-risk/read-01
来源仍用上节保留历史分支恢复的实际 `source-inputs` 根；原件只读，目录名称已占用时另选。JPM FY2021 已实测 A03=1.11 ratio（111%），实际2021-10-01至12-31；FY2021是年报分组，不能把该季度平均值年化。A12=55,000,000 USD，是全年平均VaR；95%/一日为风险口径，不是一日测量窗口。同一CLI计算、禁工厂复用、独立读取及原格出处已贯通，见[唯一接收记录](evidence/issue47_average_risk_receiving_20261010/README.md)。JPM FY2021–FY2025十坐标已完成同入口计算、全范围禁工厂复用、独立读取和原参考对照；修订/继任金额处理、其他金融族及在线历史取源仍待；默认当期指标集合没有因此扩大。
## A04/A09/A11：候选分支的金融历史范围
`task/issue47-bank-scope-history-20261010` 在 main `6e51f416` 上包含公共 PR109 的受控 DEI 参数及显式历史工厂接口，尚未进入 main。只接所选 NIM、不良贷款比率和 AUM 的既有共同计算与有限历史措辞，未扩大默认当期指标集合。
git fetch origin task/issue47-bank-scope-history-20261010
git worktree add -b review/issue47-bank-scope ../SEC_metrics-bank-scope-review \
  origin/task/issue47-bank-scope-history-20261010
cd ../SEC_metrics-bank-scope-review
  --metric A04 --metric A09 --metric A11 --source-root /saved/sec/source-inputs \
  --work-dir /new/bank-scope/state --output-dir /new/bank-scope/runs
  --state-root /new/bank-scope/state --output-root /new/bank-scope/read-01
来源使用保留历史分支恢复所得实际 `source-inputs` 根，原件只读，状态/输出写外部新目录。JPM FY2021实际A04=.0164 ratio、全年；A09=.0072 ratio及A11=3,113,000,000,000 USD均为12月31日时点，财年是年度容器。A09仍先做完整原生结构化检查，只有明确歧义且来源集合完整才可使用现有HTML解释；缺源或程序异常不能替代。原申报、原格与单位/期间都由同一CSV/出处读口保存。
同CLI首跑、禁工厂复用及另进程读取已核，见[唯一接收记录](evidence/issue47_bank_scope_receiving_20261010/README.md)。JPM FY2021–FY2025十五坐标已完成同入口处理、全范围复用、独立读取和原参考逐项核对；修订/继任金额、其他金融族和在线历史取源尚待；候选接线不等于完整业务接受。
已核的主干输出限制：Paramount FY2021–FY2024所选原件和Trace报送人为813828，但当前公共CSV仍使用今日登记CIK2041610；旧结果读取保留原字节，不能把该列作为当期申报主体结论。公共主体修复仍在接收中，新版本须核同一年度CSV与证据身份，不能手改旧记录。其2025事件宽窗不据此获得拼接财务主体的许可。见[原RPO消费者主要记录](https://github.com/wlvh/SEC_metrics/blob/e4eff843/docs/evidence/issue47_rpo_receiving_20261009/README.md)；PR96是B12候选，尚未进入上述main，完整年度E01仍未交付。

## 状态、复跑和局部失败

同一指标按财年各自保存。成功同输入复跑为 `NO_SOURCE_CONTENT_CHANGE`；已经完整检查但因业务原因扣留的同输入复跑为 `PREVIOUS_INPUT_WITHHELD`。两者均不再调用计算工厂，不新增相同结果目录。改变实际相关来源、补齐依赖或处理配置后重新处理；普通异常和未完成记录不被缓存为已完成业务结论。

当前扣留不得被同年旧成功替代。公共 `completed-check.json` 表示最近完成检查，`current-result.json` 保留最近成功；日常 CSV 读取最近完成结论。后续只请求另一指标或另一年，仍能读出原坐标当前扣留，旧成功只留作历史。`requested_in_latest_execution` 区分本次请求，不能把未请求项算成本次新成功。

缺源年份、实现失败和业务扣留分开表达。缺源/处理失败保留空值、请求财年、具体 `error_category` / reason；其他年份及指标的成功记录保留。`FLOW_COMPLETED_WITH_LIMITATIONS` 表示有明确限制，不能当成所有指标交付。`SOURCE_UNAVAILABLE` 不是正确零值；`IMPLEMENTATION_GAP` 表示已有材料或路径尚未实现。当前 main 未支持的历史家族在入口拒绝，不能省略 `--metric` 后把默认39项当成已支持。

当前 main 历史选择器明确保留修订情况，但尚未完成修订历史酒店处理；主体变换也未取得完整适配接受。Paramount 可见 August7 与原生 context August8 的真实期间冲突仍保留两种证据，不任选日期、年化或拼接前身。它不是本酒店接收的输入；这条范围限制不授其他指标接受。

## 当期模式及旧任务

保存来源当期模式省略年份范围，使用 `--period latest-complete-fy --source-root <已保存根>`；仍由既有公共当前分派选择最新适用完整财年。不要同时传历史起止年。来源读取、计算、单位和独立结果读口的受影响当期回归已执行，既有两年 B01 不重复运行。

旧 native / 原 PR52 任务按其保存身份读取，用原任务自己的 `state-root`、固定 `runtime-root` 和必要 `trust-root`。原说明中的 `historical-company-state` 等只适用于那些既有任务，不能用于上述新普通历史任务。只读旧结果不重新注册、重签或计算，也不等于内容重新接受。旧完整审计出口仍为显式 `export-results`。

## 仍需交付的部分

已入main的酒店、四指标、余额、资本、银行和B07交付上述保存来源后的范围计算、复跑、读取和CSV/出处；不包含在线历史发现、缺件补齐、所述已接事件族之外的其他历史指标或新模型执行链。其他候选按自身接收状态保留，不据分支结果扩大 main 的可用范围。事件实现已入main只解除接线候选边界，尚未验证的公司/年度、E01及完整五年业务继续。

完整历史来源准备仍须把公司、期间、指标贯穿现有来源发现/缺件清单、按具体用途许可获取、同一公司计算和结果出口。年度基础材料已保存不等于附件、图片、前期和所有指标依赖齐备。本项是仍有效的H4/历史交付责任，不因首批范围有限而取消；原十公司×39指标×五年业务目标继续。
