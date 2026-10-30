# Completed Functionality and Public API

本文档是当前已完成功能的权威说明，面向 Search、Trend 和 Application 的调用者。
下游只应依赖 `yelptext.interface.data_corpus_analysis` 与 `yelptext.protocol`，不要
直接 import `yelptext.implementation`。Search、Trend 和 Application 自身的实现
不在本文档中声明为已完成。

## 1. 完成状态

| 功能 | 状态 | 入口或产物 |
|---|---|---|
| Raw review/business preparation | 可用 | `yelptext prepare` / `prepare_reviews()` |
| Prepared review reader | 可用 | `create_review_reader()` |
| Canonical regex tokenizer | 可用 | `create_tokenizer()` |
| Classification/POS/filter pipeline | 可用 | `create_tokenizer_pipeline()` |
| Deterministic review sampling | 可用 | `yelptext sample` / `sample_reviews()` |
| Full CF/DF vocabulary | 可构建 | `yelptext vocab build` / `build_vocabulary()` |
| Zipf analysis | 可用 | `yelptext analyze zipf` |
| Heaps analysis | 可用 | `yelptext analyze heaps` |
| Tokenizer comparison | 可用 | `yelptext analyze tokenizers` |

## 2. CLI 功能

### `yelptext prepare`

连接 raw review 与 business metadata，执行 schema/类型/重复键校验，输出标准十字段
JSONL 和审计产物。

```powershell
yelptext prepare --config configs/full.toml
```

输入为 `data/raw/yelp_academic_dataset_review.json` 和
`data/raw/yelp_academic_dataset_business.json`；输出为：

```text
data/processed/reviews-full.jsonl
data/processed/reviews-full.audit.json
data/processed/reviews-full.audit.sqlite
```

`--limit N` 只取 raw 文件前 N 条，用于 smoke run，不是随机样本。

### `yelptext sample`

通过 `(seed, doc_id)` 的稳定优先级选择 schema-preserving 样本：

```powershell
yelptext sample --config configs/full.toml --size 50000 --seed 42
```

默认输出 `data/processed/reviews-sample.jsonl`。输入行顺序改变不会改变选中成员；
命令拒绝覆盖已有输出。

### `yelptext vocab build`

流式扫描 raw review text 并构建 SQLite vocabulary：

```powershell
yelptext vocab build --config configs/full.toml
```

输出 `data/processed/vocabulary-full.sqlite`，包含 term ID、CF、DF、稳定标签、
`<UNK>` 和 tokenizer/vocabulary metadata。该词典用于全局语料统计与 Zipf；Search
仍应在建立 postings 的同一次扫描中计算自己的 DF、N 和 average document length。

### `yelptext analyze`

```powershell
yelptext analyze zipf --config configs/full.toml
yelptext analyze heaps --config configs/full.toml
yelptext analyze tokenizers --config configs/full.toml
```

三个命令执行对应 notebook 并生成报告 artifacts。

## 3. PreparedReviewReader

```python
from yelptext.interface.data_corpus_analysis import create_review_reader

reader = create_review_reader("data/processed/reviews-sample.jsonl")
for review in reader.iter_reviews():
    print(review["doc_id"], review["text"])
```

reader 流式读取，每次 `iter_reviews()` 重新打开文件；它严格校验 UTF-8、JSON、
重复键、字段集合和类型，错误时抛出 `YelpDataError`，不静默跳过。

| 字段 | 类型 | 主要用途 |
|---|---|---|
| `doc_id` | `str` | document/posting 主键 |
| `text` | `str` | tokenizer、search、PMI、VADER |
| `user_id` | `str \| None` | 用户级分析 |
| `stars` | `float \| None` | 展示与 sentiment 对照 |
| `review_date` | `str \| None` | `YYYY-MM-DD` 时间聚合 |
| `business_id` | `str \| None` | 商家分组 |
| `business_name` | `str \| None` | 结果展示 |
| `categories` | `list[str] \| None` | sector/category 过滤 |
| `city` | `str \| None` | 地理筛选 |
| `state` | `str \| None` | 地理消歧 |

`categories=None` 表示 metadata 未知；`categories=[]` 表示 metadata 已知但类别为空。

## 4. Canonical tokenizer

```python
from yelptext.interface.data_corpus_analysis import create_tokenizer

tokenizer = create_tokenizer()
tokens = tokenizer.tokenize("The-best food isn't bad!")
# ["the", "best", "food", "isn't", "bad", "!"]
policy_id = tokenizer.fingerprint()
```

当前规则包括 Unicode NFC、lowercase、apostrophe/full-width punctuation
normalization；contractions 保持完整；hyphenated words 拆开；URL、email、hashtag、
emoticon、emoji cluster 和结构化 numeric forms 保持结构；`!`、`?`、独立 `#`
保留为 expressive punctuation。基础 tokenizer 不执行 POS、filter、stemming、
lemmatization、低频裁剪或 vocabulary lookup。

