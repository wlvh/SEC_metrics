# 原生候选接线增量

真实保存年报已通过Marriott D01（34条原文标题）、C03（22,970,926 USD）、C04（0）的OPEN完整图检查；Salesforce B06为0.2531872442595786412363464205，时点2026-01-31；Paramount C03为63,211,569 USD，覆盖2025-08-07至12-31，C04因同主体前期缺失而WITHHELD。各次不同草案closure见summary.json，不互相借用信用。

这些是开发中的OPEN图重放，不是最终FROZEN、正式采纳、完整发布或390坐标验收。未创建新provider/paid/SEC业务调用，未改变正式active。V12读取固定父v10字节，草案仍未激活；旧版本、失败和关闭额度保持原义。

首次真实失败保留：14条以上标题的JSON键顺序变化使Evidence重放不等；SCT先缺少确定性表格接线、后缺少完整DerivedAsset；旧B10/B11数字Run因错误位置的Trace检查回归；独立全链变造能把D01标题登记为B06。修复分别使用来源顺序、完整原网格重建、逐Result检查及安装D01精确规范/路径/正常输入身份。

70项旧Run/记录/文本回归通过；fast第二轮94入口通过，详细实际test数见summary。新增文本Spec边界15项专项通过。首次fast失败来自新增测试误用不存在的request_row_index，原日志留存，修正为真实locator字段后复跑。语义扫描首次发现并行开发中的尚未提交文本组件含业务硬编码，该组件单独修复；该次输出误落root audit，原始FAIL已另存并恢复调用前受跟踪字节，后续扫描输出到外部目录。

可重跑命令：`PYTHONPATH=scripts python3 -m unittest tests.vnext.test_replay tests.vnext.test_record_schemas tests.vnext.test_text_results`；`python3 tools/run_fast_tests.py --jobs 4`。真实原生开发入口为normal_candidates.install_saved_candidate_inputs及create_risk_heading_run/create_structured_candidate_run，数据根必须位于源码目录外。完整冻结/移植/发布接线仍须继续。


进一步实测并修复：可被重新签名的execution_authority空清单曾允许添加未授权公司trait而通过原生图；V12现绑定安装版本的全部五文件，并核对实际snapshot路径。SCT正常选择器曾在最新材料有两个CEO候选时退回旧材料取单值，现只允许确实未发现SCT表时继续。第一个自造行名称反例并未形成两个被识别的候选，已保留失败测试；第二次复用真实双候选规则建立有效反例，原暂存版代码SHA与错误接受结果一并留存。

最终本地fast第三轮96入口、307实际tests全部通过（69.483秒）；19项新增边界专项通过。独立复核确认原B06错标和权限清单裁剪反例现被具体语义门拒绝，未变D01仍通过34条原文标题。
