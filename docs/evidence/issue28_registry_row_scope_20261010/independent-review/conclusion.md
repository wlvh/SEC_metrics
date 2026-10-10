指定差异限定独审结论：**CHANGES_REQUIRED，1项P2**。复核base `f51d8c3d27f3169b9cdb3a246295830882240c1f` → patch `6731aff359746c76cedbe01cf4b7466d7b5a6204`。仅审 `ordinary_registry_scope.py`、`ordinary_current_update.py:_configuration`、`test_registry_processing_scope.py` 和 `company-current-records.yml`，沿消费者只读必要代码与已保存证据。未修改被审代码或测试。

**[P2] 复用判断遗漏了真实消费者已有的整表行业映射检查。** `scripts/vnext/ordinary_registry_scope.py:12–16`只验证行形状、必填身份和正整数CIK；结合 `ordinary_current_update.py:95–101`去掉整表摘要后，无关公司的未知行业类别能通过配置检查，继承旧成功。真实零AI消费者 `normal_zero_ai_results.py:260`仍调用 `repository_company_traits`，其 `traits.py:179–182`会因同一张表的任何未知行业类别报 `Company registry profile has no trait mapping`。因此当前检查可能报告 `NO_SOURCE_CONTENT_CHANGE`，而同输入的正常处理不能通过已有整表检查，与本次要求的“整表完整性仍验”不一致。

已做有限反例：在隔离程序登记表中，仅把Southwest的 `industry_profile`改为不存在的 `TEST_ONLY_MISSING_PROFILE`，保持Marriott整行和其他规则不变。实际base配置发生变化，patch实际配置完全相等；实际 `repository_company_traits(..., company_id='marriott_international')`报上述错误，小状态控制器仍返回 `NO_SOURCE_CONTENT_CHANGE`。原成功指针和0/0/0计数保留。这里只对来源/计算/读取采用已明示的小状态替身；配置函数与行业投影读取均为真实代码。反例不声称执行真实公司业务。原样结果见 `trait-integrity-control.log`。

建议在复用前保留与真实消费者一致的程序登记表行业映射有效性检查，并加一个“无关行未知行业类别不得继承成功”的负例。合法无关行仍应保持复用；无效整表应形成失败状态，无需让无关合法内容进入目标公司的变化依据。若决定让行业消费者改为只验证目标行，应明确这个较大的消费边界变更并另核影响，不能把当前两种校验语义的差异直接登记为通过。

本次已确认成立的部分：

- 新helper确实先调用原 `_registry_rows`，保留普通文件、必需字段、非空表和唯一公司身份检查，再检查重复表头、行缺列/多列、身份空值及正整数CIK。程序和来源两侧都读取目标公司全部12字段，未按名称猜测或只挑CIK；新helper与原loader文件仍参加处理代码比较。
- 新7项测试确实恢复实际 `_configuration`，修正的 `ProgramRegistryOverlay`同时覆盖完整路径和链式 `config/company_registry.csv`读取。程序/来源的合法无关行修改与增添保持复用；目标CIK、roles、行业、财年末、期间规则变化以及所用规则摘要变化重新进入处理。来源、计算、保存读取替身只证明这些控制器行为，不证明指标答案正确。
- 指定命令独立运行42项，0失败、0错误、0跳过，耗时0.461秒。命令：`PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp PYTHONPATH=scripts:. python3 tests/required_unittests.py tests.vnext.test_registry_processing_scope tests.vnext.test_ordinary_current_update`。原输出见 `required-tests.log`。
- 12项有限补充控制通过：两侧完整目标行/loader摘要保留；仅有旧整表摘要、缺新目标行上下文的构造配置不得静默改写；程序/来源两侧分别检查无关行空CIK、缺列、多列、空文件和符号链接。无效表均止于输入失败，保留原成功指针及0/0/0计数。见 `supplemental-controls.log`。
- 差异只改配置比较表示，没有改 `_current_sources`最新请求/原件绑定、目标CIK来源清单、来源失败判断、计数、锁、恢复或写入路径。旧配置没有自动“补上”当时未保存的目标行；升级差异会正常进入处理。构造旧配置反例强制工厂失败时，两份旧指针字节均不变。
- workflow加入新测试文件触发条件，并用 `required_unittests.py`执行该回归，无静默跳过分支。静态 `git diff --check`通过；未查询或登记此patch的远端CI结果。

已保存真实消费者证据仅作静态读取：README、`tested-tree.json`、`verify_real_consumer.py`及migration/unrelated/target/read四份JSON和必要日志相互核对。四个被审文件SHA-256均与tested-tree记录一致。最终migration正常处理得到Marriott FY2025/B04 `2601000000 USD`、CIK1048286、2025-12-31、原ResultID `sha256:c87ee735d9b6f33bbecd5c35658a4f5791dac5956341ab46244076781cade5d2`，保留12旧文件；最终合法无关行控制禁止计算并复用同ResultID，保留18文件。早期目标CIK变化控制进入禁止工厂而失败；随后独立读取将当前值置空，保留 `previous_result_value`及 `PREVIOUS_RESULT_CURRENT_CHECK_FAILED`。早期读取预期错误和重复输出目录失败记录保留，reader未放宽。目标/读取证据早于最后表头检查，README已明示；它们支持未变接缝，不能记成新commit下独立重跑。没有重跑这些公司任务，也没有重新验算B04业务事实。

实时读取Issue #28使用网页备用渠道；GitHub CLI的GraphQL与GET各一次都遭 `Internal Privoxy Error`。网页随后报告当日抓取，已读现行内部工具、产品目标、协作、开发方法和调用/发布边界。只以父任务的明确授权执行本次限定复核。渠道限制见 `issue28-read.log`。

未覆盖：修复P2后的验证；远端CI；任意并发登记表写入；所有指标/所有公司的业务接受；新来源真实性或模型准确性；生产采纳、Ready、合并、部署、active；#47目录或状态。本次没有真实SEC/provider/paid调用、账户查询/操作、commit/push、归档包、子代理或公司任务重跑。来源与计数结论限于未变代码和已执行控制，未把mock正向或既存报告升级为业务完成。

资源记录：actualUTC `2026-10-10 16:26:24 UTC` → `2026-10-10 16:48:44 UTC`；工具节点35（exec外层与每个嵌套调用各计1）；普通消息3（含最终报告）、问题0；未达到80节点/90分钟上限。结束校验HEAD及四文件均保持指定patch，Git变化仅本独审目录。机器记录见 `verification.log`。
