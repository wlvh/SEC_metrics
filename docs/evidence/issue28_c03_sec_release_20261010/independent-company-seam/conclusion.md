# C03 公司接缝限定独审：增量未发现阻断，完整成功接缝尚未覆盖

精确范围：`8f1250bf7252720d422f8fcdc43c85d431b40dfc → 32c730bf62d7272978306a633c4a0a7f663ffa0a`。工作目录：`/Users/lyuhongwang/.codex/worktrees/issue28-c03-release/SEC_metrics`。只审 `EXPLICIT_CASE_METRICS` 新增 C03、`_selected_proxy_display` 及 renderer 调用、新公司接缝测试、workflow C03 步骤新增模块。此前已通过的通用 PeoMember 修复与初始模块没有重审。

结论：本次差异在显式年度入口限制、所选 proxy 显示约束和旧路径保持方面未发现新的阻断问题。该结论有明确范围：新测试实际证明控制器可以进入显式 factory 并保存/读取它的失败，且证明 metadata helper 的正反例；它没有证明 C03 真实成功结果已通过完整公司保存、指针、CSV、冷读和复用链。本次不得据此登记完整 C03 公司成功。

## 已确认的入口与显示行为

C03 只加入 `EXPLICIT_CASE_METRICS`，没有加入 `SAVED_METRIC_IDS`。新增测试实际执行默认公司入口与未选年度的直接更新入口，分别返回 `PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED`、拒绝 `CURRENT_UPDATE_METRIC_UNSUPPORTED`。默认计算器被设置为失败控制，未被调用。

显式年度 2022 与 C03 factory 组合确实进入实际年度控制器，factory 接收 metric_id=C03、fiscal_year=2022；其人为失败被保存为 `INPUT_OR_EXECUTION_FAILED`，公司读取继续保留同一失败原因及 null，没有 current-result.json。本次独立补充“有 factory 无年度”和“有年度无 factory”两个公司入口控制，均以 `COMPANY_CURRENT_SELECTED_YEARS_REQUIRE_CASE_FACTORY` 拒绝。以上为入口与失败可读性证据，不是业务成功。

所选显示必须为 C03 的 DEF 14A；accession/form/filingDate 必须匹配 input_binding 内的 filing identity，且同一发行人的 SEC URL、accession、primaryDocument 与 governance_proxy reference 必须精确匹配，匹配项只能有一个；已有 evidence 的 accession 必须均为所选 proxy。`render_ordinary_records` 在完成原 evidence 与年度元数据处理后调用 helper，返回时只更新公共行的 form/filed_date/accession，没有改写 annual 或原计算记录。

独立执行 helper 的“同 proxy 数值 evidence”与“无 evidence 的 withheld 显示”两项正例，均返回 DEF 14A/2023-03-23/所选 accession；case 和 annual 完整输入保持一致。另执行11项负例，错误指标/表单/缺失文档字段、日期未绑定/缺少元数据、外国公司 reference、外国 CIK URL、错误文档/role、重复 primary reference、跨 proxy accession evidence，全部拒绝。见 `seam-controls.log`。这些正例仍是 helper 级验证，未声称形成了实际 valued 或 withheld 公司 Result。

旧 case 没有 selected_proxy 或其值为 None 时直接返回 None，独立验证不会访问缺失的 annual/input_binding/references。renderer 在该条件下只增加一个无结果的检查；指定回归中的既有公司、年度及报告主体路径全部通过。本增量未修改原年度选择、C03 数值 resolver 或原 evidence 计算。

## 未覆盖的具体成功接缝

新增测试的显式 factory 有意在产生 C03 case 之前抛出失败。因此目前本审阅没有下列完整运行证据：真实 C03 producer 返回原生 case/records → create_saved_result → `render_ordinary_records` 同时通过年度主体/期间/trace/source 验证 → selected_proxy 公共行覆盖 → 公司保存与 CSV → 独立只读冷读/再次运行复用。尤其是 valued 与 withheld 两类完整公司结果，这条链均不能由 helper 的两组 evidence 参数推定成功。

在该精确差异之外，producer 原件选择与业务结果、公司材料信用和真实来源验收不是本次范围。本次不要求重审未变模块；交付者应将已有的独立实际保存/读取证据与本限定结论分别登记，不能用94项测试数量代替缺少的 C03 完整接缝结果。

## 指定测试与执行字节

实际执行命令：

```sh
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_c03_company_seam tests.vnext.test_c03_sec_release tests.vnext.test_governance_signals tests.vnext.test_xbrl_namespace_policy tests.vnext.test_company_current_records tests.vnext.test_ordinary_current_update.SelectedPeriodUpdateTest tests.vnext.test_reporting_company_projection.ReportingCompanyProjectionTest
```

Python 3.14.7；94 tests，0 failures、0 errors、0 skips，8.807s，exit 0。完整结果见 `required-unittests.log`。workflow 的 C03 步骤确实加入新模块；未查询 GitHub CI 或授予远端 CI 信用。

开始与最终的四个允许审阅文件均与指定 head 精确字节一致：

- `scripts/vnext/ordinary_saved_result.py`：c1f9641a796d1d7ca1aba4c817cb157b10f7f2c6c62d75991bcd8fd8d65fa90e
- `scripts/vnext/ordinary_projection.py`：e665ed34cd7e1ee4c63452d39dd227cd96a65f02547bacdabefd8423b7678ae8
- `tests/vnext/test_c03_company_seam.py`：933d8f993955a91773ebac97d74713841eecd2fb6d45b511cac3dc2269d287ba
- `.github/workflows/vnext-fast.yml`：c8bfa9de87e3f51e14e43587a9451abeeff28275f1a52a46b48484929cc63047

## 累计边界与实际量

此前阶段首次 UTC：2026-10-10 12:11:30 UTC；工具18次、普通消息2条。
本阶段记录恢复 UTC：2026-10-10 12:30:14 UTC。
本阶段结束 UTC：2026-10-10 12:33:46 UTC。
本阶段工具：6次 functions.exec、14次嵌套调用（13次 exec_command、1次 write_stdin），保守相加20次。累计12次 functions.exec、26次嵌套工具，合计38次，低于80次上限。累计普通消息3条，含本阶段唯一最终报告；未发进展或问题。累计经过时间仍低于90分钟。

仅在 `independent-company-seam/` 写 conclusion.md 和两份日志。未改源码/测试/其他仓库文件，未网络、真实调用、spawn、commit/push、打包或查询 #47 目录/状态。指定短测试使用自身临时工作区；本次没有另外重读真实大原件或启动长测试。未触发硬上限停止；未覆盖项已明确列出，不能借用先前 PeoMember PASS 扩大接缝覆盖。
