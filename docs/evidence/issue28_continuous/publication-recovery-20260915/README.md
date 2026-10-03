# 普通更新、发布恢复和旧入口退出：本轮无外发增量

## 实际修复

当前完整仓库重新执行既有发布恢复测试时，三个场景均未进入事务验证，先被真实语义检查子进程拒绝。首次结果保留在`before.log`；`root-cause.log`保存子进程实际异常：`Historical parent snapshot bytes differ: baseline_manifest.json`。

原因是`tests/vnext/projection_fixture_support.py`复制了所有Requirement，再将Issue15父链和公司注册表重建为隔离单公司材料。被一起复制的Issue28子合同仍绑定真实十公司父字节；`source_strategy`按照该子合同读取父链，自然拒绝。修复只让这个明确用于历史Issue15/R1–R3的测试工厂复制实际使用的foundation和Issue15两套合同。生产选择器、历史快照、验证器和事务实现均未修改。

补验复用真实`PublicationView`、提交、回退和恢复函数，覆盖：原提交包回退后恢复；镜像恢复与过时发布者比较失败；指针已提交后的进程中断与恢复；实际根/伪造权限/伪造发布类型拒绝。另检查旧指标写入与已退出函数的拒绝。最终日志为`after.log`。这些是隔离记录材料验证，不是新公司指标结果、当前普通39项发布验收或生产切换；原CI34943286777的12/12结论不受首次旧场景失败倒写。

## 正常更新的当前边界

`ordinary_update_cycle.run_company`已经按指标隔离历史，`run_once`完成输入身份比较、原生Run与公共行重验、重复触发复用、失败保留、未完成意图恢复及历史结果原期间读取。原材料见`../ordinary-update-metric-isolation/`和`../ordinary-update-terminal-identities/`。本轮未重复执行已经结束的Marriott试点，也不将这些历史测试重新称为新年度自动更新。

实际开发缺口仍是：`tools/vnext_normal_update.py --process`只处理已保存准入材料，`--discover-sources`与`--process`互斥；读取器不自动连接新SEC获取和后续指标处理。现有SEC获取控制可以复用，但固定实现在正常入口完成发现、获取、变化处理、失败恢复的一体化实测尚未完成。代码版本变化时，旧更新目录按原合同拒绝混用；生产版本接续也尚未完成。这些属于实现/验证责任，不能登记为财报披露限制。

## 统一发布和退出准备

事务基础的隔离恢复能力与普通39项接线须分别判断。`annual_adoption.replay_snapshot`和`annual_projection.build_projection`仍明确选择B01/B10；后者只替换已有公共键、保留R3累计集合，拒绝新增覆盖。不能把普通`OPEN` Run目录直接传入就称全部指标进入统一发布。应在已有发布包和PublicationView之上接入逐坐标普通结果、完整来源及确切采纳集合，沿用同一前驱、指针比较、intent恢复和回退逻辑；当前原生记录信用各自保留。

`remaining-legacy-scopes.csv`从既有冻结Issue15语义生产者清单中提取尚未迁移的15项指标范围，定位当前代码中的68个相关符号。它是退出接线的影响清单，不是当前调用路径完整审计，也不是新状态平台或已退出收据。涵盖金融表格、B06借款修补、B13占位/关键词、C02/C03/C04治理修补和D01–D04文本入口；其中共享函数仍可能由新适配器复用，不能按文件或符号名一刀切删除。

正式采纳时才能把对应旧生产/补数路径退出；现有`assert_legacy_candidate_rows`、退出函数拒绝和publication-bound retirement记录提供接点。历史发布和原始来源保留，通过原固定PublicationView读取；回退只选择已验证且真实提交过的前驱包，恢复复用已验证包，不能重新启用旧语义生产者来补值。本轮没有修改这些生产入口或active。

## 390坐标的证据边界

当前正式范围仍24指标/240个vNext坐标；剩余15项迁移责任不等于150个坐标都无可用开发结果。`completed-v14-batch-340/summary.json`是旧34项快照，`resume-2026-09-13/current-gap-index.json`明确为历史53缺口对账。后续已形成新的普通来源、接续、B13结构性及D04记录响应材料；旧340不能原样当作当前待办，也不能把这些异质材料简单相加为最新390验收。该现状仍应在既有execution-state和具体坐标材料维护，本目录不另造完成总数。

本轮新增真实公司—指标结果：0。新增provider/paid/SEC：0/0/0。实际指针与HEAD保存字节一致，见`scope-and-identity.json`。没有Ready、合并、采纳、部署或长期运行权限。
