# PR55 落到 main 时的最终内容（基于 PR56 `0be58051`，已验证）

PR55 分支建在 `0bc24734` 上，下面这些继承测试在当前分支中本来就存在；它们只有在 PR55 落到 main 之上时，才会成为 PR55 的实际增量。最终工作流要调用 PR56 的 `tools/run_foundation_ci.py`，所以不能在现在的分支上启用，否则会破坏当前 CI。因此最终内容先在隔离组合树中完整做出并真实执行，这里保存可以机械应用的材料。PR56 进入 main 之后，用 `apply-on-main.sh` 一步重建，只核对相对本次已验证组合的实际差异。

## 组成

| 文件 | 内容 |
|---|---|
| `apply-on-main.sh` | 用法：`bash apply-on-main.sh <已含PR56的main> <PR55交付提交> task/issue54-main-integration <新工作区目录>`。在新工作区里创建新分支，分支已存在就停止，不会重置。所有材料都从固定的 PR55 提交读取。先应用 PR55 自身增量（`0bc24734..PR55`，3-way）。补丁失败时，只允许 5 份治理文档出现冲突；其他冲突或补丁错误会删除工作区和分支后停止，不产生提交。合并稿只用于 PR55 增量改过的文档。之后写入 carry 文件和最终工作流，只暂存明确的路径。提交前检查残留冲突标记、`git diff --cached --check`，以及所有变更路径都属于 PR55 增量、carry 清单或工作流。如果 main 侧相关文档或工作流在 `0be58051` 之后又有改动，脚本会停止。 |
| `test-apply-on-main.sh` | 小型临时仓库测试：A 预期文档冲突 → 成功并产生 1 个提交，未改动的文档保持 main 原样；B 意外代码冲突 → 停止，无分支、无提交；C 合并稿残留冲突标记 → 停止。 |
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

## 迁移脚本修正（2026-10-05）

旧脚本按"`git apply ... || true` → `git add -A` → 再检查未合并项"的顺序执行。`git add` 会把冲突状态清掉，即使文件里还留着冲突标记，因此冲突可能被直接提交。现已按上表修正，`test-apply-on-main.sh` 三种情况都符合预期。

在真实仓库上，用修正后的脚本、以 PR56 `0be58051` 为 main、`30e86785` 为 PR55 运行：
- 产物与已验证的 `e378abe3` 在 `docs/evidence/issue54_company/` 之外零差异。
- 相对 PR56 共 475 个路径：PR55 自身增量 442、carry 原件 32、工作流 1，没有无法归类的路径。
- PR56 也改过的 `AGENTS.md`、`TESTING.md`、`architecture.md`、`tools/run_fast_tests_v2.py`，PR56 新增的行全部保留（2/2、3/3、1/1、258/258）。
- 工作流中 PR56 原有三个作业的时限和步骤原样保留，只在 fast 作业里加了公司测试步骤。

## 分支方案

PR56 获批进入 main 后，从该 main 用本脚本创建 `task/issue54-main-integration`，建立以 main 为目标的替代 Draft PR，关联 #54 和旧 PR55。旧 PR55 保留完整历史和证据，不 force push，不删除分支；替代 PR 建好、内容与证据接续确认后，把旧 PR55 关闭为"被替代"，不标为已合并。不采用"改 base 后 squash"的做法：squash 不会过滤掉不该进入 main 的文件修改。
