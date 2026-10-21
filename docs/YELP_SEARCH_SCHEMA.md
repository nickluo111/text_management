# Yelp 评论搜索：数据 Schema

## 数据交接格式

- 文件名：`reviews.jsonl`
- 编码：UTF-8
- 格式：JSON Lines，每行一个 JSON 对象
- 校验：对每一行分别使用 [`yelp-review.schema.json`](yelp-review.schema.json) 校验
- 文档标识：整个文件中的 `doc_id` 必须唯一；重复运行时，同一条评论的 ID 必须保持不变
- 必需字段：`doc_id`、`text`
- 未知或缺失的可选值：使用 JSON `null`；不要用 `"N/A"`、`"unknown"`、`"None"` 等字符串代替

## 字段定义

| 字段            | JSON 类型         | 必需 | 规则与用途                                                   |
| --------------- | ----------------- | ---: | ------------------------------------------------------------ |
| `doc_id`        | 字符串            |   是 | 唯一且非空的评论 ID。若源数据包含 Yelp `review_id`，直接映射到此字段。 |
| `text`          | 字符串            |   是 | 非空的评论原文，是全文搜索的主要字段。保留评论原意和标点。   |
| `stars`         | 数字或 null       |   否 | 1 到 5 星，步长为半星。可用于结果展示或评分筛选。            |
| `review_date`   | 日期字符串或 null |   否 | ISO 8601 格式 `YYYY-MM-DD`。可用于展示或日期筛选。           |
| `business_id`   | 字符串或 null     |   否 | 稳定的商家 ID，可用于评论分组或筛选。                        |
| `business_name` | 字符串或 null     |   否 | 商家名称（若有商家元数据）。如产品需要，也可以把它纳入可搜索字段。 |
| `categories`    | 字符串数组或 null |   否 | 商家类别。`null` 表示未知；`[]` 表示已知没有类别。可用于筛选。 |
| `city`          | 字符串或 null     |   否 | 商家所在城市（若有），可用于筛选。                           |

## `reviews.jsonl` 示例

```jsonl
{"doc_id":"review-001","text":"Great food and friendly staff.","stars":5,"review_date":"2024-02-18","business_id":"business-042","business_name":"Example Cafe","categories":["Cafe","Food"],"city":"Toronto"}
{"doc_id":"review-002","text":"The service was slow, but the pizza was excellent.","stars":4.5,"review_date":"2024-02-19","business_id":"business-042","business_name":"Example Cafe","categories":["Cafe","Food"],"city":"Toronto"}
```

## 原始 Yelp 字段映射

对于常见的 Yelp 评论与商家数据结构，存在对应源字段时按下表转换：

| 原始字段           | 交接字段                                             |
| ------------------ | ---------------------------------------------------- |
| 评论 `review_id`   | `doc_id`                                             |
| 评论 `text`        | `text`                                               |
| 评论 `stars`       | `stars`                                              |
| 评论 `date`        | `review_date`（取日期部分，格式 `YYYY-MM-DD`）       |
| 评论 `business_id` | `business_id`                                        |
| 商家 `name`        | `business_name`                                      |
| 商家 `categories`  | `categories`（若源文件是逗号分隔字符串，则拆成数组） |
| 商家 `city`        | `city`                                               |
