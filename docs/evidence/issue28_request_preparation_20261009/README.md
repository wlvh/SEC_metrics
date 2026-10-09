# 离线语义请求准备

起点为 main `4a03f22393182eb642a0472f1480354ff430267c`，复用 PR66 固定提交
`ddcc61920d608d5ede64458bb02f3f166953f3df` 的 RequestLimits、请求构造、计量和用量检查。
仅新增一个开发离线函数，不接真实调用。没有重新处理公司原件，没有模型答案进入回归。

新增接口在 `scripts/vnext/continuous_request_context.py`：

```python
from vnext.continuous_request_context import prepare_development_request
from vnext.request_limits import RequestLimits

body_bytes, measurement = prepare_development_request(
    semantic_request_dict, limits=RequestLimits(output_tokens=8192))
```

同一个 limits 对象传给一次既有 request_body 和一次 measure_request。必须有参考
tokenizer；完整 payload 超限、输入加输出预留超 context、配置类型错误及缺 reference
均抛出明确 ValueError。返回实际完整请求 bytes 与参考计量，不创建 SemanticRequest、
读取调用权限、claim 账本或发送。服务仍为既有 DeepSeek/deepseek-flash/Chat Completions。
默认保持 4096/200000/8388608，旧 wire/digest 和完整 measurement 不变。

RequestLimits 与原七例测试精确复用 PR66 字节。continuous_semantic_calls 仅改变
request_body、request_digest、usage_error 和必要 import；prepare_requests、SemanticRequest、
build_plan、执行函数及权限工厂 AST 均与固定 main 一致。usage 未传 limits 时保留原行为；
显式传 limits 才增加输出上限检查。未知 usage/cost 仍为 None。

回归直接读取仓库已有 original68 B13 的实际 semantic-request、wire journal 和 intent，
没有复制大型原件或读取 assistant-output。默认完整 body 为 145209 bytes，SHA256
`700a5e7cd37ab8dd1d0095f68505bd05947d9345d94a6c17ac99fb246a8d0da7`，
与历史 wire journal 一致；digest 与历史 intent 一致。完整默认计量与固定 main 的原函数
逐字段相等：input 47927、output reserve 4096、context 52023。
显式 8192 的同一来源 input 47927、context 56119。额外 Unicode 探针只放在测试副本中，
确认组合字符、原文、提示、来源和 response_protocol 全部保留且输入字典不被修改。

定向命令：

```text
/private/tmp/issue28-company-c02-venv-20261006/bin/python tests/required_unittests.py tests.vnext.test_request_limits tests.vnext.test_development_request_preparation
```

2026-10-09T13:45:52.560865Z 开始，14 例、零失败/错误/skip，unittest 0.567 秒，
命令 wall 0.816116 秒。日志为 directed-tests.log。七例新增回归覆盖保存 wire/default、
同 limits 一次构造计量、完整 Unicode/source/protocol、输入加输出边界、完整 payload
边界、错误配置、缺 reference；每例均拦截并断言真实工厂/计划/ledger claim/执行/transport/socket
零进入。范围检查和绑定读取见 compatibility-and-binding.log。

明确未解决：旧 V14 execution_authority 同时绑定 continuous_request_context.py 和
continuous_semantic_calls.py 的旧字节；固定 main 与这两条绑定相符，本候选已经不同。
request_limits.py 也未加入旧 SEMANTIC_RULE_PATHS/执行文件绑定。本次没有改 requirements、
bindings、ledger 或工厂，不能用本候选旧 prepare_requests 宣称真实路线已接通。
旧 factory 仍不接 limits 参数，默认 request_body 仍为 4096；8192 仅为显式离线构造计量。

这是参考 tokenizer 的请求资源检查，不是 provider 实报用量、模型抽取正确性、公司指标
接受或生产采纳。新 provider/paid/SEC 调用为 0/0/0；无探针、账户操作、commit 或 push。
未运行全 CI/公司演练。可选的 test_continuous_request_context 模块在当前 main 中不存在，
未创建或冒充运行它。只修改授权五个源码/测试文件和本证据目录。

## Parent receiving adaptation: preserve old factory bytes

The child's full increment is retained in844055a2. To prevent the observed old
V14 binding regression without adding a new proof/approval chain, the parent
moves the resource-aware pure functions to explicit development_request_context
and development_semantic_requests modules. request_limits remains exactly the
PR66 class. The two old bound modules are byte-identical to main4a03 again;
requirements and ledger are not changed. Existing live factory still uses its
original4096 configuration. The new modules never enter that factory or gain
call authority. Tokenizer loading/validation remains the existing module's
implementation; body/digest/usage helpers retain the child/PR66 code.

Tests now import the explicit development modules. parent-final-tests.log:
14 pass/0.535s/zero skip; saved68 wire/digest/default identity and Unicode
coverage remain. Parent adaptation first omitted sha256_bytes import; the
NameError in parent-successor-tests.log is kept and fixed, not hidden.
parent-binding-preserved.json proves both old modules still match the exact
old V14 entries. Scope-specific CI installs the existing pinned tokenizer and
runs both modules; no new platform, real request or retired-proof requirement.
This is parent work, not part of the child's51tools/3messages result.
