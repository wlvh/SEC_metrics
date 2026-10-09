# SecureGPT 内网连通性探针

<!-- capability-anchor: CAPABILITY.securegpt_connectivity_probe -->

目标：确认**目标 OpenShift Pod 此刻能通过公司 SDK 调通 SecureGPT**，而且返回内容能被程序读出来用。`tools/probe_securegpt.py` 只发一次 `SecureGPT(env).request(...)`，不算财报指标，也不碰 DeepSeek、SEC 或 GitHub。

代码合入 main 与目标 OpenShift 真实 PASS 是两件事：合入只证明离线测试通过；真实结果只能在具备公司 SDK、网络和认证的 Pod 里跑出来。

## 1. 已经知道的和还不知道的

已知（来自一份 2026-06 在 Databricks 上的成功返回）：返回是 OpenAI 的 chat.completion 格式，另带 Azure 内容过滤字段；回答在 `choices[0].message.content`，探针默认就读这里；用量在 `usage.prompt_tokens / completion_tokens / total_tokens`。

未知，也是本流程要回答的：

- 公司 SDK 能否脱离 Databricks 运行（是否用到 `spark`、`dbutils`）；
- OpenShift Pod 的网络能否出到 SecureGPT；
- OpenShift 上的认证从哪来（环境变量、Secret，还是 Databricks 托管身份）。

那份 Databricks 样本回答不了这三点，所以仍要在目标 Pod 里真实调用一次。

## 2. 步骤

### 第 0 步：在 Databricks 里读 SDK 源码

在平时能成功调用 SecureGPT 的那个 Notebook 里、完成原有初始化之后运行：

```python
import inspect, sys
from utils.secure_gpt import SecureGPT
from utils.setup_utils import set_env_vars
from config import get_main_config

print(inspect.getfile(SecureGPT))                                # SDK 文件位置
print(inspect.getsource(sys.modules[SecureGPT.__module__]))     # 整个 secure_gpt.py，含 import
print(inspect.getsource(set_env_vars))
print(inspect.getsource(get_main_config))
```

这些函数如果又调用了别的公司函数（例如专门读取凭证的工具函数），也用 `inspect.getsource(...)` 打印出来看。报 `OSError: could not get source` 说明只有编译文件，把 `getfile` 的路径交给平台同事查。

逐项记下来（只记结论，不要把源码或密钥贴到 GitHub）：

1. 是否用到 `spark` 或 `dbutils`，用在哪个函数里；
2. 读取了哪些环境变量或 secret（名字即可，不要值）；
3. 认证方式：API key、Azure AD 令牌、托管身份，还是别的；
4. 服务地址是从哪里读的；
5. 有没有内置重试或超时。

根据结果决定后面怎么做：

| 第 0 步看到的情况 | 第 3 步怎么跑 | 还需要什么 |
|---|---|---|
| `SecureGPT` 不依赖 spark/dbutils，凭证从环境变量读 | 不加 `--bootstrap` | Pod 里有这些环境变量（第 1 步检查） |
| 凭证由 `set_env_vars` 通过 `dbutils.secrets` 读出 | 不加 `--bootstrap`（OpenShift 没有 `dbutils`） | 平台同事把同样的值做成 OpenShift Secret，注入为环境变量 |
| 认证依赖 Databricks 托管身份或其 Azure AD 令牌 | 暂不跑 | 先为 OpenShift 申请服务主体或工作负载身份；这是审批流程，越早启动越好 |
| 初始化函数不依赖 Databricks，且 `SecureGPT` 必须先初始化 | 加 `--bootstrap --workspace-url` | 工作区地址照 Databricks 原值填 |

### 第 1 步：找一个装有公司 SDK 的 OpenShift Pod（本机终端，只读）

本机需要 bash 终端（macOS/Linux，或 Windows 的 Git Bash/WSL）、能访问 github.com，并已安装 `oc` 且 `oc login` 到目标集群。

```bash
oc get pods -n 你的namespace                                             # 选一个 Running 的 Pod
oc get pod <Pod名> -n 你的namespace -o jsonpath='{.spec.containers[*].name}'; echo   # 容器名
# 找公司 SDK：输出 .../utils/secure_gpt.py 时，SDK_ROOT 填 utils 的上一级目录
oc exec -n 你的namespace <Pod名> -c <容器名> -- sh -c 'find / -path "*/utils/secure_gpt.py" 2>/dev/null | head -5'
# 只列环境变量的名字（不显示值），对照第 0 步记下的名字
oc exec -n 你的namespace <Pod名> -c <容器名> -- sh -c 'env | cut -d= -f1 | sort'
```

`find` 找不到，或第 0 步需要的环境变量名不在列表里，就停下：这个 Pod 还不具备调用条件，需要平台同事提供带公司 SDK、依赖和凭证的镜像或 Secret。纯 CSV 镜像不满足；`pip install thinc` 之类也装不出公司私有代码。

### 第 2 步：下载探针代码（本机）

仓库公开，直接下载已合入 main 的固定版本，不需要 GitHub 账号：

