# SecureGPT 内网连通性探针

<!-- capability-anchor: CAPABILITY.securegpt_connectivity_probe -->

`tools/probe_securegpt.py` 在目标环境里通过公司 SDK 真实调用一次 `SecureGPT(env).request(...)`，确认**模型调用能通，而且返回内容能被程序读出来用**。它只是一个连通性检查，不算财报指标，也不碰 DeepSeek、SEC 或 GitHub。

代码合入 main 与目标 OpenShift 真实 PASS 是两件事：合入只证明离线测试通过；真实 PASS 只能在具备公司 SDK 和认证的容器里跑出来。

## 1. 怎样才算通过

每次运行生成一个随机标记（nonce）和两个三位整数，只发一条消息，请模型返回严格 JSON：`{"nonce": "<本次标记>", "sum": <两数之和>}`。程序依次检查：SDK 确实返回了；能读到助手回答；回答是合法 JSON 且恰好两个字段；nonce 是本次的；和是正确的整数。

以下都**不算**通过：只 import 成功、HTTP 200、任意字符串、错误 JSON、旧运行的答案、被截断或被过滤的回答、套了 Markdown 代码块的 JSON（程序不替模型修补）。

小算术只是让一个很小的请求同时检验"通不通"和"能不能用"，不是财务正确性审查。

## 2. 前提：选对容器

- 在**已运行、已具备公司 SDK、认证配置和内网设置**的 OpenShift 容器里执行。只装了本仓库的 CSV 镜像没有公司 SDK，换启动参数不会让它具备 SecureGPT 能力；`pip install thinc` 之类也装不出公司私有的 `utils/config/data_io` 代码。
- Databricks 上通过可以作对照，但不能替代目标 OpenShift 的结果。
- 不要对已经退出的 CSV Job 执行 `oc exec`。
- 需要 Python 3.9+（本仓库已用 3.11/3.13 跑过离线测试）。

## 3. 在目标 Pod 上运行

在本机的 SEC_metrics 仓库根目录执行。只复制两个无凭据的源文件到 Pod 临时目录；替换 namespace、Pod、容器名、公司代码目录和工作区地址。工作区地址只出现在命令行，不写进仓库。

```bash
NS='你的namespace'
POD='运行中的企业SDK Pod'
CONTAINER='容器名'
SDK_ROOT='/opt/company-project'          # 该目录下能找到公司的 config、utils 等模块
WORKSPACE_URL='<dev工作区地址>'
REMOTE_ROOT="/tmp/sec-probe-$$"
RUN_DIR="/tmp/securegpt-probe-$(date -u +%Y%m%dT%H%M%SZ)-$$"

# 1) 复制探针和共用 SDK 模块（保持 tools/ 与 scripts/ 的相对位置）
for f in tools/probe_securegpt.py scripts/securegpt_sdk.py; do
  oc -n "$NS" exec -i "$POD" -c "$CONTAINER" -- \
    sh -c 'umask 077; mkdir -p "${1%/*}" && cat > "$1"' sh "$REMOTE_ROOT/$f" < "$f"
done

# 2) 真实调用 SecureGPT 一次；失败不要放进重试循环
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- \
  python3 "$REMOTE_ROOT/tools/probe_securegpt.py" \
    --env dev --sdk-root "$SDK_ROOT" \
    --workspace-url "$WORKSPACE_URL" --bootstrap \
    --timeout-seconds 180 --output-dir "$RUN_DIR"

# 3) 只取回不含 SDK 原始诊断的摘要
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- cat "$RUN_DIR/summary.json" > ./securegpt-summary.json
```

参数说明：

