# B13 内容拒绝、规定范围不可得与适用性接线（开发中）

本轮从 6c07fc1 恢复，同一分支与 Draft PR43。v4 修后真实请求60正确保留59的 Texas 会计政策；随后61–66逐请求原生接受，67因把事实449引用为0而失败。v5以真实来源编号作为压缩行的键，保留单独原始顺序；69个请求无损覆盖81个来源单元。68修后引用正确，但仍把制造税收抵免政策归为产能定性、把税收抵免余额归为借款额度。原生执行成功不等于这些含义正确；执行者内容核对拒绝68，原请求、响应、Candidate/Evidence及成功终态不改。原件见 `../b13-source-indexing/`。

新增9次真实调用后累计provider/paid/SEC为33/33/35，剩余207/207/45，无UNKNOWN或停用通道。**B13受影响真实调用已暂停**，不因离线接线通过而自动恢复，不对同段继续改提示抽样；D03仍等待6e5定向独立模块报告。预算与B13定义的原批准不撤回，其余安全开发继续。

新增内容检查是两个有限拒绝条件：仅有税收抵免、没有产能或产量陈述的原文不能被当作产能；仅有原生数值引用的货币额度角色，必须有既有原生概念和货币单位共同建立的借款额度证明。它们拒绝实际68及其拆分反例，不是一般语义正确性的证明，也不把其他标签/关键词当作正向准入或全申报缺失依据。完整来源集合和跨请求产量/产能检查保留。

`capacity_text_results` 在确切完整判断集合、没有相关提议、完整原件及有效Review同时成立时，可以构造有据不可得的原生非数值结果；公共行显示 `NOT_AVAILABLE_SEC`，按原件逐份附检查范围记录，不编造来源引文。该分支只完成合成无相关披露原件的Evidence/Review/结果/投影开发验证，未取得Ford/Enphase真实不可得结论。

`capacity_run` 按既有批准公司集合处理适用性。八家范围外公司从实际保存的年度输入自动完成隔离OPEN Run与公共行，均为 `N_A_STRUCTURAL`，零模型/SEC调用；不扫描产能、不声称未披露、不依赖人工审核或模型输入登记。Ford/Enphase不得进入该分支。Run从批准政策和公司登记重算全部原件/记录后，只对确切该分支使用批准公司范围；一般Spec/traits规则不放宽。新增反例将合法不适用记录替换成重新签名的披露缺失结果，必须拒绝。

当前仍未完成适用公司的完整真实B13、数值配对原生分支、D04原生、D03内容回归、390、正常更新、统一发布/恢复和旧入口退出。所有开发结果均无Ready、合并、正式采纳、部署、active切换或长期生产权限。

已完成的前一内容检查版本：21项来源/文字/账本检查11.372秒；B13实际工厂禁网接线14.758秒，D04接线回归12.837秒；记录响应完整原生Run167.325秒，106fast86.613秒，原普通V14场景112.606秒；Python3.9复制包禁网冷读通过。`provider-wiring.json`与其压缩材料绑定该版本a0e187b，不能替代其后适用性改动的证据。最终版本检查与材料另附，不提前记PASS。

最终适用性增量版本：15项来源/文字/适用性检查32.077秒，107个fast套件入口85.293秒，完整记录响应原生Run171.751秒，原普通V14回归108.985秒通过；B13/D04禁网接线14.786/12.738秒，绑定4e6105c99e3d1741cbf72d9a4c0e71ee175740e6f3de6dc4c40a149b990ac95d。八个实际来源不适用结果见structural-summary.json，Python3.9复制包冷读见final-cold-summary.json。final-provider-wiring.json只证明当前离线接线，不自动解除B13内容路线暂停。

`native-material.tar.gz`保存完整记录响应原生材料及八家公司结构性结果的运行时、来源、Run和公共行，6218个路径由1078个唯一对象恢复，全部对象已读回校验。用`python3 docs/evidence/issue28_continuous/b13-content-guards/restore_native_material.py /absolute/new/root`解包；解包后的冷读另记。记录响应没有真实provider信用，八家公司结构性结果不依赖模型；包内没有生产执行。

已实际解包全部6218路径/1078对象；解包后的记录响应Run及一个结构性Run均在Python3.9、禁止网络/子进程条件下冷读通过，见extracted-cold-summary.json、extracted-structural-cold.json及extracted-native.log。静态语义和公司特例检查通过；这些检查不是正式批次验收。

复现命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python3 -m unittest -v tests.vnext.test_capacity_applicability tests.vnext.test_capacity_text_results tests.vnext.test_capacity_semantic_review
PYTHONDONTWRITEBYTECODE=1 python3 tools/run_fast_tests_v2.py --jobs 2
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts B13_NATIVE_RUN_MATERIAL_ROOT=/absolute/new/material python3 -m unittest -v tests.vnext.test_capacity_run_material
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts NORMAL_V14_MATERIAL_ROOT=/absolute/new/v14-material python3 -m unittest -v tests.vnext.test_normal_run_v3_material
python3 docs/evidence/issue28_continuous/b13-content-guards/restore_native_material.py /absolute/new/restored
python3.9 docs/evidence/issue28_continuous/b13-content-guards/cold_read_recorded.py /absolute/new/restored/final-native /absolute/new/cold-summary.json
```

首轮引用恢复顺序、结构性reason code、空文本结果接线及测试捕获异常类型的失败日志在initial-failures，后续同问题修复和最终结果分别保留，没有把失败日志改成通过。
