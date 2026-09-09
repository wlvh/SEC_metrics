# 普通年度候选接入完整发布链

保存的 Marriott B01/B10 候选沿同一 Projector、完整发布包、PublicationView 和
切换/回退/恢复原语运行。冻结v1保留隔离演练含义；v2增加确切候选的正式采纳待审批
包与实际发布权限接线。当前新Requirement未激活、无生产grant，实际R3不切换。
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

上面的v1 switch命令只对带本阶段marker的隔离根开放。实际仓库、其他Git checkout、
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

## v2：完整待审批包与正式接线

`annual_adoption_policy.POLICIES`显式登记v1/v2路径及文件SHA。读取context/meta/采纳
对象各处policy_id后必须命中同一冻结规则，未知ID、错hash或混绑一律拒绝；不按
“最新政策”解释旧包。v1原字节不改，新v2不含自授批准布尔值。

v2只覆盖已保存的确切成功候选：完整文件集、原Run/执行、来源证明、所选Result集合
及独立内容审核均精确绑定。B01原foundation及B10 issue_28_v6执行身份保留，新的
`issue_28_v7`/V8只拥有采纳/发布提案，S-ANNUAL-ADOPTION仍待外部批准。历史repair
槽位只证明那次执行，不能变成未来每年必须经过的运行规则。B03不选中，238项仅继承。

```bash
python3 tools/vnext_annual_publication.py prepare --policy-id annual_candidate_adoption_v2 \
  --candidate-dir <saved-candidate> --publication-root <new-isolated-root> --output-json <prepare-json>
python3 tools/vnext_annual_publication.py read --publication-root <isolated-root> \
  --publication-id <prepared-id> --output-json <content-read-json>
python3 tools/vnext_annual_publication.py plan --bundle-dir <complete-bundle> \
  --target-root <actual-root> --pull-number <implementation-pr> --output-json <plan-json>
python3 tools/vnext_annual_publication.py approval-template --plan <plan-json> --output-json <templates-json>
```

这些步骤不激活规则、不签发权限、不写actual-root。首次prepare通过同一`_github`
边界读取原执行批准，不属于模型/SEC调用，但确实是网络读取。完整包的内容验证
PASS只证明这个规则范围内的源图和完整包检查；PENDING信用不是正式更新或39指标
full acceptance。explicit read用同一个PublicationView读取待批包，不切active。

正式动作已接好，最终审核后按以下顺序执行：

1. 将固定计划对应的Requirement transition模板与独立publication decision提交为
   真实Owner评论；包和计划不因追加批准而改写。计划明确原生两项与完整238继承、
   原Run/执行、来源快照、政策/Requirement、包/manifest、实际根及精确R3前驱。
2. 按计划关系合并受审实现。生产入口核对真实GitHub PR的merge commit及其第二父
   head，受审提交仍为祖先，实施文件和tests树与受审版本相同。不是要求PR永远open，
   也不是任意祖先都有效。新增功能或规则变化需要新的包/计划与审核。
3. `activate --plan ... --activation-url ... --output-json ...`核对真实未编辑Owner
   评论后保存单独激活收据。它不改冻结规则文件，也不签发模型执行许可。
4. `release --plan ... --activation-url ... --owner-url ... --operation deploy ...`
   核对全部真实外部批准、当前代码、候选/完整包和预期前驱，再复用原生包持久化部署
   inactive包。已有相同包验证后复用，不改active。
5. 同一release入口的`--operation publish`使用既有正式提交原语，随后用`read`
   核对完整新版本及两项原文。rollback、restore分别最多一次，方向在计划中固定。

每个release命令重新从真实GitHub核对批准；本地JSON、旧模型执行批准或模板不能
产生`PublicationPermission`。测试批准的decision与activation类型带TEST_ONLY，
绑定marker隔离根，不能被实际根接受。命令输出总是新文件；发生错误先查看当前
PublicationView和pending intent，不能仅从命令退出码猜测指针是否已提交。

## 同一笔切换与失败保护

源包准备/验证失败不触及实际根。部署采用既有完整包持久化；发布前再次核对预期
active指针及其manifest。正式操作只保留一次操作预留，完成事实来自原生发布历史；
没有第二套结果数据库。新的schema2 intent/receipt另绑plan/action/permission ID，
旧schema1按原字节解释，公开读取不执行包内Python。

- 有pending intent：`release --operation recover`只接受同一计划/操作/许可和原
  指针、目标及时间绑定。沿原指针提交点撤销未提交切换或完成已提交切换，不能开始新边。
- intent已关闭且同一native收据已提交：recover确认该笔完成，不再发布一次。
- 预留后、intent前中断，或软失败已补偿并清除intent：旧完整版保留，本次预留消费。
  recover返回NO_PENDING，重复publish返回ALREADY_RESERVED；两者都不是发布成功。
  若以后决定再试，可生成新的实际时间计划并取得新批准，无需为此开发新代码。
- 重复publish/rollback/restore不再写一笔切换；批准不授无限自由切换。

本轮仅在隔离根以明确模拟的GitHub I/O验证这些边界，实际生产规则激活和grant仍待
集中审核。最终填好实际身份的计划、模板及完整包见交付材料，不以以上教学占位符
替代最终计划。后续正常新输入、持续运行许可/触发与剩余迁移仍由Issue #28负责；
本次候选特定审核不作为未来每份年报永久开开发PR的产品设计。

<!-- capability-anchor: CAPABILITY.annual_candidate_formal_adoption -->

## 本轮交付

完整版本、独立审阅、实际故障演练、测试失败及修正、调用计数和原始包索引见
[集中交付记录](evidence/annual_publication/README.md)。最终实施补验及条件合并门禁见
[PR39收口记录](evidence/annual_publication/close/README.md)；合并代码不切换实际R3。
