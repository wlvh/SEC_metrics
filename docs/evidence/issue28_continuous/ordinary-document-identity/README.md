# 真实SEC来源获取、10项候选恢复与文档身份修复

本包属于同一Draft PR43、Issue28总委托；不是全PR批准、390完成或生产发布。审核从actual-counts.json、restored-coordinates.json、verification-summary.json进入，原始材料由material-index.json逐文件映射到material.tar.gz或同字节仓库原件。

## 新增实际结果

累计provider/paid/SEC=0/0/13，13次SEC均成功，无UNKNOWN或停止通道。新增来源为Salesforce两份原件、JPM当前清单与8份相关历史清单、先前年报及一份8K头文件。原请求的URL、body、headers、前缀日志、执行规则、slot终态及固定总账全部收录。每次都是原SecHttpClient一次GET，无自动重试；批准原文和规则见resume-2026-09-13及issuecomment-5651558538。旧23条recorded测试登记保留，测试材料仍为RECORDED_TEST_ONLY，未升级获取信用。

JPM A05/A06/A07与Salesforce C01/C04/E01–E05共10个OPEN候选恢复，完整数值/年度/RunID/来源信用在restored-coordinates.json；没有消费provider调用。C04的0表示该既有规格所核对的审计师变更标志，不能外推为无监管调查或无持续经营问题。普通结果记录内部PUBLISHED字段属于原生开发结果层，本包production_authorized=false，正式active未切换。

## 两个真实实现缺口与修复边界

首次Salesforce C04因获取存储名0002.body被当成原年报文件名，返回C04_SAME_CIK_FILING_REQUIRED。旧请求行、响应、原引用全部不改；另建URL文件名视图，仍绑定同一请求ID/URL/accession/rawasset及原物理body/headers。错文档、URL、请求ID及可变旧工作文件均拒绝。原冻结业务解析和旧Spec不改，不重新下载13份原件。

之后离线同正文元数据刷新暴露独立候选漏带旧请求头文件。首次失败在logs/document-identity-sec-wiring.log及其原目录；修后checkpoint安装带齐相同响应身份的所有原不可变尝试，让原读取器逐一核对后选取最新。原验证器不跳过旧请求，也不借新来源给旧来源升级信用。

## 验证及恢复

5项请求身份回归PASS5.105s，16项旧来源登记回归PASS12.156s；修后完整SEC来源/HTTP零重试/失败隔离/原生A08/复制运行时冷读PASS83.500s；provider实际来源→现行工厂→原WB-3的禁网接线PASS38.825s。101项快速检查PASS80.491s。当前V15闭包8e478c99/369；provider-wiring.json与sec-wiring.json绑定本轮离线证据，不把历史调用重绑新版本。原v14/V15调用执行规则在每个slot中按当时字节保留。

C04当前运行包经Python3.9、无Git/禁网络冷读通过；从本包和仓库已有字节实际还原后再次冷读通过。material.tar.gz为342个唯一内容对象、8332个路径映射、50049435字节，所有对象已解压读回核对SHA/size，已有仓库引用亦逐项核验。恢复程序不安装真实获取权限，也不写固定总账或生产根。

```bash
python3 restore-document-material.py --evidence <本目录> --repository <PR43仓库> --output <新的外部目录> --prefix live-c04-logical-native-final
/usr/bin/python3 cold-live-checkpoint.py <新的外部目录>/live-c04-logical-native-final salesforce C04
```

原样执行命令在本包脚本及日志中；单元/源材料命令分别为`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_storage_identity`、`tests.vnext.test_continuous_sec_acquisition`和`tests.vnext.test_continuous_semantic_calls`；后两者可通过对应MATERIAL_ROOT环境变量保存全目录。快速入口为`python3 tools/run_fast_tests_v2.py`。这些离线测试不会重发真实请求。

0ec5df8的CI34751565540为9项成功、current-instant任务取消，整体cancelled，不能登记完整PASS。此前a46608d/6754f0b的10项成功仅属原head；当前提交CI以真实Checks为准。执行者自查与CI均不构成独立审阅。

## 当前具体依赖与仍可继续的工作

| 对象 | 当前事实或依赖 | 下一动作 / 是否阻止其他开发 |
|---|---|---|
| D03/D04真实语义 | 当前进程没有DEEPSEEK_API_KEY，已请求用户本机配置位置；预算已批准 | 凭据可用后有限真源/反例验证；不影响其他来源、B13、范围开发 |
| B13 | Ford/Enphase新定义与费用已批准；后继Spec/候选/Calculator仅为开发组件 | 继续完整来源赋义、Review及原生结果；不再申请逐公司数值批准 |
| JPM/Ford B06 | 银行/工业范围接线仍需核对；融资租赁完整性/工业归母权益缺证须明确保留 | 继续范围实现，缺证不推零或拼小计；单坐标不阻断其他指标 |
| 独立审阅 | 634的ChatGPT/Fable只覆盖明列模块；新来源/调用、36适配、B06、修订主体、文本、D03/D04、发布回退仍有覆盖缺口 | 用户转交模块报告；9月17日前不重试旧Codex子任务，安全开发继续 |
| Issue最终验收 | 完整390、来源变化与失败保留的统一更新、发布/故障/回退/恢复及旧入口退出尚未全部完成 | 连续开发；不是旧340批次重跑或本次10项即可关闭 |
| 生产权限 | Ready/合并/采纳/部署/active/长期运行均未授权 | 完整开发验收就绪后集中生产确认；不妨碍隔离开发 |

固定总账恢复位置为`/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13`。恢复前只读核对初始化anchor、binding、claims和所有13个slot终态，继续同一计数；不能删除目录或把本审核还原副本当成新可用额度。D-36保持，不增加货币预算字段、金额预检/预留/硬停或账户设置。

静态语义命令首次使用默认输出，短暂生成了当前审核收据到outputs/semantic_audit_receipt.json；已把本次收据另存semantic-audit-current.json，并按HEAD原字节恢复旧收据。正式指针和业务结果未变；后续静态检查使用显式外部输出。
