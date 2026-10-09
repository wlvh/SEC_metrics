# 首次真实语义调用与输出截断修复

受审/执行基线48d73d90，首次三个provider请求位于固定总账slot0032–0034，旧31次SEC不改。Pfizer商誉估值反例得到VALUATION_OR_OTHER_MEANING，原引文/OTHER_ENTITY/HISTORICAL与执行者原文核对一致；仅一个局部反例通过，不证明D04整体成立。

Ford两个请求均finish_reason=length、4096输出token且正文为空。旧语义入口遗漏既有DeepSeek入口的thinking disabled；补齐stream=false、thinking disabled并保持max_tokens4096、200000 context、原出口及零重试。新去重指纹纳入实际生成参数，不靠新代码/来源ID重抽；首次失败永久计数，只有修改请求后的失败样本进入重验。

离线实际来源→工厂→官方opener替身→WB-3→账本及规则归档测试PASS35.457秒。CLI原先响应失败仍exit0；现按响应检查返回0/2，重放原0032/0033/0034分别0/2/2，零外发。执行只为选中的请求构造plan。内部FEASIBILITY_ONLY主动不授Evidence，因此WB-3的FAILED_TERMINAL与是否获得可检查模型响应分别记录，不能把它当正式业务终态。

initial-real-calls.tar.gz及索引保存三个真实slot、原始请求/响应/usage/首次失败、当时完整执行规则和来源输入。offline-wiring.tar.gz是独立MOCK，永不冒充真实调用。所有对象已解包重算SHA；密钥不在包或仓库中。恢复工具可复用../ordinary-document-identity/restore-document-material.py，传入对应index/目标新目录；恢复不授新请求或生产信用。

随后slot0035虽完整返回，仍把无重大网络威胁误判成无持续经营疑虑，并漏评block450；详情和后继prompt修复在../semantic-focus-repair。旧三个slot及此离线receipt不重绑新规则。

原execution-delta.json误把完整运行依赖集合与较小execution_authority集合比较；execution-delta-corrected.json按同一工厂的完整集合重算，实际仅调用配置、V15基线/decision、语义入口及CLI变化。未改旧Requirement历史、SEC/总账/来源代码。SEC复用既有有效检查。

恢复已实际验证：将所选*-index.json复制到外部临时packet目录并命名material-index.json，将对应tar.gz链接到该目录；用旧restore-document-material.py的--evidence指向该目录、--repository指向源码、--output指向新外部目录。五个包的实际恢复日志见semantic-focus-repair/restoration-checks.json。
