# SEC_metrics 测试与验证流程

本文件是项目测试策略、真实命令、full/light 边界和测试副作用的权威入口。所有命令默认在仓库根目录执行；完整阶段顺序以 `README_RUN.md` 为准。

## 1. 测试原则

- 测行为与契约，不用脆弱的源码字符串或固定数量断言替代真实结果。
- 默认使用固定 fixture、临时工作区和本地 evidence，保持确定性与隔离。
- 单元级成功不能替代 Golden、repair gate 或完整阶段场景；light review 不能替代 full validation。
- 新增测试前先说明它覆盖的真实缺口；避免为 13 个薄 wrapper 重复编写同构测试。
- Bug 修复先加入能稳定复现的最小回归，再修实现；跨阶段状态事故还需要场景级回归。
- 任何会联网或覆盖 `evidence/`、`outputs/`、报告的命令，都应在干净且隔离的 checkout 中运行，并在执行前确认配置。
- 测试记录必须包含原样命令、结果、证据路径和未运行原因；不能把预期结果写成已通过。

## 2. 环境与前提

- 运行时为 Python 3，当前代码只导入标准库和本地模块。
- 仓库没有 `pyproject.toml`、requirements、tox 或 CI workflow，因此最低支持的 Python 版本尚未由项目配置冻结。
- 快速测试建议设置 `PYTHONDONTWRITEBYTECODE=1`，避免在仓库生成 `__pycache__`。
- live SEC 命令读取 `config/sec_config.json`，只允许官方 SEC 域名，并写入请求日志和 raw evidence。阶段 11 也可能在 C04 AuditorName 本地材料缺失时条件式联网。
- 当前 `config/sec_config.json` 的联系邮箱是示例值；任何可能联网的命令（包括上述阶段 11 条件分支）运行前，必须由运行负责人换成有效 organization/contact email。

## 3. 真实测试与验证层级

| 层级 | 命令 / 入口 | 网络 | 仓库写入 | 通过条件 | 不能替代 |
|---|---|---:|---:|---|---|
| 快速回归 | `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'` | 否 | 测试设计上只写临时目录 | unittest 全部通过；允许的 skip 必须在记录中说明 | full evidence、Golden、完整阶段 |
| 能力文档对齐 | 当前无持久化自动测试 | 否 | 否 | reviewer 递归核对 anchor 唯一、引用存在、test anchor 真实 | 业务逻辑测试 |
| 静态扩展性 gate | `python3 tools/check_no_company_literals.py` | 否 | 是，覆盖 `outputs/scalability_audit.csv` | 无禁止 identity literal，进程退出 0 | 指标正确性、场景回归 |
| Golden | `python3 scripts/10_run_golden_assertions.py` | full 模式会联网；light 不联网 | full 模式覆盖 Golden outputs，并可能追加 evidence/log | 所有适用 assertion PASS；light 只能得到受限完整性结果 | repair gate、外部验收 |
| Repair / validation gate | `python3 scripts/12_validate_repair.py` | 否 | 是，覆盖多个 validation/audit outputs | 不存在 P0 FAIL 或 `WORKSPACE_INCOMPLETE`；light 只允许受限状态 | live 数据采集、完整场景 |
| Report build | `python3 scripts/11_build_report.py` | 条件式：C04 AuditorName 本地材料缺失时联网 | 是，先应用 repair；可能追加 SEC evidence，再重建多个 outputs、报告和 `README_RUN.md` | 命令完成只证明产物已生成 | 独立阶段 12 gate |
| Live smoke | `python3 scripts/00_smoke_test_sec_access.py` | 是 | 是，写 request log 与 raw response | 官方 SEC 请求满足脚本判据 | 后续指标与验证 |
| 完整场景 | 按 `README_RUN.md` 从 `00` 运行到 `11`，再运行 `12` | 是 | 是，大量 evidence/outputs/report | 每阶段成功，Golden 与最终 repair gate 均通过 | 外部审计接受 |

## 4. 快速回归覆盖

当前 `tests/test_sec_pipeline_validation.py` 覆盖：

- `LIGHT_REVIEW_MODE` 与 `WORKSPACE_INCOMPLETE` 的工作区形状和 marker 行为。
- light snapshot、fixture 与 metrics matrix 篡改检测。
- Basel threshold 排除、actual ratio 选择与 iXBRL scale/parser route。
- captive finance recall/exclusion 与第 11 家 financial institution fixture。
- 10-K/A 到同期间原始 10-K full-instance fallback。
- AST string-addition constant folding 与 I1-I8 implementation map。

