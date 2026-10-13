# 限定独立审阅结论

结论：需要修复一项 P2 业务主体问题，当前补丁不作限定通过。指定的 50 项测试全部通过，但一个独立的来源登记反例能把银行原件保存为另一家非金融公司的结构不适用结果。

- Base: `f6ef7886d6630f7675c25cd42e306c373ab05769`
- Patch / actual reviewed HEAD: `323eabf155376ae14bc130635fd86f77fb75d9d1`
- 差异范围：`financial_results.py`、`ordinary_saved_result.py`、`ordinary_current_update.py`、两份指定测试、company-current-records workflow 和 fast runner；并只读指定主要证据。追读未修改的选源、实际期间、主体、任务目录、投影与存读调用方以判断该差异。

## P2：普通模式把来源登记的 CIK 与安装规则的公司类型混用，能错误保存 N_A

位置：`scripts/vnext/financial_results.py:215`。新 `ordinary_records=True` 将 `_installed_rule` 的根改为安装程序 ROOT，因而原来检查来源根公司登记与安装登记一致的检查被绕开；随后选源仍从 source_root 的公司登记取得 CIK，而第 218 行仍按安装登记中的 `company_id` 取得公司类型。当前 A04 writer 在 `ordinary_saved_result.py:91` 显式选择这个模式。两份登记之间没有针对公司身份/CIK/行业的业务一致性检查。

独立重现只在临时来源目录修改 Macy's 登记的 CIK 和 role 为 `19617 / primary:19617`，保持安装登记的 Macy's CIK `794367`、公司类型及所有 SEC 原件/headers/请求日志不变；沿 `create_saved_result(... company_id='macys', metric_id='A04')` 实际运行后得到：

- saved result company_id=`macys`，原件 CIK=`19617`；
- publication=`PUBLISHED`，applicability=`N_A_STRUCTURAL`，value=null，reason=`TRAIT_NOT_APPLICABLE`；
- 保存的 CSV company=`Macy's`，CIK=`19617`。

这不是外部攻击前提：复制/编辑错一份来源登记就能触发。结果内部成功状态掩盖了来源主体与用于判断适用性的安装主体不同。要求保留一个限定的公司身份/角色及适用性一致性检查，或使选源和适用性明确使用同一已确认的公司登记；不需要恢复旧 Requirement 祖先、journal 或递归防伪门。补一个这样的反例并确认失败时不覆盖已有成功。

实际重现见 `subject-negative.log`。该日志来自本独审，本次临时测试目录已自动清理，没有改工作树登记、旧来源或账本。

## 本独审完成的检查

`required-tests.log` 是本次实际执行的原始输出。命令：

```
/private/tmp/issue28-company-c02-venv-20261006/bin/python tests/required_unittests.py tests.vnext.test_current_nim_company tests.vnext.test_bank_scope_dei_release tests.vnext.test_ordinary_current_update
```

实际 return code 0；50 tests，failures/errors/skipped 均为 0；unittest 32.008 秒，包含进程开销的命令耗时 32.447 秒。没有把父代理保存的测试日志当本次重跑。

代码和测试支持这些限定结论：

- 新参数严格要求 bool，默认 False 仍走原 `_installed_rule(repo_root)`、原 annual input 和原 saved-source verifier；本次没有放宽旧解析器默认 DEI release。历史 selected-year A04 仍要求显式 factory，A09/A11 默认公司写入仍闭合。
- 普通模式读取安装 Spec，而原件/body/header/当前失败记录从独立来源根读取；v2 输入保留实际年度日期与原 fiscal metadata。A04 仍调用同一 NIM 解析器：先查主体/全年、USD scale、reported-to-FTE bridge、earning-asset denominator、basis 及完整候选，再保留原披露率 `0.025 ratio`；计算只验证舍入，不替换为代理比率。没有恢复旧祖先门。
- 完整 JPM 数据集保存/读取、旧默认值/单位/期间/scope_key/publication 对照、原件改变后保留旧成功和禁止读取重算均在这次要求的测试中实际通过。Macy's 正常完整来源返回结构 N_A，缺源是在选源/验证阶段失败，不能靠 lack-of-source 分支创造 N_A；上面的登记不一致反例是另外的错误接受。
- writer/reader 复用原 manifest-last 保存、不可变 records/files、哈希读取、trace target/spec/unit/period 核对；controller 复用原原子指针/失败保留/中断恢复，这些未修改机制的限定回归通过。
- 新配置追踪包含实际 NIM 解释、期间、v2 年度输入/label、text context 和 task catalog 依赖。任务目录实际编译六个 retained Specs，因此五个其他 r4_v2 Spec 的依赖登记有实现依据。fast runner 只选两项小合同测试；company workflow 显式运行完整新模块。

父 CLI 证据只作读取：现场 source_root 实际存在且恰好九文件（registry、原混合 requests_log/manifest、三个 body/header 对），无 scripts/catalog；没有拆分/重置原请求历史。父记录仍明确 program_version=`a8237c57...` 且 has_uncommitted_changes=true；其 staged-main/dirty 执行不是当前提交的严格 SHA 复跑。README 已说明这个边界。父首次 CLI 的 rc2、保存 A04 成功、repeat/read 耗时和旧 event-header 错误被保留，本独审没有重跑该 CLI，也没有把这些父测量算作自己的结果。

## 未覆盖和权限边界

未重跑公司 CLI、十公司、全 fast/source CI、线上或模型验收；未独立重建 `original-table-read.json` 的全部原表读取，它仍只是父原件核对。新 fiscal-label 与旧 NIM inspector 对冲突标签的完整材料覆盖不在本次三模块之外扩展。没有业务最终接受、Ready、合并、采纳、部署、active 或 390 坐标完成结论。

未开发、commit/push、spawn、网络/模型/SEC 调用，未写 peer 树、生产状态或总账。工作树唯一新增路径为本目录的 conclusion.md 与两份实际日志。

审阅开始 UTC：2026-10-09T20:03:53.481427+00:00；结论写入 UTC：2026-10-09T20:07:59.465790+00:00；至结论写入用时：245.984 秒。实际工具调用：14（13 次 exec_command，1 次 write_stdin；包含最后核对），普通消息：2（初始告知及最终报告）。硬上限 20 工具调用/10 分钟未达到。
