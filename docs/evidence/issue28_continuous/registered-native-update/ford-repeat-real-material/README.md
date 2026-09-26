# Ford D04：正常入口同输入重复触发与完整历史归档

**实际重复入口通过：`UPDATES_READY / NO_SOURCE_CONTENT_CHANGE`，耗时621.223秒，复用原Run，没有新candidate或模型/SEC请求。** 这是原FY2025 Ford—D04结果的日常重复更新验证，不新增公司—指标完成信用，也不代表新主版本的全部更新验收。

## 原身份与实际执行

- 固定原V15 closure：`6ccf4a6e7c54c0d499945e0e9dae8cb61f8348312c24f1c78dac2311d108bfc4`；原源码HEAD为`03b4c3cfacdcb3fa5d813eefff94c94f9f928b3c`。
- 首次成功attempt：`2f7f1821cfe244cb91a2525f0a8f61af`；原OPEN Run：`run:ordinary-integrated:3cf9f1dec976a61e686afe504ac26fe23d06f463433660751723552cbe551d1c`。
- 原Result：`sha256:9581bcb5f55170cdc084263fc2533f16eb772fd9b56229756d7b61f5bbf11fdb`，FY2025 `D04_DEFINED_SCOPE_NO_DOUBT_DISCLOSURE`。其原真实请求为第70、72–81次，共11个原成功；本次没有重发、重签或扩大其意义。
- 重复attempt：`447a7dd7785341959e0cf2d7c3d1a15f`。正常入口先机械重放原Run、重建来源case并重验公共行，再重新发现/构建同输入并复验原收据；最终保持同一successful_attempt，追加`NO_SOURCE_CONTENT_CHANGE`终态，没有data/runs目录。
- 原失败`b322a01c9d3c4dd0983547ff3a2ed8c7`仍为`EXECUTION_FAILED / UNEXPECTED_CHILD_PROCESS`、0/0/0调用。首次失败和后续成功的完整前驱链均保留。

原成功data中的747份安装文件逐SHA复制至独立runtime，启动前再次证明全等及ROOT/config/closure一致。正常入口的登记代码需要私有信任目录；该隔离副本只复制两份已签发的原source/native登记字节，并自建无远程Git保存原只读历史blobs，不复制主Git仓库或凭据。独立Git提交仅为本地重放支撑，**不是原源码HEAD**。原安装文件和原Run未改签；具体文件见`historical-git-inputs.json`及恢复树`execution-evidence/runtime-copy.json`。

重复执行使用完整历史的独立字节副本及原固定source-inputs，全部socket/DNS访问受禁止，进程记录无网络事件、无子进程。762份原历史文件中仅可变`current.json`前移；原intent/terminal、成功data、Run、Review及公共行全部原字节保持。

## 并行总账增量与原报告断言

本次正常入口及终态明确记录新增provider/paid/SEC **0/0/0**。共享总账的观察值却从**59/59/49**增至**60/60/49**：同期根任务独立启动了第109次Enphase B13 V6请求，计数1/1/0，最终FAILED_TERMINAL；后续未在本次Ford重复路径执行。

原`repeat.py`末尾错误地要求共享账before==after，因此在已取得正确重复结果之后AssertionError。`repeat-result.json`和`repeat.log`完整保留，没有改写或重跑以消掉失败。`attribution-and-verification.json`依据原109 intent/terminal及根任务确认单独归因，并检查Ford实际返回、禁网、零调用、原历史字节及无新candidate。不把全局增加写成本次调用，也不声称全局未变。第109次失败没有可用业务结果信用。

## 自包含包与实际解包

`material-index.json`将**1789个逻辑文件**映射到**863个唯一内容对象**。`material-objects.tar.xz`为**39788372字节**，SHA256=`ae876658dd1848432ed1b7e31dcef3ed04b92da178768962630ee30cb8f923d7`。

- `history/`：失败→成功→同输入复用的完整历史、原Run及公共行。
- `runtime/`：固定执行文件、规则、已安装来源/登记字节；没有主Git仓库和凭据。
- `selected-source-inputs/`：被选中的完整Ford源原文、原响应元数据及当时源日志/配置。它不是所有十家公司来源目录的完整副本。
- `calls/0070/`、`calls/0072/`–`0081/`：从既有D04完整archive逐SHA取出的原请求、响应、收据、终态和runtime包，**已纳入本包**，恢复不依赖旧archive或/tmp原文件。
- `execution-evidence/`：首次成功、重复执行及归因的原报告、程序、日志和身份检查；`original-trust-records/`只保留上述已发行的原登记，不授新权限。

现有`restore_material.py`逐字节复用。实际新进程在全新目录、一个不存在的repository占位路径下恢复全部1789文件；独立将每份恢复文件与原文件或已提交D04原包逐字节比较，核对全部11原调用终态证据SHA并读回原runtime包。原成功与失败未变，新重复attempt没有data/runs，全部通过。见`restore.log`、`restore-check.json`和`verify-restore.log`。

```bash
python3 restore_material.py --evidence /absolute/ford-repeat-real-material --repository /absolute/unused-path --output /absolute/new-root
```

本包没有`repository_path`或临时目录回退引用。历史JSON内原绝对路径作为原身份保留；还原和逐字节验证不依赖那些路径存在。这次还原验证不冒称再次运行整个业务链，也不变更当前主版本绑定、固定总账或生产状态。
