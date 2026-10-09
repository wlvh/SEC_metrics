# 本次原生更新的完整请求构造复用

补丁 `/tmp/sec_metrics_issue28_continuous/native-request-construction-session.patch` 尚未应用。3个运行文件（其中1个新小模块）及1个CI短测试文件，SHA/版本见report.json。没有干预原Ford进程，没有调用provider/SEC，没有改源表示、分组策略、请求字节、额度或重试。

## 实测原因

同一保存Ford完整source（call70）连续构造两次，均52 units→11 requests。第一次8.707秒；第二次带cProfile9.984秒，其中62次tokenizer.encode耗7.304秒。完整请求JSON共5,220,682字节、HTTP共5,626,828字节，两次逐请求逐字节相同。profile显示主要成本为相同完整上下文的重复measured_groups/fits分词，不是来源真实性或原生证据检查。

不能由此推断原2777秒全部来自这个函数。这里只减少已证实的重复构造CPU。

## 最小作用域

`prepare_registered_update` 在同一当前Requirement内打开短生命周期作用域；`source_requests` 仅在该作用域内、已支持的完整native source+固定reference格式上复用。每次来源/收据/当前意义验证仍照常执行；没有记录或复用模型响应、评审结果或执行信用。

输入key保留完整字段、source_id、字典顺序、全部原Unicode码点。NFC/NFD可具有相同canonical source hash，仍分别构造并保留各自原字符。不忽略source_id：其token数变化或临界分组变化仍走原构造器。所有输出以本地immutable bytes保存，每次返回独立解码对象；调用方修改返回对象不会污染后续结果。非普通JSON类型（如Decimal）不引入新序列化，直接走原构造器。

每次命中仍核对实际执行规则文件hash/size、模型配置、格式常量、输出/上下文约束、分词器资源/版本与对象状态；不用mtime。规则变化锁死本作用域，即使恢复旧文件也不恢复命中。最多2份完整输入/输出、64MiB；超出时走原构造，不新增来源大小拒绝。退出清空，下一次更新从空状态开始。

复用现有FileBinding纪律；已有OfflineExecutionSession绑定一个DerivedAsset及子任务/最终表格重放，直接套用会引入无关资产或错误信用，因此仅增加这个专用小作用域，没有通用缓存平台或新持久化状态。

## 独立固定副本验证

主运行字节继续变化后，测试转到单独固定runtime，原规则验证器在其UNFROZEN V15绑定加入新模块并验证（闭包6db37be2…）。不依赖main保持冻结。

- 最终直接bytes对照轮首次8.996秒，第二0.104秒、第三0.103秒。每次全部11请求的JSON与HTTP hash/字节均匹配原未缓存基线。缓存12,363,551字节；退出后清空。
- 10项独立固定副本反例/正例通过，5.507秒；覆盖原字符、身份/内容/字段顺序变化、返回对象突变、实际规则文件变化/恢复、tokenizer对象truncation及版本/格式约束变化、源真实性仍重复检查、作用域清除和数值类型fallback。
- 新CI文件 `tests/vnext/test_native_request_construction.py` 不依赖固定用户source-inputs，使用合成source工厂；需要既有pin的tokenizers==0.22.2。实测Ford大source单独保留在measurement材料，不能把合成检查当真实业务结果。

早期探针因误用packed blocks结构、少填测试authority/policy及将canonical输出用于原字符断言而失败，日志保留；修正的是探针，未改请求协议。当前完整HTTP字节等价与实际规则变更检查分别验证，不以某个hash相等代替所有检查。

仍须根代理独立审阅、在主当前绑定补验，以及实际Ford既有收据0调用更新验证。此小补丁不替代原来源/当前审阅/Run/最终390验收。

## 独立审阅后的类型碰撞修复

原7724341版本被根代理复现：字符串键"1"与整数键1的json.dumps结果相同，导致本应被原构造器拒绝的输入命中缓存。原探针和旧patch保留。现仅递归的精确内建dict/list/str/int/bool/None且所有dict键精确str可进入缓存；tuple、容器子类、Decimal等全部走原构造器，输出非plain也不缓存或转类型。

独立固定副本13项测试7.025秒通过；原整数键负例现在由原构造器拒绝且cache hits为0，tuple/list与容器子类都不借已有plain缓存。修后Ford完整11请求的JSON/HTTP再次直接bytes==未缓存构造；首次8.937秒，命中0.119/0.118秒，原源和旧记录均未改。最终patch身份见report.json；真实调用仍0/0/0。
