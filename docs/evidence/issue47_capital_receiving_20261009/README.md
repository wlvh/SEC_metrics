# A01/A02 历史银行资本比率接收

独立从PR76/1e538643接续，原PR71/75/76范围不扩。A01 Tier1及A02 CET1均使用所选申报的母公司、标准法范围，单位ratio、实际年末时点。现有normal_accession_results检查器、Calculator、公司控制器/保存/读口不改或另造；历史薄case只选择期间、准备原件与适配记录。日期版GAAP/SRT/DEI只有既有受控release suffix在旧检查明确拒绝该版本时才使用；现代年度版的原policy对象保持。不是任意regex或公司/年份特判。

真实同公司CLI JPM FY2021–FY2025共10位置，与已有原件阅读值/单位/时点零差异：A01分别.15/.149/.166/.168/.155，A02分别.131/.132/.15/.157/.146。首次FY2021两项95.476s、后四FY八项240.339s；禁止选源/原生检查/计算的后四年复跑7.566s，计算0、80保存结果/指针不变；独立进程读十位置0.097s，CSV出处保持。最初FY2021供应受控历史namespace policy；后续现代policy不变修正不改变该年实际policy/值，不重读这一大型原件批次。剩余年度在最终代码下运行。

同一JPM FY2025真实混合A01/A02/B08 15.181s：旧两资本结果直接复用，原资本准备0、80旧文件不变，新B08按既定银行规则结构性不适用。Marriott25两个资本指标3.943s为N_A_STRUCTURAL，有来源/行业依据，不是金额0。当前模式分派、酒店/收入/流动性原factory及依赖保持；历史年度仍按独立指针保存，旧Run未原地迁移。

5项小构造原生文档实际进入同一检查器：母公司标准法纯比率通过；子公司、高级法、错主体/时点不能冒充母公司；USD/逗号数字不作为pure比率；伪namespace拒绝；现代年版保持原policy对象。构造数据无来源或业务信用。连同已有历史分派共16项0.031s、零skip，结构检查PASS并恢复副产物。准备源码、所用Spec与实际来源各自从程序/来源根读取，不复制整棵源/程序，不新建历史pipeline。

本分支仍是开发接收、未入main；具名扣留与新源/混合反例后续继续。原申报修订/继任金融主体暂无该族接收，不默认放行。普通公司命令如下：

```bash
python /path/to/SEC_metrics/tools/vnext_company.py run \
  --company jpmorgan_chase --period fiscal-years \
  --fiscal-year-start 2021 --fiscal-year-end 2025 --metric A01 --metric A02 \
  --source-root /saved/sec/source-inputs --work-dir /writable/jpm-state \
  --output-dir /writable/jpm-csv
python /path/to/SEC_metrics/tools/vnext_company.py results \
  --company jpmorgan_chase --state-root /writable/jpm-state --output-root /writable/jpm-read
```

[主要验证记录](verification.json)和[原样CLI/控制驱动/CSV/出处/普通结果材料](consumer-materials.tar.gz)已提交。原模型35调用、SEC账本、旧Run/错误不改，provider/paid/SEC新增0，无新native Run或接受；不拿十个旧值一致代替整个#47完成。公共测试selector/CI由#28集成，不写第二套runner。

后续稳定扣留/局部失败接收：只复制已保存小状态（不复制来源/程序），以明确测试处理依赖触发A01重处理并构造源scope未决。15.182秒得到当前A01 CANDIDATE_WITHHELD，A02未变复用；相同输入复跑0.923秒PREVIOUS_INPUT_WITHHELD、准备0、保存文件不变。后续只选A02，独立读A01仍null/WITHHELD、requested=False，全部旧成功结果/指针文件留存，邻居A02=.146 ratio不受影响。该小状态人为冲突不代表JPM原件错误，不给金融结论信用。已消费原公共控制器/恢复/子集视图，没有新存储核心；此范围接收成立，main/线上来源/修订金融主体仍待。
