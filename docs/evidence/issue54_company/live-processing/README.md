# 原173–178 LIVE判断与公司来源独立接入

接收[#28回执5962391576](https://github.com/wlvh/SEC_metrics/issues/54#issuecomment-5962391576)，材料固定`51f9cd7cccf5814cc1219c467f902aca271d8692`。提供方实际消费8a521e3，只证明导出/认证/错公司和52捕获来源的原入口拒绝；没有把其结果算成本方公司计算。

原完整Enphase D04登记为`44801106654d1a1fa57ed9120f8238e832c7cfe8ce5072976ff628cb6871f314`，source=`6fbbc9244e78b185ff176d9431aefc173cfc8c02d3058fcd41b1ee7fc6761c05`，V14 closure=`568ab1eb52f4f44721e94a871efe78caf389862213a9c9278201c31b7e67c8d2`，六组173–178保持LIVE、原请求/响应/执行/接受不改。原程序662成员按`fd31d639aa3a1315d85ea2ac87f83b855bdf20d8`恢复661成员，唯一56字节`outputs/scalability_audit.csv`按提供方原样例外恢复，逐项核SHA/大小；未复制旧Run/Result当计算答案。原处理登记3118724 bytes，独立基线SEC公司来源认证/导出26.146s，processing元数据、原字节和runtime索引与提供方完全相同，processing id=`7f49d9ddd34de91cfbd2acf117c2bbf771e83931fd4ccde72d6843960f0a92c7`。

## 来源与适配

实际增量为本方已完整验证的#28旧13捕获混合历史，原checkpoint=`20f696819182dea693309b9fa088d17b685705f55b39ff8d3dc5919671f3577d`，完整ledger SHA=`2dbe3bf94152eeec20946d4b8725bf703bc3c35fea6ade51f75f25588f030dd0`。准备端按本公司原件导出Enphase，新的公司checkpoint=`b9345f619be24e2755097a2cabf47278bb4de79a93058f771b01aeb53e679c05`；没有裁行、重编号、拼接前缀、重取原件或借用额度。计算端只携Enphase原件与完整全局元数据，不读其它公司原件或完整恢复根。

当前来源中的Enphase原文/主体/期间/请求责任与原判断相同。`--processing-source-version`显式提供合法旧基线Enphase公司SEC版本`1483e21e51c75e4b25a7de3d9a3996155b7dcd1d755655cf8ffacb09cc653ddf`，同由外部source-trust认证；这是真实保存的原版本，未从当前账本截取。原判断仍单独从processing-trust认证。新ordinary/native树重建完整当前语义来源，原V14 `capacity_update_input.source_equivalence`比较完整原文、年度选择、原件集合与实质请求；当前source=`e2066314a7fccf69aa1ebc188c7d9ddcfd5923371e10c6e297d7d77b7aa3d68a`，equivalence=`4af24911b1cd06f671a2363717cefe33c5372bdf4111a327b2fbe976cbfba1b4`。它明确`new_provider_execution=false`、`original_provider_bytes_rewritten=false`、`new_acquisition_credit=false`。

原V14只用原公司SEC版本计算，当前完整账本另存不可变公司快照和等价证明。Run=`run:ordinary-integrated:128f6ccad812a47063e47640c3c997ff50d812bb8763135ac822a292b7e9743c`，Result=`7bf9ea839cb7ef2c636ebf524fb4305056a048447880bd37e2df81664483f99b`，原Requirement、处理source/input身份保持；公司入口完成，原Result publication仍WITHHELD，既有defined-absence公司投影TEXT_QUAL，business_metric_completed=false，不授业务/正式发布信用。

## 实测

| 阶段 | 秒 | 实际结果 |
|---|---:|---|
| 处理材料独立认证/导出 | 26.146 | 与提供方原字节、source及662文件索引相同 |
| C13公司SEC包准备 | 17.554 | 完整原历史验证；来源包无AI/Result |
| 修前基线公司计算 | 355.298 | 已生成原生Run/行，但清理失败；不报入口成功 |
| 只读C13包初次安装 | 未单测耗时 | 非root跨父目录rename权限失败，旧提交不变 |
| C13安装修后 | 见source-install-v3.json | 私有暂存根临时可写，源包/版本原模式保持 |
| 首版C13计算 | 376.776 | 等价通过及原生Run/行生成，但相对路径审计误判使清理失败 |
| 公司计算修后 | 385.057（计算384.311） | CANDIDATE_READY，原LIVE六请求，无新调用 |
| 最终适配树新进程重入 | 176.720 | NO_SOURCE_CONTENT_CHANGE，同一成功attempt；C13内2份manifest包括修前失败材料，重入未新增 |
| 新进程公司冷导出 | 175.471 | EXPORTED，1行公司矩阵/1行证据；原/当前checkpoint、等价id、原V14 closure和LIVE mode可读 |
| 实际绑定header负例 | 1.884 | 私有state副本，EXPORTED_PARTIAL/退出2/WITHHELD；原state不改 |

清理失败先检查了复制的只读目录，私有view改为可写；第二次实际拒绝最终定位为`shutil.rmtree`的dir_fd相对open被审计错误解析到开发checkout。子进程cwd固定到外部工作区后通过，原根仍禁读。中间树和失败Run保留，不改签或删除。只读包rename只改私有暂存根并恢复原模式，输入包不改，新增事务测试含中断/旧版本恢复/再次更新。

负例从上述实际Run的SourceReference及native binding找到原attempt和headers，修改该成功attempt中**当前等价检查实际消费的来源快照**，不是未消费的working文件。原V14 data未改，旧原生结果仍可保留；公司当前匹配证明失效，出口扣留。具体URI/前后哈希与错误见bound-negative.json。冷导出还需要证明创建时的固定company树，receipt不能自行提名任意代码根；再次计算可由当前固定树重验完整相同语义包而保留旧Run及证明。新CSV的处理mode来自认证包，不由薄receipt升级recorded。

Linux UID1000，原V14/ordinary程序、输入与必要trust只读，state独立可写；拒读原仓库、本任务开发checkout、处理准备/提供方材料及完整混合恢复根。审计是Python层验证，不是内核隔离或OpenShift验收。48项组件回归含工人替身的拒绝/不建Run、冷读重建与树选择；财报内容及来源等价的实际例与模拟控制分别记录。

## 范围限制

本段原实验使用13捕获；其后已收到 #28 对303d751f的真实52捕获LIVE D04消费者验收[5963721452](https://github.com/wlvh/SEC_metrics/issues/54#issuecomment-5963721452)，并核对固定1f627251的摘要、绑定header负例和既有52来源索引，见 [../closeout/README.md](../closeout/README.md)。两份覆盖分别登记，不再将52记为待验证。新原文、期间、主体或请求集合不等价时拒绝；acquired原判断不是baseline、B13部分组与历史处理仍未适配。没有新模型调用，不能拼190或恢复失败判断。新增真实SEC/provider/paid始终0/0/0。旧8a CI主16/16+生成1/1终态SUCCESS，最新交付提交的CI和消费者补验在#54唯一队列另行固定；不借旧终态或本方测试称独审/全36项/五年验收完成。
