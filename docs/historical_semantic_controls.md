# D04 历史原件语义对照

为验证“明确存在疑虑”和“历史疑虑已经解除”的解释路线，本轮在既定公司范围内选择 Enphase 2016、2017 年报的原始正文。保存的官方 submissions 元数据已提供唯一 accession、报期和主文件名；采集仍通过本轮有限总账、原 SecHttpClient、不可变 attempts 和来源登记，不经搜索结果直接赋予来源信用。

本对照限定为两份历史 primary HTML 和各自 SEC 头文件。原件真实性由原请求证据、元数据及头文件中的 CIK、accession、表单、报期、申报日期、公司名与正文封面共同核对。旧非 inline HTML 不借用或削弱普通 inline DEI 校验；正文复用既有分块解析器并保留原始字节位置。伴随 XBRL 不在这个对照范围内，不能作整份 filing 的不存在证明。

对照保留真实历史报期，但不虚构数值计算所需起始日期。`CURRENT_REPORT` 指所选历史报告的当期；它不意味着今天仍有/无疑虑。对照不进入最新普通更新或原生 Result，不授发布许可。

`tools/vnext_continuous_sec.py plan/capture --company enphase_energy --control-id <configured-control> --url <declared-url> --output <new-external-file>` 只允许当前声明的公司与原件依赖。已有可验证文件复用；原件不能通过 metadata-refresh 重取。模型 prepare/execute 使用 `--metric D04 --control-id <configured-control>`，依旧要求当前离线接线和固定调用策略。不存在新账户设置、费用金额门或长期运行授权。

两年各一件正文、一件头文件已真实获取，固定总账 SEC 从31累计至35；模型对照是否通过以原始响应及执行者检查记录为准。保存的“来源可读”、完整JSON或无保留审计意见都不单独证明 D04 语义正确。
