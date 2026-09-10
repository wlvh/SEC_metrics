# 2026-09-10 用户执行委托记录

来源：当前 Codex 对话中用户于 2026-09-10 发送的「Codex 执行委托：PR40 正式发布、旧 PR 收口与 main 归档」。本文件是 Codex 保存的执行范围转录及原文摘录，不是新的人工作业审查、用户签名或独立 GitHub 批准。完整对话保留在原任务 01a081bb-9220-7de3-a311-b481906b3146。实际代执行者为 Codex，GitHub 实际认证账户另由 `gh api user` 核对为 wlvh。

用户明确委托原文：

> 本委托授权连续完成：发布前核验 → 关闭已过时的 #31、#33 → 提交真实批准及委托说明 → 合并 #40 → 原目录切回并同步 main → 正式采纳、部署和发布 → 回读验收 → 在 main 归档并推送 → 更新 Issue #28。

> 本轮允许提交用户明确批准的两条机器批准评论，同时必须公开记录代提交关系。审批来源核验不允许绕过。

> 本轮明确授权：正式状态稳定后，在 main 创建仅包含本次发布产物和执行证据的归档提交，并正常推送 origin/main。无需另开一个证据 PR，也不要再向 PR40 分支追加提交。

## 固定对象和不可扩大的边界

- 仓库 wlvh/SEC_metrics，原目录 `/Users/lyuhongwang/Developer/SEC_metrics`。
- PR40 获审交付 head：`36a91de058ac2fe6aee660a090f2b14d8527deb7`。
- 受审及执行 implementation head：`8ca50dd7342e5132e888abe58620c38a8cd994be`。
- 采纳政策：annual_candidate_adoption_v2；Requirement：issue_28_v7。
- 固定 plan 对象 ID：`sha256:6b6c9d2a552fe39392ecf1c72afb0b9b6fe36a61b1a1fd406106b115cc7f0339`。
- 固定 publication：`publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59`。
- 目标 manifest 文件字节 SHA：`ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec`。
- 预期正式前驱 R3：`publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8`。
- 前驱 manifest 文件字节 SHA：`69678ca9af53f7ca95f5250fd9eb319a90a9465da094f103a92ae0ed8e826d5a`。
- 新业务 provider/paid/SEC=0/0/0；不新增抽取、资格重认证、R4 重启、其他指标迁移或下一阶段实验。
- 使用原 final/ 机器计划、步骤、批准模板，并核对执行副本逐字节一致；不生成新计划或新包替换固定对象。

## 批准与公开委托

用户准许通过已认证 wlvh 账户代发 requirement_transition 与 publication_decision 两条评论，正文严格仅为模板 JSON，分别发布且不编辑。先检查现存同计划、真实有效、未编辑的等价批准；可以复用，不制造重复授权。真实回读必须经过现有 annual_candidate._github 边界，核对作者、正文、时间、位置、编辑状态和计划绑定。

第三条独立说明关联两条真实 URL，并明确：

> 这两条批准由 Codex 根据用户于 2026-09-10 在对话中的明确委托，通过已认证的 wlvh 账户代提交。批准仅对应本次列明的 PR40、固定计划、确切候选与完整包，业务调用预算为 0/0/0。它们不表示用户亲自在 GitHub 输入了评论，也不构成一次新的人工代码审查。

保留三条评论的真实 URL、正文和时间；说明不替代机器批准，不扩大权限。

## PR 和本地分支处置

#31、#33 添加真实收口说明后 closed/unmerged，不删除分支、transition 批准、计划、原失败或调用账；已有相同说明和关闭状态则不重复。#34 保持 open/Draft/unmerged、分支与停止决定不变。PR40 head 再次确认后转 ready，用 merge commit 合并；不用 squash/rebase，不删除分支。核验实际 merge M 的第二父为获审交付 head，保留 main 并行文档。

远端合并成功后在原目录 fetch、switch main、merge --ff-only origin/main；不 reset/clean/stash，不强行处理分叉。生产激活、部署、发布和归档都在 main。PR40 分支停在36a91de，不随main推进，其他历史分支/worktree/stash保留。

本次调查发现 #33 后续实际执行记录，因而原文“该计划自身未执行”的前提不成立。用户同时要求“若发现相对本次核对基线新增了实质代码或执行事实，先记录差异，不套用失真的关闭说明”。已依此记录真实原批准及 2/2/0 执行，不改历史正文、不重新认证其内容、不重启 R4。

## 正式写入范围

发布进程仅可写固定新包及其同级 `.<publication>.<uuid>.tmp/`；本计划的 permission、publish/rollback/restore action；同笔 intent/receipt；active pointer/lock；以及当前 ROOT_MIRROR_RELATIVE_PATHS 的14个兼容副本。原子 `.<filename>.<uuid>.tmp` 的创建、替换、fsync和正常清理包含在内。展开路径及实际 OS 规则另存 root-mirror-paths.json、production-write-whitelist.sb。旧包、原候选、其他数据、源代码/规则/测试只读，Git阶段的 .git 写入与最终新增证据归档另行授权。

命令 stdout/stderr/JSON 全部到现有外部 production-execution 的本次新子目录；保留已有日志，不覆盖。先 activate，再 deploy，再 publish，最后独立新进程只读 actual active；部署后先确认 inactive，不主动在生产注入故障或为验收而回退。

## 验收、已知差异和失败

active 必须为固定包，同笔 plan/action/真实权限与切换收据闭合；2采纳+238继承、327公共行；矩阵、证据与两项原文同版本；未选坐标、B03及其他行、期间/范围/证据保留；原R3/候选/失败/冻结政策不变；无pending intent、14副本与包字节一致。

用户明确接受固定包 B10 filed_date 从2026-02-10变为空，B01保留日期；完整字段差异要保存，区分新变化与本来为空。原文仍以accession、SourceReference、包内证据回溯。不手工补日期、不改Projector或固定包；发现超出固定包的新变化拒绝。

publish/rollback/restore各一次，recover仅同一已预留事务。中断先查实际pointer/intent/action；新版已提交但回读失败时，在身份和前驱可确认下可用有限rollback；问题排除且实现/候选不变才可restore。无intent预留、补偿回旧版保留消费，不换目录/plan/批准重试。NO_PENDING、ALREADY_RESERVED、exit0均非发布成功证明。

## 归档和最终状态

稳定后在main明确逐项git add，只提交本次完整新包原字节、真实权限/action/原生收据、actual active、14副本实际变化及新 docs/evidence/annual_formal_adoption/production-execution 证据。原final审阅材料和冻结政策不改。不提交密钥/认证凭据/lock/tmp/cache；不改.gitignore；发现敏感内容停止推送，不改包来逃避身份。

归档提交C不得改变scripts/tools/config/catalog/requirements/tests。正常推送main，不force。推送前fetch；并行非冲突文档可正常merge并复核，代码/规则/发布竞争或保护拒绝则保留现场并报告。C后对同一既有计划和实际读取入口只读验证，不生成新plan，不让C引用自己造成追加循环。

正常最终：原目录main；HEAD含M和C；upstream origin/main；ahead=behind=0；完整porcelain为空；PR40分支停在原交付head；#31/#33 closed/unmerged、#34 open/Draft、#40 merged。若失败如实报告actual active/事务/分支/已提交未提交文件和推送，不能为干净删除失败现场。

Issue28原位更新四PR、正式结果、M/C及下一停点，保留开放、三个终点和剩余责任。完成后停止。本次只称“同年度来源与执行版本的首次候选特定正式采纳”；正常新输入、持续许可/触发、剩余迁移与旧路径退出仍待后续。
