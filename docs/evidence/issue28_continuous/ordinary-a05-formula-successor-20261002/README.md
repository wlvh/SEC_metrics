# A05 普通更新把批准公式写进新候选公开行

JPMorgan FY2025 的已核对 Result 为 `0.01353819078340816975991354239`（约1.354%）；发行人原年报自报ROA 1.29%。两者不能混称，而旧普通公开行的`formula`为空，虽然批准的参考定义明确“净利润÷本年末与上年末资产的算术平均”。这是解释能力缺口，不是修改A05数值或会计口径的授权。

本后继只对显式新A05 Run绑定`A05_APPROVED_AVERAGE_ASSETS_FORMULA_V1`；默认`prepare_case`、`install_normal_inputs`、`create_normal_run`、`_binding`不增加字段。新绑定另有`presentation_policy`，原始来源、已批准Spec、三个选中claim与MetricResult本身不改。`ordinary_projection`只在此合同且实际选中`average_assets`时，从已安装的catalog确认公式ID与组成角色，再将`Selected net income / ((current period-end total assets + prior period-end total assets) / 2)`写入新公开行。旧包用原安装代码与身份回读，旧行的空公式和字节原样保留；未知合同或篡改绑定拒绝。

#28的正常更新CLI直接分流A05到新的`metrics/A05-formula-v1`历史目录，其它指标仍沿原有B03/普通路线；旧`metrics/A05`历史不迁移或改签。新目录的配置、输入描述、绑定、意图、Run、行哈希及冷重入均通过现有来源/Run机制核验。这个显式后继不要求日常操作者每年手填公式或指定数据。

`binding-before.json`/`binding-after.json`记录未冻结V13/V14的实际身份与三份禁网接线收据。`binding-compat.json`由Git保存的旧`_binding`函数与新默认函数对**同一真实当前来源Case**逐字节比较，确认默认绑定相同、数值Result相同，只有显式新Run身份不同。受影响的短测、真实JPM私有正常更新、另一进程无变化冷读、篡改负例、旧安装包原身份冷读的实跑结果分别见同目录日志与JSON。运行脚本在未提交树上记录HEAD和改动代码文件哈希，不冒充已提交SHA测试；提交后应核对文件哈希和新head CI。

实际新私有更新107.857秒返回`CANDIDATE_READY`，异进程冷重入40.483秒返回`NO_SOURCE_CONTENT_CHANGE`且无第二Run。旧安装代码重放旧Run所得公开行与旧保存字节一致、公式仍空；新旧`metrics_matrix.csv`逐字段仅`formula`不同，`metric_evidence.csv`逐字节相同，Result ID同为`b4af4d3b…`。真实新Run的正常回放通过，删掉/篡改公式合同及错指标等四项负例被拒。最终代码树固定fast套件146/146通过；`final-tree.json`核对了实际被测代码文件哈希、行字节与这些材料。

本次不重算或重新购买A05原始值，不改变旧Result ID、历史Run、正式active或#47运行根。私有新Run的manifest为`OPEN`、`validation.json=NOT_RUN`；单家公司一个解释更清楚的私有候选不等于390坐标统一验收、生产发布或发行人ROA口径已证同一。真实provider/paid/SEC调用均为0。共享影响限`normal_run_v3.prepare_case/install_normal_inputs/create_normal_run/_binding/replay_case`、`ordinary_update_cycle`和`ordinary_projection`的带默认值后继分支，及#28正常CLI分流；按`[shared-with-#47]`登记，#47自行核对堆叠接入。

对精确`489659e5`的首轮[限定独审](independent-review/conclusion.md)为`NEEDS_FIX`：Marriott A05合法`TRAIT_NOT_APPLICABLE`原生结果也有`publication=PUBLISHED`，却没有数值观测；新投影仅凭PUBLISHED要求一个`average_assets`观测，致正常CLI报`ORDINARY_A05_SELECTED_BRANCH_CHANGED`。审阅使用真实保存来源完成安装→Run→投影反例，不是纯静态猜测。JPM正向、旧默认绑定、旧包回读仍按各自证据保留，但不能据此宣称自动更新已完成。旧审阅发现及审阅代理57工具/4消息（超过3条上限一条）保持原义；下一提交只修这个增量并补非金融公司完整正例。接线收据目前已更新哈希，但审阅指出还欠新执行树的factory/controller禁网接线核对，下一条真实请求前不能仅凭收据哈希给接线信用。
