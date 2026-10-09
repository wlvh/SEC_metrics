# 本地运行一家公司的当前财年或历史财年范围

历史范围的正式使用说明见[历史公司使用指南](historical_company_usage.md)。截至本次核对main ae8a13c8已接PR67/71/75/76/83/86：保存来源酒店B10/B11、B01/B02/B04/B05和B08/B09历史消费者已交付。历史模式不自动发现或补齐材料。原PR52和旧任务入口保留。

公司入口已经由PR55/PR56基础及PR57交付到main；代码交付与业务结果接受是不同状态。来源与计算仍为独立阶段，`run`只负责顺序调度；没有OpenShift部署、正式发布、active切换或新模型调用。旧分阶段入口及运行树仍可读取旧Run。

以下 `run --source-root` 已随PR67进入main；普通记录路径不安装旧Requirement/trust树：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company marriott_international --source-root /fixed/company-source \
  --work-dir /writable/company-state --output-dir /writable/company-output \
  --metric B01 --metric B02 --metric B10 --metric B11
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company marriott_international --state-root /writable/company-state \
  --output-root /writable/daily-output
```

这条路径仅消费已经保存的来源，不进行在线发现、获取或AI调用。程序根/来源根共享读取；B01/B02/B03、CompanyFacts、A01/A02/B12及B10/B11的规则/Spec/trait由程序根提供，来源包不必携带计算catalog或代码。状态及输出分开，B10/B11等来源派生材料在公司共享输入目录只保存一次；状态固定公司和运行时来源位置。每项结果保存自己的记录、出处、程序版本和失败，重复输入先比较后直接读取；来源失败显示本次失败及旧结果的原期间，不冒充新财报成功。同次运行复用相同原件的不可变native解析，仍分别核对主体/期间/单位；正常CSV不重放计算或复制全部来源/程序；`results`经共用公司结果视图只读结果，不检查在线新来源；后一次仅选部分指标时，其余已保存当前结果仍可读，并标明未在该次请求中。旧native任务保留原入口，不原地改格式。公共更新器由历史消费者显式传期间和各指标的原计算函数，分别保存期间指针。main 还支持同一`run --period fiscal-years --fiscal-year-start <首年> --fiscal-year-end <末年>`入口：已保存、未修订、连续主体的B01/B02/B04/B05和B10/B11，最多五个财年；来源发现/补齐尚未接入历史模式。实际分支组合、五年先导结果、复跑与CSV命令见[历史四指标公司接收记录](evidence/issue47_statement_pilot_20261009/README.md)，上述代码已入main，业务结果仍须按各自证据接受；历史说明的最新订正在PR88。已知错误按确切Result身份扣留，旧E01计数不当作新并购口径结果，缺少AI处理不造答案。

已完成的稳定扣留与成功都能复用未变输入：`completed-check.json`记录最近完成结论，`current-result.json`仅保留最近成功。复用扣留仍为`PREVIOUS_INPUT_WITHHELD`并显示原因，不计算、不新增结果目录；旧成功只能按原期间作为历史读取。来源/相关配置变化重新处理；中断和程序异常不当成稳定结论。

B03还保存只读的`input-assessments.json`，保留原件数量比较及收入减项排除；Marriott按既有4.58亿范围计算，Salesforce具体冲突扣留，不替换成较大的现金流数值。Paramount原文表头Aug7与native contextAug8冲突明确扣留，侧车保留两种日期与定位，不选择日期、年化或拼接前身。

本批实测Marriott B01/B02、B10/B11及银行/非自然年结果见 `docs/evidence/issue28_company_records_20261007/`；程序通过与内容接受分别登记。保存来源路径不进行在线获取；有限在线B01/B02接续已由PR83进入main。同次不可变原件解析共享已有实现，完整同批表格共享、AI输入消费和所有39项业务验收仍未完成。以下描述的是旧固定版本的在线/native路径；修前29c9的新在线安装受旧字节绑定阻断；当前默认native入口已通过固定main8588过渡兼容回修成对验证，尚未迁移，不把接口保留当作新安装已通过。

旧native任务的只读兼容需要其原固定程序与原来源登记位置，当前入口可明确指定：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company jpmorgan_chase --state-root /saved/old-company-state \
  --runtime-root /saved/original-runtime --trust-root /saved/original-source-trust
```

这不是重新安装或计算：本批已用现有JPM D01任务实际验证，原Run的manifest/records不变。旧任务的来源/程序/登记位置须取自它自己的保存记录；不能以任意新目录代替，也不将只读成功升级为本期业务接受。旧完整审计导出仍显式使用`export-results`；新普通任务用上面的`run --source-root`和`results --output-root`，修前默认在线新安装未交付的状态已由本页“首批接收回修”更新；有限轻量在线B01/B02已由PR83进入main，其余在线能力仍未完成。

## 先选当前入口与输入

本页核对 main `ae8a13c8`（已接收 PR67/71/75/76/83/86）。同名 `run` 的三个路径不能互换；代码可运行、业务结果已接受与生产许可分别判断。

