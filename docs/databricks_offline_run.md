# 在无外网的 Databricks 上计算一家公司的指标

<!-- capability-anchor: CAPABILITY.databricks_offline_package -->

做法：在能上 GitHub 的电脑上，把“程序 + 一家公司已存档的 SEC 原件”打成一个 zip；传到 Databricks 后离线计算。另有一个只调用一次 SecureGPT 的检查 notebook，和计算互不依赖。

| 文件 | 在哪运行 | 作用 |
|---|---|---|
| `tools/databricks/build_offline_package.py` | 能访问 github.com 的电脑（Python 3.8+，只用标准库） | 打包，不向 SEC 发请求 |
| `tools/databricks/company_metrics_notebook.py` | Databricks | 核对包内每个文件后离线计算，不访问外网、不调用模型 |
| `tools/databricks/securegpt_check_notebook.py` | Databricks（能跑公司 SecureGPT 测试 notebook 的集群） | 只调用一次 SecureGPT，检查 `scripts/securegpt_sdk.py` |

## 为什么不在打包时直接从 SEC 下载

- 离线计算（`tools/vnext_company.py run --source-root`）只接受请求账本 `evidence/requests_log.csv` 登记过的原件：文件的 SHA-256 和长度必须与 SEC 当初返回时记录的一致。用别的脚本从 SEC 新下载的文件不在账本里，会被拒收。
- 项目自己的联网采集需要已绑定 #28 授权的调用账本，新电脑上不能直接运行。
- 仓库已经存档了各公司计算所需的 SEC 原件与账本，打包脚本只从 GitHub 取，`new_sec_requests` 恒为 0。

因此仓库尚未存档的新申报（例如某公司刚发布的年报）不能走这条路，要先经正式采集流程入库。数据只能单向进入：SEC → 受控采集入库 → GitHub → 离线包 → Databricks。

## 第一步：在电脑上打包

从 GitHub 下载 `tools/databricks/build_offline_package.py` 这一个文件（网页上点 Download raw file 即可），然后：

```
python3 build_offline_package.py --list-companies                    # 每家公司已存档的请求数与大小
python3 build_offline_package.py --company marriott_international    # 生成 sec_metrics_marriott_international_681b35d8.zip
```

- 程序版本固定为脚本里的 `DEFAULT_REF`（端到端验证过的 commit），写进 `PACKAGE.json`。`--ref <commit>` 可以换版本，但新版本可能需要更多运行文件。开发时缺文件都会在计算 notebook 里直接报错，但这不能保证所有情况，换版本后要重新核对结果。
- 每个文件都按该 commit 的 git blob 哈希核对；SEC 正文另按账本记录的 SHA-256 和长度核对，任何一项不符都不写 zip。
- 输出里的 `skipped_overwritten_working_copies` 是工作副本（`evidence/submissions/`、`evidence/accession_materials/` 下）后来被新的采集覆盖、内容已与账本对不上的文件，所以不打包。万豪是 2 个，计算用不到。
- 同一 commit、同一压缩库重打，zip 字节相同。不同电脑的压缩库可能不同，zip 本身的哈希可能不同；notebook 会逐个文件核对 `PACKAGE.json` 里的哈希，这才是完整性检查。
- 网络问题：公司代理设 `HTTPS_PROXY`；证书错误设 `SSL_CERT_FILE` 为公司 CA 文件；GitHub API 限流（每小时 60 次）时等一小时或设 `GITHUB_TOKEN`。

## 第二步：在 Databricks 上计算

1. 把 zip 上传到 Unity Catalog Volume（Catalog → 选 volume → Upload to this volume）。
2. Workspace → Import 导入 `company_metrics_notebook.py`。文件开头的 `# Databricks notebook source` 会让它自动拆成多个单元格。
3. 改第二格的 `PACKAGE_ZIP`。非万豪的公司要把 `METRICS` 换成该行业适用的指标（B10/B11 是酒店业指标）。然后 Run all。
4. `WORK_ROOT` 用驱动节点本地盘（默认 `/local_disk0/tmp/sec_metrics`），不要用 `/dbfs` 或 `/Volumes`：计算要用文件锁。本地盘不可写时自动改用系统临时目录。`SAVE_TO` 可以把结果另存到 Volume。

摘要应为 `status: PASS`；`calls` 是程序自己统计的本次新调用（provider=模型、paid=付费、sec=SEC 请求），应全为 0。万豪（默认程序版本）应得到 2025 财年：

| 指标 | 含义 | 值 |
|---|---|---|
| B01 | 营业收入 | 26186000000 美元 |
| B02 | 收入同比增长 | 0.04326693227091633466135458167 |
| B04 | 净利润 | 2601000000 美元 |
| B05 | 自由现金流 | 2608000000 美元 |
| B10 | 入住率 | 69.3（%） |
| B11 | 每间可售房收入（RevPAR） | 128.8 美元 |

- 同一集群再跑一次，各指标显示 `NO_SOURCE_CONTENT_CHANGE`：来源没变、复用上次结果，不是错误。
- 状态不是 PASS 时，摘要的 `flow_status` 是程序给出的流程状态，`metric_failures` 列出没有就绪的指标及原因。
- `CANDIDATE_READY` 只表示候选结果已生成，不等于业务验收。