- `--bootstrap` 按用户提供的顺序执行 `get_main_config → load_config → 核对工作区与 env → set_env_vars`，再 `SecureGPT(env)`。不需要 `spark`；如果公司 `set_env_vars` 或 `SecureGPT` 内部依赖 `spark/dbutils`，探针会在实际出错的阶段报 `INITIALIZATION_FAILED`，不会伪造 Spark。
- 只有企业镜像确实为**每个新 Python 进程**都做好了初始化时才去掉 `--bootstrap`；另一个 Notebook 进程初始化过不算。
- `--init-adls` 只在需要复现 `ADLSConnect` 可能的初始化副作用时追加，不是默认前提。
- 也可用环境变量：`SEC_ENV`、`SEC_INTERNAL_SDK_ROOT`、`SEC_WORKSPACE_URL`、`SEC_INTERNAL_CONFIG`（默认 `config/main_config.cfg`，相对 SDK 目录）、`SEC_INTERNAL_TEXT_PATH`。
- 输出目录必须是新的（脚本自己创建，权限 0700，文件 0600）；已存在就拒绝，避免混用旧结果或变相重试。

## 4. 结果怎么看

| 退出码 / status | 含义 |
|---|---|
| 0 / `PASS` | SDK 返回了，助手 JSON、nonce、和全部对上 |
| 1 / `INITIALIZATION_FAILED` | SDK 路径、配置、依赖或初始化失败；**尚未**调用 `request()` |
| 1 / `REQUEST_ERROR_REMOTE_OUTCOME_UNKNOWN` | `request()` 抛出异常；远端是否已执行未知；看内网 `failure.json`，不自动重试 |
| 1 / `WORKER_EXIT_FAILED` | 工作进程在自身处理之外退出（如 SDK 调用 `sys.exit`、被 OOM 杀掉）；`remote_outcome` 说明调用是否已发出 |
| 2 / `RESPONSE_RECEIVED_UNPARSED_OR_ERROR` | 收到返回，但类型或 HTTP 状态不能当成功 |
| 2 / `RESPONSE_RECEIVED_CONTRACT_FAILED` | 收到返回，但找不到回答、JSON/nonce/和不符；**不等于网络不通** |
| 124 / `TIMEOUT` | 本地工作进程已被终止；已发出的远端请求不保证随之取消，不自动重试 |

`sdk_request_invocations` 是本脚本发起的 SDK 调用次数（最多 1）。SDK 内部是否重试没有读过实现（`sdk_internal_retries: NOT_INSPECTED`），所以"一次调用"不等于服务端保证只计费一次。

## 5. 收到了回答但读取位置不同：离线复查，不再调用模型

`response.json` 保存的是 SDK 返回对象的 JSON 形式，不是 HTTP 原始报文。默认能读：纯字符串、`choices[0].message.content`、顶层 `output_text/text/content`。如果实际回答在别处（例如 `data.answer`），先在内网看 `response.json`，再对**同一次返回**复查：

```bash
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- \
  python3 "$REMOTE_ROOT/tools/probe_securegpt.py" --replay-dir "$RUN_DIR" --text-path data.answer
```

`PASS_SAVED_RESPONSE` 表示原回答重新解析通过，新增 SDK 调用为 0；它不代表重新验证了当前网络。

## 6. 隐私

`settings.json`（含工作区地址）、`request.json`、`response.json`、`failure.json` 和 `sdk.*.log` 可能含内部信息，只留在内网，不提交 Git、不贴公共渠道。需要反馈时先给 `summary.json`；错误详情按公司规则脱敏后再给。

## 7. 与 #28 N1 内外网模式的关系

[#28 N1](https://github.com/wlvh/SEC_metrics/issues/28#run-test-simplification) 要求：内网 transport 放进现有唯一 provider 边界（`ai_adapter`、`TransportPolicy.provider`、`check_provider_egress` 允许集合），沿用 WB-3 调用账本，不另建第二套调用器。本探针**不是**那个 transport：

- `scripts/securegpt_sdk.py` 是仓库里唯一接触公司 SDK 的代码（消息格式转换、初始化顺序、单次 `request`、回答读取），探针和将来的 N1 transport 共用它，避免"探针一套、业务一套"。
- 外网 DeepSeek 路径不变，也没有新增 `SEC_NETWORK_MODE` 开关；现有指标调用点都未切换到内网。
- 探针跑完后，请把以下信息带回 N1（不带原文）：`summary.json`；`response.json` 的字段结构（回答在哪个路径、是否有 `usage` 及其字段名）；`--bootstrap` 是否必需；是否出现 spark/dbutils 依赖。这些正是 N1 当前列为"待用户补充"的项目。
