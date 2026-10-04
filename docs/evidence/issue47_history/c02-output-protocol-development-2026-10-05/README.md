# Ford：让新的回答直接使用可逆的紧凑结构

原 Ford FY2022 独立回答的54事实、3未决，按目标 tokenizer 计量为4448 token，超过4096；原回答、来源支持核对及 F35 前董事遗漏均保留原状。先前将该旧答无损转换为3570 token，只证明表示可以缩短，不能证明模型可以在额度内生成完整回答，也不恢复原答信用。

这次准备的是一个**新精确问题**。它只替换原 system prompt 的输出表示段，完整的任务说明、年度/时间/身份边界、64事实上限、4096输出限额、完整来源解码说明及 user 内容均不变。所有4912文字块、5195字典条目、402张表的模型输入字符串逐字相同；没有提供冻结参考、旧答或遗漏姓名。构建器只读取原请求，不读取任何回答。

新请求 SHA `1acfed0cc294bc359eef69421e49dfff83c2b2b15dc74c1ac8e109a72dba0dae`。计量为 **168396输入 + 4096预留 = 172492**，原上限200000；相比原168124增加272输入 token，用于完整解释输出格式。模型、temperature、thinking、stream及其他请求设置不变，计量仍是固定参考格式的离线结果，不是服务商实际 usage。

输出保留每项陈述、引用、时间和未决问题，用两个字典省去重复文字。比如类别字典的第0项为 `board_membership`，时间字典的第0项为 `CURRENT_IN_FILING`，则一行 `[0,"某人任董事",[3,5],0]` 解码为原有四字段事实对象。类别和时间只是字符串引用，不能作为来源或新事实；`unresolved` 仍是原对象。示例不表示本申报实际存在这项陈述。

`tools/c02_development_response_codec.py::expand` 可以无损恢复这些对象。新增 `check_development_output.py` 对本提案作更严格的开发检查：类别必须属于原九项，引用只能指向原 B0–B4911，未决对象字段及引用完整，整个原始回答按固定 tokenizer 计量不超过4096。它保留所有字符串和顺序，不裁剪、修字、归一化、重发或接入任何答案。即使此检查通过，来源支持、角色/时间准确性、完整性、各媒介解释和独立生成仍需另行判断。

验证包含18个形状/JSON反例：错误字典索引、布尔值冒充索引、重复字典、额外字符串字典索引冒充来源、未知类别、空陈述/时间/未决、越界来源、65事实、额外字段、重复JSON键、非JSON数字、截断JSON，均明确拒绝。一个23055 token但语法有效的合成回答经真实检查CLI在保存输出前被原4096限额拒绝，原合成输入保留。正例只检查原字符串空白、引用和未决对象保留；它不是对Ford原件的回答试验。反例检查禁止创建网络socket。

`proposal-materials.tar.gz` 保存精确新请求、提示、计量、变更边界证明及合成检查材料和日志。成员及归档字节/SHA见 `manifest.json`。先前精确原请求仍从已提交 `evidence/issue47_local_inputs/c02-table-context-v2.tar.gz` 恢复到 `work/issue47-inputs/c02/ford_motor_company-2022-12-31/`；本提案不依赖旧虚拟机。解包到新目录后，使用原请求运行构建器，精确新请求、提示、计量和提案应逐字节一致；重建结果见 `rebuild-verification.json`。

```bash
work/issue47-venv/bin/python \
  docs/evidence/issue47_history/c02-output-protocol-development-2026-10-05/prepare_output_protocol.py \
  --code-root . \
  --original-request work/issue47-inputs/c02/ford_motor_company-2022-12-31/request-body.json \
  --original-sha256 146142032aea59dcc713cd07e6dfd1a44aaa0b8083ce8a5bcbc53115440b9f32 \
  --out <新开发目录>
```

新增 DeepSeek/paid/SEC `[0,0,0]`，新Run/接受0。原一次Ford子代理许可已经消费，**本新请求尚无新的独立子代理许可，也没有执行**。正式DeepSeek额度不因此增加。正常请求构建器和响应读取器没有接入新表示，旧模型包/旧答案/历史失败/接受登记不改。资格与角色评价仍待#28回复；图片及其他媒介缺口不会由输出结构改变消失。
