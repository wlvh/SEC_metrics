# Databricks notebook source
# MAGIC %md
# MAGIC ## SEC_metrics：在 Databricks 上离线计算一家公司的指标
# MAGIC
# MAGIC 输入是笔记本上 `tools/databricks/build_offline_package.py` 生成的 zip（程序 + 这家公司已保存的 SEC 原件）。
# MAGIC 本 notebook 不访问外网、不调用 SEC 或任何模型：先核对 zip 的 SHA-256 等于设置里的预期值（预期值来自仓库页面
# MAGIC 或你自己的打包输出，不能取自 zip 本身），再解压、逐个文件核对哈希，然后用项目自己的
# MAGIC `tools/vnext_company.py run --source-root` 计算，最后显示结果表。
# MAGIC
# MAGIC 用法：把 zip 上传到 Unity Catalog Volume，改下一格开头的 `PACKAGE_ZIP`（用自己打的包时再改 `EXPECTED_ZIP_SHA256`）后运行。

# COMMAND ----------

# ===== 只需要改这里 =====
PACKAGE_ZIP = "/Volumes/<catalog>/<schema>/<volume>/sec_metrics_<company_id>_<ref前8位>.zip"
EXPECTED_ZIP_SHA256 = "388d49c206d1688a6011e93a8a2c0e47ce93499713713c72e360d9c005049fd4"  # 仓库附带的万豪包；自己打的包填打包输出里的 zip_sha256
METRICS = ["B01", "B02", "B04", "B05", "B10", "B11"]  # 万豪（酒店业）验证过的六项；B10/B11 是酒店业指标，其他行业要换
WORK_ROOT = "/local_disk0/tmp/sec_metrics"  # 驱动节点本地盘；不要用 /dbfs 或 /Volumes（计算要用文件锁）
SAVE_TO = None  # 结果另存目录，例如 "/Volumes/<catalog>/<schema>/<volume>/sec_metrics_outputs"；None 不另存
# ========================

import csv
import hashlib
import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

started = time.monotonic()
summary = {"status": "NOT_STARTED"}


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


def extract_package(zip_path, work_root, expected_sha256):
    """Check the zip against the expected SHA-256, extract those exact bytes once, then verify every file."""
    data = Path(zip_path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.strip().lower():
        raise RuntimeError(f"zip 的 SHA-256 是 {digest}，与 EXPECTED_ZIP_SHA256 不符，没有解压也没有运行。"
                           "确认上传的是哪个包；用自己打的包时，把打包输出里的 zip_sha256 填进设置。")
    target = Path(work_root).resolve() / f"package-{digest[:12]}"
    root = target / "sec_metrics_package"
    if not (root / "PACKAGE.json").is_file():
        partial = Path(work_root).resolve() / f".extracting-{digest[:12]}-{int(time.time())}"
        with zipfile.ZipFile(io.BytesIO(data)) as archive:  # 解压的就是刚核对过的这份字节
            archive.extractall(partial)
        partial.rename(target)
    package = json.loads((root / "PACKAGE.json").read_text(encoding="utf-8"))
    bad = [name for name, sha in package["files"].items()
           if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha]
    if bad:
        raise RuntimeError(f"{len(bad)} files differ from PACKAGE.json, first: {bad[0]}")
    return root, package, digest


WORK_ROOT = usable_work_root(WORK_ROOT)
root, package, zip_sha256 = extract_package(PACKAGE_ZIP, WORK_ROOT, EXPECTED_ZIP_SHA256)
company = package["company_id"]
summary.update(company_id=company, package_ref=package["ref"], zip_sha256=zip_sha256,
               verified_files=len(package["files"]), sec_bodies=package["sec_bodies"])
print(f"包已核对：{company}，{len(package['files'])} 个文件，SEC 原件 {package['sec_bodies']} 个，程序版本 {package['ref'][:12]}")

# COMMAND ----------

program, source = root / "program", root / "source"
# 按包区分：同一个包在同一集群上重复运行会复用已算结果；换了包（字节不同）用新目录从头计算
state = Path(WORK_ROOT).resolve() / f"state-{company}-{zip_sha256[:12]}"
output = Path(WORK_ROOT).resolve() / f"output-{company}-{zip_sha256[:12]}"
command = [sys.executable, "-I", str(program / "tools" / "vnext_company.py"), "run", "--company", company,
           "--source-root", str(source), "--work-dir", str(state), "--output-dir", str(output)]
for metric in METRICS:
    command += ["--metric", metric]
print("运行：", " ".join(command[2:]))
completed = subprocess.run(command, cwd=WORK_ROOT, capture_output=True, text=True, timeout=1800)
summary["cli_exit_code"] = completed.returncode
try:
    result = json.loads(completed.stdout)
except json.JSONDecodeError:
    print(completed.stdout[-3000:])
    print(completed.stderr[-3000:])
    raise RuntimeError(f"计算没有输出结果摘要，退出码 {completed.returncode}；上面是原始输出。")
summary["flow_status"] = result.get("status")
summary["calls"] = result.get("calls")  # 程序自己统计的本次新调用：provider=模型，paid=付费，sec=SEC 请求
summary["metrics"] = {m["metric_id"]: m["status"] for m in result.get("metrics", [])}
failures = {m["metric_id"]: m.get("reason", "") for m in result.get("metrics", [])
            if m["status"] not in ("CANDIDATE_READY", "NO_SOURCE_CONTENT_CHANGE")}
if failures:
    summary["metric_failures"] = failures
output_root = Path(result["output_root"])
summary["output_root"] = str(output_root)

with (output_root / "metrics_matrix.csv").open(encoding="utf-8") as stream:
    rows = [row for row in csv.DictReader(stream) if row["metric_id"] in METRICS]
columns = ["metric_id", "metric_name", "value", "unit", "period_start", "period_end", "fiscal_year",
           "status", "local_metric_status", "accession", "notes"]
table = [{column: row.get(column, "") for column in columns} for row in rows]
summary["values"] = {row["metric_id"]: row["value"] for row in table}
show = globals().get("display")
if show is not None:
    import pandas as pd
    show(pd.DataFrame(table))
else:
    for row in table:
        print(row)

if SAVE_TO:
    destination = Path(SAVE_TO) / f"{company}-{output_root.name}"
    for item in output_root.rglob("*"):  # 只复制内容：Volume 不一定支持修改文件时间
        if item.is_file():
            (destination / item.relative_to(output_root)).parent.mkdir(parents=True, exist_ok=True)
            (destination / item.relative_to(output_root)).write_bytes(item.read_bytes())
    summary["saved_to"] = str(destination)

calls_zero = all((result.get("calls") or {}).get(kind) == 0 for kind in ("provider", "paid", "sec"))
summary["status"] = (result.get("status") if result.get("status") != "FLOW_COMPLETED"
                     else "PASS" if calls_zero else "UNEXPECTED_CALLS")  # 离线计算应零调用，不为 0 或未知都不算 PASS
summary["elapsed_seconds"] = round(time.monotonic() - started, 1)
print(json.dumps(summary, ensure_ascii=False, indent=2))
