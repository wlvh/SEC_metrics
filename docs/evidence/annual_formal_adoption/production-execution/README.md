# 正式采纳与发布执行记录 — 2026-09-10

已在原目录 main 完成固定 Marriott FY2025 B01/B10 候选的首次正式采纳，部署和一次 publish 后，独立只读新进程回读通过。**当前 active 为 `publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59`，前驱仍完整保留为原 R3。** 2项采纳+238项继承，327行公开矩阵；没有主动执行生产 rollback/restore 或故障注入。

- PR40 merge M：`5e9363171d803e2345e287bf825a8699b46d5e91`，第二父为获审交付 `36a91de058ac2fe6aee660a090f2b14d8527deb7`；PR40本地/远端分支保留该head。
- 受审实现：`8ca50dd7342e5132e888abe58620c38a8cd994be`；实现与测试身份见 execution-summary.json。归档只增加发布数据/证据，不改变 scripts/tools/config/catalog/requirements/tests。归档提交C的实际身份在最终交付和Issue28记录，不作自引用。
- 固定plan对象ID：`sha256:6b6c9d2a552fe39392ecf1c72afb0b9b6fe36a61b1a1fd406106b115cc7f0339`。目标manifest文件字节SHA：`ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec`。
- 激活receipt对象ID：`sha256:44ae0380d9c53d91d860998b8571f962ea21c23e68d77429f21430f3a74a0631`；正式生效由真实批准、权限和原生切换收据证明，冻结规则/包内PENDING字段及历史final文件不改。

## 真实批准及委托关系

- [Requirement transition](https://github.com/wlvh/SEC_metrics/pull/40#issuecomment-5611711476)
- [独立 publication decision](https://github.com/wlvh/SEC_metrics/pull/40#issuecomment-5611711644)
- [公开委托代提交说明](https://github.com/wlvh/SEC_metrics/pull/40#issuecomment-5611711815)

由Codex根据用户2026-09-10明确委托，经实际认证的wlvh账户提交；不表示用户亲自在GitHub输入，也不是一次新人工代码审查。原文及真实作者/时间/位置回读在 approvals.json，执行委托范围见 USER_DELEGATION.md。所有模型/SEC凭据均从执行子进程剥离；业务socket拒绝。必要GitHub审批/PR/Issue网络操作实际发生。

## 验收与公开差异

`production-verification.json`逐项关联active、完整包、原生action/switch receipt和实际permission，确认14兼容副本一致、无pending intent、两项原始来源可读，未选坐标与B03未误选，历史包/候选/失败/冻结政策/stash/worktree未变。

矩阵完整字段差异只有B10 filed_date从2026-02-10变为空；B01仍有该日期。B10原本已空的fiscal_year/form仍空，不能算本次新删除。证据表B01来源路径、原始来源hash、引用文字和parser版本更新，B10来源路径更新。全部前后字段见 field-differences-approved-package.json 和 production-verification.json；数值未变，不手工回填日期。

## 真实失败与恢复边界

发布前采证工具三次失败均保留：/dev/null保护规则、空目录枚举及JSON键顺序比较，第四次完整核验通过。首次deploy被外部OS正则定长表达式拒绝在permission写入前，只有空目录创建，无permission、publish action或intent，R3未变。修正为等价精确长度路径表达式并在隔离目录验证允许/禁止路径后，同一plan/同一批准的deploy-02成功。没有更改政策、核心代码、包或计划，没有重发批准。首次deploy失败日志不改为成功。

只有一次publish且已完成；rollback/restore未使用，recover未调用。不把exit0、NO_PENDING或旧反例资料当成当前发布证明。完整命令、开始/结束、退出状态、日志hash和真实Github响应在 execution-summary.json 及各 execution 文件。

## 旧PR与最终边界

#31/#33均closed/unmerged且分支保留；#34继续open/Draft/unmerged。#33正文“未执行”是生成时快照，实际同一计划后续曾JPM通过、Citi失败，该轮2/2/0；关闭说明已纠正范围，原transition、授权与执行历史保留，不追认内容正确性、不重启R4。

本轮新增provider/paid/SEC=0/0/0；PR38历史累计仍2/2/0。只是同年度来源与执行版本的候选特定正式衔接；不是生产FY2024→FY2025更新、未见材料泛化、长期自动运行或39指标全量完成。下一步仍由Issue28跟踪正常新输入、持续许可/触发、剩余指标迁移及旧路径退出。本轮完成后停止。
