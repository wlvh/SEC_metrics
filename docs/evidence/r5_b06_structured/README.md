# PR42：B06 结构化主路径与完整待审候选

**PR41已合并；B06结构化主路径、十公司原生运行和完整候选已交付。PR42保持Draft，候选BLOCKED，正式active不变。** 本工作包业务调用provider/paid/SEC为0/0/0。没有重开Marriott验证阶段、恢复R4或迁移其他R5指标。

## A：PR41收口

获审交付head：`437d438dbfbca65ff34be2dab453ac77c425a97f`；实际merge commit：`000718745891198d8b05699689447c54dd0977aa`，第一父为原main `48b233f875d07145464e078afe686249e38e963b`，第二父精确为获审head。原目录main已快进，随后建立task/r5-b06-structured；PR41分支保留原head。

复用原独立审阅、两轮真实更新及CI34504694905（44入口、新4方法确实执行）并核对交付仅docs不同。合并后新的只读进程读取实际正式版本及S1/S2、两项原生结果和来源成功。初命令在三次读取完成后，因审计脚本过窄地要求两个旧阶段也必须报STAGE_CLOSED而退出1；实际按冻结内容应拒绝REQUIREMENT_CHANGED。随后只补关闭/旧失败核对，17.1秒通过，没有重跑三包或放宽产品校验。命令和补验均见`a-close/`，不把最初退出码改成零。

PR41完成的是已知历史材料上的受限连续运行；持续生产许可、正常触发和真实新材料仍未完成，未用隔离S2覆盖生产。

## B：已实现和实际验证

主入口：`tools/vnext_r5_b06.py prepare/read`，参数见`docs/r5_b06_structured.md`。实际计算与最终完整包执行head：`f56d740b47ad433f0762862c73b6089c408d3f65`。后续`14d5d5e`只修测试异常类型并增加白名单外债务概念反例，运行代码和规则树不变；归档提交只增加材料及当前入口。

新primary Spec并未覆盖旧B06 table Spec或修改source strategy：仍是结构化优先、歧义触发fallback，本轮fallback未执行。普通来源来自submissions→确切10-K→同accession/时点CompanyFacts；不从旧输出选择数字、期间或概念。声明式直接总额和同族pair防止重复加数；非正权益由通用正分母约束处理，没有Calculator中的B06专用分支。

工业/金融范围由已保存的原生XML时点/member提供证据；XML不补分子分母。Run freeze/replay重新发现完整来源集合、核对财政标签、解析原件、重选候选并重算结果。删除scope来源后重算Run、同值异源或可信原件身份不符均拒绝。结构化路线不伪造AI Evidence/人工Review，独立模型原文审阅另行保存。

完整候选复用现有Projector、publication原子持久化/完整校验和PublicationView。包含**250候选坐标=240继承+10个B06新状态，328公开行**。前驱实际只有9条B06；保留其他318行/证据、替换9项并新增JPM的明确阻断行。第一次prepare因错误假定已有10条B06而停止，原日志保留；修正为既有Projector的完整key union后实际封包通过，不改变原矩阵补齐假象。

- 候选publication对象ID：`publication_fa51db0b563c0ea97c545a3edced42cdfdd9a21a1a7d6f341f140bbe28653e71`。
- manifest文件字节SHA-256：`105eea0390a184278a9a3c70050885f6297abe2c68d3a31f749fda7397ab30f3`。
- 真实前驱：`publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59`；manifest字节SHA `ce8b2c3fe7ac9b94ed721287c23948503a87b59e3b471bd285cc569a2d2336ec`。
- `issue_28_v9` / V10与有限ReleasePlan均是待审核草案，未激活。正式集合仍24指标、327公开行，不是已迁移25指标。

完整包约209MB留在执行端，所有1,352文件的集合/大小/SHA及publication、batch、采纳收据对象ID已独立核对。包内Python只作为字节核对，不执行。精简审阅包不复制嵌套前驱和全套运行环境；原始来源各一份、原生Run和关键检查保留。

## 十公司覆盖与差异

详见[完整覆盖表](coverage.md)、[来源与精确值CSV](coverage.csv)和[逐字段新旧差异](field-differences.json)。原生数值三个：Enphase、Southwest、Paramount；原始HTML独立核对了总额/同族组合、真实权益及合并主体。Marriott为非正权益；其他六个坐标保留真实歧义。Southwest/Paramount的原始普通10-K数值通过，但后续10-K/A相关性未被程序裁定，公开候选均为空NEEDS_REVIEW，不能混同原生数值和已准采纳。

与旧数值一致的三个正例不是由旧值驱动；旧数据只在运行后作字段比较。Pfizer/Salesforce等旧OK被新主路径挂起，是存在债务涵盖性待决，不直接断言每个旧值都错误。Lumen同时有直接总额冲突和负权益，均保留。JPM之前没有B06公开行。未选318行及其证据、顺序和期间与真实前驱逐项一致。

## 证据、退出证明及停点

- 最终完整prepare：同一f56实现实际退出0，309.33秒；新进程CLI冷读退出0，86.16秒，十公司原始来源通过PublicationView回读。
- 短测试9项及实现CI34558559562通过；CI原日志明确45入口、B06模块实际9项。alignment、provider egress、semantic/scalability检查通过；CI不是完整材料或生产验收。
- 完整材料五项初执行：四项PASS，生产拒绝项因测试捕获ValueError而原生抛PublicationError导致ERROR。只修测试异常类型，14d上受影响项单独重跑80.955秒PASS，包含拒绝生产及重复prepare复用同包；没有把原五项日志改成全绿。
- `resolve_total_debt_component`不可用时，新的Enphase原生Run仍FROZEN/PASS。新路径不调用旧B06生产/补数；未提前禁用实际生产入口，正式退出须与后续正式采纳一起验收。
- 独立模型完成原始CF/HTML/范围XML/修订说明核对、两轮代码问题复核、原件身份与缺scope/改财政标签负例、完整文件集及结果关联。亲自执行、日志读取、未重跑部分分别记录于`review/`。不是人工审查或GitHub APPROVE。
- 实际正式根、前驱包、历史失败/调用账/原seed保护通过，旧连续线累计4/4/0不清零。本工作包0/0/0；只有获准GitHub读取、PR/Issue写入和合并网络操作。

剩余决定：债务子集/独立短债/租赁/standalone涵盖性、工业分母、修订采纳及必要fallback；完整B06正式迁移、生产授权与发布接入、旧B06正式退役仍未完成。持续生产许可/正常新材料、其余R5、WB-7、R4新路线、R6、Rf保留，未自动开始。

原目录最终停在干净、已推送的task/r5-b06-structured；PR42不自动合并，main仅包含PR41 merge。本包用于集中审核，不用更多Marriott演练延长试点。