| 当前入口 | 使用者能做什么 | 前提与限制 |
|---|---|---|
| main `run --source-root` | 对合法保存来源计算受支持指标，保存普通结果，再由 `results` 日常读取 | 来源只读，状态/输出另存；成功和稳定扣留均可未变复用。未接入项、缺件及已知错误继续显示；不是在线获取。 |
| main `run --call-context`（PR83） | 从空来源完成当期 B01/B02 的发现、获取、计算和 CSV/证据 | 需要现存且用途适用的 SEC 计数上下文；录制 HTTP 的完整链已验证，不授新真实调用。尚未提供轻量在线39项或新AI能力。下文有完整参数。 |
| main `run`（不带以上两个参数） | 保留原生新任务兼容路径，自动安装固定 `8588ccbb` 程序；已有任务保原程序 | 需完整 Git 对象和匹配依赖；代表性 Marriott B01/B02 从空目录的成对录制验证成立，不是全部39项业务接受。原生路径的 macOS系统/tmp别名修正仍在 PR87，尚未合入main。 |
| main 历史调用 | 使用已交付的酒店、年度收入/部分比率和余额消费者 | 来源、年份、财年标签、主体及修订范围见 [历史使用指南](historical_company_usage.md)；当期在线发现不等于历史在线采集。 |
| 已保存旧原生任务 | 通过创建任务的原 runtime/trust 与状态读取旧结果 | 不默认混用任意新CLI和旧程序，不重签旧Run；下文保留版本说明适用于这些任务。 |

[PR67 回修记录](https://github.com/wlvh/SEC_metrics/blob/f7905156f7972b214e71d7f0a9a1172f7ac969cf/docs/evidence/issue28_company_records_20261007/default-online-review-20261009/README.md)保存原三入口比较；[PR83 接线记录](evidence/issue28_company_online_20261009/README.md)保存有限在线验证。PR87平台修正和PR89事件来源/宽窗出口是未合入的候选，不写成main现有能力。来源与计算继续可分别调用，保留原生入口是过渡兼容，不是永久双系统。

## 保留原生版本：默认新任务兼容流程

下面是不带 `--source-root/--call-context` 的固定原生入口，需要前表所述完整Git对象、原依赖及有效许可；不用于证明新的轻量在线全量能力。

在源码目录之外的工作位置执行，固定源码也可用绝对路径指定：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
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

## 已接收的默认空任务回修（历史比较依据）

PR67修前29c9c9e在normal_source_authority旧绑定处、HTTP前失败；实际main相同回复/公司/B01/B02成功。本轮保持不带source-root的原用户命令与main支持范围，新默认native程序从可取得的固定main8588程序/规则安装，程序内没有SEC原件，真实来源仍需原适用许可；原已存在任务优先保留原program_root。PR67本批的source-root生产者保持，不将本PR83的轻量在线后继视为PR67前置。该保留native路径是过渡兼容，不表示新轻量在线39项或业务接受已经完成。

需要含main8588及旧规则Git对象的代码仓库；审查的HTTP录制使用Python3.12/B01/B02，所有实际子进程运行且网络禁止。准确三入口、只读原件位置、全新目录命令与成对证据见 [主要回修记录](evidence/issue28_company_records_20261007/default-online-review-20261009/README.md)。新轻量记录state-root是work-dir；旧native才使用company-state及原runtime/trust，不混用参数。

## main 有限在线接续：B01/B02从空来源完成

这段由 PR83 合入main；它与保留原生入口分开。`run --call-context` 将来源发现/获取与普通记录计算/CSV串接；首批只支持 B01/B02，不调用旧计算，不新建真实额度或恢复失败机会。当前验证替换外部 HTTP 返回，使用真实保存 SEC 原件，发现、落盘、解析、计算、保存和导出均走实际程序；不代表新的真实 SEC 验收或全部39指标完成。

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company marriott_international --period latest-complete-fy \
  --work-dir /data/marriott-task --output-dir /data/marriott-output \
  --call-context /data/existing-sec-call-context.json \
  --metric B01 --metric B02 --max-sec-requests 20
```

调用上下文只说明本次适用的既有账本/用途/公司/指标、原调用上限、原执行模式和运行版本；不能用这个文件给自己新增许可。真实运行须先核原适用授权，本文没有授予新用途。原账本的初始化锚点、历史行、停止和计数继续生效，不能通过新任务目录拆分/重置额度；未知远端结果或落盘中断保留占用并停止，不自动重发。`--sec-allowance`不覆盖已有账本上限。

来源保存在任务 `sources`，普通计算状态在 `company-state`，输出在指定输出目录；用户不手工准备 FULL_SOURCE 或选择内部程序树。独立采集用同版 `acquire --company ... --work-dir ... --call-context ... --metric B01 --metric B02 --max-sec-requests 20`；单独计算可用同版保存来源 `run --source-root <任务/sources>` 指向另一个普通状态目录。日常读取用 `results --state-root <任务/company-state> --company ...`，不重放计算。已有原生任务继续原固定入口，不覆盖旧原生状态。

同一原账本已保存的不可变原件，不能因为换任务目录就再取一次。调用上下文可固定既有完整 SEC `source_root`，直接复用其原请求行/原件/身份，不能裁账本或拼不同历史；未给原来源位置但账本已有同URL成功记录时，新入口在申领前返回 `ALREADY_CAPTURED_SOURCE_REUSE_REQUIRED`。元数据刷新单独明确计数。该配置是持久运行配置，不是每年手填来源答案；既有来源根必须在代码和状态/输出根之外。

录制上下文必须指定 `recorded_http_root`；该入口只从保存的HTTP原件读取回复，走原客户端的落盘/日志路径，不打开网络。LIVE上下文拒绝这个录制输入字段，使用正常HTTPS及原真实计数。录制模式不是一个可以免费访问SEC的通道；缺少回复不降级到真实网络。
