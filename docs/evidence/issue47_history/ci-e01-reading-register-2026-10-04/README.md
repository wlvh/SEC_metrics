# 四分片 CI 实跑暴露的 E01 阅读登记回归

四片提交 `4d6540ca` 的 run 37182511452 在 merge `afb3b7ee` / base `05d11df2`
上执行到 `tests.vnext.test_e01_eight_o_one_reading`，两条旧断言失败。
这是实际断言失败，不是 35 分钟取消，原完整分片报告和本地复现保留。
本地同一模块 15 项中恰好这两项失败，与 CI 相同。

原因是测试仍使用付费阅读前的登记形状：其允许来源集合没有已经登记的
`e01-paid-content-confirmed-read.json`，并假定 Pfizer 缺陷只有一个释放项。
原登记实际保留了先前扣留 Result 的精确释放，再追加付费完成且阅读为 1 的
新 Result/Run/closure；原零值和其他对象仍撤回。没有运行时答案变化。

测试现在核对完整五类阅读来源集合（从原子集断言改成严格相等），并核对
两个释放项的完整四元身份：Result、Requirement closure、Run 和阅读证据。
不删除来源检查，不按坐标泛化释放，不改登记、原答、失败、值或生产权限。
其它 source/spec 不互授信用的断言保留。

`python -m unittest -v tests.vnext.test_e01_eight_o_one_reading tests.vnext.test_paid_e01_reading tests.vnext.test_acceptance_identity`
最终 45 项通过，4.315 秒；其中包含付费候选阅读及跨身份/闭包拒绝检查。
`local-final-pass.log` 保存逐项结果。曾误写不存在的模块名的命令另存
`incorrect-module-command.log`，不计为测试通过或业务故障。
`vnext_mint_historical_requirement.py --check` 仍相等，封存模型包不包含此测试改动。

本改动只影响 saved-source 选择器中的这个阅读测试；快速层选择未变，复用刚完成的
181 入口通过记录。新的完整 CI 须独立执行，旧分片失败不被重标为通过。
新增 provider/paid/SEC 0/0/0，接受仍 909，原缺陷对象仍 104。
