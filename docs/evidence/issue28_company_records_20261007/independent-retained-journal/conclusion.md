# 旧独立普通 journal 限定独审

结论：**PASS_LIMITED**。在指定新增分派、归档引用读取和六个小例的范围内，未发现需要修复的问题。该结论不授予 C04 当前数值/语义接受、完整原生审核、全模块或 PR67 批准。

审查基线 `adee30366a13c0c4ead3f30ec5344db19ebf746f`，补丁 `497e0458ea1e8b279d37150b4b2dad60a7147a48`；实际检出 `6b2b8d925fb357a449b582e9f9b2a96f3d8467ae`。三份源码/测试工作树与补丁及当前 HEAD 逐字节相同，见 `source-binding.log`。原 `_ordinary_candidates`、`_manifest`、测量期间读取、缺陷筛选、公司 checkpoint 读取与构建函数 AST 未变；`ordinary_update_cycle.py` 字节未变。这些旧范围只核对复用边界，未重新作全模块审核。实时读取 Issue #28 的三个目标、当前队列、测试减负及权限边界；父方提供的日志仅作为线索，下面的执行均由本独审实际完成。

## 实际验证

- 指定命令 `TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest tests.vnext.test_company_results.CompanyResultsTest -v`：21 项通过，零失败/错误/跳过；套件 0.182s，完整进程 0.516s，见 `unittest.log`。包括六个新增小例；首次失败不造 Result，后续失败保留旧结果的归档引用，错公司与断链成功指针拒绝，读取不计算、不重放、不写公司视图，精确缺陷和其他 runtime 的释放信息仍可见。
- 指定真实 CLI `/private/tmp/issue28-company-c02-venv-20261006/bin/python -B tools/vnext_company.py results --company southwest_airlines --state-root /Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/private-c04-southwest-20260927`：exit 0，0.330s。实际读取原 C04 `sha256:2f06895d80507148edfd7602427abffb8f6918323a48689c26345345c8170fe6`、原 OPEN Run 和 FY2025 归档坐标；`source_checkpoint_id=null`，`NOT_RECHECKED/NOT_ASSESSED/NOT_REPLAYED`，测量期间仍 `NOT_AVAILABLE`。输出没有把归档坐标或旧 source_credit 升级为当前验收。见 `cli.log` 与 `execution-summary.log`。
- 真实旧根读取前后，**927 个既存文件逐一 SHA-256 相同，文件集合相同**，无新增/删除文件；计数包含本次读取前已存在的锁文件。旧 Run、保存源码、journal、来源均未改。本次计数是自身实际快照，不沿用父方 926 文件的口径。
- 四个独立临时小探针通过，见 `boundary-probes.log`：精确错误 Result 即使列同 runtime 释放仍保持 `CONFIRMED_INVALID`；坐标级缺陷仅在 Result+runtime 都匹配时清除 hold，结果仍为 `NOT_ASSESSED`；占用原 update 锁时拒绝 `UPDATE_ALREADY_RUNNING`；要求新日常 CSV 时拒绝，未创建输出目录。探针禁用计算与重放，未碰真实旧根。

## 机制与范围

新增分派先保留 `company-task.json` 的既有保存记录入口，再识别顶层 `configuration.json/current.json`；旧公司 checkpoint 分支仍走原路径。归档分支在原 update 锁内读取原链、配置/intent/terminal 绑定、成功指针和原 manifest，承接原失败/公司/断链检查；不安装 checkpoint/trust、不创建新 Result、不写回 `company-results.json`。有失败时输出失败当前输入状态；无失败也只显示未复核。缺陷释放逻辑复用既有实现，不以其他运行版本的放行解除当前 hold。

未执行计算、原生重放、长材料、模型/SEC/账户请求、Git 写入或原运行账本操作；实际改动仅为本目录的结论与日志。未扩展 CSV/计算家族，未验证在线更新或完整 C04 业务正确性。

## 资源记录

父方 spawn：2026-10-08T14:41:33Z；首次实读时钟：2026-10-08T14:42:39Z；结论写入：2026-10-08T14:47:44.389419+00:00。含本次最后核对，合计 37 次工具调用（含 functions 包装和嵌套；低于 80），无子代理，普通进展消息 0、问题 0、最终消息 1。于截止 2026-10-08T16:11:33Z 前完成，未接近 90 分钟限制。
