# 新公共按指标路由：限定独立审阅

结论：PASS（仅限本次新增接口与短回归）；未发现需要修复的缺陷。该结论不是整个 PR67/74、实际混合历史财报、全业务验收或生产批准。

## 精确输入与覆盖

- 代码根：`/Users/lyuhongwang/.codex/worktrees/issue28-metric-routing/SEC_metrics`。
- 补丁：`35c3626839f70abac63928f243ff42d2e0d0a6ee` → `5a0352d1fa2ca19c66f99de6c2338fe7a07c1b92`；开始和结束检查 HEAD 均为后者。
- 只审 `scripts/vnext/company_current_records.py` 新参数/校验/透传，`tests/vnext/test_company_current_records.py::PerMetricProducerTest` 和本增量 README。
- 为核对接收接口，读取了原控制器的参数/输入身份/复用分支；没有对控制器、store 或 B03 既有业务实现进行新一轮全面审阅。精确 SHA 对比确认 `ordinary_current_update.py`、`ordinary_saved_result.py` 无差异。未扩到 architecture/interact 的变更。

## 核对结果

1. 第 83–92 行先校验 factory 字典必须正好覆盖本次选中且原来支持的指标；缺失、多余、不可调用、与单 factory 混用均拒绝。声明文件字典须为 dict、键属于已选指标、值为 tuple/list，且不能和非空旧全局文件集合并用。这些校验先于 work/output 创建。
2. 第 119–124 行直接选取原 callable 和原 tuple/list，不生成统一 dispatch、不合并其他指标的文件集合。两个参数均为 None 时，原单 callable/tuple 分支保持原对象。声明文件映射是可选的：遗漏某个指标等于该指标没有额外声明文件 `()`；不声称缺项文件映射也必然拒绝。各 factory 的业务适用性与声明文件完整性仍由原 producer/store 和接入方承担，本接口没有证明这些业务事实。
3. 指定短套件 24 项全部通过（0.177s）：每指标透传、旧对象 identity、映射拒绝、真实旧控制器对 B03→B03+B10→同组合的重入均通过。真实控制器实验的来源/配置/计算保存/读取边界使用合成对象，计数 1/1；不赋财报数值信用。
4. 独立补充 7 类错误映射，在已有合成 work/output 后重试：全部于进入 controller 前拒绝，文件路径与 SHA256 全部不变。另检查 FY2024/FY2025 的每指标 callable、非空 tuple 原对象精确透传；D04/E01 仍不进入 controller。
5. 将旧控制器重入实验补充为非空原 B03 文件 tuple 与 B10 独立文件 tuple，仍保持 producer 计数 1/1、后续 NO_SOURCE_CONTENT_CHANGE。新增指标自身的声明文件没有造成旧 B03 重算。
6. 公司登记、年数/年份边界、原支持集合、当前/历史 controller 根、保存坐标和旧任务限制均未改动。原 CurrentCompanyTest 中期间范围、公司/来源绑定、坐标错误、已支持范围、独立读取与其他指标保留的回归全部通过。

## 重现与限制

运行命令：

```sh
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools /private/tmp/issue28-company-c02-venv-20261006/bin/python -m unittest -v tests.vnext.test_company_current_records.PerMetricProducerTest tests.vnext.test_company_current_records.CurrentCompanyTest
```

- 本方证据：`tests.log`、`edge-checks.log`、`review.log`。
- 未机械重跑父方 29 项全模块证据；未运行长材料、真实混合历史 producer、业务请求、模型或在线获取。
- 本次未写代码/测试实现、commit/push、对方文件或来源原件；只写本 independent 目录的审阅结论与日志。没有嵌套 agent。
- 未覆盖的实际来源、期间、数值、CSV 和跨进程重复 factory 为接收方接入验收；本审阅不将其视为通过。
