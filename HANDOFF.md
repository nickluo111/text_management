# Group A → 下游交接说明

本文面向 Search/Index（Group B）和 Trend/Application（Group C）。当前稳定的
跨组运行时协议只有：

1. `PreparedReviewReader`
2. `Tokenizer`

真实入口统一位于：

```python
from yelptext.interface import data_corpus_analysis
```

下游不要直接 import `yelptext.implementation`。implementation 内部可以继续
重构；interface 和 protocol 才是跨组边界。

## 1. 当前交付状态

| 能力 | 状态 | 公共入口或产物 |
|---|---|---|
| 原始数据准备与 business join | 可用 | `yelptext prepare` / `prepare_reviews()` |
| Prepared review reader | 可用 | `create_review_reader()` |
| Regex tokenizer | 可用 | `create_tokenizer()` |
| 确定性 review sampler | 可用 | `yelptext sample` / `sample_reviews()` |
| 全量 CF/DF 词典 | 可构建 | `yelptext vocab build` |
| Zipf/Heaps notebook | 可用 | `yelptext analyze zipf/heaps` |
| Tokenizer baseline comparison 主 CLI | 尚未正式接入 | `yelptext analyze tokenizers` 仍为 scaffold |
| Search/Trend 实现 | 由 B/C 开发 | 当前 interface/command 仍可能是 placeholder |
| B/C 开发区 | 空目录已建立 | 根目录 `groupb/`、`groupc/` |

真实 Yelp 数据与生成产物不会提交到 Git，因此每位需要
真实数据的组员必须按 README 自行准备，或在符合 Yelp 数据协议的前提下从组内
获得原始压缩包。

## 2. PreparedReviewReader

### 2.1 功能

Group A 将 raw review 与 business metadata 连接，输出严格的十字段 JSONL。
reader 负责：

- 流式读取，不将全文件载入内存；
- 每次 `iter_reviews()` 都重新打开文件，因此同一个 reader 可重复迭代；
- 检查 UTF-8、JSON、重复 JSON key、字段集合和字段类型；
- 遇到不符合 schema 的记录立即抛出 `YelpDataError`，不静默跳过；
- 保持原始 review text 的大小写、标点和 Unicode。

协议定义在
[`src/yelptext/protocol/reviewer.py`](src/yelptext/protocol/reviewer.py)，schema
版本为 `2.0`。

### 2.2 十个字段

| 字段 | 类型 | 推荐用途 |
|---|---|---|
| `doc_id` | `str` | posting/document 主键、搜索结果 ID |
| `text` | `str` | tokenizer、搜索、PMI、VADER、句子分析 |
| `user_id` | `str \| None` | 用户级去重或稳健性检查 |
| `stars` | `float \| None` | 结果展示、与 sentiment 对照；不是相关性标签 |
| `review_date` | `str \| None` | 年/月/季节聚合，格式 `YYYY-MM-DD` |
| `business_id` | `str \| None` | 商家级分组与筛选 |
| `business_name` | `str \| None` | 搜索结果和应用展示 |
| `categories` | `list[str] \| None` | sector/category 过滤；`None` 与 `[]` 含义不同 |
| `city` | `str \| None` | 地理筛选与展示 |
| `state` | `str \| None` | 与 city 联合消除同名地点歧义 |

`None` 表示未知。特别地，`categories=None` 表示没有 metadata，
`categories=[]` 表示 metadata 已知但类别列表为空。下游不能把二者混为一谈。

### 2.3 最简单的真实数据用法

```python
from yelptext.interface.data_corpus_analysis import create_review_reader

reader = create_review_reader("data/processed/reviews-sample.jsonl")

for review in reader.iter_reviews():
    print(review["doc_id"], review["business_name"], review["text"][:80])
```

不要使用 `json.loads()` 在 B/C 内重新实现 raw/prepared parsing；这样会绕过共享
schema 校验，并导致 sample/full 行为不一致。

## 3. Tokenizer

### 3.1 稳定协议

```python
class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...
    def fingerprint(self) -> str: ...
```

真实用法：

```python
from yelptext.interface.data_corpus_analysis import create_tokenizer

tokenizer = create_tokenizer()
tokens = tokenizer.tokenize("The-best food isn't bad!")

assert tokens == ["the", "best", "food", "isn't", "bad", "!"]
policy_id = tokenizer.fingerprint()
```

