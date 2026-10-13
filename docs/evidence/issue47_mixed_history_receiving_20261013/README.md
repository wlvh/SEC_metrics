# 原酒店任务消费已接收混合范围入口

实际main293e495f已包含PR241/2b121ee9。接续原[57b218b6反例](https://github.com/wlvh/SEC_metrics/blob/57b218b6ffc67ca1a6d6bdbf711ebb5c289d136a/docs/evidence/issue47_history_mixed_scope_20261013/README.md)：同一现有Marriott五年酒店任务、FY2024 B10+D02，以前整体前置拒绝；本次不新建任务、不重算财报。

使用现有company CLI，真实hotel工厂、shared计算及Calculator入口均以profile禁止，socket也禁止：混合检查3.312s/exit2、同输入复跑3.128s/exit2；B10均NO_SOURCE_CONTENT_CHANGE，D02均PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED，没有D02结果目录或Result ID。原60个结果文件逐字节保持；原152个state增至156，仅普通检查记录增加。

独立进程results/CSV2.233s/exit0，156状态文件不变；11行包括十个原酒店结果和D02 FY2024无结果限制。十个酒店坐标的value/unit/start/end/fullResultID与上一份已提交导出完全相同。不是重新验证酒店表格阅读或新财务计算，也不把D02空值当业务不适用/无诉讼。详见`actual.json`。

初次尝试导入旧developer driver会触发它的顶层argparse，尚未进入处理就退出，保`actual.log`；更正为带main guard的本次驱动后实际执行，见`actual-fixed.log`。未改公共代码或因harness问题制造重复计算。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 \
  docs/evidence/issue47_mixed_history_receiving_20261013/verify.py \
  --state /absolute/existing/hotel-state \
  --output /absolute/new-output/mixed-history \
  --receipt /absolute/new-output/mixed-receipt.json
```

驱动只用于上述已存在五年Marriott任务，任务source_root从company-task.json读取，不替换来源或任务身份。第二次复现须新输出目录。所有来源/旧结果只读；新普通检查记录由现有controller写入，未手改旧状态。

指南同步接收方在PR241指出的第355行旧“未实现家族整批拒绝”说明，并将取得版本明确为293。默认39项是请求集合，不是完成声明；未知/重复/空指标前置拒绝仍按公共实际已验反例保，本轮不为纯说明重复这些输入或财报。

新增真实SEC/provider/model0，无Run/业务接受/Ready/作者合并/active。完整五年指标与在线来源接续责任保。D02完整业务provider已另有固定Git接口，待公共入口消费；本记录只验收混合范围普通状态接缝。
