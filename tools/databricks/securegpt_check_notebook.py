# Databricks notebook source
# MAGIC %md
# MAGIC ## SEC_metrics × SecureGPT：Databricks 检查（默认 gpt-5.5）
# MAGIC
# MAGIC 只调用 SecureGPT **一次**。检查 SEC_metrics 的 `scripts/securegpt_sdk.py`（消息格式、发送、读回答、读用量）
# MAGIC 和探针的随机标记/求和校验，能否配合公司的 `utils.secure_gpt.SecureGPT` 正常工作。
# MAGIC
# MAGIC SEC_metrics 代码取自 `tools/databricks/build_offline_package.py` 生成的同一个 zip（不访问外网）。用法：挂到平时能跑
# MAGIC 公司那个 SecureGPT 测试 notebook 的集群；先运行下一格安装 thinc，再改第 3 格开头的设置后运行。最后的摘要不含密钥或令牌，可以直接发回。
# MAGIC
# MAGIC 不覆盖的部分：我们模块里的 `open_client` / `bootstrap`（它们用 dev/pp/prod，而 SDK 认 dv/pp/pr），
# MAGIC 探针命令行的子进程与超时，以及 OpenShift。

# COMMAND ----------

# MAGIC %pip install thinc

# COMMAND ----------

# ===== 只需要改这里 =====
PD_ROOT = "/Workspace/Repos/<你的用户名>/<公司 Databricks 代码库>"  # 含 config.py、config/、utils/ 的目录
PACKAGE_ZIP = "/Volumes/<catalog>/<schema>/<volume>/sec_metrics_<company_id>_<ref前8位>.zip"
WORK_ROOT = "/local_disk0/tmp/sec_metrics"  # 与 company_metrics_notebook 相同即可，已解压的包会直接复用
DEPLOYMENT = "55"  # SecureGPT.request 的 url 参数："55"=gpt-5.5；None=默认 gpt-4o；也可填 "41"、"5mini"、"51"、"54"
SDK_ENV = None  # None=按当前工作区自动判断；也可直接填 "dv"、"pp"、"pr"
# ========================

import hashlib
import importlib
import json
import os
import sys
import time
import traceback
import zipfile
from pathlib import Path

CONFIG_ENV_FOR_SDK_ENV = {"dv": "dev", "pp": "pp", "pr": "prod"}  # 与 SecureGPT.__init__ 内的对应关系相同
DEPLOYMENTS = ("41", "5mini", "51", "54", "55")

summary = {"status": "NOT_STARTED", "token_step_attempted": False, "securegpt_calls": 0,
           "deployment": DEPLOYMENT or "default"}
_started = time.monotonic()


def fail(status, message, error=None, show_traceback=True):
    """Record why the check stopped; full tracebacks stay in this notebook."""
    summary.update(status=status, message=message)
    if error is not None:
        summary["error"] = f"{type(error).__name__}: {str(error)[:300]}"
        if show_traceback:
            traceback.print_exception(type(error), error, error.__traceback__)
    return False


class ChosenDeployment:
    """Pass SecureGPT.request's own deployment shortcut (url="55" and so on)."""

    def __init__(self, client, deployment):
        self.client, self.deployment = client, deployment

    def request(self, body):
        return self.client.request(body, url=self.deployment)


def usable_work_root(path):
    """Prefer the driver's local disk; fall back to the system temp directory if it is not writable."""
    import tempfile
    for candidate in (Path(path), Path(tempfile.gettempdir()) / "sec_metrics"):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-test"
            probe.write_text("ok")
            probe.unlink()
            return str(candidate.resolve())
        except OSError:
            continue
    raise RuntimeError(f"No writable work directory: {path}")


