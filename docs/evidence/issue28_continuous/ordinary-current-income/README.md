# 接续主体当前收入期间与原年度长度守卫

Paramount原HTML、XML及Company Facts显示当前主体报告期2025-08-08至2025-12-31，共146天：收入12269m、营业利润-95m、折旧摊销590m USD。前身2025-01-01至08-06收入16622m单独列报，不能相加成当前全年收入。

原B01/B03 Spec要求300–400天，现按真实原件期间调用原Calculator，两项原生OPEN及公共行均为NOT_MEANINGFUL/ANNUAL_DURATION_OUT_OF_RANGE，值为空，B03仍复用B01观察及依赖结果。不是没有披露、不是N/A，也不是完整全年收入。旧Spec、300–400天守卫和旧源记录不改。

## 当前输入的证明范围

新ordinary_income_input按原件官方GAAP概念、当前主体/申报、USD、无分部维度、当前财年结束及财年内报告期间选择原收入期，主HTML/XML期间集合一致，保留重复与其他报告期间；从最早当前起点取实际报告段，不取最大金额或手写日期。所有Calculator选中CF观察都逐项匹配原HTML/XML的期间、主体、申报、金额及精度。没有跨主体拼接，也没有把原观察内容改成新数字。

PartIII修订不是自动通行证。本组件复用完整说明/原申报身份/主体、未勾选错误更正、只含治理原生事实、无新财务报表声明、完整财务更正/有界条件性追偿检查，再增加收入/营业利润/折旧摊销相关更正和财务报表标题检查。该新输入类仅用于B01/B03，没有原地扩大旧余额或债务许可。当前原件及修订通过；来源或更正疑点仍拒绝。

## 验证和首次过程记录

5项来源/观察检查PASS22.541s；金额不符、前身期间、未绑定原件变造均拒。收入更正反例进一步升级为真实修改修订HTML、重建Blob/Reference及scope，PASS24.427s。两个原生及公共行、B03依赖通过。保持真实观察但重新签名为“短期收入当全年”或“前身+当前拼接”的两个结构合法图被原件重算拒绝，PASS30.145s。Python3.9独立目录冷读B03共21记录、包含B01/B03结果，通过实际还原后再冷读。

早期纯Calculator探查不授当前修订准入；原ORIGINAL_STATEMENT_VALUES的WITHHELD诊断保留。初始源级组件把新增观察检查写进已标识packet，发现后在原生绑定前改为另存income_observation_checks，原income_input_id不被追加内容破坏；初始组件JSON只作开发过程，不充当最终原生证据。新原生材料与当前检查分开保存。

原normal_zero_ai_results对应分类方法单独回归PASS63.099s，其余未受影响证据按原版本保留；SOURCE_TESTS加入新5项，不写成已在CI完成。当前factory禁网PASS37.779s，SEC获取/准入/计数代码未变，复用既有94.031s材料，差异在current-income-reuse-audit.json。新后继闭包130d796a/373，当前门控及总账重读0/0/31，无新增真实调用。

## 审核包与恢复

735个路径/135个唯一对象/10646993压缩字节均读回校验SHA/size，已有仓库同字节引用亦核验。原件、初始纯探查/作用域限制、修后原生与重签反例、factory、日志和源码绑定均在material-index映射中。income-coordinates.json和verification-summary.json为入口；MANIFEST为主文件逐项索引。

```bash
PYTHONPATH=scripts python3 -m unittest tests.vnext.test_ordinary_income_input
CURRENT_INCOME_NATIVE_BATCH=<两项原生目录> CURRENT_INCOME_ATTACK_ROOT=<新外部目录> PYTHONPATH=scripts python3 -m unittest tests.vnext.test_current_income_run_material
python3 restore-document-material.py --evidence <本目录> --repository <PR43仓库> --output <新外部目录> --prefix current-income-native-first
/usr/bin/python3 cold-current-income.py <新外部目录>/current-income-native-first B03
```

当前两个非数值结论使用原保存来源，不提升为本轮新获取信用。自查和CI不算独立审阅，新版本CI以真实Checks为准。继续B13、D03/D04、其余390、正常更新、发布/故障回退恢复和旧入口退出；模型凭据及未覆盖独立模块审阅仍分别登记。未授Ready、合并、正式采纳、部署、active或长期运行。
