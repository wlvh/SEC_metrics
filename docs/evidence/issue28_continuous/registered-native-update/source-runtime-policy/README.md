# 来源根与规则根的显式分离

独立补丁 `/tmp/sec_metrics_issue28_continuous/native-source-runtime-policy.patch`（SHA见hashes.json），不包含B13角色守卫。

根的真实固定source-inputs准备首次缺catalog/r6/semantic_source_v1.json，记录未覆盖或删除。本补丁在显式ordinary_registered/current_runtime路径从当前ROOT读取semantic/capacity/fiscal-label规则；原申报、正文、company registry与request log仍从source_root读取。旧默认仍要求原source/installed root规则，不能自动fallback；没有复制规则目录到来源根。

真实只读准备：Ford FY2025 D04完整1文档52units/11请求，25.344秒；Enphase FY2025 B13完整1文档29units/6请求，17.881秒。固定来源仍缺semantic_source_v1规则文件，两个准备成功，0/0/0、无新Run/来源/结果信用。第一次工程probe用了不存在的ford_motor逻辑ID导致COMPANY_NOT_UNIQUE，保留原日志；按registry的ford_motor_company更正后通过。

新测试验证三工厂显式当前路径越过缺失source规则后仍读取给定source_root，旧默认缺规则仍拒绝。真实完整正常更新仍由根继续验证，不把这个输入准备正例当作全链完成。
