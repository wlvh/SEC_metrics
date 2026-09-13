# 普通零AI原型独立只读审阅

结论：在本次限定的B01/C01保存来源原型范围内，没有新增阻断发现。19个独立检查点全部通过；保持prototype、无Run和无正式信用。这个结论不等于22项普通更新、来源修订/主体接续、SF财年标签或完整生产已经完成。

审阅对象始末字节一致：

- scripts/vnext/normal_zero_ai_results.py：5cc97ca9f6792781865eb853ab7e2295ca58f13ec9a7cc60755058806c0fbf23
- tests/vnext/test_normal_zero_ai_results.py：b799346903c9c20af0f962e50fa40585b23e45d7dbeccc96279dda8a3424a131

没有修改作者文件、D03文件或V13；未创建Run、freeze、PR、SEC/provider请求。provider/paid/SEC=0/0/0。独立脚本及全部机器结果为 independent-review/probe.py、probe-first.log、probe-result.json。

## 实际结果与口径

B01沿normal_annual_input的真实普通年报身份及期间，采用现有B01 Spec/approved concepts和Calculator，显式给定来源CIK及accession（模块:134–171）。独立从Marriott Company Facts原件 sha256:af2fea717f696acfa6f5f2436aa6e4175c3c56ab1628a2e3198964300f32422a 重查 `us-gaap:Revenues`，同申报0001048286-26-000007、2025-01-01至2025-12-31、USD、值26186000000，和原生Observation/Result相同。旧年份或季度target不能靠重签外层hash复用这个结果。

Salesforce仅独立确认原生记录的实际期间为2025-02-01至2026-01-31，并从保存原件重建相等。本审阅不授予其fiscal_year=2025标签正确性；正文/DEI标签冲突按root与r4另项调查保留。

C01严格依现有catalog/event_routes.json的5.02直接item规则计算唯一申报/item键数量；不声称实际CEO/CFO更换人数（模块:151–155,175–181）。独立从Marriott十个header逐项读取原始TYPE、FILING-DATE与ITEMS；完整header/primary成对、集合union与20个事件来源引用完全一致，日期都在实际年度窗口。三个5.02为0001193125-25-009110、0001193125-25-118861、0001193125-25-158742；中间一份真实form为8-K/A，未遗漏或改标8-K。Count=3与Calculator结果一致。Pfizer完整九个8-K、没有5.02，得到真实0；不是缺来源的0。

SourceSet保留current/history shard、索引/body日期一致性、唯一accession、完整header/primary和acquired补集核查（模块:62–124）。独立删除上述实际8-K/A header后返回WITHHELD，reason为原始request-ledger定位失效，未产生缩小计数2或错误0。缺必要current submissions则在源入口被拒绝。

## 调用者边界与原件重放

模块入口仅允许repo_root/company_id/metric_id；data root的B01 Spec、event catalog、registry及trait/applicability文件必须与代码安装目录一致（模块:46–53），真实body/header/proof由normal_source_authority重验（:137,188–190）。独立改B01 approved concept、C01 item code或registry CIK均立即拒绝；把Marriott原型交给Pfizer调用也拒绝，不能借相同公式或重哈希重绑主体。

读取期间阻止outputs、fixtures、REPORT、旧matrix/evidence和派生filing inventory，并禁socket connect。Marriott B01/C01稳定JSON、Salesforce B01实际期间及Pfizer C01仍可正常从原始来源重建。仅复制返回proof所需文件和authority，B01共14文件、C01共54文件，在没有Git、历史输出或额外人工答案的目录重建出逐字段相等的原型。C01此实际包的acquired census所需header已包含在其返回proof中，无需额外按公司填事件。

19项中9项为明确拒绝/保留测试：两个catalog篡改、两个registry主体篡改、两个current metadata遗漏、实际8-K/A遗漏、重哈希季度target及跨公司重用。其余正向/独立原件比对/已有失败状态检查见JSON逐项结果。全部拒绝原因均来自真实入口与原验证器，未mock验证器或造许可。

## 保留的开发边界

- Southwest修订影响与Paramount主体接续尚未接入此原型，按IMPLEMENTATION_GAP/WITHHELD保留。未要求通过或改成不适用。
- JPM C01历史索引/body覆盖冲突、Salesforce C01已有header最后GET失败仍保留；本次没有执行新请求、回退到旧成功或把它们改为0。
- acquired补集中发现未进入submissions的申报，目前明确拒绝并报告补集未实现；本原型没有悄悄删该旧覆盖义务。
- native Result中的PUBLISHED是既有结果记录状态；外层明确NOT_CREATED、production_authorized=false、current_latest_verified=false，且没有任何Publication/Run。因此不得把组件ID或这次审阅当FROZEN/正式采纳。
- 后继Run接线仍须固定动态C01 Spec与catalog/执行字节、原件与补集依赖；本次是可继续集成的有限原型审阅，不是正式上线确认。
