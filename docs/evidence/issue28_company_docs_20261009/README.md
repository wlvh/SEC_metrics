# 公共公司文档的版本边界

原候选ccf9d56f基于main `8588ccbbb1c91d81e0fb1a89dff3575214282549`；本次接收最新main `f447a3747a88edf080b740dca0681ce18b35c3d2`已合入的PR61/58，解决TESTING顶部唯一文本冲突，保留新快测分层及已发生真实首跑两方事实。相对最新main仍仅修改公共导航、公司使用说明和四项公司能力的文字声明。源码、测试、配置、Requirement、冻结包和来源均不改。PR57是已交付来源；#28负责公共及当期集成，#47负责历史消费者。10月6日受信任内部工具决定替代冲突工程前置。

已实际核对 main 与 PR67 `29c9c9e2080a1de8c809660ac8fbdfc49072ef12` 的 CLI help：main无run --source-root，候选有；公司/期间/工作/输出/指标及results参数存在。修改文件的相对链接、JSON、差异空白检查通过，见 checks.log。所查 issue54 baseline manifest 未引用本次文档；这不是对所有历史Requirement的重新认证。既有真实首跑/复跑材料按其原范围引用，没有重跑财报或新取数。

main既有原生run完整流程、PR67保存来源run及保留原生任务读取分别说明。此前ccf9的PR67未接通描述现已更新：f7905156默认空任务自动安装固定main8588原生程序，完整HTTP边界录制验证已有主要记录；新的轻量在线PR83仍独立待接收。资料充分的全流程新任务不能用“旧代码在Git”或39项状态表替代。轻量在线续接在#28保存来源阶段之后接续，另交代码及HTTP边界录制验收，不在此文档PR虚构已实现。

提交后机械alignment可验证结构，不证明语义、真实在线新任务或业务结果接受。本文没有Ready/合并/采纳/部署/active权限。

本次验证为未提交树（ccf9＋main f447合并及说明差异）：真实install-runtime --kind local 3.063s成功，仅安装/无HTTP，current-main-install.json保代码根/输出根/时间；不扩大为完整获取或财报接受。5个runner分层/输出测试0.004s通过，CLI参数/相对链接/JSON另核。提交前alignment因工作树尚未提交与HEAD有七项字节差异失败，保留原日志；这是该工具核验提交字节的行为，提交后再核，未修改断言或生成新信任链。旧文档PR的两项30秒快测失败保历史，已合入main的PR61将这些完整原件例归材料层；不删除业务断言、不把旧失败改绿。

提交94dbf48e后的capability alignment实际通过，committed-alignment.log保留原输出。该工具只证明结构/提交字节对应，不证明业务。此时main随后由接收方合PR62前进到dae5c660；本次被测安装树仍明确是f447＋文档，PR相对最新main的共同祖先差异仍仅公共文档/同一证据目录，不删除PR62。并未由本方merge main。

## Current-main reception after public/history delivery

The doc branch receives main ae8a13c8 and resolves six prose/JSON conflicts
by retaining the current CLI/history implementation facts and the trusted
internal-tool navigation. PR67/75/76/83 are now delivered code, not pending
source-only/online prototypes; old task/native/real-run evidence stays historical.
New source/window candidates are explicitly not main. The actual current
run/results help output is in main-receiving-*-help.txt. JSON parses and git
diff --check pass. The precommit document alignment report refers to the old
HEAD and therefore reports incoming files/document differences; it is kept
and is not a final new-tree validation. No financial materials rerun.

Main subsequently advanced to `73ead3b4` through the reception session. The
doc branch receives it without modifying the delivered public/history code.
PR87 is now main (merge2931d078), PR88 supplies the actual history guide;
source/window PR89 remains candidate. Current nav/version claims are updated
again only for those changed delivery facts. Three precommit alignment
differences are preserved; a postcommit run confirms the actual committed tree.
