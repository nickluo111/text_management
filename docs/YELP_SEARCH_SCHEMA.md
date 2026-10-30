# Yelp 评论数据交接 Schema

本文档定义 Group A 向 Group B/C 提供评论数据时的权威交接格式。Python
protocol、真实 reader、各组 fake 和派生 fixture 必须与这里保持一致。
当前 schema 版本为 `2.0`；相较八字段草案，新增 `user_id` 和 `state`。

## 数据交接格式

- 文件名：`reviews.jsonl`
- 编码：UTF-8
- 格式：JSON Lines，每行一个 JSON 对象
- 校验：每行分别使用 [`yelp-review.schema.json`](yelp-review.schema.json) 校验
- 文档标识：整个文件中的 `doc_id` 必须唯一；重复运行时，同一条评论的 ID 必须保持不变
- 必需且非空字段：`doc_id`、`text`
- 未知或缺失的可选值：使用 JSON `null`，不要使用 `"N/A"`、`"unknown"` 或 `"None"`
- Group A 的 reader 总是返回全部十个键；可选值未知时对应 Python `None`

## 字段定义

| 字段 | JSON 类型 | 允许 `null` | 规则与用途 |
| --- | --- | ---: | --- |
| `doc_id` | 字符串 | 否 | 唯一且非空的评论 ID；Yelp `review_id` 直接映射到该字段。 |
| `text` | 字符串 | 否 | 非空的评论原文；保留原始大小写、标点和 Unicode。 |
| `user_id` | 字符串或 `null` | 是 | Yelp 的匿名用户 ID；用于用户级去重、分层或趋势稳健性检查，不作为文本相关性分数。 |
| `stars` | 数字或 `null` | 是 | 单条评论的 1–5 星评分，步长为半星；不要与商家平均星级混淆。 |
| `review_date` | 日期字符串或 `null` | 是 | ISO 8601 `YYYY-MM-DD`；支持年份、月份和季节聚合。 |
| `business_id` | 字符串或 `null` | 是 | 稳定的商家 ID，用于分组或筛选。 |
| `business_name` | 字符串或 `null` | 是 | 商家名称，用于结果展示。 |
| `categories` | 字符串数组或 `null` | 是 | `null` 表示未知，`[]` 表示已知没有类别；用于筛选和 sector 分析。 |
| `city` | 字符串或 `null` | 是 | 商家所在城市，可用于展示或地理分层。 |
| `state` | 字符串或 `null` | 是 | 商家所在州/地区；与 `city` 一起避免同名城市歧义。 |

## `reviews.jsonl` 示例

```jsonl
{"doc_id":"review-001","text":"Great food and friendly staff.","user_id":"user-007","stars":5.0,"review_date":"2024-02-18","business_id":"business-042","business_name":"Example Cafe","categories":["Cafe","Food"],"city":"Toronto","state":"ON"}
{"doc_id":"review-002","text":"The service was slow, but the pizza was excellent.","user_id":null,"stars":4.5,"review_date":"2024-02-19","business_id":"business-042","business_name":"Example Cafe","categories":["Cafe","Food"],"city":"Toronto","state":"ON"}
```

## 原始 Yelp 字段映射

| 原始字段 | 交接字段 |
| --- | --- |
| review `review_id` | `doc_id` |
| review `text` | `text` |
| review `user_id` | `user_id` |
| review `stars` | `stars` |
| review `date` | `review_date`，只保留 `YYYY-MM-DD` 日期部分 |
| review `business_id` | `business_id` |
| business `name` | `business_name` |
| business `categories` | `categories`，逗号分隔字符串拆成数组 |
| business `city` | `city` |
| business `state` | `state` |

## 有意不进入共享协议的字段

- review `useful`、`funny`、`cool`：平台互动反馈，不是评论文本质量或相关性的可靠标签；若用于检索排序会干扰 TF-IDF/BM25 的公平比较。
- review 时间部分：本作业的趋势粒度是年份或季节，日期已经足够。
- business 地址、邮编、经纬度：当前搜索、sector 趋势、PMI 和文本应用均不需要。
- business 平均星级、`review_count`、`is_open`：这些是商家级快照，不能代表评论发表时的状态，容易造成历史趋势误读。
- business `attributes`、`hours`：结构复杂、缺失模式不稳定，且没有已确认的下游消费者。

这些字段仍保留在原始 Yelp 文件中。如果后续应用确定需要其中某项，应先由消费者提出具体用例，再版本化更新本 schema、protocol、fake 和 fixture。
