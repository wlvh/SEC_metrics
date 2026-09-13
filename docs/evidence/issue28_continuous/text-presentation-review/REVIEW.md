# 独立只读复核：普通文本投影与统一 CLI

受审文件及始末哈希见 result.json。本轮未修改任何仓库文件，未安装新输入，未创建或冻结 Run，provider/paid/SEC=0/0/0。

## 发现

新增 material 测试 tests/vnext/test_normal_text_projection_v2.py 第 27 行断言 ValueError；实际 OPEN 进入 frozen API 由 run_store.py 第 129、3669 行的 RunStoreError(RuntimeError) 拒绝。因此测试将 ERROR，尚不能到后续 OPEN preview/FROZEN 断言。应该匹配 RunStoreError 并验证 `Replay requires a FROZEN Run`。首次复现完整 traceback 保存在 review.log。已通知 root，由 root 修复；未改测试或生产代码。

没有发现本次限定面上的实际错误接受或日期/原文展示错误。

## 实际核对

1. Marriott C02：DEF 14A，2026-03-27，PROXY，29 条；年度归组仍是 FY2025，context 明示不推断董事会测量日。
2. Paramount C02：10-K/A，2026-04-24，TEXT，12 条；没有冒称 DEF 14A；年度归组保留 FY2025。
3. JPM D02：10-K，2026-02-13，34 条；结果和每条 evidence_quote 等于原生 text_payload，并逐项核对完整原件摘要、原文字节区间摘要、该区间解码后的原文及公开 context 字节定位。三例合计 75 条，20/18 列 CSV 往返不丢字段或文字。
4. 三个真实 OPEN Run 调用公开 frozen API 均以 RunStoreError 拒绝，未改变状态。纯展示回执仍标明 run_status=OPEN。
5. 既有 Salesforce C04 无 Observation、WITHHELD、NORMAL_INPUT_SOURCE_ACCESS_FAILED 记录可纯渲染成空值 WITHHELD 行，保留具体原因和 23 份来源范围，Evidence 为空。
6. CLI 仅做受控依赖替换的路由测试，安装器与 Run producer 都是 mock：selection=None 的 C02 不进入执行失败，文本 frozen renderer 被调用并输出两 CSV；C04 WITHHELD 仍调用数值 renderer 并输出行，退出码 2 与 COMPLETED_WITH_GAPS 保留。要求 freeze=True 的调用参数已核对。TEST_ONLY_mocked_cli_* 目录仅是路由测试产物，不是安装/执行/冻结证据。

## 边界

前三项使用 fb76 既有 OPEN 原始记录调用私有纯展示函数并直接核对原件字节，不等于当前漂移中 V13 的 source replay、FROZEN 验收或业务政策采纳。未运行会 install/freeze 的 material 测试全类。数值 frozen API 的完整验证仍待 root 稳定 V13 后继续。

Root 已通知将异常断言改为 assertRaisesRegex(RunStoreError, requires a FROZEN Run)；生产实现未变。当前规则仍未冻结，完整 material 测试未运行。本报告保留首次 harness 失败，不把仅修改断言视作完成整类验证。
