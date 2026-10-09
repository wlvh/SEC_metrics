# A13 历史公司消费者接收

本记录为本批唯一主要验证记录。代码从实际main6e51f416开始，只接公共PR104固定0623ecac（前含78767a7c解析及1da8e6bb公司门），历史側只加A13已选年度case和现有company_local分派。普通控制器、保存器、读取、Calculator与金融原件检查器均复用；没有新历史pipeline、保存器或runner。尚未main，不授正式采纳/发布/active或全五年接受。

## 已形成的可用能力

`historical_geography_cases.prepare_historical_geography_year_case` 选择请求的发行人财年，使用真正列该申报的submissions分片和完整primary。共用inspect_inline_financial_claims显式传YEAR_QUARTER_OR_DATE，默认金融入口仍YEAR_ONLY；新选项只识别已有SEC标记版本，不给任意regex/validator。A13实际全年期、国际净收入范围、USD/原生维度/原格及同主体检查保持。没有地区加总、手工金额或新模型输入。

本批仅A13。非金融traits使用原Calculator的N_A_STRUCTURAL/null；修订及接续主体保留具名扣留；未决范围保持null，源错误传播为实际处理失败，不叫未披露。当前latest默认A13仍未接入，其他五个金融指标也未开放；公共门只让指定财年且明确提供的A13 factory进入原run_once。

## 实际JPM FY2021来源、计算、CSV与读取

来源为PR52保存SEC导出恢复的source-inputs。真正列申报的是submissions-034，accession0000019617-22-000272，原件SHA7c58f18f…36d478。原financial-route记录94fdaf25已有直接原表核对：2021 Total international28,971百万USD、scale6/ordinal7406、table614(6,6)，Revenue(c)包含净利息及非利息收入；不重新读取整份年报。

新case经真实Calculator、原save_calculated_case及另一进程read_saved_result，28971000000USD、2021-01-01至12-31、FY2021/CIK19617均相同。prepare57.872s（含历史选期/来源准备）、纯保存1.794s/独立读.459s，见actual-case.json。普通ResultID666c1ed0…22b97/Tracefacbf899…4a0f0是新普通消费者身份，无native Run或旧信用继承。

同一公司CLI第一次真实计算52.516s、禁止原factory复跑3.187s/调用0、另一进程读.555s，8结果及pointer文件字节保持；company.json/log给实际输出和出处。代码尚未提交时验证，记录有code_uncommitted_at_execution=true，不假报已测提交。

完成实际处理依赖声明后，正常单坐标配置迁移54.064s、禁factory复3.144s/调用0，原ResultID/值/单位/原年度版本保持。新目录独立读取.492s、14结果/pointer文件保持；company-final.json/log保终态。初读重复使用已有输出目录而被原保护拒绝，只更换读取目录final-read-02，不重新计算；旧版本也按原manifest逐文件SHA读取通过。

此前两项真实开发失败保留：第一次给direct Calculator的target额外entity/accession，被其精确字段合同拒绝，改为原五字段（主体归源绑定/年报）而非放宽Calculator；第一家公司调用已过company门但update门仍CURRENT_UPDATE_METRIC_UNSUPPORTED，公共0623补有限条件后再接入，不修改原失败或SAVED_METRIC_IDS默认集合。

## 验证与实际依赖

5个小型构造控制明确不是财报结论，调用真实Spec/Calculator：不适用不读金额、修订/主体扣留、未决不作部分合计、源失败报因、错误家族在选源前拒绝。现有dispatch增加一例混合A13/A01/B01/B10保持原工厂，原历史状态、公共DEI选项和当前公司组合共64项7.380s/零skip，combined-tests.log可查。解析/金额原件验证与小控制分开，不以mock代替实际公司结果。

PROCESSING_FILES声明实际历史选择、DEI、financial_structured/financial_duration/relationship、SourceSet、约束/表格解析、A13 Spec、现有任务配置和被检查器读取的政策说明；28路径均存在。policy文件只是继承检查器的实际读取依赖，不创建/重铸新授权。相关处理依赖变化才能重新处理，原controller的其他家族保持。

## 可取得版本与命令

检出本候选分支；公共必要源码已在同一树，不依赖两会话的未提交文件。来源仍由原task/sec-history-five-year的`tools/vnext_historical_sec.py restore --export evidence/issue47_acquired --out <新目录>`恢复，使用返回的data_root；恢复不是GET/模型或新许可。已有恢复根复用，不复制完整源/程序树。

```bash
python3 tools/vnext_company.py run --company jpmorgan_chase \
  --period fiscal-years --fiscal-year-start 2021 --fiscal-year-end 2021 --metric A13 \
  --source-root /saved/sec/source-inputs --work-dir /new/a13/state --output-dir /new/a13/runs
python3 tools/vnext_company.py results --company jpmorgan_chase \
  --state-root /new/a13/state --output-root /new/a13/read-01
python3 -m unittest -v tests.vnext.test_historical_geography_cases \
  tests.vnext.test_history_company_dispatch tests.vnext.test_selected_history_result_state \
  tests.vnext.test_dei_release_selection tests.vnext.test_company_current_records
```

原件只读，状态/输出在代码和来源目录之外；results输出目录必须新。年度缺件与金融完整五年、其他公司年度、online历史发现/补齐及其余指标仍未验证，责任继续。全部本批新SEC/provider/paid=0，无原调用额度重启或旧回答改写；有限公开组件接收与完整业务关闭标准分别说明。
