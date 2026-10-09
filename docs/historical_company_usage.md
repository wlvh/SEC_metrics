# 历史公司使用指南

截至2026-10-09，main `ae8a13c8` 已接收 PR61/58/62/67/71/74/75/76/79/83/86。同一 `tools/vnext_company.py`、公共更新器、保存器和结果读口支持保存来源的历史 B10/B11，以及未修订、连续主体的 B01/B02/B04/B05和所选CIK余额的B08/B09。酒店共用计算与四指标历史适配已 main；PR58 合入的是机械 D02 引文检查，D02 公司模型链和完整五年业务验收仍未完成。

A01/A02等后续历史候选仍在各自 Draft PR；C01/E02–E05的新增普通历史适配仍在原开发分支。PR83 的普通在线接续不等于历史模式已能在线发现与补齐来源；本指南的 `fiscal-years` 仍需已保存来源根。代码合入不表示正式采纳、发布或 active 切换。

## 取得代码和已保存输入

审查者在已有仓库创建自己的新目录和新分支，名称被占用时另选，不覆盖已有任务：

```bash
git fetch origin main
git worktree add -b review/issue47-hotel-history ../SEC_metrics-history-review \
  ae8a13c8
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

B01 为收入、B02 为增长比率、B04/B05 为所选年度现金流。B02需要同主体且实际相邻的前期申报；不以任意重述值或错误年份代替。目标或前期修订尚未完成该族适配时，显示具名缺口/扣留，其他项继续保存。Salesforce FY2026 原 DEI 字面标签为2025，发行人定义明确解析FY2026，实际日期2025-02-01→2026-01-31；两种标签与冲突依据保留，不改写原件或日期。

B01源核对同时读取所选primary/XML的金额、单位、主体及实际期间；main此次接收的边界仍是连续主体、未修订输入。它不解除 Paramount 收入的 August7/August8 冲突，也不接 B03、继任收入范围或所有39指标；B08/B09的年末余额接收见下节。

## 年末余额指标

B08流动比率和B09现金储备已随PR76进入main。沿用上节命令，指标改为 `--metric B08 --metric B09`；可与已接收的四指标/酒店指标同次选择，按各自既有工厂与处理依赖保存。余额实际期间为年度末日的单日，财年字段仍使用发行人标签。Macy’s FY2023的余额日是2024-02-03，不把它称作FY2024或53周流量。

原十公司五年100位置的来源、计算与限制验证见[余额主要记录](evidence/issue47_liquidity_receiving_20261009/README.md)，main接收未改计算。结构性不适用保留N_A_STRUCTURAL依据与空值，不当作零或缺源。修订仅经已有共享输入属性核对后用于指定余额指标，未决类别仍扣留；继任主体只取所选CIK期末余额，不拼前身、不据此证明可比完整年度或债务完整性。Paramount FY2024两项明确采用原申报年末余额；收入August7/August8冲突仍另行保留。

## 状态、复跑和局部失败

同一指标按财年各自保存。成功同输入复跑为 `NO_SOURCE_CONTENT_CHANGE`；已经完整检查但因业务原因扣留的同输入复跑为 `PREVIOUS_INPUT_WITHHELD`。两者均不再调用计算工厂，不新增相同结果目录。改变实际相关来源、补齐依赖或处理配置后重新处理；普通异常和未完成记录不被缓存为已完成业务结论。

当前扣留不得被同年旧成功替代。公共 `completed-check.json` 表示最近完成检查，`current-result.json` 保留最近成功；日常 CSV 读取最近完成结论。后续只请求另一指标或另一年，仍能读出原坐标当前扣留，旧成功只留作历史。`requested_in_latest_execution` 区分本次请求，不能把未请求项算成本次新成功。

缺源年份、实现失败和业务扣留分开表达。缺源/处理失败保留空值、请求财年、具体 `error_category` / reason；其他年份及指标的成功记录保留。`FLOW_COMPLETED_WITH_LIMITATIONS` 表示有明确限制，不能当成所有指标交付。`SOURCE_UNAVAILABLE` 不是正确零值；`IMPLEMENTATION_GAP` 表示已有材料或路径尚未实现。当前 main 未支持的历史家族在入口拒绝，不能省略 `--metric` 后把默认39项当成已支持。

当前 main 历史选择器明确保留修订情况，但尚未完成修订历史酒店处理；主体变换也未取得完整适配接受。Paramount 可见 August7 与原生 context August8 的真实期间冲突仍保留两种证据，不任选日期、年化或拼接前身。它不是本酒店接收的输入；这条范围限制不授其他指标接受。

## 当期模式及旧任务

保存来源当期模式省略年份范围，使用 `--period latest-complete-fy --source-root <已保存根>`；仍由既有公共当前分派选择最新适用完整财年。不要同时传历史起止年。来源读取、计算、单位和独立结果读口的受影响当期回归已执行，既有两年 B01 不重复运行。

旧 native / 原 PR52 任务按其保存身份读取，用原任务自己的 `state-root`、固定 `runtime-root` 和必要 `trust-root`。原说明中的 `historical-company-state` 等只适用于那些既有任务，不能用于上述新普通历史任务。只读旧结果不重新注册、重签或计算，也不等于内容重新接受。旧完整审计出口仍为显式 `export-results`。

## 仍需交付的部分

已入 main 的 PR71/75/76 交付上述保存来源后的酒店、四指标与余额范围计算、复跑、读取和CSV/出处；不包含在线历史发现、缺件补齐、其他历史指标或新模型执行链。其他候选按自身接收状态保留，不据分支结果扩大 main 的可用范围。

完整历史来源准备仍须把公司、期间、指标贯穿现有来源发现/缺件清单、按具体用途许可获取、同一公司计算和结果出口。年度基础材料已保存不等于附件、图片、前期和所有指标依赖齐备。本项是仍有效的H4/历史交付责任，不因首批范围有限而取消；原十公司×39指标×五年业务目标继续。