边界说明：

- `validation_package_mode()` 的 `FULL_VALIDATION` 工作区分类目前没有独立 unittest；完整模式仍依赖真实完整工作区、Golden 和 repair gate 的运行证据。
- `FullInstanceFallbackTest` 只覆盖 10-K/A 到同期间原始 10-K 的 full-instance fallback，不得计入 package-mode coverage；它在缺少 `evidence/submissions/` 时整类 skip，必须在测试记录中保留 skip 数量与原因。
- JPM CET1 amount cross-check 在相关 instance CSV 缺失时可能没有 failure；light 环境中的成功不能证明真实 CET1 evidence 已验证。
- 快速回归不访问网络，也不证明完整 M0-M7 artifact handoff。

## 5. Fixture 简介

| 路径 | 用途 |
|---|---|
| `tests/fixtures/sec_10_company_spike/golden_expected_values.csv` | 固定结构与数值 Golden expected |
| `tests/fixtures/eleventh_company_smoke/` | 配置驱动的新增公司/profile 行为与去公司特例边界 |
| `tests/fixtures/inline_scale_route/mock_inline_scale.xml` | iXBRL scale、sign 与 parser route 回归 |
| `tests/fixtures/regression/previous_ok_status_snapshot.csv` | 已有 OK recall 的回退防护 |

fixture 可以包含公司身份；生产 `scripts/` 与 `tools/` 不得用公司身份触发业务分支。

## 6. FULL、LIGHT 与不完整 workspace

`validation_package_mode()` 当前按工作区形状判定：

1. `evidence/`、`evidence/requests_log.csv` 和至少一个 `outputs/concept_inventory/*.csv` 存在时，返回 `FULL_VALIDATION`。
2. 上述材料有缺失且根目录存在 `LIGHT_REVIEW_PACKAGE.marker` 时，返回 `LIGHT_REVIEW_MODE`。
3. 材料有缺失且没有 marker 时，返回 `WORKSPACE_INCOMPLETE`。

重要限制：

- `FULL_VALIDATION` 只是形状分类，不证明每个 raw evidence 文件都齐全；可信度仍来自 Golden、repair checks 与具体证据核对。
- 完整工作区优先于 marker；不能仅靠 marker 强制降为 light。
- light 中依赖 raw evidence 或 concept inventory 的检查必须显示 `SKIPPED_LIGHT_PACKAGE`，总 gate 只能给受限通过。
- 某个 helper 在 evidence 缺失时返回空 failures，不等于该证据路径已经验证。
- 未声明的部分工作区必须硬失败，不能自动降级为 light。

## 7. 写入副作用

### 7.1 静态扩展性 gate

`tools/check_no_company_literals.py` 会覆盖 `outputs/scalability_audit.csv`。运行后必须用 `git status --short` 检查是否产生非预期 diff。

### 7.2 Golden

full 模式会通过 G2 访问 SEC companyconcept，可能更新 `evidence/requests_log.csv` 和 raw response，并覆盖：

- `outputs/golden_results.csv`
- `outputs/golden_candidates.csv`

light 模式只做随包 snapshot integrity，不能被记录成 full Golden 重算。

### 7.3 Repair gate

阶段 12 总会先重建 implementation map 与 spec audit；full 模式还写 stub-period sidecar。FULL/LIGHT 工作区继续重建 stratified/scalability audit 与 repair validation。若工作区为 `WORKSPACE_INCOMPLETE`，它只写 repair validation 的失败行便提前返回或非零退出，不会刷新 stratified/scalability audit；此时已有文件可能是旧 snapshot，不得作为本次运行证据。它是 gate，但不是只读检查。

### 7.4 Report build

阶段 11 会先执行 bounded P0 repair，再生成 coverage、crosscheck、异常清单、审计、最终报告与 `README_RUN.md`。C04 AuditorName repair 在本地 fact/material 不足时会创建 `SecHttpClient`，请求 accession index 与 XBRL instance，并追加 `evidence/requests_log.csv`、raw response、headers/hash、accession material inventory 和 instance inventory；所以它不是保证离线的命令。内部 `run_repair_validation(exit_on_failure=False)` 不会替代独立阶段 12。

## 8. 按变更类型选择测试

