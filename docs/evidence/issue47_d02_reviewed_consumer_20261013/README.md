# 历史D02：完整保存子审阅消费与原生case

本方负责历史来源/期间、完整Item8请求及只替Item8的业务汇总，公共[#239](https://github.com/wlvh/SEC_metrics/pull/239)负责七文件保存回答读取；公司分派/controller/store/renderer由#28接。有限源页眉规则消费[#240](https://github.com/wlvh/SEC_metrics/pull/240)当前5a74，默认旧路径不改。候选用同一可取得组合，不能依赖对方未提交目录。

## 固定接口

`d02_reviewed_source.prepare_historical_legal_sources(repo_root,company_id,fiscal_year)` 沿已有历史选择器、annual及普通保存源检查，返回完整prepared/source_arguments、请求集合、真实期间/主体/proofs。当前只接受未修订连续主体；主体转换/修订缺口具名拒绝，不改历史取值规则。

`item8_requests(prepared,target)` 包含所有合格文字，不只关键词命中；嵌套已引用附注归附注自己，已定位审计报告排除，未闭合或尚未迁移的note ownership明确IMPLEMENTATION_REQUIRED。没有匹配回答时不能从旧答案裁取补问题，也不为一般pool宣称一个单块样本足够。

公共方对每份完整请求调用`read_saved_legal_review(call_root,request)`；本方`apply_saved_reviews(prepared,target,reviews)`只替Item8。完整请求集合必须有且只有一份匹配回答；重查公司/CIK/报告日/Source/doc身份及H1表型，未决全项扣留。Item3与附注逐项保持。错原文、长度失败、缺答/重复答不被裁剪或合并成成功；构造IN/OUT/extra仅验证机械行为，不作法律正确参考。

`finish_historical_legal_case(bundle,reviews)` 复用D02自身candidate/Evidence/Review/Calculator生成已有普通case形状，不写状态/Run、不调用模型。`d02_text_results_v3`新增默认None的`d02_saved_reviews`传递，使相同回答选择贯穿原件重建；旧默认保持。case为原文披露集合，不主张案件数、总负债或语义无诉讼；Reader的三个false信用不被误当完整模型业务判断。

```python
bundle = prepare_historical_legal_sources(
    repo_root=source_root, company_id=company_id, fiscal_year=fiscal_year)
reviews = [read_saved_legal_review(call_root=answer_roots[r['request_id']], request=r)
           for r in bundle['requests']]
case = finish_historical_legal_case(bundle=bundle, reviews=reviews)
# Public owner feeds this case to the existing controller/store/company entry.
```

## 已执行材料

源采用已提交PR52恢复根，原call0009只读复制七必要成员到新的本方开发目录（不是执行账本），成员字节均与原tar相同。原请求/回答/失败、35次model历史及SEC1772归属不改。

实际Ford FY2025：历史来源/完整request准备9.003s，request7f0d与原完整请求相同；公共只读0.000408s，旧LIVE1/1/0归属保；纯汇总0.062760s。空Item8子答后仍45块/17765字符，计算后才与原完整值比较、逐字节相同，未将旧值作为输入。详见`actual-ford.json`。

首个native case误用D01review构建器导致TEXT_V2_REVIEW_BINDING_CHANGED，原`native-case.log`保留；改用D02自己的构建器后，历史准备8.921s、原生case7.984s，Result fd73a6b3…/TEXT_V1/text/EXACT/PASS/2025-01-01→12-31，17765字符及ecf514…全文SHA相同。见`native-case-fixed.json`。这是内存case/native记录对象，尚未通过公共公司保存/复跑/CSV；没有创建新Run或把原调用登记成新执行。

57定向控制0.370s/零skip，公共239、来源/汇总、V2默认及H1原4通过/8拒绝/14真实长引文保持。小输入覆盖完整非关键词池、空子答保全文、非Item8不动、缺/重复/错公司/CIK/日期/未决拒、note owner尚缺具名停止。

处理依赖沿公共实际函数追踪：来源/读取/汇总31个scripts模块无漏，见`dependencies.json`；完整nativecase41模块追踪发现render.visible_untrusted_text漏登记，原`native-dependencies.json`保留，增加实际render文件后用同一观察集合复核无漏，见`native-dependencies-fixed.json`，没有重新执行原件。消费公共case时还须登记公共Reader的四实际文件，不能把本方PROCESSING_FILES替代公共base配置。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 tests/required_unittests.py \
  tests.vnext.test_d02_reviewed_source tests.vnext.test_saved_legal_review \
  tests.vnext.test_text_results_v2 tests.vnext.test_legal_review_contract
```

新feature selector文件供既有v2 runner加载。实际发现foundation.partition未纳入新增feature清单，已给#28最小复现并由其修公共runner；当前只如实登记local执行，不用未执行CI灯证明本模块。新head远端及接收亲复另核，不新建历史runner。

下一项是由公共方薄接这个实际case与来源版本/回答根，验证同公司run→save→零算repeat→独立results/CSV。其他多块请求、完整源导航及已知税务/自保语义失败继续保，本文不证明全部五年D02或1950完成。新增真实调用0/0/0；作者无Ready/merge/采纳/部署/active权限。
