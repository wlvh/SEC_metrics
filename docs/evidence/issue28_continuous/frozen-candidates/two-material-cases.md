# 两份普通候选：真实冻结与新进程冷读

在提交 `180a05e816a6f2b4014f403768458506d56c96c9` 的V12实现上，两例均实际调用 `validate_and_freeze_run` 成为 **FROZEN / validation PASSED**，随后由新的Python进程调用 `load_frozen_run` 成功。不是OPEN检查或单个JSON往返。材料测试共2项，45.556秒，全部通过，没有失败需要重跑。

| 公司/指标 | 实际结果 | 实际期间 | 来源引用 | Review | 新进程PID |
|---|---|---|---:|---|---:|
| Marriott D01 | 34条原文标题，4774字符，TEXT_V1/EXACT | 2025-01-01至2025-12-31 | 3 | 1条SYSTEM | 94247 |
| Paramount C03 | 63,211,569 USD，EXACT；保留真实DERIVED_ASSET | 2025-08-07至2025-12-31 | 16 | 0条；声明的确定性结构化路径 | 94284 |

父进程PID为94230。Requirement closure：`sha256:b275dc81a817283d60593d58fbe31ca7668222e0d1a7f779b4339d65947dcf67`。执行后核对全部V12 execution authority与五文件相对180a05e没有源码差异；其他并行工作的金融文件不属于该执行闭包。

每案各用全新外部data/run目录。data分别保存461、487个文件，均无.git。冷读进程工作目录也在外部；审计钩子禁止任何socket事件和任何子进程（包括git），blocked_events均为空。冷读使用当前可信安装代码；这里没有声称交付了完全独立的代码安装包或完成新目录重定位测试。

冻结前与冷读后逐项一致：完整Result、全部record graph、SourceReference及其正文SHA、全部data文件（含来源metadata/header/ledger）、实际期间、ReviewDecision与全部渲染审阅文件。`records.jsonl`、`review_decisions.jsonl`字节不变。冻结manifest的records/review/validation/content/audit hashes已保存。正式active、matrix/evidence、报告、validation manifest及原始ledger/ledger manifest前后hash不变。

真实命令：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts NORMAL_NATIVE_MATERIAL_ROOT=/tmp/sec_metrics_issue28_continuous/pr43-review/native-material-180a05e python3 -m unittest -v tests.vnext.test_normal_native_material
```

工作目录：`/Users/lyuhongwang/Developer/SEC_metrics`。Python：3.14.7。复跑必须使用新的NORMAL_NATIVE_MATERIAL_ROOT，测试拒绝覆盖既有材料。

每个子进程的实际完整命令、工作目录、PID和returncode见各案outcome.json；其形式为：

```text
/opt/homebrew/opt/python@3.14/bin/python3.14 /Users/lyuhongwang/Developer/SEC_metrics/tests/vnext/test_normal_native_material.py --cold-read <data> <run> <before-freeze.json> <cold-read.json>
```

Marriott Run：`run:normal-saved:0c9e57e53239508bd69512b6f1fe21fa24ea16284f4115ec235d2e0628945f3c`。

Paramount Run：`run:normal-saved:ce1b48fa08a5b2aa8df626667a8cf114a275fad06701050e1abf6fa223548226`。

索引：`summary.json`汇总身份/结果/实际命令；各案`before-freeze.json`、`frozen-manifest.json`、`cold-read.json`与`cold-process.log`保留比较依据。上一级`native-material-180a05e.log`是实际unittest日志。

Provider / paid / SEC = **0 / 0 / 0**。原生Result内PUBLISHED不等于正式发布；没有合并、正式采纳或active切换。D01证明的是标题级来源摘录，不证明风险已发生或所有R6业务解释已完成。本轮按最新委托只跑这两个正常流程，没有展开破坏性负例矩阵，也不表示Issue #28收口。
