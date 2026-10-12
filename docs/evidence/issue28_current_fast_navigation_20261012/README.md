# 当前快测入口与旧版本导航

从实际main `e3c17f81` 接续，只修正 AGENTS、SOP 和 TESTING 中把旧 `run_fast_tests.py` 写成当前CI入口的语句。当前命令为 `python3 tools/run_foundation_ci.py --suite fast --jobs 4`，与实际 `.github/workflows/vnext-fast.yml` 相同。旧runner、D-26及旧R4保存程序的原说明仍保留，并在命令旁标明历史适用范围。

未修改运行器、测试选择器、workflow、计算、来源、冻结旧包或业务结果；没有把取消的祖先字节证明恢复成新开发前置。当前普通代码推荐顺序指向foundation入口，旧formal Cutover段明确只适用保留版本，不自动授予生产操作。

实际执行CLI `--help`，核对参数存在；读取workflow实际命令，与三份文档对照；检查当前普通代码段不再指向旧runner；检查改动只有三份文档，`git diff --check`通过。日志在 `cli-help.log`、`navigation-check.log`；被测工作树与原文件摘要在 `tested-worktree.json`。

该核对证明导航/参数一致，不证明全套快测、财报业务或真实模型再次执行。未为纯说明修改重跑十家公司或旧快测，也未新增SEC/provider/paid调用。与PR189公共B06、Salesforce存量D04公司演练分开，不改其候选范围或在途运行文件。

提交8d8f0194后还实际运行既有capability结构检查（base e3c17f81）通过，见structure-check.log。它只核机械文档结构/符号存在，不能证明业务声明或旧反篡改机制恢复正确；没有新增业务测试前置。
