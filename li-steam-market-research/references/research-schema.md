# Steam 市场调研字段与证据口径

## 第一阶段表结构

CSV 按以下顺序保存：

| 字段 | 含义 |
|---|---|
| `collected_at` | 采集日期，`YYYY-MM-DD` |
| `primary_tag` | 固定填写 `Indie` |
| `secondary_category` | 本次用户指定并经页面复核的可变类别 |
| `source_rank` | Steam 主榜原始排名，1–50 |
| `steam_source_rank` | Steam 主榜原始排名；启用“排除免费游戏”时与过滤后的 `source_rank` 分开保存 |
| `title` | Steam 英文标题 |
| `app_id` | Steam App ID；无法适用时记录实际条目 ID 并解释 |
| `item_type` | game、DLC、demo、software、free 等 |
| `developer` | Steam 详情页开发商，多个用 `; ` 分隔 |
| `publisher` | Steam 详情页发行商，多个用 `; ` 分隔 |
| `release_date` | Steam 显示的发布日期，保留页面原文 |
| `supported_language_count` | 详情页支持语言总数 |
| `all_languages_rating` | All Languages 评价标签，如 Very Positive |
| `all_languages_positive_pct` | 可直接验证的全球好评率整数；否则留空 |
| `all_languages_review_count` | All Languages 累计评论精确整数 |
| `us_basic_list_price_usd` | 美国区单体 Basic 原价，十进制 USD；免费填 `0` |
| `review_based_lower_bound_signal_usd` | 评论数乘 Basic 原价；字段缺失则留空 |
| `store_url_us_en` | 带 `cc=us&l=english` 的 Steam 详情页 URL |
| `notes` | 缺失、免费、DLC、价格或页面异常说明 |

CSV 内的数字字段不放 `$`、千位逗号或评价文字，便于复算。展示表可以另外格式化货币。

## 计算纪律

```text
review_based_lower_bound_signal_usd
  = all_languages_review_count
  × us_basic_list_price_usd
```

- 使用精确评论整数，不用 `8.5K` 等缩写；
- 使用两位小数或 Steam 实际价格精度；
- 乘法结果保留两位小数；
- 免费游戏价格填 `0`，结果为 `0`，并在 notes 标记 free-to-play；
- 缺少评论数或 Basic 原价时结果留空，不按零处理；
- 该指标只用于同口径粗筛，不能命名为实际营收或最低实际营收。

## 排名与异常纪律

- 榜单排名由 Steam 当次页面决定，采集日期是结果的一部分；
- `Indie` 是固定主标签，第二类别按每次任务独立确定，不沿用上次类别；
- 默认排除免费游戏：遇到免费条目不进入结果表，继续向下加载并记录被排除的 App ID；付费 DLC/序章/试玩版等异常条目仍保留并标注；
- 启用排除免费游戏时，`source_rank` 是过滤后的 1–N，`steam_source_rank` 是 Steam 原始名次；
- 相同 App ID 重复加载时只保留首次出现并继续加载，直到有用户要求数量 N 个唯一条目（默认 20）；
- 标题相同但 App ID 不同视为不同条目；
- 区域不可售、年龄门槛或登录拦截必须写入 notes；
- 第三方站点只能辅助定位，不能覆盖 Steam 可直接验证的排名、评论数和价格。

## 第二阶段证据表

用户批准后，为每个候选游戏追加独立证据表：

| 字段 | 含义 |
|---|---|
| `team_size_claim` | 可证实的团队人数或区间 |
| `team_roles` | 核心岗位、兼职与外包 |
| `development_start` | 开发开始日期或可证区间 |
| `early_access_date` | 抢先体验日期，如适用 |
| `release_date` | 正式发行日期 |
| `effective_development_months` | 剔除已知中断后的月份或区间 |
| `person_month_estimate` | 人数 × 有效月份的区间估算 |
| `support_factors` | 外包、发行商、融资、复用资产等 |
| `source_title` | 来源标题 |
| `source_url` | 可打开的证据 URL |
| `source_date` | 来源发布日期 |
| `evidence_quote` | 支撑结论的短引文或准确摘要 |
| `confidence` | high、medium、low，并说明原因 |

同一结论有冲突来源时并列呈现并解释取舍。团队人数和周期是时间变化量，必须注明来源对应的时间点。人月是估算值，使用区间优先于虚假的单点精度。

补查顺序：Steam 详情页 → 开发商/发行商官网 → About / Team / Credits / Careers → 开发日志、访谈、公开演讲和可信媒体。Steam 没有官网链接时仍需做定向网页搜索并记录检索范围；只有找不到可追溯证据时才填写 `Not disclosed` / `Not estimable`。公司总人数不得直接当作单个项目人数，必须在字段和备注中注明归属层级。
