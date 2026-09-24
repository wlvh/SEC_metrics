# 8-K12B 注册人变体：仅来源发现小补丁

## 2026-09-24 安装源复核：四份其实已在原账本

下文是当时**仓库基线**的缺失快照，不代表今日原账本安装源仍缺文件。当前`source-inputs`经原SEC槽105—108已保存并验证两份8-K12B/8-K12B/A的primary与header四个URL；`audit_installed_four.py`以当前发现入口逐一核对角色、原请求尝试和来源引用，4/4为`VERIFIED_SAVED_SOURCE`。对第一份URL调用现有捕获入口只返回`EXISTING_VERIFIED_SOURCE_REUSED`，账本仍为143/143/49；本次没有新增SEC/provider调用，也不重复购买相同原件。见`installed-four-status.json`与`sec-current-bridge-summary.json`。初次尝试的完整旧测试在后段普通Run的复制根执行版本校验失败；`sec-current-nonnetwork.log`保留该限制，不能说成完整原生Run已重新通过。受影响的SEC请求工厂、录制持久化和零重试HTTP路径已用更短的当前禁网接线验证。

`audit_installed_content.py`还从原槽105—108的保存字节和请求证明读取原文。可见正文中没有找到`Item 4.01`标题；8-K12B/A的Ernst & Young文字明确限定于**Skydance Media, LLC**审计材料，8-K12B里的PricewaterhouseCoopers命中属于一名董事的过往履历。两者均不是本注册人前后期审计师比较事实。文本检索不等于整个C04的否定验收：当前注册人仍没有同CIK前期10-K，旧C04 v2的支持形式和否定条件也没有变。下一步不再把“四URL待获取”列为阻断；真正剩余的是版本化事件形式接受与新注册人无同CIK前期时可否依据原件明确否定陈述给出结论的业务规则决定。C04当前仍未完成。

以下记录的是当时未应用的`/tmp/sec_metrics_issue28_continuous/registration-event-discovery.patch`候选及零调用测试；现行分支的来源发现代码已包含对应变体发现，旧C04 Spec/Run与固定总账仍未因此改写。`report.json`里的`runtime_patch_applied=false`只解释当时快照，不应再当作当前分支状态。确切当时patch/hash见该报告。

## 机制

原 `_filings` 增加显式 `include_registration_variants=False`。旧调用默认仍只保留原六种形式，`_FORMS`、`_EVENT_FORMS`、C04 v2和旧事件接受器不改。仅既有来源发现对当前/相关历史元数据开启该选项，保留8-K12B、8-K12B/A的原始form、行定位和实际filingDate。

按既有期间及登记CIK，自动给每份变体添加primary和header两个原有GET依赖；URL用注册人CIK及实际primaryDocument，不把第三方申报agent的accession前缀当CIK。所有变体都发现，不用metadata.items未列4.01作为排除依据。跨清单重复先整体拒绝再生成要求。新条目标注SOURCE_DISCOVERY_ONLY_NOT_EXISTING_EVENT_ACCEPTANCE；旧events集合不扩大，变体另置于现有来源发现结构。

## 实测与四URL计划

原真实完整CIK2041610 metadata经现有来源证明读取。7项测试通过：四URL与先前调查相同且现在仍全部missing，元数据items清空不减少来源，窗口/未知形式排除，非法accession/路径/日期/列数及重复拒绝，原默认形式不变，注册人CIK正确。完整Paramount discovery实际通过98.868秒：旧当前CIK events仍4份，变体2份，新增4个去重URL，整体状态SOURCE_DEPENDENCIES_UNRESOLVED，固定source ledger/manifest字节未变。

完整发现后只将重复accession检查提前到添加任何依赖之前；最终7项实际metadata及反例补验覆盖该差异，没有机械再跑整份发现。两次实现身份分别保存，不把旧测试说成后续字节全重验。

`four-url-plan.json`保存当前原metadata proof、完整两份filing字段及四个GET URL/角色/缺失事实。若执行前仍缺这四份，需要4个SEC槽，发现本身不需provider。当前未发；主wiring绑定、原共同总账和零重试门仍须满足，不申请新额度、不预先扣账。

## 源路由以外的责任

C04 v2 Spec的event_forms、governance resolver的manifest精确比较、普通governance事件选择以及acquired-header/source-set receipt都仍只接受8-K/8-K/A。旧六事件的source-set路径也有该限制。取得四份原件后，需要版本化扩展这些接受规则并验证原生Evidence/Run，不能只把形式改名为普通8-K，也不能把本次发现视为旧指标全覆盖。

若原件包含4.01，其事实可在相应后继形式接受路径下评估；目前原文未知，不能从items列表推断。

Paramount同registrant前期年报不存在和前身比较事实限制仍在。若新原件没有4.01，当前v2仍不能仅凭Item9 None、连续审计原文或跨前身同名审计师给0；采用这类替代否定路径需明确的后继业务接受决定。源路由修复不代作该决定，C04继续未完成。
