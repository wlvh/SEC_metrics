# 指定新差异限定独审结论

结论：在本次指定的新差异范围内，未发现需要修复的问题。该结论仅适用于下列提交之间的源码差异及本地短测试；不代表全公司、全 PR、业务正确性或生产采纳批准。

- Base：`f6ef7886d6630f7675c25cd42e306c373ab05769`
- Patch / 实际 HEAD：`08d3e620239426bd692f2bdb3577c21c352aa2f9`
- 工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-source-proof-batch/SEC_metrics`
- 输入：本目录 README、before/after-readonly-profile.log、actual-update.json、actual-company.json、tested-tree.json，以及指定源码、测试和 CI 接线差异。
- 对 tested-tree.json 五项文件逐一重算 SHA256，均与提交工作树一致；结束时再次确认 HEAD 和五项字节未变。

## 已核验的行为

1. batch 仅在一次校验操作内读取当前 CSV 快照并建立行身份索引。每项证明仍进入由原 single API 抽出的同一 `_validate_named_row`，逐项核对 GET/200/error、URL、accession、document、内容摘要及完整正文/响应头字节和路径。Single API 保留原始查找、返回值和异常边界；既有调用未切换成长期缓存。
2. `_current_sources` 仍先选择每个 URL 的实际最新 GET。旧成功不能覆盖最新失败；缺失 URL、错误来源身份、损坏或缺失正文/响应头、过期 manifest 均拒绝。重复完全相同的 GET 保留各自原始行身份；实际传入 batch 的是最新行身份。
3. 调用方先固定 log 摘要，batch 将其与读取快照比较，并在操作中及末尾再次检查 log/manifest。已执行的有限 race 反例包括逐项 locator 校验时 log 改变，以及 latest 选择后、batch 读取前发生合法追加；均未返回不变成功。这不是对任意并发文件系统情形的完整原子性证明。
4. 配置比较仅剔除 `ordinary_current_update.py` 和 `request_bindings.py` 的 processing_files 摘要；两者的当前来源检查仍在复用判断前执行，检查失败阻止旧成功复用。producer、年期、parser、Calculator、Spec、prompt/模型、registry、source_root 和声明处理依赖仍完整参与比较。版本变化测试保留原完成配置和结果身份；其他处理输入变化仍进入处理分支。当前检查版本另写于新检查记录，未重签旧 Result/完成配置。
5. 实际 CI 文件在 pull_request paths 加入新测试文件，并在现有 company-current job 的运行命令直接加入新模块。这里核验的是提交中的真实接线；未访问或声称远端 CI 已通过。
6. before/after 两份 profile 中均有 44 次 locator 检查，差异来自减少 CSV 解析和重复生成行身份。actual-update/company 记录清楚标明隔离状态、零新调用、保留旧七文件和原 structural N_A/null；本审阅仅核读这些已保存记录及其源码字节绑定，未重跑该公司 CLI、对方状态或大材料，也未把这些记录升级为新的实测性能或业务完成证明。

## 独立执行

`PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_request_binding_batch tests.vnext.test_saved_source_checks tests.vnext.test_ordinary_current_update`

实际运行 58 tests，failures=0、errors=0、skipped=0，exit=0；unittest 1.852 秒，包含启动的命令墙钟 2.091 秒。详见 `required-tests.log`。

另执行 6 项有限反例/比较检查：重复 latest 行身份、删除 URL 后有效 manifest 仍拒绝、选择后合法追加 race、调用方旧 log 摘要、require_immutable 必须为 bool、producer/year/声明输入/Spec/parser/prompt/registry 精确比较，均通过，见 `supplemental-checks.log`。第一次补充脚本误选首条历史 GET，而 fixture 未复制它的 locator，程序正确拒绝缺失正文；这是审阅脚本的准备错误，修正为实际最新 GET 后通过，记录保留于 `supplemental-first-attempt.log`。未修改产品或测试源文件。

## 未覆盖及操作计数

未覆盖全仓闭包、全部公司/指标/首次处理成本、完整 company job、远端 CI、在线来源发现、来源或模型业务准确性、生产权限/采纳，也未证明任意时点正文/响应头与 log 的完整并发事务隔离。不将本结论扩展到这些范围。

本审阅共 18 次工具计数（7 次 functions.exec 包装 + 11 次 exec_command 嵌套调用），普通消息仅最终报告 1 条。未 spawn、commit、push、network、SEC/provider/paid/account 或写对方 worktree/ledger；仓库唯一新增文件位于本 independent-review 目录，不生成 tar。必要测试临时文件由原 fixture 管理并清理。

完成时间 UTC：2026-10-09T22:17:49.314129+00:00
