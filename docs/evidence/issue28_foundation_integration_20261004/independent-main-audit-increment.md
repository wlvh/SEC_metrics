# main 审计与历史测试增量独立审阅

本次固定差异审阅完成，发现一项需修复的 P2 选择器边界问题：两个 successor 安装路径同时为悬空符号链接时，新增存在性判断跳过别名拒绝，退回旧 scanner。其余已审新增范围没有发现新的阻断问题。该结论不等于完整 PR 批准、业务验收、main CI 通过、合并或生产权限。

## 身份、范围与执行计数

- 精确候选：`d1648880e7518f019f734a00e0a3444dab45a9bc`。
- 增量基线：`e4108a6ffbd729aab2134da7d81c75a7ff9aa5f0`；指定 main：`af1984ad5f1a3598ded3626fe999d3abeffd29b9`。
- 工作树：`/Users/lyuhongwang/.codex/worktrees/issue28-foundation-integration/SEC_metrics`。
- 本次仅审 publication.py 的 main 审计工具选择、ordinary_scalability_audit.py 可选 policy 与独立于 scoped registry 的语法证明、新 main 工具/两份 policy、V13/V14 未冻结执行绑定同步、历史测试 Git 对象与配置修复、scoped helper 复制工具和新 CI 覆盖。
- 继承 `independent-main-boundary-review.md` 中固定来源/父闭包/传输的未变结论。没有重审303运行模块、旧B13 P2、D04长材料或完整146回归。
- 保守工具计数 **29次**：11次 functions.exec、17次内部 exec_command/apply_patch、1次 collaboration.send_message；包含写入与最终回读。普通消息 **3条**：开工说明、限定发现通知、最终报告；问题0条。开始约在首次读取后，至写入 **443秒**；结束登记时间 `2026-10-04T12:40:22.731Z`。最终回读在随后数秒完成，未触及80次/90分钟上限。
- 没有 spawn、HTTP/SEC/model 调用、源码或快照修改、commit/push。指定7项套件不重复执行；父正在执行的回归没有停止或重复。只写本报告、同名日志及 execution-state.json 的本子任务终态。
- 没有在线刷新 Issue：受本次禁止 HTTP 的明确限制。轻量记忆检索只用于证据/完成状态表达惯例，未从旧记忆认定当前交付事实。

## P2：双悬空别名未按不完整安装拒绝

位置：`scripts/vnext/publication.py:3071`；后续拒绝位于3072–3074。

`Path.exists()` 对悬空符号链接返回 False。若 `tools/check_main_scalability.py` 和 `config/main_scalability_exemptions_v1.json` 都是悬空符号链接，新分支的 `exists() or exists()` 为 False，因此不会执行其中的 `is_symlink()` 检查，选择仍保留 `check_no_company_literals.py`。只有一个悬空链接、另一路径完全缺席，也具有相同选择性质。

独立小反例调用实际 `_execute_scalability_audit`，仅以 mock 模拟这两个路径的真实 pathlib 状态：exists=False、is_symlink=True、is_file=False；截获 subprocess 选择结果为旧工具。TemporaryDirectory 与 subprocess 用只读选择捕获替换，没有实际文件写入、scanner执行或完整发布。该反例证明新安装判断遗漏了一类别名状态；**没有把它夸大成当前 d164888 的完整发布或公司错误接受**。当前候选的两个真实路径都是普通文件，旧 scanner 对当前代码的9处已知语法仍会报错；未证实双悬空变体能绕过全链发布。问题在于新增“部分/别名安装必拒绝”的安全边界不成立。

现有新测试覆盖 tool 删除而 policy 仍在，以及 policy 符号链接指向一个存在文件；两者均会让 exists 分支进入。没有覆盖上述“两个都 exists=False、目录项仍存在”的状态，见 `tests/vnext/test_main_scalability_audit.py:73`。建议存在性判断使用 `os.path.lexists` 或同时纳入 `is_symlink()`，再保留原普通文件检查；补双悬空及单悬空+另一项缺席反例。仅修复受影响选择器，不修改旧工具/政策语义。该发现已通知父执行者，父明确要求先完成固定 SHA 报告，再做最小修复。

## 语法豁免、真实身份与源码变动

独立读取两份 policy 的9条记录，逐条用实际 `_approved_exemptions` 验证源码 SHA256/大小，再对实际 AST 节点证明上下文。两份集合相同：7处 F 前缀属于 native fact 引用编号，2处日期属于已登记授权原文的 user_instruction_date 比较。没有公司路由或财务期间进入新增政策。源码与 policy 的精确绑定分别在 `ordinary_scalability_audit.py:26`、`:53`；语法判断在 `:70`、`:98`。

