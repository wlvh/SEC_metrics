# C04清单文件名视图与其余JPM事件恢复

JPM六项事件C01/E01–E05已使用本轮取得的完整来源依赖生成原生OPEN候选。C04首次返回C04_HISTORY_SHARD_SET_INCOMPLETE：清单已存在，但9次获取的当前/历史清单以编号存储名传给旧业务解析器。第一次只处理历史清单后进一步返回C04_INVENTORY_ORIGIN_MISMATCH，原日志同样保留。

修后为当前及8份历史清单建立同一不可变请求的URL文件名视图；原URL、请求ID、正文、原存储名、headers及旧引用全部不改。每个SourceSet只允许清单引用身份及本集合身份改变，已发现申报集合、表单、窗口、原件顺序、截止请求必须相同；原集合及新视图共同保存。JPM/Salesforce C04均为EXACT0、原生OPEN和候选公共行，未发布生产。0仅是既有审计师变更标志，不代表无调查或无持续经营问题。

## 验证和证据复用

文档身份的2项单元测试覆盖实际持久化的模拟当前/历史清单，原准备对象/请求日志逐字节保持不变；错误文档名、URL、请求ID、可变旧工作文件以及重新签名的虚假发现集合被拒。JPM/Salesforce两个C04完整原生图与展示通过；JPM用Python3.9、独立复制运行时、禁网冷读139条记录，通过实际还原后再冷读。

当前执行版本相对bdc41只改变ordinary_storage_identity和调用配置中的两个材料路径，逐文件及配置字段差异在history-identity-reuse-audit.json。SEC获取、统一计数、请求控制和原来源准入代码未改，因此复用ordinary-special-debt-scope的82.459s SEC完整材料及原CI/快速证据，没有声称本轮重跑这些未受影响检查。当前新规则工厂仍实际完成36.843s禁网接线；当前调用前检查及累计总账也重新读取通过，没有发SEC或模型请求。

本轮V15闭包71160fb3/371，provider/SEC接线收据分别引用新证据与明确复用的旧证据，直接校验其文件SHA。旧13个真实调用slot继续绑定各自当时执行版本，不借新版本重复获取或消费原样请求。实际本轮新增0/0/0，累计0/0/13，无UNKNOWN/停止通道，D-36及240/240/80总上限不变。

## 材料和还原

material.tar.gz包括JPM7项首轮（6成功+C04失败）、两公司C04修后、当前provider禁网材料和本轮日志，按哈希只存一次；2198个路径/145个内容对象/6076340压缩字节已逐项读回。原13次真实获取包、银行/工业范围包保留，未再复制或重跑。restored-and-regression-coordinates.json列8项本次验证坐标，其中Salesforce C04是前轮回归；自来源补齐起累计恢复17个唯一正向坐标，不计成18，也不代表390完整验收。

```bash
PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_storage_identity
python3 restore-document-material.py --evidence <本目录> --repository <PR43仓库> --output <新外部目录> --prefix history-identity-native-final
/usr/bin/python3 cold-live-checkpoint.py <新外部目录>/history-identity-native-final jpmorgan_chase C04
```

恢复不安装真实调用权限，不改固定总账、生产指针或旧请求。源码/规则、逐路径SHA与原错误文本在索引和材料中可核对；自查/CI不是独立审阅。最新CI按PR Checks实况登记，不借旧head成功覆盖本次。

## 继续责任

Paramount事件不能只放行当前主体：旧批准catalog/zero_ai_public_projection.json要求已登记的主/前身CIK，并按PRIOR_CALENDAR_YEAR_START_TO_TARGET_END覆盖；FY2025为2024-01-01至2025-12-31。当前主体4份申报/7条事实只是局部，前身一份8-K原件缺失；继续完整依赖发现及既有预算下获取。PartIII修订的FISCAL_EVENT_WINDOW已证明不变；这不授予收入/B03 EBITDA的财务跨主体合并。

模型凭据仍只阻止真实语义请求。继续主体/事件、B13完整赋义/原生结果、D03/D04真源反例、390、更新、发布/故障回退恢复和旧入口退出。JPM融资租赁与Ford工业归母权益缺证不推数。未覆盖模块由用户转交独立审阅，9月17日前不重试旧Codex审阅子任务。没有Ready、合并、采纳、部署、active或长期生产许可。

CI34755365944两个任务的原GitHub annotations明确记录“The job has exceeded the maximum execution time of 20m0s”，原日志与annotations在ci-timeout-originals.tar.gz。current-instant仍在构建、debt已到最后反例；两项job上限改为30分钟，未改请求资源/调用预算。原取消不是PASS，新head仍须实跑。
