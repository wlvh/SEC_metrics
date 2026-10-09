# 普通B06银行/工业范围接线及具体缺证

本次新增的是当前原件的范围识别、已报告融资分项和具体未决关系，已进入原普通Run和公共行。没有交付完整银行/工业B06比值，也没有认证SEC无披露。范围固定JPM/Ford及已批准B06定义；不修改历史Spec、Run、旧范围复核记录、失败或已关闭预算。

## 可核对的业务结果

| 公司/范围 | 从当前HTML与XML重建的事实 | 保留的限制 |
|---|---|---|
| JPM银行融资 | 长期435206m、短期64776m、证券融资442396m、合并VIE融资27951m；报告分项小计970329m USD | 融资租赁完整性仍未证明，小计不能当完整B06，不推零 |
| Ford工业 | Company excluding Ford Credit分节、当前年度列的当前5550m与非当前16369m；报告债务21919m USD | 同范围归母权益仍未证明；工业净资产、合并权益或未分配NCI不能替代 |

两项指标值均为空、WITHHELD；原生Run为OPEN，公共行已生成，批次CLI退出2表示预期缺证状态。scope_source保留原件引用、所有选定原生报告、精度/单位/期间/主体、表格与金额定位。Ford的工业主体维度还必须对应金额所在的最近实体分节和当前年度列。所有金额来自原件，代码不按公司名/CIK或历史原件哈希选择结果。旧逐公司范围复核表没有成为常态输入。

原当前修订核对和分母守卫顺序保持；其他公司直接继续原三类债务解析，未改业务定义或提前退出旧生产。特殊范围当前只提供已报告分项与未决原因，后续若资料充分仍需实现完整关系证明，不能靠持续拒绝视为能力完成。

## 验证及首次失败

6项真实来源测试PASS23.968s；金额冲突、假会计命名空间、工业标题改写、原件未绑定变造、原生金额/上下文整体移到上一年度列均被拒。两项完整原生来源图与展示已生成；4项记录重新计算身份且结构合法的伪造完整比值/无披露记录全部被原件重放拒绝，材料测试PASS68.492s。Python3.9分别冷读JPM/Ford通过，从压缩包+仓库字节实际还原Ford后再冷读通过。JPM新来源信用为VERIFIED_SEC_ACQUISITION；Ford引用原来源，仍PREEXISTING_SAVED_ACQUISITIONS_ONLY，不随同一日志升级。

首次Ford标签规则遗漏原文“long-term”而拒绝，按完整原表补齐；最初全表范围标题检查后被自查收紧，直接按列标题的第一版误拒实体分节布局，原日志和较早原生包保留。修后按最近实体分节/实际年度列验证。首次重签反例工具错误地向Decimal接口传str，未执行反例；修正工具后4项真正拒绝，首次日志和目录不删除。

当前V15闭包34cd0c86/371，离线provider接线PASS38.066s、SEC完整来源/失败隔离/零重试/原生冷读PASS82.459s；101快速测试PASS79.907s。首次新provider离线测试在绑定脚本尚未完成时启动，因parent不符提前失败，未发任何请求；等待绑定完整后重验通过。当前sec-wiring/provider-wiring绑定新执行字节，原13个真实调用slot仍保留各自当时规则和响应。自查与CI均不算独立审阅。

## 审核材料及恢复

材料为6615个路径、195个唯一内容对象、17966555压缩字节；每个压缩对象解压读回核对SHA/size，仓库复用引用同样逐项核验。原native-first/final、首错/修后反例、旧/新离线接线、源码绑定及全部本次日志按material-index.json还原。完整13次真实请求及原始来源已在前一ordinary-document-identity包，本次不重新获取或改写。逐文件清单见MANIFEST.sha256.json。

```bash
PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_special_debt_scope
SPECIAL_DEBT_NATIVE_BATCH=<两项原生目录> SPECIAL_DEBT_ATTACK_ROOT=<新外部目录> PYTHONPATH=scripts python3 -m unittest tests.vnext.test_special_debt_run_material
python3 restore-document-material.py --evidence <本目录> --repository <PR43仓库> --output <新外部目录> --prefix special-debt-native-final
/usr/bin/python3 cold-special-debt.py <新外部目录>/special-debt-native-final ford_motor_company
```

恢复只在新的外部审核目录，不安装真实调用权限，不改固定总账或active。原生包与原配置共同恢复；本次源工作区仅同步了未冻结开发规则，旧规则字节及同步记录保留，SEC原件、日志、slot未改。

## 剩余依赖与下一动作

本轮实际新增0/0/0，累计provider/paid/SEC仍0/0/13，上限240/240/80。当前进程模型密钥缺失，已请求用户本机配置位置，只影响真实语义请求。预算和B13口径已批，不再等待逐公司许可。

继续B13完整来源赋义/原生结果、D03/D04真实语义和反例、剩余390、统一更新、发布/故障回退恢复和旧入口退出。JPM融资租赁和Ford归母权益的具体缺证保留，不推数。新模块及其他未覆盖路线仍需用户转交独立模块审阅，9月17日前不重试旧Codex审阅子任务。完整开发验收就绪后才集中生产确认；没有Ready、合并、采纳、部署、active或长期运行许可。