`fingerprint()` 当前返回可读的 tokenizer policy/config ID，不是文件 hash，也不
执行 SHA 验证。Search index 应保存该 ID，并在 query-time 比较 tokenizer ID，
防止 index 与 query 使用不同切词规则。

### 3.2 当前规则摘要

- Unicode NFC normalization；
- lowercase；
- curly apostrophe/backtick 归一为 `'`；
- contractions 保持为一个 token，例如 `don't`；
- hyphenated/run-on form 拆开，例如 `the-best-food`；
- URL、email、hashtag、emoticon、emoji cluster 保持完整；
- grouped number、fraction、money、percentage、temperature 保持结构；
- `!`、`?` 和独立 `#` 可作为 expressive punctuation token；
- 普通句号、逗号、分号等作为 delimiter；
- tokenization 本身不读取词典、不做 POS tagging，也不自动裁剪低频词。

### 3.3 推荐 use cases

Search/index：index-time 和 query-time 必须使用同一 tokenizer：

```python
reader = create_review_reader("data/processed/reviews-sample.jsonl")
tokenizer = create_tokenizer()

for review in reader.iter_reviews():
    terms = tokenizer.tokenize(review["text"])
    # Group B 在自己的实现中构建 postings、TF、DF 和 document length。
```

PMI/trend：PMI 需要稳定的 term identity，因此使用共享 tokenizer；时间窗口、
context window 和 minimum co-occurrence 仍由 Group C 定义。

Sentiment：VADER 应直接接收原始 `review["text"]`，不要先 tokenize 或 lowercase，
因为标点、大小写、emoji 和否定结构都可能影响 sentiment：

```python
score = vader.polarity_scores(review["text"])
```

Zipf：直接读取全量词典中的 CF，不重新扫描 review。Heaps：使用共享 reviewer
与 tokenizer 流式累计 growth checkpoints，因此必须重新扫描所选 prepared 文件。
两者都必须明确是否过滤 punctuation；低频裁剪会改变研究对象，因此不应把 rare
terms 先映射为 `<UNK>`。

### 3.4 词典与 token ID 的边界

全量词典位于：

```text
data/processed/vocabulary-full.sqlite
```

它包含 `<UNK>`、term ID、CF、DF 和标签，是 Group A 的离线分析/复用产物。
当前跨组 `Tokenizer` protocol 只承诺 `list[str]`，没有承诺 SQLite 表结构或
`MappedToken`。因此：

- Group B 可以根据 tokenizer 输出在自己的 index 中建立内部 term ID；
- 不要让 query-time 重新切 raw JSON 或使用不同 tokenizer；
- 若 B/C 确实需要共享词典中的 CF/DF/term ID，应先把该需求加入 protocol，
  再通过 interface 暴露，不能直接把 private SQLite schema 当作永久 API；
- Search 查询 OOV 通常应 drop，而不是建立 `<UNK>` posting；分类模型是否将
  rare/OOV 映射到 `<UNK>` 应由验证集决定。

## 4. Sample 与 Full 的相同调用方式

下游算法不应知道自己正在处理 sample 还是 full。差异只存在于配置文件：

```python
from yelptext.runtime import load_config
from yelptext.interface.data_corpus_analysis import create_review_reader

config = load_config("configs/sample.toml")  # 改为 full.toml 即全量
reader = create_review_reader(config["data"]["prepared_path"])
```

对应路径：

```text
configs/sample.toml -> data/processed/reviews-sample.jsonl
configs/full.toml   -> data/processed/reviews-full.jsonl
```

两种配置使用相同的 tokenizer policy 和 full vocabulary。切换时不修改 import、
函数调用或算法实现，只更换 `--config`。

### 4.1 使用 seed 42 建立统一开发子集

先确认 Group A 的全量 prepared 文件已经生成：

```text
data/processed/reviews-full.jsonl
```

然后所有组统一使用 50,000 条、seed 42 的开发样本：

```powershell
yelptext sample --config configs/full.toml --size 50000 --seed 42
```

输出为：

```text
data/processed/reviews-sample.jsonl
```

