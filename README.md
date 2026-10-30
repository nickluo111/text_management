# Yelp Text Analysis

AI6122 Text Data Management & Processing 小组项目。本文档说明如何从零配置环境、
准备 Yelp 数据并运行当前已经完成的数据与语料分析功能。公开 Python API、tokenizer
标签、POS/filter 行为和下游使用方式见 [FUNCTIONALITY.md](FUNCTIONALITY.md)。

## 1. 环境配置

项目固定使用 CPython **3.12.4**。以下命令从仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m nltk.downloader stopwords averaged_perceptron_tagger vader_lexicon
```

确认环境：

```powershell
python --version
yelptext --help
```

macOS/Linux 使用 `source .venv/bin/activate` 激活环境，其余 Python 与
`yelptext` 命令相同。

## 2. 放置 Yelp 数据

项目只使用 Yelp Open Dataset 的两个文件，并要求以下最终路径：

```text
data/raw/yelp_academic_dataset_business.json
data/raw/yelp_academic_dataset_review.json
```

可从 [Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/)
下载；若官方地址不可用，也可在登录后使用
[Kaggle Yelp Dataset](https://www.kaggle.com/datasets/yelp-dataset/yelp-dataset/data)。
数据访问与许可说明见 [docs/DATA_ACCESS.md](docs/DATA_ACCESS.md)。原始数据、处理后
数据、词典和实验产物均由 `.gitignore` 排除。

## 3. 生成标准数据与词典

### 3.1 准备全量 reviews

```powershell
yelptext prepare --config configs/full.toml
```

该命令流式读取 raw review/business，连接 business metadata，校验 schema，并生成：

```text
data/processed/reviews-full.jsonl
data/processed/reviews-full.audit.json
data/processed/reviews-full.audit.sqlite
```

### 3.2 生成 seed-42 样本

```powershell
yelptext sample --config configs/full.toml --size 50000 --seed 42
```

默认输出 `data/processed/reviews-sample.jsonl`。sampler 完整保留十字段 schema；
相同数据版本、`doc_id` 集合、seed 和 size 会产生相同样本。

### 3.3 构建全量 CF/DF 词典

```powershell
yelptext vocab build --config configs/full.toml
```

输出 `data/processed/vocabulary-full.sqlite`，记录 `<UNK>`、term ID、CF、DF、类型
标签和 tokenizer policy metadata。构建词典是显式离线操作；调用 tokenizer 不会
自动重建词典。

## 4. 运行 Dataset Analysis

```powershell
yelptext analyze zipf --config configs/full.toml
yelptext analyze heaps --config configs/full.toml
yelptext analyze tokenizers --config configs/full.toml
```

命令分别执行：

- `notebooks/01_zipf.ipynb`
- `notebooks/02_heaps.ipynb`
- `notebooks/03_tokenizer_comparison.ipynb`

Executed notebooks 写入 `artifacts/notebooks/`；实验产物位于：

```text
artifacts/zipf/
artifacts/heaps/
artifacts/tokenizer_comparison/
```

## 5. Sample 与 Full

| 配置 | Prepared reviews | Index output |
|---|---|---|
| `configs/sample.toml` | `data/processed/reviews-sample.jsonl` | `artifacts/indexes/sample` |
| `configs/full.toml` | `data/processed/reviews-full.jsonl` | `artifacts/indexes/full` |

两种配置使用相同 tokenizer policy 和 full vocabulary。下游通过切换 config 改变
数据规模，不修改 import、接口或算法。

## 6. Python 快速示例

```python
from yelptext.interface.data_corpus_analysis import (
    create_review_reader,
    create_tokenizer_pipeline,
)

reader = create_review_reader("data/processed/reviews-sample.jsonl")
pipeline = create_tokenizer_pipeline(
    enable_pos=True,
    skip_types={"punctuation", "stop_word", "pos:determiner"},
)

for review in reader.iter_reviews():
    terms = pipeline.terms(review["text"])
```

`tokenize()`、`analyze()`、`terms()` 的差异、全部 filter types、review schema 和
任务级用法见 [FUNCTIONALITY.md](FUNCTIONALITY.md)。

## 7. 文档

- [FUNCTIONALITY.md](FUNCTIONALITY.md)：已完成功能、CLI、公开 API 与 use cases
- [docs/YELP_SEARCH_SCHEMA.md](docs/YELP_SEARCH_SCHEMA.md)：prepared-review schema
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)：代码库边界
- [notebooks/README.md](notebooks/README.md)：报告 notebooks
- [report/3.1_dataset_analysis.md](report/3.1_dataset_analysis.md)：报告草稿
