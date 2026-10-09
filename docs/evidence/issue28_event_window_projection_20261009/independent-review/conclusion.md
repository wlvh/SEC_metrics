# 指定补丁限定独审结论

结论：限定范围内通过，未发现需阻断此补丁的正确性问题。仅评价期间展示修复与新增测试接线，不授合并、业务正式采纳、生产、来源获取或模型调用权限。

- Base：`4118efdc77cebdc918cf9cface9584168bcbf071`。
- Patch / 实際 HEAD：`e2ca7c8f1101ccf915cd9a7887d93b0101e18109`。
- 开始：2026-10-09T09:27:15Z；结束：2026-10-09T09:31:59Z（UTC）。
- 工具计数：27，包含8次 functions.exec 包装与19次嵌套 exec_command；普通消息3条（含最终），问题0条。低于80工具调用、90分钟与3条普通消息上限。

## 实际检查

检查 `scripts/vnext/ordinary_projection.py` 的 `_registered_event_period` 与 `render_ordinary_records` 期间例外、`tests/vnext/test_registered_event_projection.py`，以及 company-current-records workflow 和 fast selector 新接线。先读取实时 Issue #28，采用2026-10-06可信内部工具前提；没有恢复独立信任库、批准防伪或递归证明链。

新例外只对 C01/E02/E03/E04/E05 且有显式 registered_event_scope 的输入有效。窗口由现有 catalog 的 successor_predecessor 规则再次派生，原 annual 报告期间不修改。财务指标及 E01 返回无例外；缺 scope 同样无例外。公司、主注册人CIK、successor policy、完整注册CIK列表、annual/manifest/result窗口、源库存归属与每个源集合窗口均需一致。历史库存分片可归属于同一CIK，其他CIK的分片仍被拒绝。

保存入口的公司/记录、已安装Spec、单位、结果期间、Trace目标以及实际来源检查原代码保持；本补丁只扩展已证明事件窗口的展示期间条件。来源完整性、事件匹配和业务计算仍属生产者责任，本 helper 不替代这些职责。

`selected_event_source_v1.py` 与 `normal_zero_ai_results.py` 的 base/patch Git blob 完全相同。仅确认输入合同与未改字节，没有重新评审其实现。父真实保存测试的 `70cd4a7803cf727bf9469616cca889e40a1dead7` 与当前 patch 的生产renderer及新增测试字节相同；之后差异只有workflow/selector接线。

## 独审实际执行

1. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_registered_event_projection`：5项，0.005s，失败/错误/skip均0，见 `required-tests.log`。
2. `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_precalculated_case`：9项，2.925s，失败/错误/skip均0，见 `adjacent-tests.log`。检查真实小B01保存/读取以及错期间、错Spec、错主体、错财年标签与共享资料损坏的保存失败。
3. 按workflow实际入口且去除额外PYTHONPATH：`env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_selected_event_source_v1 tests.vnext.test_registered_event_projection`：13项，0.102s，失败/错误/skip均0，见 `workflow-entry.log`。其中已审来源8项只作为新接线命令验证。
4. 28个有界小探针，见 `small-counterexamples.log`：5指标×直接/嵌套component共10个正例、1个同CIK历史分片正例、16个明确拒绝反例、1个缺scope不给例外。反例涵盖错公司、前身当主注册人、错主体模式、错manifest坐标、错结果起止、缺CIK、错per-CIK行、缺/错公司库存引用、缺/错公司/错库存源集合、另一CIK历史分片。使用仓库既有小fixture，不构造业务成功或真实材料信用。

合计27次 unittest 测试执行，22个不同测试（新5项重复执行一次），另28个小探针。fast selector AST确认恰有一次 FAST_TESTS 新登记，无 source/retired 重复登记。未运行长测试、全仓CI或真实事件链。

## 父执行证据的边界

读取 README、saved-wide-window.json/.log、related-tests.log 与 driver-first失败日志，未重跑真实来源提取、原生长链或历史消费者。

父证据记录相同C01 case在原renderer被 `ORDINARY_PROJECTION_PREPARED_PERIOD_CHANGED` 拒绝，新renderer保存并独立读回原 Result ID / 12 count；实际事件窗2024-01-01至2025-12-31，annual容器仍为2025-01-01至2025-12-31；35份事件申报、75份来源检查、CSV存在。第一次driver失败来自对错误模块patch render函数，README与失败日志如实保留；后次复用已保存case，准备时间为空，不把前次失败当终态成功。

这些是真实保存/公共接口父执行证据，独审仅核读与确认相关字节一致。49项related-tests是父执行记录，不计入独审实跑。未独立复核12个Item 5.02原件内容、未验证E02—E05真实材料，也未验证#47公司CLI重入/完整历史/390统一接受或远端CI；均按委托留在其原责任边界。

## 写入与副作用

仅在本 independent-review 目录写 conclusion.md 和5份日志。无源码修改、commit、push、子代理、tar/MANIFEST、真实SEC/provider调用或账户操作；未触碰#47工作树、真实来源/账本/状态。`review-metadata.log`保存精确字节及范围核对。
