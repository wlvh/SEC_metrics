# Validation snapshot provenance

## 1. 解决的问题

`outputs/validation_run_manifest.json` 回答“哪一次 validation 刷新了哪些 tracked audit artifact”，但它原先不能回答两个更强的问题：

1. 这次运行使用的代码、配置、测试 fixture 与验收文档，是否仍等同于当前 checkout？
2. manifest、报告、矩阵、证据、Golden、request ledger 与 validation CSV 在运行后是否被修改？

只比较 `manifest.source_commit` 与当前 `git rev-parse HEAD` 也不够。完整批次通常会在验证后提交生成 artifact，PR merge 又可能产生新的 merge commit；commit SHA 可以变化，而真正影响行为的 source tree 未变。相反，整个工作树的 `+dirty` 也可能只来自预期生成的 `outputs/`，不能据此判断源代码被修改。

因此当前模型把 provenance 分成两层：

```text
source-input closure
    代码、工具、配置、测试、指标定义、能力契约和核心验收文档

acceptance artifact closure
    manifest、报告、README、metrics/evidence/coverage/Golden、events、
    request log/manifest，以及本轮 refreshed validation artifacts
```

第一层用 deterministic tree digest 绑定；第二层逐文件记录 SHA-256 与 size。

## 2. 核心文件

- `scripts/validation_provenance.py`：捕获、发布、验证和 fail-closed helper。
- `scripts/11_build_report.py`：新一轮报告开始前删除可安全识别的旧 regular provenance；alias/非 regular 目标提前失败，避免 stale success proof。
- `scripts/12_validate_repair.py`：stage 12 返回零之前，发布并重新验证 provenance。
- `tools/check_validation_snapshot.py`：读取当前 checkout 与 artifact bytes 的独立验收入口。
- `outputs/validation_snapshot_provenance.json`：成功 full/light terminal run 的 sidecar。

## 3. Source-input closure

Git checkout 中，closure 由 `git ls-files` 对以下路径求精确集合：

```text
scripts/
tools/
config/
tests/
capability_contract.json
02_指标定义_SEC_10公司单年指标.md
AGENTS.md
SOP.md
TESTING.md
architecture.md
interact.md
docs/business_user_guide.md
docs/validation_snapshot_provenance.md
docs/concepts/sec_xbrl_and_evidence_model.md
```

每个文件以如下 record 进入整树 SHA-256：

```text
repo_relative_path NUL byte_length NUL content_sha256 LF
```

路径按字典序排序。任何 tracked modification、staged modification、删除或 closure 内 untracked 文件，都会使 stage 12 在运行主 gate 前失败。symlink 或非 regular file 也失败。

生成的 `evidence/`、`outputs/`、报告和 README 不进入 source tree；它们由 artifact closure 单独绑定。这样 stage 00–11 的合法生成副作用不会被误判为 source dirty。

## 4. Commit 与 tree 的关系

provenance 同时记录：

```text
source_commit
source_input_tree_sha256
source_file_count
source_dirty_paths
```

验收规则：

- stage 12 同一次运行内要求 Git HEAD 不变、source tree digest 不变、source dirty paths 为空；
- 当前 checkout 与记录 commit 完全相同，是最直接匹配；
- artifact commit 或 merge commit 造成 SHA 不同时，独立 checker 只有在完整 source-input tree digest 和文件数仍一致、当前 source closure 仍 clean 时，才给出 warning 并继续；
- tree digest、文件数或任何 source byte 不一致时失败，不能以“commit 看起来相关”替代内容证明。

这比简单的 `source_commit == HEAD` 更严格地约束真实行为输入，同时不会把内容等价的 merge commit 错判为不同实现。

## 5. Artifact closure

full snapshot 至少绑定：

```text
outputs/validation_run_manifest.json
outputs/golden_results.csv
outputs/metrics_matrix.csv
outputs/metric_evidence.csv
outputs/coverage_matrix.csv
outputs/events.csv
outputs/<manifest.refreshed_artifacts>
evidence/requests_log.csv
evidence/requests_log_manifest.json
REPORT_十公司财务指标.md
README_RUN.md
```

每个 key 的值严格只有：

```json
{
  "sha256": "<64 lowercase hex>",
  "size_bytes": 123
}
```

sidecar 的 key set 必须和当前 manifest 推导的 expected set 完全一致；缺少、多余、size 变化或 SHA-256 变化都失败。light package 不要求被明确省略的 raw evidence，但仍绑定随包 source 与 artifact bytes，并标记 `LIGHT_PACKAGE_NO_GIT`。

## 6. Publication 顺序

```text
stage 11 start
→ 删除旧 provenance
→ bounded repair / report / README

stage 12 start
→ 删除旧 provenance
→ 捕获 clean source snapshot
→ 运行既有 repair validation 与 report terminal publication
→ 仅在 manifest 为 FULL/PASSED 或 LIGHT/PASSED_WITH_CAVEATS 时计算 artifact digests
→ 原子写 provenance sidecar
→ 从磁盘重新读取并验证
→ 成功后 stage 12 才 exit 0
```

若既有 stage 12 已生成成功 manifest/report，但 provenance postflight 写入或自验失败，wrapper 会：

1. 删除可安全识别的未完成或旧 regular sidecar；unsafe alias 保留为 checker 必然拒绝的状态；
2. 把 manifest `result` 降为 `FAILED`；
3. 把报告 verdict 改为 `NO-GO` 并写入失败原因；
4. 非零退出。

因此不会留下“stage 12 exit 0 但没有 source/artifact binding”的成功态。

## 7. 人工验收命令

```bash
git rev-parse HEAD

python3 - <<'PY'
import json
from pathlib import Path

manifest = json.loads(
    Path("outputs/validation_run_manifest.json").read_text(encoding="utf-8")
)
print(manifest["source_commit"])
PY

python3 tools/check_validation_snapshot.py
```

前两条命令用于观察 commit 关系；第三条才是最终内容验收。checker 输出：

- `PASS`：source closure 与 artifact closure 均匹配；
- `WARNING`：commit SHA 改变，但完整 source-input tree 内容等价；
- `FAIL`：缺 sidecar、schema/identity 失配、dirty source、tree mismatch、artifact hash/size mismatch 或路径边界错误。

## 8. 边界

- sidecar 是仓库内自证明，不替代外部时间戳、签名或不可篡改存储；能同时改写全部文件并重签的人仍在本地信任边界内。
- Git workspace guard 与后续 Git 命令不是一个原子系统调用，不宣称抵御恶意同 UID 进程的主动 namespace TOCTOU。
- source closure 是显式策略。新增会影响运行或验收的路径时，必须更新 closure、文档和负例测试。
- provenance 证明 bytes 一致，不证明业务方法本身正确；Golden、repair validation、外部审计和人工判断仍各自负责自己的结论。
