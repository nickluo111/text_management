# Yelp Text Analysis：从零开始运行

这是 AI6122 Text Data Management & Processing 小组项目。当前已经正式集成的
Group A 交付包括：原始 Yelp 数据准备、严格的 prepared-review reader、共享
regex tokenizer、可复用 sampler，以及全量 CF/DF 词典构建。

下游开发者应先阅读 [HANDOFF.md](HANDOFF.md)。架构和团队协作约定分别见
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 与
[docs/TEAM_WORKFLOW.md](docs/TEAM_WORKFLOW.md)。

## 1. 环境要求

- CPython **3.12.4**（版本同时固定在 `.python-version` 和 `pyproject.toml`）
- Git
- 足够保存 Yelp 原始 JSON、prepared JSONL、临时文件和实验产物的磁盘空间
- Windows PowerShell 示例中的命令都从仓库根目录运行

克隆并创建环境：

```powershell
git clone https://github.com/nickluo111/text_management.git
Set-Location text_management

py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

安装运行时所需的 NLTK 数据：

```powershell
python -m nltk.downloader stopwords vader_lexicon
```

只有显式启用实验性 POS tagging 时才需要：

```powershell
python -m nltk.downloader averaged_perceptron_tagger
```

确认安装：

```powershell
python --version
yelptext --help
```

macOS/Linux 将激活命令替换为 `source .venv/bin/activate`，其余 Python 和
`yelptext` 命令相同。

## 2. 下载并放置 Yelp 原始数据

项目只需要以下两个文件，最终路径和文件名必须完全一致：

```text
data/raw/yelp_academic_dataset_business.json
data/raw/yelp_academic_dataset_review.json
```

先创建目录：

```powershell
New-Item -ItemType Directory -Force data/raw | Out-Null
```

### 方法 A：Yelp 官方 Open Dataset

从 [Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/)
下载官方压缩包，并阅读其中的数据使用协议。假设下载文件为
`$HOME\Downloads\yelp_dataset.tar`：

```powershell
tar -xf "$HOME\Downloads\yelp_dataset.tar" -C data/raw
```

不同版本的压缩包可能多一层目录。解压后请将所需的两个 JSON 移到上述最终
路径；不要修改 JSON 内容。

### 方法 B：Yelp 在 Kaggle 上的数据集

如果 Yelp 下载地址返回 403，可使用
[Yelp Dataset on Kaggle](https://www.kaggle.com/datasets/yelp-dataset/yelp-dataset/data)。
登录 Kaggle、安装并配置官方 Kaggle CLI 后运行：

```powershell
kaggle datasets download yelp-dataset/yelp-dataset `
  -f yelp_academic_dataset_business.json `
  -p data/raw --unzip

kaggle datasets download yelp-dataset/yelp-dataset `
  -f yelp_academic_dataset_review.json `
  -p data/raw --unzip
```

确认文件：

```powershell
Test-Path data/raw/yelp_academic_dataset_business.json
Test-Path data/raw/yelp_academic_dataset_review.json
```

两个命令都应输出 `True`。不要提交原始数据、prepared 数据、样本或词典；
这些内容已由 `.gitignore` 排除。更多访问说明见
[docs/DATA_ACCESS.md](docs/DATA_ACCESS.md)。

## 3. 完成当前已集成的 Group A 流程

### 3.1 准备全量 review handoff

```powershell
yelptext prepare --config configs/full.toml
yelptext sample --config configs/full.toml --size 50000
```

该命令流式读取 review/business 原始文件，完成 business metadata 连接并严格
校验输出。此外生成一个大小为50000的sample子集，主要是为了比对tokenizer之间的表现，避免全量过慢。
主要产物是：

```text
data/processed/reviews-full.jsonl
data/processed/reviews-full.audit.json
data/processed/reviews-full.audit.sqlite
data/processed/reviews-sample.jsonl
```

`reviews-full.jsonl` 每行包含固定的十个字段，是 B/C 组应读取的标准数据。
命令不会覆盖已有输出；需要重新运行时应明确选择新的 `--output`，或在确认旧
产物不再需要后自行移除。

### 3.2 建立全量 tokenizer 词典

```powershell
yelptext vocab build --config configs/full.toml
```

词典从原始 review 文本独立构建，记录每个 term 的 `term_id`、CF、DF 和稳定
类型标签。输出位置：

```text
data/processed/vocabulary-full.sqlite
```

这是显式离线步骤；import tokenizer、读取 review 或调用 `tokenize()` 都不会
自动重建词典。构建时进度输出到 stderr，结束时 stdout 输出 JSON 摘要。词典
保留所有观察到的词项，`<UNK>` 固定为 ID 0；低频裁剪留给具体下游任务。

### 3.3 当前 Group A 状态边界

`prepare`、`sample`、`vocab build`、reviewer 和 tokenizer 已正式接入公共
interface。Zipf、Heaps 与 tokenizer baseline comparison 分别由
`notebooks/01_zipf.ipynb`、`notebooks/02_heaps.ipynb` 和
`notebooks/03_tokenizer_comparison.ipynb` 实现，并可通过对应的
`yelptext analyze` 子命令自动执行。

```powershell
yelptext analyze zipf --config configs/full.toml
yelptext analyze heaps --config configs/full.toml
yelptext analyze tokenizers --config configs/full.toml
```

Zipf 直接读取全量词典 CF，不重新扫描 reviews；Heaps 为获得中间 vocabulary
growth checkpoints，必须流式扫描并 tokenize 所选 prepared 文件。开发时先用
sample config，最终结果再切换 full config。

## 4. 仅开发：生成 sample

先完成一次全量 `prepare`，然后从 prepared review 中生成确定性样本：

```powershell
yelptext sample --config configs/full.toml --size 50000
```

默认输出：

```text
data/processed/reviews-sample.jsonl
```

sampler 会完整保留十字段 schema。相同 seed、sample size 和 `doc_id` 集合会
得到相同样本，输入行顺序改变也不会改变选择结果。默认 seed 为 `42`，可用
`--seed` 覆盖：

```powershell
yelptext sample --config configs/full.toml --size 10000 --seed 42 `
  --output data/processed/reviews-sample-10k.jsonl
```

