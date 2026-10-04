# PR55 落到 main 时的最终内容（基于 PR56 `0be58051`，已验证）

PR55 分支建在 `0bc24734` 上，下面这些继承测试在当前分支中本来就存在；它们只有在 PR55 落到 main 之上时，才会成为 PR55 的实际增量。最终工作流要调用 PR56 的 `tools/run_foundation_ci.py`，所以不能在现在的分支上启用，否则会破坏当前 CI。因此最终内容先在隔离组合树中完整做出并真实执行，这里保存可以机械应用的材料。PR56 进入 main 之后，用 `apply-on-main.sh` 一步重建，只核对相对本次已验证组合的实际差异。

## 组成

| 文件 | 内容 |
|---|---|
| `apply-on-main.sh` | 以"已含 PR56 的 main"为底：应用 PR55 自身增量（`0bc24734..PR55`，3-way），套用 `../governance-merge-drafts/` 中的 5 份文档，按 blob 写入 `carry-manifest.json` 列出的文件，再装上最终工作流。若 main 侧上述文档或工作流在 `0be58051` 之后又有改动，脚本会停止，要求重新合并，不会直接覆盖。 |
| `carry-manifest.json` | 26 条路径共 32 个文件，均为 `0bc24734` 原件（记录 path、mode、git blob）：18 个核心测试模块、它们导入的 4 个测试模块，以及 4 组夹具 |
| `vnext-fast.main.yml` | 最终工作流：保留 PR56 的 `fast`（其中加入 PR55 公司测试步骤，6 个模块，含 `test_company_local`）、`inherited-source-material`（PR56 的 94/25 分组）、`main-foundation`；新增 8 个 `company-*` 作业 |
| `tests/required_unittests.py`（已在 PR55 实际代码树中） | 统计实际执行数、失败、错误和跳过数；跳过超过原工作流已有值、或执行数为 0 时失败 |

## 实际受测版本与结果

隔离组合树 `e378abe3` = PR56 `0be58051` + PR55 `2bc877a8` 增量（3-way）+ 合并后文档 + carry 文件 + 最终工作流 + 执行器。用 `run_workflow_local.py` 解析工作流，逐作业执行其中的 `run` 步骤：环境变量取自工作流；`runner.temp` 换成每个作业独立、初始不存在的目录；矩阵展开；tokenizer 按固定 hash 安装。日志见 `final-run-logs/`。

| 作业 | 执行 | 失败/错误 | 跳过（允许） | 耗时 | 时限 |
|---|---:|---:|---:|---:|---:|
| fast：公司测试 6 个模块 + `run_foundation_ci --suite fast` | 67 OK + 94 项短测试 | 0 | — | 138 秒 | 5 分钟 |
| inherited-source-material（25 项） | OK | 0 | — | 317 秒 | 15 分钟 |
| main-foundation | OK | 0 | — | 312 秒 | 10 分钟 |
| company-source-core | 84 + 9 | 0 | 1（1，原工作流已有，见下） | 103 秒 | 15 分钟 |
| company-acquisition-c04 | 6 | 0 | 0 | 644 秒 | 30 分钟 |
| company-c04-source-install | 9 | 0 | 0 | 1532 秒 | 50 分钟 |
| company-native-runs | 1 + 1 | 0 | 0 | 620 秒 | 30 分钟 |
| company-going-concern（按原作业设三个 D04 开关） | 2 | 0 | 0 | 993 秒 | 25 分钟 |
| company-remaining-source（Marriott / JPMorgan） | 1 / 1 | 0 | 0 | 759 / 2112 秒 | 45 分钟 |
| company-update-history | 1 | 0 | 0 | 744 秒 | 30 分钟 |
| company-partial-update | 1 | 0 | 0 | 763 秒 | 30 分钟 |
| 能力契约对齐（`--base-ref af1984ad`，已提交树） | PASS | | | | |

- PR56 的三个作业是在 `46b69a54` 上执行的；它与 `e378abe3` 只差删除误提交的 `TESTING.md.orig`，以及这三个作业都不使用的执行器修正。
- 允许的 1 项跳过：`test_registered_native_update` 需要"已登记的复制原生来源夹具"，旧工作流同样没有设置相应变量，所以这项跳过不是本次迁移造成的。
- 本机最多 3 个作业并行，宿主不是独占的。JPMorgan 用了 35 分钟，离 45 分钟上限（沿用旧工作流）余量不大，GitHub 上的实际耗时以 CI 为准。
- 执行器先后有两个导入路径错误，都被跳过/错误防护拦下、记为错误，没有被误判成通过。第二次修正后，以上结果全部来自同一个最终执行器。
- 本地执行模拟的是工作流中的命令，不等于 GitHub Actions 的实际结果。PR55 改目标后，以实际 CI 终态为准。

## 不在本包范围

旧 v2 / source-material 中其余与 #54 无关的指标路线测试（见 `../final-integration-tree/old-ci-v2-selection-vs-pr56.json`），由基础方或 #28 决定带入，或登记为不接收。本包不复制，也不把它们算作 PR55 的合并前置。
