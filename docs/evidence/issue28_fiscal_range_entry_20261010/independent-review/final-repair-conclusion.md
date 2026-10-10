最终限定回修复核通过：41ac1a5daeb95b1ccba605efb7004b18a315d885 → 6f5cb7e42f641b9be7bd1bddeb619c04ed3f728a 直接修复了上一轮的 P2 误拒，未在本次限定正反例中发现新的误收或误拒。原 conclusion.md、repair-conclusion.md 及其失败反例/日志均保留；这份结论只关闭原问题及该作用域回修，不重审完整功能或一般语言边界。

静态差异核对：标签模块现在对照原记录 kind 和 mapping，定位该条映射在同一块中的匹配位置，只用映射立即前缀的同一句文字检查条件/假设限定，不再把同段另一独立句的标记施加给全部定义。company_fiscal_range.py 的不可变年份快照没有再次变化。修后模块与 peer 0c6cd6c53f555851f8e0f7e526c2d96f54d44df9 逐字节一致，assertion-local-tested-tree.json 四项源码/测试 SHA 全部匹配当前修后字节。该旧收据仍是 uncommitted_at_test=true；本次亲跑由当前精确 SHA 承担，不改写原运行身份。

亲跑直接反例：两句 “A hypothetical example of an expense calculation follows.” 和 “If the lending covenant changes, our naming convention remains unaffected.” 分别置于无条件有效 mapping 前/后，四项实际 public-range discovery 均返回 FISCAL_RANGE_RESOLVED、all_source_bytes_available=true、FY2026；没有执行指标。原明确条件句、普通引号假设句、附52 weeks的 ordered 条件句又亲跑三项实际 discovery，均保持 FISCAL_RANGE_UNRESOLVED/source unavailable，不恢复错误财年信用。七项 probe 的逐项输入/结果附在 final-repair-tests.log 末尾。

授权四模块命令亲跑 exit0、55次执行、55个 distinct IDs、0 failure/error/skip、2.048s。新 public-range test 包含上述4个 subtests；原三项失败边界、合法 quoted-label 正例、年份 append/reorder 保护和重复 fixture 修正继续通过。assertion-local-repair-tests.log 只作为既有对方日志读取，独立亲跑完整日志在 final-repair-tests.log。

本次没有重跑真实公司/长材料，没有 Calculator、SEC、provider 或其它业务调用，没有网络、commit/push/spawn、产品/测试修改或 #47 写入。持久追加仅 final-repair-conclusion.md 与 final-repair-tests.log。未覆盖的完整业务验收、Macy FY2022/收入口径、PR119/120修复、全39指标、远端CI、正式采纳与生产范围沿前两份结论保持；此次通过不升级这些信用，不授全PR或模型准确性。

本轮实际时间：2026-10-10T07:58:57+08:00 至 2026-10-10T08:00:02+08:00。累计起止：2026-10-10T07:44:28+08:00 至 2026-10-10T08:00:02+08:00。本轮7次工具（functions.exec外层2、exec_command4、write_stdin1）；累计54次（外层20、exec_command31、write_stdin3），未重置。累计普通消息3次，只有三份最终报告，没有问题或进度消息，已用完本委托的普通消息额度；低于80工具/90分钟硬限。
