# 完整独立运行时：新年度 D04 原生记录执行与历史

**通过。** 这次运行使用包含本轮三个补丁的完整独立运行时，执行器保存的 runtime 文件清单逐字节覆盖实际9个改动文件。不是把先前 overlay 调用旧核心的材料升级。确切实现、闭包、原始调用和全部本地材料索引见 `report.json`、`full-local-material-index.json`。

## 实际经过的链

1. 保留全部原FY2025 Enphase基线，另提供明确的完整微型合成FY2026年报、对应新申报元数据及同accession财年标签事实。原 `recorded_sec_session` 通过正常声明URL、`SecHttpClient`持久化、同一本recorded账本和创建者来源登记取得三份新输入。
2. 当前完整来源工厂自动准备新D04请求；新有限helper执行**1个真实WB-3记录测试调用**。响应是明确的模型替身数据；原请求、plan、wire、响应、acceptance、terminal和当时执行文件保留在 `bound-recorded-provider/`。该目录不是provider真实调用证据。
3. 原登记器复核完整请求和当前内容检查，创建schema2输入。随后原普通更新入口生成native Run与公共行（`native-run/`、`public-rows/`）。合成输入没有持续经营疑虑，严格定义域无披露分支经原专用检查进入普通成功历史。
4. 再次触发复用同一登记与Run；给模型执行和Run创建函数设置“若被调用即失败”断言，两者均未触发。破坏副本来源账本后保存INPUT_FAILED，前次成功和原年度值仍保留；恢复原字节后再次NO_SOURCE_CONTENT_CHANGE。所有原执行文件hash保持一致。

最终recorded账本为 **provider/paid/SEC槽1/1/3**，重复/失败保留/恢复阶段没有新增槽。实际外部调用 **0/0/0**，新增真实公司—指标结果 **0**。源期间2026仅是合成测试，不是真实Enphase FY2026披露，也不是任意输出标签可合法无披露的证明。

## 原始错误与修复范围

- 较早overlay材料先暴露正常来源发现未接 `FiscalYearLabelError`：新年报已取得但同accession Company Facts未到，发现函数逃出，阻止继续取得CF。单列两行 `native-new-year-discovery.patch` 纳入既有未决处理；不宣布完整、不泛捕ValueError。原2个recorded SEC成功及原错误保留；之后原capture确实继续获得CF。
- overlay材料还保留测试生成器的浮点/指数序列化错误，原始坏测试输入不重写，随后以严格Decimal生成的新记录继续。overlay最终167.400秒通过，但其调用捕获的是旧bf71核心，单独解释。
- 新独立运行时首次完成3个recorded SEC和1个recorded provider及登记后，Run安装因空本地Git缺少HEAD中的继承foundation receipt而失败。`before-local-receipt-head/`保存原EXECUTION_FAILED。仅向独立Git写入原固定SHA验证的继承receipt本地提交（无clone、无借用对象、工作树运行字节不变），直接复用原provider成功继续。没有重发模型请求。恢复后完整Run/history验证145.752秒通过。

普通UNFROZEN V14闭包 `47bde4438bdf3297d83c7cd27ac06ff189b310cf179984e0885e3bf16e34bdfa`；连续UNFROZEN V15闭包 `5cc1b460f3b488d96ee4db8a102264a5195b1b72ae4cace71ae7e822a935b513`。仅独立副本的这两个开发快照按原helper重绑，冻结parent-v10 89文件逐原index核对，不改历史。12项短测试也在该运行时自身通过。

## 证据边界

业务来源工厂、单元分组、context检查、WB-3 controller、账本、Evidence、登记、Calculator/Run、公共投影和更新历史均用真实实现，没有替换成返回成功的double。替身仅为明确的SEC响应字节和模型响应字节；全程禁止网络。重复阶段另装禁止执行/创建的负向断言。

这次直接验证新有限native helper→普通更新历史；**全39来源发现宽度和刷新协调器真正新输入的正向完整运行仍分开验收**。跨source部分旧组复用仍未实现并在新调用前拒绝。B13 LIVE暂停、D03未接、统一发布/生产权限均未改变。本材料不构成全PR批准或Issue28完成。
