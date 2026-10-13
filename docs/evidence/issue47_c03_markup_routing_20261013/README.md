# C03 路径探测不执行完整属性校验

回应 [PR233 原审查意见](https://github.com/wlvh/SEC_metrics/pull/233#discussion_r4254266255) 与[接收者复核](https://github.com/wlvh/SEC_metrics/pull/233#discussion_r4254288854)。PR233 已按原范围合入 main `731f8fd1`；本批只修其接收记录明确保留的后继问题，不改已接收候选或重跑50格普查。

构造普通代理有两个相同 ID 的无关 `xbrli:unit`，实际 native parser 仍报告 no contexts。旧历史路由继续调用完整 `_FactAttributes`，因此在进入 SCT 前改报 `GOVERNANCE_DUPLICATE_OR_NESTED_UNIT`；原失败见 [before.log](before.log)。此构造只验证路由控制，不冒充真实薪酬结论。

改动只在 `historical_compensation_case` 的 markup detector：直接使用标准 HTMLParser，沿现有 QName 与 void-tag 定义识别实际 inline URI、裸 ix 元素或 contextRef 属性。仅保存元素的 namespace 作用域；无命名空间变化的嵌套共用同一映射，不建立事实、unit、measure 清单或执行金额校验。命中后只保布尔值，不让后续无关标记覆盖原生错误。完整 ECD/SCT 解析、单位/人员/期间、首次代理选择及公共 controller/store/renderer 不改。

保留原五种损坏 structured 表示拒绝 SCT；新增重复 unit 普通代理实际通过路由、无关深嵌套、前缀遮蔽与退出作用域、带重复 unit 的实际 inline 标记反例。注释、script和转义样例不成为事实。损坏 structured 文件仍不能借普通表格变成成功；真实 SCT 多人拒绝、单位/期间和表格范围判断仍由原共享读取器执行。

实际本地：57项现有及新增选择/共享SCT/名称/公司分派测试，0.369秒，零失败、错误、跳过，见 [after.log](after.log)。命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_historical_compensation_case tests.vnext.test_proxy_compensation_source \
  tests.vnext.test_organization_name_core tests.vnext.test_history_company_dispatch
```

三个已核对原件只重验本次改变的路径识别及 body/header 哈希：[sources.json](sources.json)。Macy's FY2021=false/0.156s、Marriott FY2021=false/0.095s、Marriott FY2022=true/0.053s，与 PR233 原资格一致。原薪酬值/多人拒绝、首次长计算与独立读取沿 [PR233 主要记录](../issue47_c03_prefix_boundary_20261013/README.md) 复用；本批没有新财报计算、新保存/读取身份或复跑信用。不重读全部原表，不重复全部五年，不将微小耗时差异写成整体性能改善。

当前既有 company-current-records 工作流 paths 包含 test_historical_compensation_case.py，company-history 步骤直接执行该模块。未修改工作流、公共runner或清单；新 head 远端实际执行另核。接收方亲自复核后继与解决旧审查线程，作者不代为给出接收结论。

正常接入实际 main731f 后，仅重跑受影响的同一57项组合，0.375秒、零失败/错误/跳过，见 [main-combination.log](main-combination.log)。生产修补字节与前次相同，未重财报；base main已含233以及此前230/232，不再堆叠未接收消费者。

新增真实 SEC/provider/model 调用均0；原件、账本、原答、失败和旧Run/结果不改。现有处理依赖已登记历史case本文件，所以正常检查会为相关新代码版本重新处理一次；不能拿旧记录可读声称新配置已经从头计算。完整1950位置、在线历史来源接续及其余C03真实缺口继续。
