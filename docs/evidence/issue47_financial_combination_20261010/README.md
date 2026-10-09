# 六金融历史候选的消费者组合接收

此分支只核PR105/108/110有限组合，不新建指标能力/公共内核/runner或另一个PR。底PR1105b3e6ee7，公共source/controller/store/projection沿最新109；仅逐字接105固定62bf的A13 case/tests和108固定aefcca的A03/A12 case/wording/tests，company_local合并三个历史family映射。旧公共文件不覆盖最新；八共享生产文件逐字同底110。

58构造/时期/分派/状态例.211s零skip，combined.log含六族混指标factory路由。构造不当财报结论。

同一组合程序另进程读取三个原任务：A13五值1.489s、平均族十值2.134s、范围族十五值3.361s；30旧正确值/单位/期间/ResultIDs全部保持，各缺26状态保，261结果/pointer字节保持，factory和网络禁止。old-state-read.json/log；没有复制源/program树、原state或新Result ID。

公共相关代码变化后旧配置不一定可复用，直接比对105配置发现真实DEI/projection变更；不手工重签configuration。实际混合接收仅在110原task新增尚没有的FY21 A03/A12/A13三坐标，原15位工厂禁止/135文件保护，然后六族禁factory复跑和独立读取。该首轮后来已完成，下文mixed-summary记录其终态；三个旧任务可读与同state混批的证据分开。新调用0，原Run/active不改，首次集成接收与完整历史/在线目标分开。

混合工厂禁止测试为每次Python调用安装profile，因此本次首处理耗时包含全量profile开销，不能拿它与各候选普通首跑比较宣称性能退化。当时进程PID43668实际CPU99.6%/2分18秒活跃，未因无stdout当停止；后来正常完成，未取消写入或重启。

五个接收的既有生产/短测试文件逐字同原候选，component-receiving.json仅这个有限组合来源摘要，不建立逐文件迁移总台账。普通共享核心和源/状态仍沿原110，不用旧快照重签或SourceBook复制。

只读sample PID43668一秒采样确认715次code_hash采样，监视中的每调用code-object set成员检查重复递归哈希是主要开销；这是验证驱动问题，不改业务抽取器、不把该wall time当产品性能。profile-sample仅本地诊断，不增审批证明材料。原业务写入保留至终态；后继驱动已改为对象身份比较。

实际同state六指标混批已终态：只新FY21 A03/A12/A13三个缺位，原15 scope工厂禁止且135旧files保持；六族禁factory复跑0调用，随后独立read保全部18正确坐标；此前缺26日志按原版本保留，本次最新请求FY21不把它们算成本次缺年行、159结果/pointer文件保持。mixed-summary.json/log。首2533.924s、复291.997s包含错误code_hash profile开销，冷读4.087s；它们仅诚实报告此harness，不当性能benchmark。三新增值/精确季度或全年窗同原候选参考，原15值/ID均同，不复制三任务目录或手拼结果。

## 实际main更新后的接收边界

origin/main已接95/97为cf8e997b，组合普通合入为02209ec9；仍未把三个金融候选合入GitHub main。58定向例.207s过。只读比对A03FY21刚保存配置：仅processing_files里未使用ordinary_source_session移除、ordinary_current_update自身hash及公共呈现配置（仅B12说明）变动；源、Spec、caseproducer及declared实际依赖同。现公共字典比较会触发无关LCR再计算，unrelated-main-dependencies.json已给#28。旧记录/配置不手改，不重算30位，也不借7b92禁factory成功宣布cf8复跑通过。新组合仍可独立读取旧正确值，保存完整性与当前处理复用缺口分开。公共一方修controller/依赖接缝，本方消费同一修复。

实际main cf8组合独立读三旧任务（identity guard无code哈希）：.661/.682/.831s，30原五年正确值/日期/ID全保，另读新增3混批值；285结果/pointer文件字节保持、计算/网络0。actual-main-old-state-read.json/log给实际行分类；A13/平均族仍展示其最近缺26行，scope最近请求FY21只显示18成功保存值，旧缺年报告留原版本，不虚称本次仍请求26。


## 接收者可运行的检查

代码用 `origin/task/issue47-financial-combination-20261010`；这是明确的main＋候选组合，尚不是GitHub main。来源仍用现有恢复根，不重复下载。下列短控制直接检查六金融工厂映射和原已交付族、时期与状态；不计算财报。

```bash
python3 -m unittest -v tests.vnext.test_historical_geography_cases \
  tests.vnext.test_historical_average_risk_cases tests.vnext.test_historical_bank_scope_cases \
  tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state
python3 tools/vnext_company.py results --company jpmorgan_chase \
  --state-root /existing/company/state --output-root /new/review-read-01
```

独立results使用所要读取的原任务根，output-root必须新。公司实际run会按本次配置比较是否复用；上述cf8无关依赖差异未修前，不能把“重复run必不计算”作为当前可用承诺，也不为测试这句话重算全部位置。修补接收后仅用受影响代表坐标、禁factory及原文件保护核对。