sampler 使用 `(seed, doc_id)` 生成稳定优先级，并按优先级与 `doc_id` 选择
bottom-k。只要输入数据版本、`doc_id` 集合、sample size 和 seed 不变，各组会
得到相同子集；原文件行顺序改变不会改变成员。若输出文件已经存在，命令会拒绝
覆盖，应先确认它是否就是组内共享的 seed 42 样本，不要静默重建成另一份。

开发时，Group B/C 自己的入口接受 config path，并传入 sample 配置：

```python
config_path = "configs/sample.toml"
config = load_config(config_path)
reader = create_review_reader(config["data"]["prepared_path"])
tokenizer = create_tokenizer()
```

此时所有功能代码都运行在 `reviews-sample.jsonl` 上。sampler 保留完整十字段记录，
因此 reviewer 输出类型、tokenizer 调用和算法实现与全量模式完全相同。Group B
应将 sample index 写入独立位置；Group C 的 sample 统计、图表和缓存也不能覆盖
最终全量产物。

### 4.2 开发完成后切回全量

算法验证完成后，只把 config path 改为：

```python
config_path = "configs/full.toml"
```

或者让本组 CLI 使用同一参数约定：

```powershell
python groupb/<本组入口>.py --config configs/full.toml
python groupc/<本组入口>.py --config configs/full.toml
```

尖括号内容是各组后续自行确定的入口文件，不是当前已有命令。切回全量时：

1. 不修改 reviewer/tokenizer import 或函数调用；
2. 不重新建立 sample 专用词典，继续使用
   `data/processed/vocabulary-full.sqlite`；
3. 重新构建依赖文档集合的 index、计数、聚合、缓存和图表；
4. 不复用 sample 模式的 index 或最终统计结果；
5. 在全量结果上重新检查 sample 阶段选择的阈值、sector、minimum count 和其他
   数据相关参数。

也就是说，sample → full 的迁移只改变数据路径和派生产物规模，不改变接口与算法
实现。edge-case audit sample 是有意偏置的数据，不能代替这里的 seed 42 通用
sample，也不能用于估计总体分布。

## 5. Group B/C 的开发与后续整合

Group B 和 Group C 现在分别在根目录 `groupb/`、`groupc/` 中自由组织实现，
直接调用已经完成的真实 Group A interface，不再维护 fake upstream 或镜像接口：

```python
from yelptext.interface.data_corpus_analysis import (
    create_review_reader,
    create_tokenizer,
)
from yelptext.runtime import load_config

config = load_config(config_path)
reader = create_review_reader(config["data"]["prepared_path"])
tokenizer = create_tokenizer()
```

组内代码验证完成后，再按正式的 `cli/command/interface/implementation` 边界整合
进 `src/yelptext/`。在此之前不为 B/C 在 `src` 中新增镜像实现或假数据层。

## 6. 推荐职责边界

Group A 负责：

- raw Yelp parsing 与 business join；
- prepared-review schema/reader 的真实实现；
- tokenizer policy 与真实实现；
- sampler 和词典构建；
- 对上述组件的真实数据审计和单元测试。

Group B 负责：

- 在 `groupb/` 中完成并验证搜索实现；
- postings、document statistics、term ID/index storage；
- TF-IDF/BM25、query processing、evaluation 和展示；
- 在 index artifact 中记录 tokenizer policy ID。

Group C 负责：

- 在 `groupc/` 中完成并验证趋势与应用实现；
- VADER sentiment、时间/category 聚合；
- PMI context 定义、过滤和 drift 分析；
- 独立 NLP/IR application。句子分割属于该 application，不由共享 tokenizer
  隐式承担。

## 7. 常见错误

- 直接读取 raw review/business：应改用 prepared reader。
- 在 index 和 query 中使用两个 tokenizer：会导致检索不一致。
- 对 VADER 输入 tokenizer 输出：会丢失 sentiment cue。
- 把 `categories=None` 当作 `[]`：会把未知 metadata 当成已知无类别。
- 使用 edge audit sample 估计总体分布：该样本有意过采样 edge cases。
- 在 sample 模式重新构建一个不同词典：会导致 sample/full term ID 不稳定。
- 直接依赖 implementation 或 SQLite 私有表：应先确认是否需要新增跨组协议。
