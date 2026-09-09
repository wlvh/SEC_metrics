# 普通年度候选接入完整发布链

本阶段把保存的 Marriott B01/B10 普通候选接到现有 Projector、完整发布包、
PublicationView 和切换/回退/恢复原语。产物明确是隔离演练，实际 R3 不切换。
PR38 已合并为 `1e97cd08ad26edc1e7a720550811240af1889cb3`；其原失败、新成功、
批准、预算及原运行现场保留，累计调用仍为 2/2/0，剩余额度不转给本阶段。

## 使用者怎样读取版本

`tools/vnext_annual_publication.py` 是现有发布组件的薄入口。prepare从原始成功
候选目录读取保存的批准和来源，把原始输入、Run、Review、原始响应和controller
完整复制成只读快照，执行原生记录图校验，再构造完整包。它不重新调用模型或SEC。
首次准备会只读核对原GitHub批准评论；这不是签发新批准。

```bash
python3 tools/vnext_annual_publication.py prepare \
  --candidate-dir <original-accepted-candidate-directory> \
  --publication-root <new-absolute-isolated-root> --output-json <new-prepare-json>

python3 tools/vnext_annual_publication.py switch \
  --publication-root <isolated-root> --publication-id <prepared-id> \
  --operation publish --output-json <new-switch-json>

python3 tools/vnext_annual_publication.py read \
  --publication-root <isolated-root> --output-json <new-read-json>
```

read内部用`PublicationView.open(publication_root=...)`固定一个完整版本，再读取
矩阵、证据与原始来源。返回的`verified_source_locations`明确列出原始storage_uri、
包内路径、来源身份和逐字节核对的hash；不会把路径改写成另一份证据。
报告、矩阵、证据、覆盖、审核与内部来源链都在同一immutable bundle中。

只读程序也可直接使用原有接口读取包内数据：

```python
view = PublicationView.open(publication_root=isolated_root)
report_bytes = view.read_bytes(relative_path="REPORT_十公司财务指标.md")
source_bytes = view.read_bytes(relative_path=source_location["bundle_relative_path"])
```

切换、回退和恢复只对带本阶段marker的隔离根开放。实际仓库、其他Git checkout、
别名路径及没有本阶段标记的active根均拒绝。每份CLI输出使用新文件，不覆盖旧报告。

## 采纳与完整继承

原 B01 与 B10 仍是OPEN Run，原validation状态与字节不改。B01属于原foundation
规则并附带B03；B10属于issue_28_v6。它们不能被强塞进要求单一Requirement及全部
Run结果的旧Batch入口，也不能被改名成历史qualification cycle。

新的`ANNUAL_CANDIDATE_ADOPTION_RECEIPT`只封存通过完整原生重放的源字节，另有
自己的身份；不是把原Run手改为FROZEN。历史只读校验使用原受审Git对象、保存的
Requirement/Spec、原stage/plan、不可变SEC请求、唯一execution/marker/响应和实际
usage；只读view的类型不能进入执行入口或provider adapter。

Projector的原生`_project_result`从已验证Result/Trace/Observation生成两项公共行，
展示起点为空字段，不输入旧数值作为答案。原`project_metric_rows`与
`project_evidence_rows`负责完整有序替换。累计清单明确为2项采纳和238项从固定R3
继承，合计24指标/240坐标；公开矩阵327行及所有未替换行、期间和证据保持完整。
B03记录完整保留在源Run快照，但不被当作本次新增正式结果。

当前R3本身已含FY2025。本演练验证同年结果的来源/执行版本衔接，不是把生产人为
退回FY2024后再宣称新财年上线。旧版本完整包原字节嵌入新包，继承记录指向它。
既有R3的源证据层级和历史限制也保留，不以本轮替换两项重认证其余238项。

## 为什么失败不会拼出混合版本

所有发布文件和目录集合、hash及manifest身份仍先经过现有通用校验。新的类型
只增加采纳记录与完整继承的重算；包内Python只作为数据检查，不会被验证器执行。
实现代码对应的Git对象、语义扫描和公司常量扫描都会独立核对。

- 缺来源、缺Review/Result、外来Run、冲突或错误绑定在准备/重放时拒绝；active保持旧版。
- 软切换失败沿已有机制恢复原指针与全部兼容副本，继续读取旧完整版本。
- 模拟进程中断留下pending intent时，读取入口拒绝不完整切换。原恢复器根据唯一
  指针提交点恢复旧版或完成新版，之后再提供一致读取；不承诺中断期间仍可无条件读取。
- rollback/restore沿同一既有发布边进行；重复publish已active的版本不生成新切换。
- 同一候选、政策和实现版本重复prepare复用原包，不查询新的批准、不重新计算模型，
  不自动发布。实际代码改变会形成不同准备身份，旧失败准备现场不删除。

## 正式发布还缺什么

`config/annual_candidate_adoption_v1.json`是明确提出的最小采纳规则，状态为
`PROPOSED_FOR_FORMAL_ADOPTION`，本阶段只允许`ISOLATED_REHEARSAL_ONLY`。
新包始终标记`NONE_ISOLATED_ADOPTION_REHEARSAL`；即使内层Result写PUBLISHED、
或Result ID与R3相同，也不获得正式资格或发布信用。

正式运行仍需集中决定并落实：

1. 是否接受完整原生重放、原始执行/usage及来源证明作为普通候选的采纳条件；
   不能把旧R3资格自动借给新的普通执行或Evidence规则。
2. 将批准的采纳规则绑定到受审发布实现与明确候选的正式Requirement/激活身份。
3. 授予实际完整发布及回退/恢复边的明确权限。当前工具设计上仍拒绝实际R3根，
   合并本PR本身不会打开生产开关。

没有发现为本次隔离接线必须新增模型或SEC请求的材料缺口。正式规则是否另需
额外资格验证属于上述明确决定，本轮不擅自增加调用。剩余15指标、WB-7、39指标
统一生产与旧路径退出仍由Issue #28跟踪，不在本工作包继续开发。
