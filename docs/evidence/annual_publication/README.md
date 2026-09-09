# PR39：普通年度候选完整发布链隔离交付

已用PR38保存的真实成功候选形成并读取完整隔离版本：24指标、240个坐标，
其中2项采纳、238项继承，327行公开矩阵。B01为FY2025收入261.86亿美元，
B10为FY2025入住率69.3%；原始来源可通过同一个PublicationView回读和核对hash。
实际R3没有更新。PR38已合并，本PR保持Draft，最终审核由用户完成。

## 身份与实际入口

- PR38 merge/main：`1e97cd08ad26edc1e7a720550811240af1889cb3`。
- 本阶段受审/最终prepare与switch实现：`9b40c9c7c1d7b30f1597a078559242ab1222a663`。
- implementation tree：`sha256:b4670a5ea719e4a3a7cd3dfd89a3186b962c3ba51db6e63c5f64b200c472cebb`。
- 最终隔离版本：`publication_2003618f263e3eee42d42c03ceb49d8c5986fee9fb03f231adaad6b12f09b280`。
- 前驱仍为原R3：`publication_4f2542a2e74de50e2e005d787a7edd57cbf587697593e4f3b74a59a81a684cc8`。
- 入口：[运行说明](../../annual_publication.md)，`tools/vnext_annual_publication.py prepare/switch/read`。

普通Run仍为OPEN，原validation和执行身份不改。新采纳收据封存完整重放结果，
分别保留B01与B10的原Requirement；B03附带记录保留，但不成为本轮新增公共结果。
新旧Result内容身份可能相同，不能据此冒充复用执行、历史资格或正式发布许可。

## 使用者能读到什么

[最终读取记录](switch-final.json)包含完整行数、选定结果、期间、证据，以及
`verified_source_locations`。这些位置是PublicationView内可逐字节核对的原始
Company Facts/10-K文件，原storage_uri另行保留，不通过改路径掩盖来源身份。

[完整版本清单](complete-version.json)列出每个坐标来自新采纳还是固定R3继承。
未替换行、期间和证据均精确保留；[投影证明](projection-proof.json)记录完整集合。
本次是已有FY2025材料的来源/执行版本衔接，不是线上发现了新财年。

## 验收结果及其准确层级

- 首次完整演练三个test共925.440s，其中完整故障/回退/冷读方法及重复准备方法通过。
  整个suite因反例方法中3个测试构造/异常捕获错误而FAILED，原[日志](rehearsal-tests-1.log)保留。
- 修正了原始SEC JSON序列化、JSONL单换行和原生异常类捕获，拒绝预期保持不变。
  最后独立重跑8项反例全部PASS，229.582s：[日志](rehearsal-negative-tests-3.log)、
  [逐项拒绝理由](rehearsal-negative-checks-3.json)。中间失败日志也保存，未覆盖。
- 已实际验证软失败读旧完整版本；指针提交前/后模拟进程中断时先拒绝不完整读取，
  再由既有恢复器分别恢复旧版或完成新版；正常回退、恢复和重复发布均通过。
- 43项controller/新旧发布边界通过；最终新增边界4项及Python3.9四项通过。
  33项fast和实施head CI成功。早期CI发现改动冻结pipeline，已恢复其原字节；
  没有修改BASE SHA或旧测试期望。[最终fast](fast-restored-pipeline.log)。
- [独立完整审阅](independent-review.json)与[最后增量复核](independent-review-final.json)
  均为NO_BLOCKING_FINDINGS，明确来自模型子任务，并非人工认证。
- [导出冷读](export-cold-read.json)在禁止网络和禁止写入导出目录下通过，
  文件/目录不变；[保护记录](protection-final.json)确认实际R3的35项文件、旧现场、
  worktrees、stash、冻结pipeline与Requirement不变。

本阶段新增provider/paid/SEC=`0/0/0`。PR38累计仍为`2/2/0`，未使用的修复名额没有
转用。本轮没有模拟validator成功、调用旧指标生产函数或进行实际Root/Stage12发布。

## 正式发布尚未满足的条件

本规则仍为PROPOSED_FOR_FORMAL_ADOPTION，本包信用为
`NONE_ISOLATED_ADOPTION_REHEARSAL`。它可以在测试根切换，不能进入实际R3根。

仍需集中决定并落实：是否接受普通候选完整原生重放作为正式采纳条件；将批准的
规则与实施版本/明确候选绑定到正式Requirement及激活；授权实际发布和回退边。
当前没有可用生产grant或生产开关，不应解读成“批准PR即可直接上线”。如果正式
规则要求额外资格验证，应按该决定另外限定；本轮未发现隔离接线需要新增外部请求。

没有证明未见材料泛化、长期正常触发或39指标full acceptance。剩余15指标、WB-7、
R4/R5/R6/Rf与旧路径退出仍由Issue #28跟踪，本轮不继续开发这些指标。

## 完整审阅材料

原始完整包、前驱R3与读取指针的只读导出位于：
`/Users/lyuhongwang/Documents/Codex/2026-09-09/annual-publication-integration/annual-publication-review.zip`

ZIP为14,683,026字节，CRC检查通过；SHA-256：
`44db974f2530398baf29370d59ce6d8ca5eca4ab3da6728c8bad9b64352bb189`。
导出是审计副本，不是新的运行根或发布授权，使用可信仓库的PublicationView读取。
[导出清单](export-receipt.json)、[总验收摘要](verification.json)、
[文件hash索引](evidence-manifest.json)用于交叉核对；长日志和原始字段不由本说明替代。
