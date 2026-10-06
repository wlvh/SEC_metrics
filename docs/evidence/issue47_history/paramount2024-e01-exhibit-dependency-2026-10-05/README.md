# Paramount FY2024 E01：一个具体的附件来源缺口

原请求中 `0000813828-24-000018#8.01@2224` 的正文只写April29,2024发布并全文引用附件99的新闻稿，没有主题。原候选/合同/扣留不改。已从认证导出读完整个主文件 `para-20240429.htm`（30759字节，SHA `04c3af26f90298c45c7430014fe6b8b4e19e4e7690b3485e52d34f9e1889fbf0`）；实质条目只有8.01和9.01，附件清单也只给日期/类型，没有足以按本条正文判断并购的新增信息。

原HTML唯一href为 `ex-99.htm`，原标签字节跨度及SHA已固定，对应官方URL为 `https://www.sec.gov/Archives/edgar/data/813828/000081382824000018/ex-99.htm`。整本已恢复ledger没有此URL获取行，附件未取得、未阅读，不能从日期或新闻记忆猜主题。账本总历史row_count不是本次批准消费；本次仍按原1771/1867及未获resume的余96解释。

具体待审对象在owner-review-plan.json：最多一次GET、retry0、新模型/Run/接受0；假设只花这一次，批准累计才从1771变1772。这个假设不是许可。本计划不新建空账本、不批准重绑原ledger根，也未实现新的获取接线。所有者还需明确后继输入如何纳入实际引用的附件；现合同只能按每条本身文字确认，不能把新附件或新回答补绑旧问题/原Run。取得附件之后仍需新的必要参考、固定请求和方法验证，未自动授予新模型调用。

七成员归档核字节/SHA并安全解包，原请求二进制哈希、父原件及href跨度重验通过。没有读取或裁剪旧模型答案；所有原导出、原参考、失败和扣留仍保留。新增DeepSeek/paid/SEC `[0,0,0]`，新Run/接受0。

后续同一生产planner的真实离线探针已完成：恢复来源、years5、socket禁止，返回 `HISTORICAL_URL_IS_NOT_A_DECLARED_DEPENDENCY`，186.116秒。执行文件与当前历史获取代码SHA相同。现有capture会在同一声明检查后才进入许可/累计账本和传输，因此官方URL加resume仍不足，必须显式接入附件依赖声明及后继输入，而不是任意URL捕获或把它伪装成既有主文件。此结果不增加模型/SEC调用或改变原扣留。


2026-10-06：所有者已在本会话批准附件范围及最多一次SEC GET恢复。8cf2bc9e新增仅后继输入的明确附件声明：实际认证原父文档SHA、原178字节链接跨度和同accession官方URL，正常historical_dependency现已返回该附件；独立无网络实际读取通过（approved-actual-dependency.json），四项内存负例通过。仍未获取附件，累计SEC1771/1867不变。原固定包、请求、答案和Run不改签。原/root物理路径在macOS不可用；同一本完整账本的已验证位置恢复、1771→最多1772的目标限定、原链及发布resume标记接线尚待完成，不创建空账本或借用其他额度。

2026-10-06按完整简化指令重新核本机：没有相关SEC执行进程、claims/binding打开句柄或待完成reservation；原账本1547个调用槽，最后1546/1547终态均SUCCEEDED，claims SHA仍为`a238db91ca5f112ca7535f3da719999fa4b8dca5cfe6b3c911dc9755aa291262`，计入224保守预留后累计1771。无1548槽，来源账本无指定EX-99 URL。恢复标记[6017015367](https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-6017015367)只表示已登记这次具体恢复，不表示HTTP已发生。实际CLI拒绝已保存为`capture-preclaim-refusal-20261006.json`：新增调用[0,0,0]，在HTTP前因`ISSUE_47_REQUEST_OUTSIDE_EVERY_GRANT:paramount_skydance_paramount_global:FISCAL_EVENT_FILING:2024-12-31`停止。该次许可仍未消费；不重发、不扩大用途、不改原运行机制，不创建空账本。此次核查未发现远端UNKNOWN或在途持久写入，附件获取/后继内容核对仍列H6，其他离线工作继续。