## 5. Classification/POS/filter pipeline

### 5.1 创建 pipeline

```python
from yelptext.interface.data_corpus_analysis import (
    available_token_types,
    create_tokenizer_pipeline,
)

pipeline = create_tokenizer_pipeline(
    enable_pos=True,
    skip_types={
        "punctuation",
        "stop_word",
        "pos:determiner",
        "pos:conjunction",
    },
)
```

使用前安装 NLTK data：

```powershell
python -m nltk.downloader stopwords averaged_perceptron_tagger
```

### 5.2 三种调用

```python
raw_terms = pipeline.tokenize("The food was really excellent!")
tagged_tokens = pipeline.analyze("The food was really excellent!")
filtered_terms = pipeline.terms("The food was really excellent!")
```

- `tokenize()`：canonical、未过滤的 `list[str]`，不执行 POS；
- `analyze()`：classification -> optional POS -> filter，返回带 `term` 和 `tags`
  的 occurrences；
- `terms()`：执行同一 pipeline，只返回过滤后的 `list[str]`。

典型 `analyze()` 结果：

```text
food       {word, pos:noun}
really     {word, pos:adverb}
excellent  {word, pos:adjective}
```

### 5.3 Filter types

无需 POS 的稳定标签：

```text
word, stop_word, conjunction, url, email, emoticon, emoji,
number, money, percentage, temperature, hashtag, punctuation
```

`enable_pos=True` 后额外支持：

```text
pos:noun, pos:verb, pos:adjective, pos:adverb, pos:determiner,
pos:conjunction, pos:adposition, pos:pronoun, pos:particle, pos:other
```

```python
stable_types = available_token_types()
all_types = available_token_types(include_pos=True)
```

一个 occurrence 可同时拥有多个标签；filter 采用“任一标签命中即删除”。例如 money
同时带有 `money` 和 `number`，过滤 `number` 也会删除 money。未知类型会报错；使用
任何 `pos:*` filter 却未启用 POS 也会报错。

`pipeline.fingerprint()` 标识 tokenizer、stopword、POS 和 filter policy。Search
index 应保存它，并在 query time 验证配置一致。

## 6. 推荐用法

### Search/index

Index-time 和 query-time 必须使用相同 pipeline：

```python
pipeline = create_tokenizer_pipeline(
    enable_pos=True,
    skip_types={"punctuation", "stop_word", "pos:determiner"},
)

document_terms = pipeline.terms(document_text)
query_terms = pipeline.terms(query_text)
```

Search 在建立 postings 的同一次 scan 中计算 TF、DF、N、document length 和 average
document length。不要把 full-vocabulary DF 直接当作 POS/filter 后 index 的 IDF。

### PMI/trend

PMI 使用同一 pipeline 获得过滤后的 terms，但应在各时间窗口重新计算 term 和
co-occurrence counts。全局 CF/DF 不能替代窗口统计。

### Sentiment/VADER

VADER 直接接收原始 `review["text"]`；不要先 lowercase、tokenize 或 filter，因为
标点、大小写、emoji 和否定结构会影响 sentiment。

### Zipf/Heaps

Zipf 直接读取 full vocabulary CF。Heaps 流式扫描 selected prepared reviews 以获得
中间 growth checkpoints。两者应明确 punctuation policy，且不应先把 rare terms
映射为 `<UNK>`。

## 7. Vocabulary lookup 边界

内部 `VocabularyLookup` 可将 occurrence 映射为 `term_id/CF/DF/tags`，并支持
`unk`、`drop`、`error` 三种 OOV policy，但目前不是 B/C 默认 public pipeline 的
一部分。

Search 需要与实际 document set 和 POS/filter policy 一致的 index-local DF；PMI
需要时间窗口 counts。B 可建立自己的 index term ID，C 可直接使用 term strings。
`vocabulary-full.sqlite` 保留用于全局统计、Zipf、阈值参考和 consistency check。

## 8. Sample/Full 切换

```python
from yelptext.runtime import load_config

config = load_config("configs/sample.toml")
config = load_config("configs/full.toml")
```

两种配置使用同一接口和 tokenizer policy。切换 full 时必须重新生成依赖 document
collection 的 index、DF、PMI、sentiment aggregation 和图表，不能复用 sample 统计。

## 9. Public exports

```python
from yelptext.interface.data_corpus_analysis import (
    AnalyzedToken,
    Tokenizer,
    TokenizerPipeline,
    YelpDataError,
    available_token_types,
    build_vocabulary,
    create_review_reader,
    create_tokenizer,
    create_tokenizer_pipeline,
    prepare_reviews,
    sample_reviews,
)
```

函数签名和协议以 `src/yelptext/interface/data_corpus_analysis.py` 与
`src/yelptext/protocol/` 为准。