## 第三步（可选）：SecureGPT 检查

1. 挂到能跑公司 SecureGPT 测试 notebook 的集群，导入 `securegpt_check_notebook.py`。
2. 先单独运行 `%pip install thinc` 那一格（公司配置代码需要）。
3. 改设置格：`PD_ROOT` 是公司 Databricks 代码库所在目录（含 `config.py`、`config/`、`utils/`）；`PACKAGE_ZIP` 同上；`DEPLOYMENT` 默认 `"55"`（gpt-5.5），`None` 表示 SDK 默认模型；`SDK_ENV` 一般保持 `None`，按工作区自动判断 dv/pp/pr。
4. 运行。全程只取一次令牌、只发一次请求。摘要不含密钥或令牌，可以直接转发。

| 状态 | 含义与处理 |
|---|---|
| `PASS` | 消息格式、发送、读回答、读用量都正常；`model` 显示实际服务的部署 |
| `SETTINGS_INVALID` | `DEPLOYMENT` 不是允许的取值，没有任何调用 |
| `SEC_METRICS_PACKAGE_FAILED` | zip 路径不对或文件核对不通过 |
| `COMPANY_CONFIG_FAILED` | 公司配置没加载成功：检查 `PD_ROOT`、`%pip install thinc`，并确认公司自己的测试 notebook 在这个集群上能跑 |
| `SDK_ENV_UNKNOWN` | 当前工作区在公司配置里没有对应的 dv/pp/pr，在 `SDK_ENV` 里手动填 |
| `SDK_INIT_FAILED` | `SecureGPT(env)` 初始化失败，多半是该环境缺某个模型地址或 secret 配置 |
| `TOKEN_FAILED` | 读密钥或令牌服务失败：当前账号读不了 secret scope，或令牌服务拒绝了凭证 |
| `SEC_METRICS_IMPORT_FAILED` | 没能从包里加载 `probe_securegpt` / `securegpt_sdk` |
| `REQUEST_FAILED` | 发请求时出错，远端是否已执行未知，**不要直接重跑**；SDK 只把真实原因打印在以 `Error making request to GPT endpoint` 开头的那一行 |
| `RESPONSE_UNREADABLE` | SDK 返回的对象无法读取 |
| `SERVICE_RETURNED_ERROR` | 网关或服务返回了错误体：401 常见于订阅密钥或令牌问题；消息提到 api-version 时是该模型地址的接口版本需要更新 |
| `ANSWER_NOT_USABLE` | 有回答，但不是纯 JSON（例如包了 ```` ```json ```` 代码块）、被过滤或截断，或随机标记/求和不对；看 `assistant_text_preview` |

我们发出的请求体只有 `messages`，不带 `max_tokens`、`temperature` 等参数，因此不会触发新模型对这类参数的限制。公司配置里的模型地址带固定 api-version，较新的模型是否接受该版本只能由真实调用回答；如果 `"55"` 报 api-version 错误，可以把 `DEPLOYMENT` 改为 `None` 再试一次，区分“5.5 地址的问题”和“整体连接的问题”。

## 两个 notebook 证明什么

计算部分不调用 SecureGPT，所选指标本身也不需要模型。两者都 PASS 只说明两件事：项目代码能在 Databricks 上离线计算；`securegpt_sdk` 能和公司 SDK 正常配合。它**不**说明项目已经在 Databricks 上用 SecureGPT 计算指标：把 SecureGPT 接进指标计算的调用边界（#28 N1）尚未实现。检查 notebook 也不覆盖 `securegpt_sdk.open_client` / `bootstrap`（其环境名 dev/pp/prod 与 SDK 的 dv/pp/pr 尚不一致）、探针命令行的子进程与超时，以及 OpenShift。

## 已验证范围（2026-10-14）

- 打包：在 `681b35d8` 上为万豪从 GitHub 实际打包，645 个文件、74 次已存档 SEC 请求、40 个原件、排除 2 个被覆盖的工作副本，zip SHA-256 为 `388d49c206d1688a6011e93a8a2c0e47ce93499713713c72e360d9c005049fd4`，重打字节相同。
- 计算 notebook：用上面的包在 Python 3.10、3.11、3.12、3.13 上运行均为 PASS，数值同上表，调用数全为 0；首次约 30–55 秒，重跑约 5 秒。Python 3.10 对应 Databricks 13.3/14.3 LTS，3.11 对应 15.4 LTS，3.12 对应 16.x 及以后。
- SecureGPT notebook：用公司 SDK 代码的本地抄本（未提交）加模拟的令牌服务、模型网关、dbutils 和 spark 运行，正常回答为 PASS 且请求发往 gpt-5.5 地址；401 错误体、代码块包裹的 JSON 等情况按上表报告，每次只有一次令牌请求与一次对话请求。
- 仓库测试：见 `TESTING.md`「Databricks 离线包测试」，只用假 GitHub、桩程序与模拟 SDK。
- **未验证**：真实 Databricks 集群（Volume 路径、集群访问模式、本地盘权限）、真实的 secret scope 与令牌服务、真实的 gpt-5.5 调用。这些结果需要在目标环境实际运行后单独报告。
