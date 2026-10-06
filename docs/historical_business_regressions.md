# H2：历史业务边界的短反例

本项供 [#28 T1 公共测试分层](https://github.com/wlvh/SEC_metrics/issues/28#run-test-simplification)消费，不新增历史 runner 或修改 CI。[#47 H2](https://github.com/wlvh/SEC_metrics/issues/47#history-simplification-20261006)继续复用 PR58 的真实 D02 回答、PR59 的酒店表格与最小 DEI 样例；本小 PR补银行范围和主体/事件/计算边界。

`tests.vnext.test_history_business_boundaries`直接调用现有公共函数：

- JPM 样例来自保存 FY2025 原件的两段完整文字，共 2847 字节夹具，附原件路径和字节跨度。AUM 的客户排除、子集限定、总客户资产替代 AUM、相互矛盾的业务分部均不能证明所需范围；单个正确术语表也不能证明全公司 AUM，仍需经理分部、客户群和完整表格组成。
- Paramount 注册前身/继任关系不授权合并财务报表。事件回看窗口从 2024-01-01 到 2025-12-31，与继任的 146 天财务期间分开；错角色及未知连续性明确失败。
- 构造金额 `100`只验证现有 B01 计算的期间/主体/单位边界，不是假定任何公司的实际收入。146 天返回 `NOT_MEANINGFUL`/null并保留输入，前身金额不能填继任结果，53 周保留真实日期；B01现有`preserve_reported`政策下EUR不改标成USD。

主要验证：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_history_business_boundaries -v`，15项通过，测试执行0.005秒；含解释器启动的本机命令1.79秒（同时有定向来源测试）。按类读取小夹具/配置、编译一次指标定义，不安装公司、不拷来源树、不生成Run或启逐例进程。

同一JPM客户排除边界仍保留完整来源集成：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:. python3 -m unittest tests.vnext.test_financial_balance_scope.AumClientFastTest.test_excluding_clients -v`实际通过，9.249秒。完整原件证实排除客户后不能给全公司范围；短例覆盖其中的原文和关系判断，不替代整个完整来源检查。两层均重新执行，没有缓存旧绿灯。

真实模型正反例继续在PR58同一必要夹具维护：8份原失败/14条过长原文及4份原合同通过回答，均不重发。合同通过不能接受法律语义、遗漏或完整指标，Marriott自保遗漏等原缺陷保留。没有以旧结果全对作为测试预期。

本项尚未入main，只提供消费者反例；公共runner/CI由#28接收。新增模型/SEC调用为0，未修改费用、发布许可、原Run或原失败；既有两年B01和已落地四份补丁不重做。
