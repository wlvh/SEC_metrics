# 原110的一次受限恢复

用户已正式采用所附GPT-6 Pro第五节，确认充值处理完成并授权110一次新执行；真实GitHub代登记见approval-comment.json/comment5775635612。它不是代码APPROVE或生产许可，也不增加240/240/80上限。原根、binding和初始化锚点不变，原110继续HTTP402/FAILED_TERMINAL/1-1-0，调用前累计61/61/49。

## 实现边界

continuous_recovery_110将固定评论中的根/binding/110 intent/terminal/业务digest绑定到原账本的新recovery-110.json。LIVE登记和调用前核验真实GitHub评论；离线读者核验已绑定的原评论。没有本地approved布尔值、新账本、金额检查或自动重试。

snapshot保留原110停止；仅该业务请求可在claim中获得一次例外，新intent记authorization_id，申领日志追加即消费机会。snapshot允许该唯一、有授权的新重复，但不允许第三次、无标记重复、别的失败或新停止被消除。追加与进程间竞争沿用原目录flock，半写申领仍拒绝继续而不释放机会。

恢复后的完整登记还须区分历史失败和当前失败。只有经账本验证的授权后继成功，才能将原HTTP402移入recovered_http402_failures；原intent/terminal/wire及授权完整保留，冷读核对其链接，当前结果只消费新的成功。无恢复记录时默认结构和旧路径不增加此字段。

## 验证

- ledger-final-tests.log：19项账本/授权检查通过，包含无授权、一次申领、并发/重启/半写、新停止、旧文件/计数及真实评论来源拒绝。
- offline-wiring.log：实际Enphase工厂/同一110业务摘要、禁网模拟官方opener、旧402→授权新claim→原生成功→重读/成功复用，32.001秒PASS；无真实调用。
- offline-wiring-registration.log及offline-summary.json：增加完整六组登记和读取器检查，101.519秒PASS；7个录制槽保留1失败+6成功，未重复大Run/发布演练。
- complete-small-tests.log保留初始兼容失败：旧合成集合测试未提供intent，收集器增加的无条件读取造成两个失败。随后只在账本存在恢复记录时读新增恢复信息，旧默认回到原路径；final-small-tests.log当前26项通过。此修正不改变有恢复记录时的处理分支，current-registration检查复用原录制收据而不重执行。
- before-recovery-invariants.json证明request_digest函数和列明共享/B13引用实现字节不变，并保存原110槽终态、binding、锚点及申领前缀摘要。真实执行后核对旧数据与累计。

独审/当前接线收据及真实执行结果分别登记，未发生之前不写成功。D03不调用，增额决定暂缓，基础缺口至少39；主CI35716887065已成功，35716887021为参考表工作流，不重跑或改时限。
