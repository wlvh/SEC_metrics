# PR43 B13 CI作业时限修复

起点 ed8bf11 的 CI35245710633：capacity native在15分钟、capacity program-role在20分钟被取消，其他11作业成功。program-role在8346c32约15分钟，后续撞20分钟上限，按用户已核对事实处理。

本次仅将两个B13作业总时限改为30分钟，保留原步骤、测试及断言；不改变模型请求的120秒限制或预算。没有生产架构/指标含义变化。不操作PR52。

本地唯一实际计时进程由launch.json登记，nohup运行run.py，结束输出run.log和result.json。环境为隔离Python3.13.5及仓库哈希固定tokenizers0.22.2；原临时tokenizer目录已缺文件，先行空nohup未启动测试、空日志不计测试。与CI Python3.14分别标记。未复跑bf71或Ford大测试。

实际PASS：测试604.545秒，进程605.007秒，6组录制响应、完整Run/公共行及3类重签攻击。新增0/0/0。日志只在完成后读取一次tail -n80。未运行已通过的其他大测试；原native作业使用此次push后的CI检查，不冒称本地重跑。