如果只是验证数据准备能否运行，而不需要随机样本，可以使用开发前缀：

```powershell
yelptext prepare --config configs/full.toml --limit 1000 `
  --output data/processed/reviews-prefix-1000.jsonl
```

`--limit` 是原文件前 N 条，不是随机抽样，不能用于估计总体分布。

## 4.1 在 sample 与 full 之间切换

两个配置文件都是完整、独立的 TOML，不存在隐式继承：

| 模式          | 配置                    | `prepared_path`                       | 下游 index 目录              |
| ------------- | ----------------------- | --------------------------------------- | ---------------------------- |
| Sample 开发   | `configs/sample.toml` | `data/processed/reviews-sample.jsonl` | `artifacts/indexes/sample` |
| Full 正式运行 | `configs/full.toml`   | `data/processed/reviews-full.jsonl`   | `artifacts/indexes/full`   |

生成 sample 时使用 `configs/full.toml`，因为 sampler 的输入必须是全量 prepared
文件；生成完成后，下游命令通过配置切换输入：

```python
from yelptext.runtime import load_config

config = load_config("configs/sample.toml")  # 快速开发
prepared_path = config["data"]["prepared_path"]

config = load_config("configs/full.toml")    # 最终全量
prepared_path = config["data"]["prepared_path"]
```

下游代码必须读取 `[data].prepared_path`，不能硬编码路径。两种配置都使用同一个
`data/processed/vocabulary-full.sqlite` 和同一 tokenizer policy，因此切换数据
规模不需要修改算法或 import。Group B/C 分别在根目录 `groupb/`、`groupc/`
开发；各自入口完成后只需让它接受上述 config path。

## 4.2 关键产物一览

| 产物                  | 默认位置                                           | 用途                     |
| --------------------- | -------------------------------------------------- | ------------------------ |
| 原始 business         | `data/raw/yelp_academic_dataset_business.json`   | Group A preparation 输入 |
| 原始 review           | `data/raw/yelp_academic_dataset_review.json`     | preparation 与词典输入   |
| 全量 prepared reviews | `data/processed/reviews-full.jsonl`              | 下游正式数据接口         |
| Sample reviews        | `data/processed/reviews-sample.jsonl`            | 下游快速开发             |
| Preparation audit     | `data/processed/reviews-full.audit.json/.sqlite` | 数据质量与连接审计       |
| 全量词典              | `data/processed/vocabulary-full.sqlite`          | term ID、CF、DF、标签    |

## 4.3 下游接入

reviewer、tokenizer、sampler、full/sample 切换方式及推荐 use cases 见根目录
[HANDOFF.md](HANDOFF.md)。下游只应依赖
`yelptext.interface.data_corpus_analysis` 和 `yelptext.protocol`，不要直接 import
`yelptext.implementation`。

Group A 的 Zipf/Heaps 实验驱动、拟合与报告图表保存在 notebook；reviewer、
tokenizer、sampler、词典等可复用运行时设施保存在 `src/yelptext/`。
