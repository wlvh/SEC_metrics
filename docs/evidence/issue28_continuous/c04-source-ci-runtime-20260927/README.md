# C04 来源材料 CI 单项时限修复

已推送`2f3a36da`的主CI `36257074760` 只有 saved-source material 作业失败，其余12项成功。该作业结果JSON指向新加入的`tests.vnext.test_c04_refresh_cycle.C04RefreshCycleMaterialTest`达到单项240秒限制（返回124），没有业务断言失败；见`ci-timeout-summary.json`。这不是源获取或C04语义失败，也不能写成主CI通过。

仅从该测试中移除一遍额外的旧Run重放；两版真实保存清单和Company Facts的四条录制SEC来源、两次完整`UPDATES_READY`、不同C04成功尝试/Result及前驱关系断言全部保留。旧Run可读已在原`c04-normal-update-20260926/`独立冷读材料及后来的真实第193—194槽禁网双版本回读得到实际验证，不需要每次CI重复第三遍。业务模块、需求绑定、收据、调用配置和资源上限均未变。

缩短后的相同source-material selector本地执行1项通过，180.047秒，日志`shortened-selector.log`。这给原240秒单项限制留出约60秒本地余量；CI环境是否在限制内，以新提交的远端终态为准，不把本地时间当作远端保证。新真实SEC/provider/paid调用均为0，原真实账本第193—194槽结果保持原身份。