| 变更类型 | 最低证据 | 追加证据 |
|---|---|---|
| 纯工作流文档 | JSON/Markdown/anchor 对齐检查、`git diff --check`、workflow 同步机械检查 | 只有文档声明引用了代码行为时，运行相关快速回归 |
| 普通 Python 逻辑 | 快速回归 | scalability gate；涉及指标/验证时再跑 Golden 与 repair gate |
| 公司、CIK、profile 或 extractor 配置 | 快速回归、第 11 家 fixture、scalability gate | 在隔离 checkout 跑受影响阶段、Golden 与 repair gate |
| parser、期间、证据或 CSV schema | 快速回归 + 受影响阶段 | 隔离 checkout 中完整场景、Golden、repair gate 与产物 diff |
| validation / report verdict | 快速回归 + Golden + repair gate | 验证失败传播与报告内容，阶段 11 后仍显式跑 12 |
| SEC HTTP 客户端或 URL | 相关本地检查；当前缺 mock HTTP 单测 | 有效身份下的 live smoke，再按影响范围跑场景 |
| 仅报告文案 | 生成器相关检查，不能手改生成报告替代代码 | 若运行阶段 11，必须随后运行阶段 12 |

纯文档变更不强制重跑联网 M0-M7；不得为了“全绿”无谓覆盖已审计的 evidence 与 outputs。

## 9. 推荐执行顺序

### 9.1 普通代码改动

1. 快速回归。
2. 静态扩展性 gate。
3. 受影响的 Golden 或阶段场景。
4. 最终 repair gate。
5. 检查 `git status`，确认生成 artifact 与预期一致。

### 9.2 数据采集、阶段 handoff 或 schema 改动

1. 创建干净、隔离的 checkout。
2. 确认有效 SEC 身份配置与目标 scope。
3. 按 `README_RUN.md` 执行完整阶段。
4. 显式执行阶段 12。
5. 核对 metrics/evidence/coverage/report、请求日志与 artifact diff。

### 9.3 纯工作流文档同步

1. 验证 `capability_contract.json` 是 UTF-8 合法 JSON。
2. 递归检查 `anchor_id` 唯一，Markdown 引用存在，非空 `test_anchor` 的路径和符号真实。
3. 运行与所引用行为相关的快速回归。
4. 运行固定上游对应的 workflow docs 机械检查。
5. 记录机械检查只证明最终文件状态，不证明分析、审计或测试历史。

## 10. 失败定位

- unittest：从失败 test method 回到对应 helper 与 fixture；不要用改 expected 的方式消除真实回归。
- Golden：查看 `outputs/golden_results.csv` 的 expected、actual、evidence path 与 notes。
- Repair：查看 `outputs/repair_validation_results.csv` 的 `check_id`、status 与 details。
- 指标/证据不一致：按 `(company, metric_id)` join `metrics_matrix.csv` 与 `metric_evidence.csv`。
- coverage：核对 `coverage_matrix.csv` 的 status、has_evidence、needs_review 与 reason。
- live 请求：核对 `evidence/requests_log.csv` 的 URL、status、User-Agent、retry_attempt 与 error。
- light 包：先确认 marker 与缺失材料，禁止把 skipped 当 PASS。

## 11. 新增或修改测试

- 行为性 Bug 必须先有可复现的最小回归。
- 只有跨阶段累计状态、阶段间 artifact 或固定顺序才能暴露的问题，必须增加 scenario 级回归；单 helper 测试不能替代。
- 测试新增或职责改变时更新本文件的覆盖与 fixture 简介。
- 不为薄 wrapper 重复写同构测试，不用正则统计源码中的指标/检查数量，不自动测试教学文案风格。

## 12. 已知高价值缺口

- 尚无 capability contract 与 Markdown 引用的持久化 alignment 测试。
- `validation_package_mode()` 的 `FULL_VALIDATION` shape 缺少临时工作区单元测试。
- 尚无 `sec_http.py` 的 mock HTTP 单测覆盖 User-Agent、域名限制、retry/backoff、日志和 raw response 落盘。
- 尚无使用录制 SEC fixture、临时工作区贯穿 M0-M7 artifact 契约的离线 scenario test。
- 最低支持 Python 版本未冻结。
- 个别 full-evidence helper 在文件缺失时应 FAIL、SKIP 还是保持当前空 failure 行为，尚未统一。
