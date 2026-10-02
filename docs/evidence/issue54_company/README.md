# #54 公司交接实测材料

本目录对应 `COMPANY-SEPARATION-v2.1-20261002`，起点 PR55 `0442896740c2f320fa999f932bc4d4ae0bfdf856` / 普通程序 `0bc24734736bb1e6cb34fbcf7ab9fece6951764e`。唯一当前执行记录在 [#54 §7](https://github.com/wlvh/SEC_metrics/issues/54)，本页只索引可复核证据；没有 Ready、合并、采纳、部署或 active 权限。新增真实 SEC/provider/paid 调用全部为 0/0/0。

`file-index.json` 登记保存文件的原路径、字节数、SHA256。原输入来自既有提交或有封印的保存归档，未重新获取。记录中的本地路径只描述这次执行，不是产品默认路径。

| 范围 | 本方实际结果 | 限制 |
|---|---|---|
| A 已提交公司基线 | 十个公司来源包导出；Marriott B01 原核心固定树原生候选 | 不是十公司所有指标验收；JPM metadata refresh、Salesforce/Paramount unresolved 按原声明保留 |
| B 同历史仅目标新捕获 | 原 recorded 获取 JPM submissions，一次新捕获；独立原核心树 A08 成功、只读程序重复成功 | 全部 RECORDED_TEST_ONLY，非真实获取 |
| B v1→v2 | 同 ledger/root 再追加 JPM 新捕获；稳定 source_root 安装，A08 新候选，重复为 NO_SOURCE_CONTENT_CHANGE | 第二次包含明确 synthetic metadata 标记，不算真实新财报 |
| C #28 已保存混合增量 | 完整13捕获（JPM/Salesforce）校验；原验证器拒绝缺 Salesforce 原件的裁剪；后继公司准入后 JPM A08成功 | B通过没有替代C；旧账本/行号/原检查点全保留 |
| C #47 已保存混合历史 | 固定60c6b4d6获取归档完整恢复1547追加行，原冻结获取验证器通过 | 公司包/原生历史消费者独立记录，恢复成功不等于公司包或业务通过 |
| 导入事务 | 十二个测试通过，包含三个中断点、首次中断、重试、旧结果保留、跨公司、非前缀、别名与另一进程锁 | 使用已认证包替身，不能代替来源真实性验证 |
| 实际Run原件负例 | A08 OPEN原生冷重放成功；实际绑定 body 变更报 RawBlob changed，实际绑定 headers 变更报 request-ledger invalid | 不是改未消费 working副本；不是FROZEN业务验收 |
| 非root/只读 | uid1000，固定程序 chmod a-w，另进程重复成功；禁止读原采集账本与checkout SEC evidence | Python审计/网络守卫不是集群网络策略；OpenShift未部署、动态UID未测 |
| 特殊入口 | Salesforce C04专用入口独立公司包 CANDIDATE_READY（81.433609s）；JPM INPUT_FAILED原因保留；B13/D04来源包不含答案，需合法处理输入 | 不把接口存在或录制结果写成真实业务完成；保存AI输入接线另验 |

最小改动面来自实际C失败：原完整来源验证必须在准备端完成；计算端使用独立安装的公司准入，核对完整账本元数据及携带原件/headers，不再要求其他公司的原件。普通/历史分别安装后继Requirement运行树，旧快照与Run不重签。baseline仍提供不改核心的运行树。程序、规则、来源、持久state和独立信任登记的路径与命令见 [运行说明](../../company_compute_boundary.md)。

## 来源及信用

- #28 保存包：`docs/evidence/issue28_continuous/ordinary-document-identity/material-index.json` / `material.tar.gz`；SHA绑定恢复见 `mixed-28-full-restore.json`。两份旧规则引用已漂移，通过原 `ordinary-continuity-policy/native-continuity-material.tar.gz` 的成员绑定取回确切旧字节，未重签或用新规则覆盖旧材料。
- #47 固定接口：[60c6b4d6](https://github.com/wlvh/SEC_metrics/blob/60c6b4d6/docs/evidence/issue47_history/collab-54/README.md)，消费者固定815c7820；恢复自身封印的 `evidence/issue47_acquired`。审批的旧预算根保留在审计记录中，但本次没有访问或消费该预算。
- Fable在PR43 0bc24734的五路线报告只按#54 §2外部报告引用。其原脚本/日志尚未取得，本方没有冒称复跑。旧E01=0、D02文本及已登记业务缺陷不作为金标。

## 本轮计时和体积

| 实际对象 | 准备/安装 | 计算/重放 | 体积 |
|---|---|---|---|
| B首次capture+原公司导出 | 32.348246s（含capture） | 原树A08 84.005421s；只读重复34.287575s | 导出58,073,868 bytes |
| 产品B首次 | 安装日志独立保存 | A08 63.431903s | 分项见包元数据 |
| 产品B第二捕获 | 稳定路径安装1.194141s | 86.776237s；重复29.171636s | 第二包原件58,389,020、账本/registry536,979、规则4,154,123 bytes |
| 产品C #28 JPM | 完整恢复未单独计时 | A08 107.732688s | 原件/metadata/规则分项另登记 |
| A Marriott原核心 | runtime安装2.535702s | B01 38.369146s | 来源分项见baseline-company-export-summary.json |
| 实际Run负例 | 仅隔离复制 | 正向13.560475s；body拒绝0.142287s；headers拒绝0.232892s | 绑定locator/hash在bound-run-probes.json |

十家公司首次来源导出12–19s/公司（两个并发准备进程）；实际原件约18–53MB/公司，共享规则每包4,154,123 bytes，全局账本和registry每包535,903 bytes。准备耗时含真实原件验证，不包含新SEC请求。未单测的压缩传输、所有36项、完整历史业务及OpenShift耗时标为未测，不能从本表推算30–60分钟承诺。

`fast-report.json` 为119入口、四workers、30s/case：117通过、两项TIMEOUT，162.525s。同轮材料计算竞争CPU；单项重跑 structured 24.625s通过，balance两次30s仍timeout。未因此提高上限或宣称fast全绿。旧初始checkout不含该测试，不能拿其ImportError作为有效baseline对照。必要后续检查及消费者独立审阅状态在#54唯一记录更新。