```bash
REF=67ae2c193c5dc8d1b5904154b7751155a9b58422   # PR100 合入 main 的提交
BASE="https://raw.githubusercontent.com/wlvh/SEC_metrics/$REF"
mkdir -p securegpt-probe/tools securegpt-probe/scripts
cd securegpt-probe
curl -fsSL -o tools/probe_securegpt.py "$BASE/tools/probe_securegpt.py"
curl -fsSL -o scripts/securegpt_sdk.py "$BASE/scripts/securegpt_sdk.py"
ls -l tools scripts            # 应各有一个 .py 文件
```

后面的命令都在这个 `securegpt-probe` 目录里执行。请始终用上面固定版本下载的文件；不要用本地仓库当前分支里的文件代替，那可能是另一版代码。

### 第 3 步：复制进 Pod 并运行（本机）

把前四行换成你的值，再整段执行：

```bash
NS='你的namespace'
POD='第1步选定的Pod'
CONTAINER='容器名'
SDK_ROOT='/opt/company-project'          # 第 1 步找到的 utils 上一级目录
ENV_NAME='dev'                           # dev / pp / prod
REMOTE_ROOT="/tmp/sec-probe-$$"
RUN_DIR="/tmp/securegpt-probe-$(date -u +%Y%m%dT%H%M%SZ)-$$"

# 1) 复制两个文件进 Pod（保持 tools/ 与 scripts/ 的相对位置，不含任何凭据）
for f in tools/probe_securegpt.py scripts/securegpt_sdk.py; do
  oc -n "$NS" exec -i "$POD" -c "$CONTAINER" -- \
    sh -c 'umask 077; mkdir -p "${1%/*}" && cat > "$1"' sh "$REMOTE_ROOT/$f" < "$f"
done

# 2) 真实调用 SecureGPT 一次；失败不要放进重试循环
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- \
  python3 "$REMOTE_ROOT/tools/probe_securegpt.py" \
    --env "$ENV_NAME" --sdk-root "$SDK_ROOT" \
    --timeout-seconds 180 --output-dir "$RUN_DIR"

# 3) 取回不含 SDK 原始诊断的摘要
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- cat "$RUN_DIR/summary.json" > ./securegpt-summary.json
echo "REMOTE_ROOT=$REMOTE_ROOT RUN_DIR=$RUN_DIR"   # 记下这两个值，第 4、5 节要用
```

只有第 0 步表格最后一行的情况，才在第 2 段命令里加上 `--bootstrap --workspace-url '<工作区地址>'`。它按 `get_main_config → load_config → 核对工作区与 env → set_env_vars` 初始化，不会伪造 `spark`；需要复现 `ADLSConnect` 的初始化副作用时再加 `--init-adls`。

其他说明：输出目录必须是新的（脚本自己创建，权限 0700，文件 0600），已存在就拒绝，避免混用旧结果或变相重试；需要 Python 3.9+。

### 第 4 步：看结果，定位问题

第 2 段命令会在终端打印一行 JSON 摘要。先看 `status`：

| 退出码 / status | 含义 |
|---|---|
| 0 / `PASS` | 调通，且回答是本次请求的正确 JSON。**只有这一项算通过** |
| 2 / `RESPONSE_RECEIVED_CONTRACT_FAILED` | SDK 有返回，但内容没通过检查。不一定调通了模型，按下面第二张表区分 |
| 2 / `RESPONSE_RECEIVED_UNPARSED_OR_ERROR` | SDK 有返回，但类型或 HTTP 状态不能当成功 |
| 1 / `INITIALIZATION_FAILED` | 还没发请求就失败了：SDK、依赖、配置或初始化问题 |
| 1 / `REQUEST_ERROR_REMOTE_OUTCOME_UNKNOWN` | 请求时抛出异常，远端是否已执行未知；不自动重试 |
| 1 / `WORKER_EXIT_FAILED` | 工作进程在自身处理之外退出（如 SDK 调用 `sys.exit`、被 OOM 杀掉） |
| 124 / `TIMEOUT` | 180 秒内没结束。原因不确定：网络被挡、服务慢、SDK 卡住或在内部重试都可能；已发出的请求不保证被取消，不自动重试 |

失败时查看 Pod 内的错误详情（可能含内部信息，只在自己终端看，不要转发到公共渠道）。`TIMEOUT` 和 `WORKER_EXIT_FAILED` 不会生成 `failure.json`，这条命令会改为显示 SDK 自己输出的最后 50 行错误日志：

```bash
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- \
  sh -c 'cat "$1/failure.json" 2>/dev/null || tail -n 50 "$1/sdk.stderr.log"' sh "$RUN_DIR"
```