def extract_package(zip_path, work_root):
    """Same extraction as the processing notebook: one directory per zip content, every file verified."""
    digest = hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()
    target = Path(work_root).resolve() / f"package-{digest[:12]}"
    root = target / "sec_metrics_package"
    if not (root / "PACKAGE.json").is_file():
        Path(work_root).mkdir(parents=True, exist_ok=True)
        partial = Path(work_root).resolve() / f".extracting-{digest[:12]}-{int(time.time())}"
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(partial)
        partial.rename(target)
    package = json.loads((root / "PACKAGE.json").read_text(encoding="utf-8"))
    bad = [name for name, sha in package["files"].items()
           if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha]
    if bad:
        raise RuntimeError(f"{len(bad)} files differ from PACKAGE.json, first: {bad[0]}")
    return root / "program", package


def run_check():
    if DEPLOYMENT is not None and DEPLOYMENT not in DEPLOYMENTS:
        return fail("SETTINGS_INVALID", f"DEPLOYMENT 只能是 None 或 {DEPLOYMENTS} 之一")

    # 1) SEC_metrics 代码：来自上传的包，逐个文件核对哈希
    try:
        program_root, package = extract_package(PACKAGE_ZIP, usable_work_root(WORK_ROOT))
        summary["package_ref"] = package["ref"]
    except Exception as error:
        return fail("SEC_METRICS_PACKAGE_FAILED", "读不到或核对不通过 PACKAGE_ZIP；确认路径和上传的文件完整。", error)

    # 2) 公司配置：与公司 SecureGPT 测试 notebook 加载配置的步骤相同，但不调用 set_env_vars（SecureGPT 不用它设的环境变量）
    try:
        os.chdir(PD_ROOT)
        if PD_ROOT not in sys.path:
            sys.path.insert(0, PD_ROOT)
        from config import get_main_config
        from utils.config_utils import load_config
        workspace = spark.conf.get("spark.databricks.workspaceUrl")  # noqa: F821 (Databricks 提供)
        mapping = load_config(config="general", field="workspace").get("environment", {})
        sdk_env = SDK_ENV or mapping.get(workspace)
    except Exception as error:
        return fail("COMPANY_CONFIG_FAILED",
                    "公司代码或配置没加载成功：确认 PD_ROOT 路径正确、已运行上一格 %pip install thinc，"
                    "且公司自己的 SecureGPT 测试 notebook 在这个集群上能跑。", error)
    if sdk_env not in CONFIG_ENV_FOR_SDK_ENV:
        return fail("SDK_ENV_UNKNOWN",
                    f"当前工作区对应的环境代码是 {sdk_env!r}，SecureGPT 只认 dv/pp/pr；请在设置里填 SDK_ENV。")
    summary["sdk_env"] = sdk_env
    try:
        get_main_config("config/main_config.cfg", CONFIG_ENV_FOR_SDK_ENV[sdk_env], True)
    except Exception as error:
        return fail("COMPANY_CONFIG_FAILED", "get_main_config 失败：这一步是公司代码加载配置，与 SEC_metrics 无关；先确认公司自己的 SecureGPT 测试 notebook 在这个集群上能跑。", error)

    # 3) 公司 SDK：必须在 get_main_config 之后导入。注意：导入会把本进程的 https_proxy 置空（SDK 自身行为）
    try:
        from utils.secure_gpt import SecureGPT
        client = SecureGPT(sdk_env)
    except Exception as error:
        return fail("SDK_INIT_FAILED",
                    "SecureGPT(env) 初始化失败：多半是 main_config.cfg 缺少该环境的某个 chat_completions_url_* "
                    "或 secret_scope 配置（看上面的 KeyError）。", error)

    # 4) 令牌：读 dbutils 密钥并请求令牌服务；不打印令牌
    try:
        summary["token_step_attempted"] = True
        client.get_token()
    except Exception as error:
        return fail("TOKEN_FAILED",
                    "取令牌失败：错误来自 dbutils.secrets 时，说明当前账号读不了该 secret scope；"
                    "HTTP 401/403 说明令牌服务拒绝了这组凭证。", error)

    # 5) SEC_metrics 代码：只从包里的 program 目录加载，避免用到别的版本
    try:
        sys.path.insert(0, str(program_root / "tools"))  # 包里的版本优先于环境中同名的模块
        for name in ("probe_securegpt", "securegpt_sdk"):
            sys.modules.pop(name, None)
        probe = importlib.import_module("probe_securegpt")
        sdk = probe.sdk
        expected = (program_root / "scripts" / "securegpt_sdk.py").resolve()
        if Path(sdk.__file__).resolve() != expected:
            raise ImportError(f"loaded {sdk.__file__}, expected {expected}")
    except Exception as error:
        return fail("SEC_METRICS_IMPORT_FAILED", "SEC_metrics 的模块没加载成功。", error)

    # 6) 唯一一次调用：消息格式与发送都用 SEC_metrics 的 securegpt_sdk.send
    challenge = probe.challenge()
    request_client = client if DEPLOYMENT is None else ChosenDeployment(client, DEPLOYMENT)
    print("开始调用 SecureGPT（只此一次）。超过 3 分钟没有返回请点 Cancel，不要直接重跑。")
    summary["securegpt_calls"] = 1
    try:
        raw = sdk.send(client=request_client, messages=challenge["messages"])
    except UnboundLocalError as error:
        return fail("REQUEST_FAILED",
                    "SDK 发请求时出错，真实原因只打印在上方以 'Error making request to GPT endpoint' 开头的那一行；"
                    "远端是否已执行未知，不要直接重跑。", error, show_traceback=False)
    except Exception as error:
        return fail("REQUEST_FAILED", "调用时抛出异常；远端是否已执行未知，不要直接重跑。", error)

    # 7) 读回答与用量：用 SEC_metrics 的 normalize_response / assistant_content / response_usage
    try:
        normalized = sdk.normalize_response(raw)
    except Exception as error:
        return fail("RESPONSE_UNREADABLE", "SDK 返回的对象无法读取。", error)
    if isinstance(normalized, dict):
        summary["response_keys"] = sorted(normalized)[:20]
        summary["model"] = normalized.get("model")
        choices = normalized.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            summary["finish_reason"] = choices[0].get("finish_reason")
        if hasattr(sdk, "response_usage"):
            summary["usage"] = sdk.response_usage(normalized)
        error_body = normalized.get("error")
        status_code = normalized.get("statusCode")
        if error_body or (isinstance(status_code, int) and status_code >= 400):
            detail = error_body if isinstance(error_body, dict) else {"message": error_body}
            summary["service_error"] = {"statusCode": status_code, "code": detail.get("code"),
                                        "message": str(normalized.get("message") or detail.get("message") or "")[:300]}
            return fail("SERVICE_RETURNED_ERROR",
                        "服务返回的是错误信息，不是回答；看 service_error（401 常见于订阅密钥或令牌问题，"
                        "提到 api-version 时说明该模型地址的接口版本需要更新）。")
    try:
        summary["answer"] = probe.validate(normalized, challenge)
    except Exception as error:
        try:
            summary["assistant_text_preview"] = str(sdk.assistant_content(normalized))[:200]
        except Exception:
            pass
        return fail("ANSWER_NOT_USABLE",
                    "模型有返回，但没通过检查：被过滤或截断、不是纯 JSON（比如包了 ```json 代码块），或标记/求和不对；"
                    "看 error 和 assistant_text_preview。", error, show_traceback=False)
    summary["status"] = "PASS"
    summary["message"] = "SEC_metrics 的消息格式、发送、读回答和读用量在 Databricks 上与 SecureGPT 配合正常。"
    return True


run_check()
summary["elapsed_seconds"] = round(time.monotonic() - _started, 2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
if summary["status"] != "PASS":
    raise RuntimeError(f"SecureGPT check did not pass: {summary['status']}")
