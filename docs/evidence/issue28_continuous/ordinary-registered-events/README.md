# 已登记前身事件范围的完整来源发现与有限获取接线

保持旧批准catalog/zero_ai_public_projection.json的事件窗口及已登记主/前身CIK，不改变财务定义。Paramount FY2025窗口为2024-01-01至2025-12-31，当前CIK2041610有4份、前身813828有31份窗口内8K/8K-A；已知缺9份前身8K正文及对应头文件，共18件。完整URL与原清单证明见registered-events-discovery-first.json。当前主体4份不是完整范围。

normal_source_requirements逐份核对清单CIK、相关历史范围及重复申报，沿既有请求核验列出原件/头文件；元数据缺失或错主体仍未闭合。11项来源测试PASS22.116s，包含旧8项回归及主/前身窗口、缺前身清单、错CIK三个新增检查。没有把前身财务与当前财务合并，也未生成事件指标。

## 受控获取检查

本轮范围会改变有限SEC出口的URL发现集合，因此重新运行完整SEC材料，PASS94.031s：既有HTTP/零重试/失败隔离、来源登记、原生A08及冷读保持；新增第三笔RECORDED前身头文件请求被接受，其他未声明公司URL仍拒绝。前身测试响应是明确的opaque测试字节，只证明传输范围，不授事件内容或真实获取信用。所有原始测试目录、请求、响应与终态都保留。

原测试已断言模拟账本3条，但打印摘要遗漏更新，仍显示旧字面量2。sec-summary.json与原日志没有覆盖；registered-events-count-reconciliation.json独立重读证实3条，测试报告代码已改为读取实际账本。这是报告输出修正，没有再跑未改执行。真实全局调用仍provider/paid/SEC=0/0/13，未受影响。

当前工厂→WB-3禁网接线PASS36.219s；V15闭包5577c514/371，新SEC/provider接线绑定本轮代码和证据。静态语义/扩展性通过。已有未受影响快速证据按原版本复用，不写成新head全量执行；新CI按实际Checks。独立审阅仍未覆盖本新增模块，自查及CI不能替代。

## 还原与下一动作

材料包含2054个路径/70个唯一对象/10819246压缩字节；全部压缩对象读回核对SHA/size，已有仓库引用亦核验。实际还原原生A08测试包后，Python3.9禁网冷读13条记录通过，仍RECORDED_TEST_ONLY。完整路径映射在material-index.json，主文件SHA见MANIFEST.sha256.json。

```bash
PYTHONPATH=scripts python3 -m unittest tests.vnext.test_normal_source_requirements
SEC_ACQUISITION_MATERIAL_ROOT=<新外部目录> PYTHONPATH=scripts python3 -m unittest tests.vnext.test_continuous_sec_acquisition
python3 restore-document-material.py --evidence <本目录> --repository <PR43仓库> --output <新外部目录> --prefix registered-events-sec-wiring/native-
/usr/bin/python3 cold-recorded-acquisition.py <新外部目录>/registered-events-sec-wiring
```

提交后alignment通过及同一PR推送后，沿原SecHttpClient、不可变attempts、日志前缀与固定总账逐笔获取18件已声明缺失原件，预计累计SEC31/80。无需新预算申请，不重新下载已有可验证原件，不自动重试；402/UNKNOWN/来源真实性失效暂停受影响调用并封存，其他失败永久计数。原13个slot、已关闭额度及历史失败不改。

获取后仍须把完整已批准事件窗口/两CIK来源接入既有Claims、Calculator、普通Run及回读。这里不是6事件完成、完整390或生产验收；B01收入/B03 EBITDA的财务接续范围仍另行核对。继续B13/D03D04、390、更新、发布/故障回退恢复及旧入口退出，模型凭据和模块独立审阅按实际依赖登记。无Ready、合并、采纳、部署、active或长期运行许可。
