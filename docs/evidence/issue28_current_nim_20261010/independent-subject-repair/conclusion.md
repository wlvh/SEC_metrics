# 公司登记修补的限定增量独审

结论：指定登记修补在本次限定范围内通过；没有发现新的可操作问题。旧 P2 的 Macy's 公司名配 JPM CIK/role 的登记反例，在进入选源、公司类型判断或 N_A 计算之前被拒绝。这个结论仅覆盖登记检查的新增差异，不是整个当前 HEAD、完整 NIM 路线或生产采纳的通过结论。

## 本次身份和范围

- Base：`323eabf155376ae14bc130635fd86f77fb75d9d1`。
- 指定 Patch：`a541a5b606379a478198a4d41190fd5088db52f9`。
- 实际工作树 HEAD：`8f28e09e7bc09527420d0430fb420ade3bafab1b`。
- 目标源码和测试在审阅开始、结束时均逐字节等于指定 Patch 的对应文件；当前 HEAD 相对该 Patch 的两个目标文件差异为空。摘要及指定差异见 `scope.log`，结束复核见 `final-verification.log`。
- 只审 `scripts/vnext/financial_results.py:60` 的 `_current_company_registration`（新增 12 行）及 `resolve_ordinary_financial_metric` 第 227–228 行调用点，共 14 行源码增量；测试范围为 `tests/vnext/test_current_nim_company.py:25`、第 41 行两个新增登记方法。
- 只追读登记 CSV 加载器、必要的调用顺序和当前合同测试。继承 `independent-review/conclusion.md` 与 `subject-negative.log` 中的原 P2 事实，未改旧记录，未把其旧 SHA 审阅视为新 SHA 通过。

## 为什么旧 P2 在该入口被阻断

`ordinary_records=True` 先从来源根与安装根分别读取同一 `company_id` 的登记，要求各恰好一条，然后核对 `primary_cik`、`related_ciks`、`roles`、`industry_profile`、`entity_continuity_status` 五个业务字段。登记缺失或不同直接失败，位置早于 `_installed_rule`、`_ordinary_sources`、安装公司类型读取和 Calculator。公司身份不能再从来源根选银行 CIK，同时用另一家安装公司的类型输出 N_A。重复 `company_id` 由既有 CSV 加载器先行拒绝。

比较只针对当前公司的这些业务字段。显示名、CSV 行顺序、无关公司的变化和仅保留该公司一行的来源登记，不要求整个 CSV 逐字节一致。当前字段比较使用已安装登记的原始字符串值；本次正向控制的业务字段均与安装登记一致，没有把不同业务登记自动当作同一含义。

`ordinary_records=False` 或省略该参数不进入新增检查，仍将原来源根交给旧 `_installed_rule`。本次没有修改或重新判断旧 NIM 公式、实际期间、银行解析及公司长链。

## 本次实际验证

必要命令见 `required-tests.log`：

```text
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 python3 tests/required_unittests.py tests.vnext.test_current_nim_company.CurrentNIMContractTest
```

实际 return code 0；4 项测试通过，failures/errors/skipped 均为 0；unittest 0.052 秒，命令含进程开销 0.574058 秒。仅运行指定合同类，没有运行同文件的完整年报集成类。

另用临时小 CSV 和隔离调用完成 17 个独立控制，全部通过，详见 `isolated-controls.log`：

- 11 个负向控制：原 P2 的 CIK/role 联合错误；独立 CIK、role、related CIK、行业、主体连续性错误；缺少所选公司、未知公司、改错 company_id、重复 company_id、缺失 roles 字段。均在选源前拒绝；未触发 N_A Calculator。前六项同时观察到安装规则、选源、公司类型及 N_A Calculator 调用数全为 0。
- 4 个正向控制：合法原登记、仅显示名不同、单公司 CSV、无关公司变化并重新排列行。真实新增检查及安装规则检查通过后，进入隔离的选源观察点；没有读取年报或伪称产生了真实公司结果。
- 2 个旧默认控制：省略 `ordinary_records` 和显式 False。新增登记检查调用数为 0，旧安装规则收到原来源根，符合原默认分支。

## 未覆盖责任和授权边界

本次没有重跑原完整 writer/reader/controller 成功保存、失败保留旧结果、完整来源材料、公司 CLI、十公司、全 fast/source CI 或真实模型验收。那些机制的旧审阅保持其原 SHA、原含义；不得把本次隔离控制扩大成当前 HEAD 的完整端到端证明。完整保存结果及不中断旧成功的当前提交回归、必要接线与最终业务验收仍由主任务承担。

没有 Ready、合并、正式采纳、部署、active 切换或 390 坐标完成结论。未修改源码、测试、旧证据，未 commit/push、spawn、联网、模型/SEC 调用、tar、触碰 #47 或账本。唯一持久输出为本目录的一个 `conclusion.md` 和实际日志。

审阅开始 UTC：2026-10-10T05:57:29.728606+00:00；结束复核 UTC：2026-10-10T06:00:29.416640+00:00；截至结论写入用时：179.688 秒。工具节点共 10（5 次 functions.exec wrapper + 5 次 exec_command），低于 20 节点硬上限；普通消息仅最终报告 1 条，低于 2 条硬上限。
