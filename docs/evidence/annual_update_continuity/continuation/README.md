# PR41：模型切换后续验交付

**真实两轮目标未达到，PR41保持Draft。** 新配置下FY2024首轮请求与返回均为`deepseek-flash`，模型身份通过，但仍把Company-Operated的69.7%与下一组Systemwide标签混用，原生`EVIDENCE_FAILURE`终态拒绝；未经修改的响应离线重验确认为`ANNUAL_SCOPE_VALUE_GROUP_MISMATCH`。B01原生结果保留；B10无成功Result，真实S1/S2均未产生。按本次委托，FY2025未执行，第二个名额未用并随阶段关闭。原失败不改，未用额度不转用。

## 已完成的工程与离线证据

受审及本次真实执行提交为`1ea60fd44a0e401963515102ed2eadfc28f7e851`；实现内容身份为`sha256:e408d9cd4e802ac371babed23faed99adf189b1ed83b207f79eeee5160af8018`，测试身份为`sha256:d50939591ed33789a3a10e293ea2f5c577e0e756f0ceb47912100608f0c710eb`。这些是各自定义的对象身份，不能与文件字节SHA混用。

- 复核bd18fe0→61e6135的模型配置、历史读取、检查子步骤输出和业务范围保护。没有新增模型别名放行、prompt/schema变化或业务门槛放宽。
- `a289efa`新增明确的schema2续验许可：2/2/0、无repair、原关闭阶段及其原生1/1/0、累计上限3/3/0、两个有序允许期间、隔离根和截止时间。旧同名v8按封存内容与原Git身份读取；没有新政策/Requirement版本。
- 增量审阅找到失败终态一致性缺口；`1ea60fd`补齐已知失败枚举、单次attempt一致性、无success receipt和非空error_class。重算外层哈希后的三个伪造终态均被真实校验拒绝，原失败仍可追溯。
- 40个fast入口及[CI 34471435623](https://github.com/wlvh/SEC_metrics/actions/runs/34471435623)通过，原始日志确认连续更新14+3+4项实际执行。独立模型另亲跑26项内容门禁，正确scope与真正同值错组正反例均符合预期。
- 当前同一干净实现上的完整三项离线均通过，无SKIP：当前正式基线、失引用/指针故障恢复/部分失败、S0→S1→S2及每轮重复输入。HTTP边界回放明确记录原request/response与派生model/id外壳SHA；故意失败分支另把测试content设为`{}`。原始材料不改，核心validator没有mock；这些回放实际新增API为0/0/0。

完整日志、独立复核、原生字节与源链核对见`checks/`、`offline/`。较早offline-01因独立审阅修正主动中止，不计PASS。旧冷读脚本三个包步骤通过后在末尾撞到开发中的dirty authority，整体exit1，记录保留该区别。计时器与UTC间隔原值均保留，不作为性能验收。

## 真实尝试与预算

[新阶段批准](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5619977072)及[委托说明](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5619981297)由Codex按本次用户委托，通过真实wlvh账户代登记并沿原GitHub边界回读。它们不冒称用户亲自在GitHub输入或进行了新的人工代码审查。原[关闭阶段批准](https://github.com/wlvh/SEC_metrics/pull/41#issuecomment-5616160149)未编辑、未重开。

| 项目 | 本次事实 |
|---|---|
| 新stage对象内容ID | `sha256:046b38a3d3f8a06187e1ab0fcd3ad89607b1ea7ec98a8b9926f4b23744678059` |
| 新计划对象ID | `sha256:31e2acf0bede067f8e9b21f1d266d326a9097e5b24b377b441672cbdcda700fe` |
| execution ID | `sha256:489a130e61376e6516c9e9eb35cf07bfc27cbacbdb456f508551fcd03c4670d0` |
| provider request ID | `fcfda19a-0aa8-4126-8963-e4e21703d5a2` |
| 请求 / 返回模型 | `deepseek-flash` / `deepseek-flash` |
| HTTP / 原生终态 | 200 / FAILED_TERMINAL，EVIDENCE_FAILURE |
| usage | input159653、output784、total160437；cache159488+165=159653 |
| 新增 / 原阶段 / 合计 | 1/1/0 + 1/1/0 = **2/2/0**；零重试，无UNKNOWN |
| FY2025新执行 | 未执行：FY2024首轮失败，不用第二名额重抽或凑成功数 |

原始响应文件SHA为`c14db83fa4259075870fd5dd9e0160650f8627aa81b505c41bc9d827d0d5139c`；assistant内容文件SHA为`0314bedbdcfe8e80020093ff23fd8903b301a0740d07d41ce1966091c9b2772e`。usage通过上限仅表示资源条件成立，不赋予内容正确或发布信用。原PR38累计2/2/0独立保留，不在本表清零或转用。

## 结果与版本边界

| 对象 | 期间 / 来源 | 状态 |
|---|---|---|
| 新B01 | FY2024，原Company Facts与`0001628280-25-004818`申报绑定；USD25100000000 | 原生PASS，部分结果保留 |
| 新B10 | 同份完整FY2024年报；模型声称69.7及Systemwide | 被Evidence拒绝，无成功Result；原文目标Systemwide Worldwide为69.8，未手工补成候选 |
| 真实隔离S0 | 真实FY2023原生B01/B10，其他238坐标保留其各自期间 | `publication_a78550c65ca2d0f7337f1b8de6e7639ca02f6c89079f54cc24c212f457c2b209`；失败后仍active，327公开行 |
| 真实S1/S2 | 无 | 未生成，成功引用不存在 |
| 实际正式包 | 既有FY2025正式来源与执行版本 | `publication_24bf8f1654f3b80ecd2e996eb7393c0bcff706de65890e94c19878065f407a59`未变 |

离线S0=`publication_dc4dbe0791bebf4b548e311ef02bca2e3202a9430e97b08e3a7a80e4e3a06438`，S1=`publication_266cf47743a0a6a64444fb8e2850c015644f29a9ec49b534c9014ed12cbcd82d`，S2=`publication_65f4fab86fd28be23d5fc3172c75387c3ed4f07b9d3d2363781148fe8b22bb65`。第二轮计划真实绑定S1前驱；它们是已知历史材料回放，不能冒充两次新provider成功或未见年报泛化。

失败重入返回`CONTINUITY_FAILED_INPUT_REQUIRES_REVIEWED_REPAIR`，无新增调用。新阶段已关闭，关闭后执行校验返回`CONTINUITY_STAGE_CLOSED`；触发器`TRIGGER_DISABLED`。S0新进程禁网冷读通过、无pending intent。原live的4103文件、原seed和实际正式包/兼容副本全部保持字节不变。

## 仍未证明与下一决定

**当前Reader对目标业务分组的选择尚不可靠；校验能够拒绝错误，但真实连续更新验收线仍未达到。** 改请求模型名解决了身份一致性，没有消除跨组取值。

最小后续方向应围绕请求中组标题与数据行的从属表达、目标范围选择和相应离线反例作有限调整，再由新的明确委托决定验证；不要继续原样重抽、换模型碰运气，或放宽Evidence让69.7通过。本轮没有修改prompt/schema、模型通道、指标定义或验证阈值。精确原文诊断另见独立记录。来源和旧/新响应的Worldwide标签均为长度14、首字符实际LF（码点10），下一字符W（87），字符完全相等；本次不是换行失配。独立审阅曾误读JSON转义为字面backslash+n，其诊断断言失败及更正均保留，旧文件不回写。

PR41保持Draft，不合并、不推进main、不更改正式active、不进入R5。正常新财报更新和39指标统一生产/旧路径退出仍未完成，Issue #28保留全部责任。原第一次交付README保持历史快照，本页是当前入口。
