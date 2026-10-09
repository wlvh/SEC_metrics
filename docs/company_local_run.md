# 本地运行一家公司的当前财年

## 先选版本与输入

| 版本/入口 | 能做什么 | 前提与限制 |
|---|---|---|
| main 既有实现，固定基线 `8588ccbbb1c91d81e0fb1a89dff3575214282549` | `run` 从空任务发现/获取来源，调度原生计算和 CSV/证据出口；`acquire` 独立采集 | 这是 PR57 已交付的原生流程，使用其固定依赖及原任务账本。真实请求仍须适用许可；39项状态不代表39项内容通过。 |
| [PR67](https://github.com/wlvh/SEC_metrics/pull/67) 保存来源候选 `29c9c9e2080a1de8c809660ac8fbdfc49072ef12` | `run --source-root` 处理已保存来源，普通记录 `results` 日常读取 | 尚未进入 main；新在线安装未接通，不能在这个候选上省略 `--source-root` 后宣称全流程可用。已接入指标和验证见 PR67。 |
| 已有原生任务 | `results` / 显式审计导出读取原 Run | 使用创建该任务的固定程序、状态、来源登记及依赖；新 CLI 与任意旧程序混用不保证兼容。 |

来源与计算分别运行，`run`只顺序调度。main 原生流程与 PR67 普通记录是过渡版本，不是永久双系统。轻量在线续接由 #28 在保存来源阶段后接入，尚未实现的能力不写成默认可用。代码交付、运行成功、业务接受和正式发布分别判断。

## main 固定原生版本：新任务完整流程

下面命令仅用于上述固定 main 实现及其匹配依赖，不用于 PR67 的新在线安装。Marriott 的既有真实首次、重复运行与局部重入见本页末材料；不是对所有公司/指标的完成保证。

在源码目录之外的工作位置执行，固定源码也可用绝对路径指定：

```bash
python /path/to/main-8588ccbb/SEC_metrics/tools/vnext_company.py run \
  --company marriott_international \
  --period latest-complete-fy \
  --work-dir ./work/sec-metrics \
  --output-dir ./outputs/marriott
```

公司须已在登记中。当前本地 `run`仅选择最新已披露完整10-K及其原文确认的财年，不硬编码年份，不承诺某份尚未披露财报。历史五年仍走既有历史入口，不成为本地首年启动前提。相对路径转为安全绝对路径；别名、源码树重叠、生产active目录及工作/输出重叠拒绝。

本地程序自动安装固定的普通/native继承树（`issue_54_v4`继承V14），按已有Spec选择各自原生验证器，包含无需模型的B13结构性N/A；不修改普通、native或历史旧树。

第一次建立新任务时，只安装公司登记、规则、原生空请求CSV及其完整性manifest。任务来源目录中没有保存财报；原财报只能经现有`SecAcquisitionSession.capture`／`SecHttpClient`进入。旧基线、真实52/1547历史及私人总账不搬入、不清零、不重新编号。公司交接仍由现有验证器验证整个任务历史后裁出目标依赖；原件和HTTP headers、前期/窗口外与主体依赖原样携带。

实际SEC执行须先取得适用许可。用户已直接批准Marriott首次＋同目录复跑及必要修复重跑累计最多120次GET、provider/paid0；本次授权登记见 `docs/evidence/issue54_company/live-marriott/authorization.json`。失败请求计入，403/429后本地层停止，后续调用也保留停止，不改变身份或代理。入口的默认调用界限为单次最多120、同一任务累积120，可用`--max-sec-requests`收窄；`--sec-allowance`在建立任务时固定，重复执行不能加额。零自动重试；本入口同一Unix用户共用每秒1次的稳定锁，其它SEC工具也须由操作者协调总速率，不能按公司分别领取10次每秒。不借#28/#47余额、不自动买模型判断。

同样的命令可再次运行，固定原程序及任务账本不变。先刷新发现用元数据，复用已验证的不可变原件；实质来源内容未变时，现有指标更新接口复用候选，没有新Run。来源更新经不可变公司版本和稳定`company-state/source`路径导入，计算固定该版本；导入中断沿既有恢复机制，不暴露混合输入。

每次输出：

```text
outputs/marriott/<run-id>/
├── metrics_matrix.csv
├── metric_evidence.csv
├── run_summary.json
├── company-results.json   # 已有可读取状态时
└── stages/               # 各阶段命令、原样stdout/stderr和耗时
```

摘要包含请求期间与原文实际期间/申报、下载/复用/失败、来源版本、阶段耗时和配置中39项的结果状态。矩阵复用原字段/原生投影，缺结果项补状态行；已有期间和指标继续来自公司持续视图。附加`local_run_*`/`local_metric_status`/`local_source_status`列说明本次请求，避免把保留旧值说成本次更新成功。原结果的规则版本、归档期间、测量窗口、输入匹配和缺陷释放守卫不改变。阶段失败时仍尝试原生冷读取旧结果，失败本身保留；无法读回的旧结果不伪造。

`FLOW_COMPLETED_WITH_LIMITATIONS` / exit 2表示来源部分、指标失败或待处理，仍有完整状态表；`FLOW_INCOMPLETE`表示阶段未完成。只有本次所请求项达到现有候选状态且阶段完整时exit0，仍不是业务接受或发布。默认39项含尚无普通完整Run入口的D03，因此不声称39项全成功。B13完整公司判断、D03和相关业务限制由#28维护；历史处理由#47维护。

新本地环境需安装仓库固定离线tokenizer依赖（特别是已保存D04输入的严格请求等价/冷读）：

```bash
python -m pip install --no-deps --require-hashes \
  -r /path/to/main-8588ccbb/SEC_metrics/requirements-continuous-context.txt
```

它只安装本地程序依赖，不调用业务模型。

独立来源阶段（同一固定 main 版本、同一任务；真实请求需原适用许可）：

```bash
python /path/to/main-8588ccbb/SEC_metrics/tools/vnext_company.py acquire \
  --company marriott_international --work-dir ./work/sec-metrics \
  --max-sec-requests 40 --sec-allowance 120
```

它只发现/捕获来源，输出明确`source_root`、捕获集合和原生receipt，不执行旧计算或AI。准备树和trust由程序管理。计算环境可继续单独调用原`export → install → compute → export-results`，不需要网络和采集现场。

合法已保存的D04用单独`work-dir/processing.json`接入：`package_root`、原`runtime_root`、处理`trust_root`、原SEC `source_version`及其`source_runtime`、`source_trust_root`。这些是在准备端认证一次后管理的独立输入，不放入SEC包、不改签旧请求/响应。空历史版本由新的固定树验证，原SEC版本由它自己的旧树独立认证，再用原判断程序检查完整内容等价；期间/原文/输入责任变化则拒绝复用。未配置、记录不完整或需要新判断时明确待处理；当前没有本任务已获准的新本地模型入口，不调用#28的私人provider预算。旧已接通D04和新空来源接线的覆盖分列。

运行位置：程序/规则在`work-dir/programs/<version>`固定保存，计算期间只读；来源在`work-dir/acquisition/source-inputs`、其独立调用账本在`acquisition`，来源登记在`trust/acquisition`，公司准入在`trust/company`；公司持久状态/旧Run在`company-state`，结果冷出口在`result-exports`，业务用户文件在`output-dir`。无需个人HOME、root、特权或unshare。当前执行用户UID1000、无capabilities，Marriott真实首跑/同目录复跑和只读程序实际通过；不据此声称OpenShift或系统级网络隔离验收。

Marriott真实空来源首跑和同目录复跑已完成：累计31次真实SEC GET、27份来源复用，复跑36个原生候选独立冷读通过；39项中D02/D03/D04仍明确限制，不是39项业务验收或正式发布。实际CSV、摘要、来源/运行版本、修复与合并依赖见[真实运行材料](evidence/issue54_company/live-marriott/README.md)；[此前本地接线材料](evidence/issue54_company/local-run/README.md)仍按录制范围保留。

2026-10-04另以新工作目录从空来源重新真实运行（新增29+2次GET，含原31次累计62/120），首跑36候选冷读通过、复跑0新Run、局部重入保留其它行；已配置的旧LIVE D04因本次收到的10-K比原版本多一个script元素（注入方未归因）、原始字节身份不同，严格等价按现行规则被拒并如实保留。见[本轮材料](evidence/issue54_company/live2/README.md)。

## PR67 候选：已保存来源及普通记录读取

以下命令须使用 PR67 对应源码；main 基线 CLI 没有 `run --source-root` 参数。来源必须为已合法保存的完整输入，缺件、来源失败和已知错误继续显示，不复活旧成功。

```bash
python /path/to/pr67/SEC_metrics/tools/vnext_company.py run \
  --company marriott_international --period latest-complete-fy \
  --source-root /data/saved-source --work-dir /data/company-task \
  --output-dir /data/output --metric B01 --metric B02
python /path/to/pr67/SEC_metrics/tools/vnext_company.py results \
  --state-root /data/company-task --company marriott_international
```

此候选不默认重放/复制整套状态来日常出表；成功和稳定扣留均可复用已完成检查，扣留仍显示原原因。新在线采集、未接入族与新模型执行不在该候选交付范围。保留原生任务的 `results` 仍需匹配原版 `--runtime-root` 与 `--trust-root`，不能套用普通记录无 trust 的示例。
