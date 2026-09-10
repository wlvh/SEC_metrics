# PR40 最终交付：候选特定正式采纳与现有发布链

PR39 已按五项硬条件收口并合并。PR40 已完成首次候选特定正式采纳所需的政策解析、
真实批准核对、完整包部署、发布与有限恢复接线，并交付完整待审批包和已填实际身份
的计划。**PR40保持Draft待集中审核，未自动合并；新生产Requirement未激活，生产
grant未签发，实际R3未切换。** 新业务调用0/0/0，PR38历史累计仍2/2/0。

## A：PR39的实际收口

- 实施 `77dd7f3407d09bec3e5d19356f11028a9038326f`，证据交付 `21afb282074ddfa22867d0dbf239c28962acb2df`。
- merge commit `74af2fd106c54938306d7c354323c45be861cbf2`；使用merge方式，原目录main已安全同步。
- 新增fast模块实际4项测试进入最终交付 [CI](https://github.com/wlvh/SEC_metrics/actions/runs/34341721990)并通过。
- 最终实现新根首次prepare、完整验证/switch/原文读取和两个指定正向集成899.201s通过，无SKIP。
- 代码—执行—完整包关联、独立增量及归档差异复核通过；合并后三包只读兼容通过。

A同步之后远端main另有`56610e03a2dc92daef172b62e93f021e18885229`上传`docs/sec_metrics_report.html`，不涉及运行/测试目录；本工作包保留该并行改动，最终PR CI在其合并测试ref上执行。

完整证据见`pr39-close/`及`../annual_publication/close/`。原A采证工具失败保留，未冒称
全部历史测试在同一head重跑。实际R3、原v1包和A新包可读，两份年度包各有两项原文。

## B：实际实现与完整包

共享链为`annual_adoption → annual_projection → annual_publication → PublicationView`。
只增加`annual_adoption_policy`的有限v1/v2映射、待激活V8/issue_28_v7，以及
`annual_publication_authority`的计划/真实评论核对/许可/部署/有限操作接线。没有复制
v2执行器、发布器或数据库。代码以严格校验后的原生Result投影两项，238项完整继承。

权限验证使用`annual_candidate._github`，独立publication decision不包含模型许可，
也不要求PR永远open。实际生产运行必须证明指定PR的merge父关系、获批实现和测试
内容一致；本地JSON和TEST_ONLY正文不能授实际根权限。完成状态读取既有native
switch history，新schema2只增加plan/action/permission绑定；旧schema1不改。

| 身份 | 实际值 |
|---|---|
| 最终实施/测试提交 | `8ca50dd7342e5132e888abe58620c38a8cd994be` |
| 生产实现身份 | `sha256:8ec3e518edf05934a3d9586906ca1709db3fec4e46a6e26d08e3350347d7d74f` |
| 测试身份 | `sha256:0e0ec555f619549f3fdd1f1c3471fa02d7eec895c07cdabf1dd342463b19423b` |
| 新完整包 | `publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59` |
| manifest文件字节SHA | `ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec` |
| 采纳对象内容ID | `sha256:0ca14292d4ed0315cb144a2cdf37cb5680187acd820564b79a1a471e5ba99eef` |
| 待批准plan对象ID | `sha256:6b6c9d2a552fe39392ecf1c72afb0b9b6fe36a61b1a1fd406106b115cc7f0339` |

原生产核心审阅head为`73dfe05223f2407fcffabf34d472f83daf3b390f`；之后仅两个测试
方法改动。两head的运行文件、政策和Requirement完全一致，最终包另绑定新测试提交。
本阶段不将Git tree、implementation tree、对象内容ID和文件SHA互相替代。

实际入口：`tools/vnext_annual_publication.py prepare/read/plan/approval-template/activate/release`。
源码职责和命令说明见`../../annual_publication.md`；[完整计划](final/PENDING_EXECUTION_PLAN.md)、
[机器计划](final/pending-production-plan.json)、[模板](final/approval-templates.json)、
[运行绑定](final/run-binding.json)均已填好真实身份。批准来源和时间尚未发生，未伪造。

## 证据、状态与内容边界

| 坐标 | 期间/业务范围 | 来源与原执行 | 机械/内容验证 | 新采纳状态 |
|---|---|---|---|---|
| Marriott B01 | FY2025，收入，USD；26186000000，原生直接取值 | CompanyFacts `af2fea717f696acfa6f5f2436aa6e4175c3c56ab1628a2e3198964300f32422a`；原structured Run | 完整源图与计算重放；独立核对Revenues、主体、期间、单位和申报 | 内容通过，待生产激活/批准 |
| Marriott B10 | FY2025，69.3%；全球、可比、全系统物业 | 10-K `c372495ac4ad3e62399040675f490315db137e17cd9a9a4a8c10cb1d09312547`；原execution `sha256:e2e9361b656772608e760e1b46cc46945aa1bd7d62f3ee5c5c3b4829b59b5a9c` | 原文/定位/年份/百分比及范围核对，原生Evidence/Review/Calculator重放 | 内容通过，待生产激活/批准 |
| 238继承坐标 | 各自原期间及原范围不变 | 精确R3前驱及逐项row/evidence哈希 | 完整集合与未替换字节核对；不重新认证业务内容 | 继承原有证据边界 |

原B01/B10 Run仍OPEN，分别保留原foundation与issue_28_v6；B03记录保留但不选中。
源图的Result PUBLISHED不代表本次已上线。新包为240坐标/327公开行，完整原文位置
在`final/read.json`，统一PublicationView实际读取并核对两项来源字节。

## 验收、失败与独立复核

最终包已完成新正常完整链：批准边界、部署不切active、publish、rollback/restore、
重复拒绝、权限重建稳定及矩阵/证据/两项原文读取。同一v2候选再次prepare实际复用原包，GitHub和业务调用为零，发布目录完整文件树未变。三个政策混绑反例与8项深度反例
在修正测试后通过；拒绝原因具体核对，原指针、镜像和包字节未变。最终test head
[CI](https://github.com/wlvh/SEC_metrics/actions/runs/34359330612)实际执行v1四项与新六项短测试。

首轮8方法的完整运行是FAILED(errors=3)，其余7方法实际通过。按独立审阅认可的
差异范围，关闭PR合并关系、指针前后恢复、计划/批准反例、无intent预留、软失败和
v1/R3兼容的通过日志保留原head/包身份承接，未伪称整个失败suite为PASS。
旧JSON曾在subTest错误后继续append政策PASS，该行与原生日志冲突，**明确不计信用**。
旧deep suite的末端active假设失败也保留；修正仅让反例命中实际政策门并保护真实
运行前版本，不修改业务validator。详细证据来源分工见独立最终复核。

一次开发扫描误用默认输出，短暂改写实际根semantic审计兼容副本，已保存产物并按
事前SHA/HEAD字节精确恢复；active和历史包未变。`safety/`保存该事件，不能宣称全
阶段actual-root零写入。此后全部执行用OS级只读保护，运行前后源包、原候选、原历史
和正式文件均核对。业务模型/SEC调用仍为0；必要GitHub读取和PR/Issue操作实际发生。

## 最后需要的决定

只余集中审核PR40及这份候选特定规则/完整包/计划，并决定是否批准合并与首次正式
采纳。批准后使用已有activate、真实Owner评论核对、deploy/publish/read和有限
recover/rollback/restore，无须再开发发布功能。本轮没有执行这些生产动作。

预留后无intent或软失败已补偿时，旧完整版本保留，本次尝试不自动重发；NO_PENDING/
ALREADY_RESERVED不等于发布成功。之后如决定再试，可另作新实际计划和批准，不需要
修改代码。真实新输入、正常持续许可/触发、剩余15指标和旧路径退出仍是后续责任。

当前R3已经包含FY2025数值；后续成功切换也只能称同年度来源与执行版本衔接，不能
称为生产FY2024→FY2025更新、未见材料泛化通过或39指标全部完成。

完整审阅ZIP：`/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-formal-adoption/annual-formal-adoption-review.zip`，文件SHA `5ed91c216ccf70ef07af9b9f9aee6b3d16ff44b1e5543ad18ed2e61995571952`，
大小10221743字节。归档已逐项hash检查并冷读验证；它是只读审核材料，不是生产授权。