新增 `:147`–`:149` 只在实际 marker 语法且 policy 四字段坐标匹配时记为已证明。它使一公司 registry 不包含 F ticker 时，合法前缀仍能满足 policy 必评集合；没有删除身份匹配循环，也没有把所有同拼写常量加入豁免。一般 ticker、company、CIK 仍按目标 registry 扫描，拼接仍复用原 folded_ast_literal_value。日期/accession 仍独立核查。最终 used 必须与政策全集相同，不能用缺失或伪位置凑通过。

独立执行的5个小 AST 反例：真实 F ticker 比较、Ford Motor + Company 拼接、真实2025-12-31期间、无 kind 约束的 F+str(index)、单纯放在 user_instruction_date 字典中的日期，均未获语法豁免；前三者相应身份/日期命中存在。未声称这些小反例等于完整 scanner 发布验收。

父已保存的 `main-scanner-targeted.log` 是7项测试通过、64.380秒；其具体负例覆盖实际发布钩子、scoped registry、真实拼接/财年、已批准源码加换行、删除豁免、匹配哈希的非语法假豁免、部分/有效别名安装。这些是本次只读复核的创建者运行证据，不能写成我重新运行了7项。双悬空发现保留，不因这7项通过而抹去。

## 未冻结绑定、旧字节与历史测试

独立逐字节核对 V13 的393项与 V14 的495项 execution_authority.files，SHA256/大小全匹配；另核对 V13 new_rule_files 的97项与 V14 的61项。V14 parent 的5个 V13 snapshot 成员均匹配，transfer parent closure 字段与 baseline 一致。新增 main 工具/政策和 ordinary 审计文件进入声明绑定，publication.py 当前源码哈希同步。未独立重跑完整 Requirement loader；新 closure 值采用已有 `main-scanner-binding-update.json`，不是我新计算的证明。

与指定 main 比较，active pointer、metrics matrix、validation manifest、Issue15 release plan 索引、sec_pipeline.py 和旧 check_no_company_literals.py 的 Git blob 不变。整个 outputs/publications、requirements/issue15_v1 与 issue28_v1 相对指定 main 也无差异。因此新 selector 没有切换历史 active 或重写旧 artifact/snapshot；历史测试只固定其取材对象。

`test_issue28_requirement_transition.py:47` 从冻结 v1 baseline 声明的 Git commit 读取历史 pointer/mirrors，仍验证 repository/parent tree、R3/R2/R1 IDs、14 mirrors、原 Issue15 closure。历史 publication 仍严格 verify_publication_bundle，伪 successor 身份和缺失字段反例保留。它从“今天 root mirrors 必须仍是旧R3”改为核对旧固定对象，符合历史兼容测试目的；当前 active 可读性不由这组历史测试替代。

独立 Git 对象检查确认 main 与0bc历史测试 blob 都是 f29e9e4188c61984c5f5bcdb8a9b4a3b88aa2913。独立解析固定 main fast selector，只选该模块的 historical parent fast smoke；两项先前失败方法不在名单。现有同条件对照日志记录原两项在 main 失败，而相同 fixed-object 测试在 main/候选均通过。最终 `historical-transition-final.log` 记录20项通过、41.639秒。早先 summary 中 full 模块 returncode1保留原义，不能替代后来的终态；本次不把既有默认历史helper/镜像假设修复说成候选引入的退化，也不推断全部历史CI。

`projection_fixture_support.py:345` 在既有全部 config 复制后复制 successor 工具；scoped registry 改写及冻结配置/收据恢复仍保留。CI新增 main-foundation job 全模块执行新7项/历史20项、main scanner、provider egress和reference check；fetch-depth0供固定Git对象访问。旧fast job仍在，v2把慢于30秒的新审计模块放入 source-material类别。本次只审CI配置与覆盖，没有实际GitHub CI运行信用。

## 未覆盖与下一步边界

未覆盖：完整146回归、所有业务指标/新原件解析、303模块重审、旧B13 P2重开、D04/消费者长材料重验、Linux真实执行、新HTTP/model/SEC、实时Issue权限、main真实CI、完整production publication及合并/active切换。父的后台回归须按其最终日志单独收尾，本次没有替它判PASS。

结论限定为 **CHANGES_REQUESTED_FOR_MAIN_SELECTOR_DANGLING_ALIAS_BOUNDARY**：应先修复P2并对真正新增的最小差异复核；无需重建未变基础来源或把历史测试修复重审为业务算法。现有正确源码/语法/历史兼容证据可以复用，但不能为尚未修复的安装边界授通过信用。