| 现象 | 问题在哪 | 找谁 |
|---|---|---|
| `ModuleNotFoundError` / `ImportError` | `SDK_ROOT` 填错，或镜像缺 SDK 的依赖 | 自查路径；缺依赖找平台同事改镜像 |
| 错误里出现 `spark`、`dbutils` | SDK 依赖 Databricks 对象 | 回到第 0 步，按表格换做法 |
| `KeyError` 或提示缺某个环境变量 | Pod 里没有需要的凭证或配置 | 平台同事配 Secret |
| 错误或日志里**明确**出现 DNS、`Name or service not known`、`Connection refused`、`connect timed out` | Pod 连不到 SecureGPT | 平台/网络同事放通出站 |
| 401 / 403 | 认证失败或没有权限 | IAM/权限负责人 |
| `TIMEOUT`，日志里没有上述明确的网络错误 | 不确定。摘要里 `remote_outcome` 为 `NO_REQUEST_INVOCATION_OBSERVED` 表示卡在初始化、还没发请求；为 `UNKNOWN_DO_NOT_AUTOMATICALLY_RETRY` 表示卡在请求过程中 | 把摘要和日志交给平台同事一起判断；不要直接重跑 |

`RESPONSE_RECEIVED_CONTRACT_FAILED` 时，看 `failure.json` 里的 `message`：

| `message` | 含义 | 算不算调通了模型 |
|---|---|---|
| `SDK_ERROR_RESPONSE` / `SDK_HTTP_ERROR_RESPONSE` | 服务返回的是错误信息，不是回答；具体内容在 `response.json` 里（常见为认证或参数问题） | 不算 |
| `INCOMPLETE_OR_FILTERED_RESPONSE` / `NOT_AN_ASSISTANT_ANSWER` | 回答被截断、被内容过滤或拒答 | 模型可达，但这次回答不可用 |
| `ASSISTANT_TEXT_NOT_FOUND` | 回答不在默认位置 | 待定：按第 3 节离线复查 |
| JSON 解析错误（如 `Expecting value`）/ `JSON_FIELDS_MISMATCH` | 模型回答了，但不是要求的纯 JSON（例如外面包了代码块） | 模型已调通；JSON 格式问题记给 N1 |
| `NONCE_MISMATCH` / `SUM_MISMATCH` | 回答不是本次请求的正确结果，可能是缓存或模型没照做 | 不能算通过 |

`sdk_request_invocations` 是本脚本发起的 SDK 调用次数（最多 1）。SDK 内部是否重试取决于第 0 步看到的实现，所以"一次调用"不等于服务端只计费一次。

### 第 5 步：带回什么

- `securegpt-summary.json`；
- 第 0 步的五项结论（不带源码和密钥）；
- 实际是否加了 `--bootstrap`；
- 失败时：`status`、`error_type` 或 `remote_outcome`、`failure.json` 里的 `message`（如有），以及按上表判断的原因。

## 3. 回答位置不同时：离线复查，不再调用模型

默认能读：纯字符串、`choices[0].message.content`、顶层 `output_text/text/content`。按第 1 节已知格式，正常不需要这一步。若回答实际在别处（例如 `data.answer`），先在内网看 `response.json`，再对**同一次返回**复查：

```bash
oc -n "$NS" exec "$POD" -c "$CONTAINER" -- \
  python3 "$REMOTE_ROOT/tools/probe_securegpt.py" --replay-dir "$RUN_DIR" --text-path data.answer
```

`PASS_SAVED_RESPONSE` 表示原回答重新解析通过，新增 SDK 调用为 0；它不代表重新验证了当前网络。`response.json` 保存的是 SDK 返回对象的 JSON 形式，不是 HTTP 原始报文。

## 4. 隐私

`settings.json`、`request.json`、`response.json`、`failure.json` 和 `sdk.*.log` 可能含内部信息，只留在内网，不提交 Git、不贴公共渠道。需要反馈时先给 `summary.json`；错误详情按公司规则脱敏后再给。第 0 步的源码同样只在公司允许的范围内查看。

## 5. 与 #28 N1 内外网模式的关系

[#28 N1](https://github.com/wlvh/SEC_metrics/issues/28#run-test-simplification) 要求：内网 transport 放进现有唯一 provider 边界（`ai_adapter`、`TransportPolicy.provider`、`check_provider_egress` 允许集合），沿用调用账本，不另建第二套调用器。本探针**不是**那个 transport：

- `scripts/securegpt_sdk.py` 是仓库里唯一接触公司 SDK 的代码（消息格式转换、初始化顺序、单次 `request`、回答读取），探针和将来的 N1 transport 共用它。
- 外网 DeepSeek 路径不变，没有新增 `SEC_NETWORK_MODE` 开关；现有指标调用点都未切换到内网。
- 已知格式对 N1 的意义：把 SDK 返回的字典转成 JSON 后，仓库现有的 chat.completion 回答解析和用量读取可直接沿用；保存的是 SDK 返回值，不是 HTTP 原始报文。
- N1 还需单独处理：2026-06 样本显示背后模型为 `gpt-4o-2024-11-20`，一次最多约 12.8 万 tokens（第三方资料，待公司核实），现有酒店表格请求约 16 万；请求格式里没有"只返回 JSON"的参数，只能靠提示词；内容过滤要作为明确终态，与"没找到数据"区分；在 DeepSeek 上验证过的准确性需在该模型上重新验收；失败时的返回形式与 SDK 可接受的额外参数仍未知。
