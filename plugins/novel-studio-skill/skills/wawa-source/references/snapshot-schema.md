# 蛙蛙统计快照契约 `wawa.stats.v1`

这是给离线导出器、`wawa-source` 和 Dashboard 之间使用的最小数据契约。它不是蛙蛙写作的接口文档，也不要求导出器暴露平台的原始字段。

## 顶层字段

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `schema_version` | string | 必须是 `wawa.stats.v1`；未来不兼容变更使用新版本名。 |
| `captured_at` | RFC 3339 时间字符串 | 必填，表示数据观察时间，必须带时区。 |
| `ttl_days` | 正整数 | 可选，默认 7；建议不超过 31。 |
| `expires_at` | RFC 3339 时间字符串 | 可选；若存在必须等于 `captured_at + ttl_days`，用于审计和展示。 |
| `source` | object | 必填；只描述本地来源类型，不放 URL、路径、账号或登录态。 |
| `works` | array | 必填；每项是一个作品的匿名化前或原始本地统计。 |

`source.kind` 推荐使用 `synthetic-fixture`、`manual-export` 或 `user-provided`；`source.label` 只能是人工可读的非敏感描述。快照可包含 `account` 或 `title` 等本地原始字段，但这些字段在公开展示前必须经过脱敏函数。

## 作品与指标

作品对象允许输入 `work_id`、`title`、`author` 等原始字段，处理后不得进入公开视图。统计字段使用非负数：

```json
{
  "status": "连载",
  "metrics": {
    "chapters": 42,
    "words": 123456,
    "followers": 820,
    "readers": 731,
    "follow_delta": 18,
    "total_revenue": 123.45,
    "daily_revenue": 12.34
  },
  "series": [
    {"date": "2026-08-17", "followers": 802, "readers": 710, "revenue": 8.20},
    {"date": "2026-08-18", "followers": 820, "readers": 731, "revenue": 12.34}
  ]
}
```

`metrics` 中的 `chapters`、`words`、`followers`、`readers`、`follow_delta` 为整数；收益字段为有限的非负数。趋势点可包含章节、字数、累计/日收益、追读、阅读和追读增量这些规范字段或明确别名。兼容输入中的 `revenue` 按当日收益处理。缺失指标表示该日没有提供该指标，不得猜测为平台的零值。

为兼容人工导出，脚本也接受 `chapter_count`/`word_count`/`follower_count`/`reader_count`/`revenue` 等明确别名，并在规范化输出中统一为上面的字段名。

## 新鲜度与失败关闭

- `fresh`：`now <= expires_at`，可以进入 Dashboard 的正常数据路径，但仍须显示采集时间。
- `stale`：`now > expires_at`，只能作为历史诊断；不得声称实时。
- `invalid`：版本、时间、TTL、类型或数值校验失败；不得使用任何聚合值。

TTL 只描述快照有效期，不会刷新数据，也不会触发网络访问。跨时区比较统一转换为带时区的时间；没有时区的时间直接拒绝。

## 脱敏规则

公开视图至少移除：账号 ID/昵称、作品 ID/书名、作者、URL、绝对路径、Cookie/Token/密码以及未知的身份字段。作品以 `作品 1`、`作品 2` 等本地序号表示。金额、字数和趋势数值不是身份字段，但仍应只在用户授权的本地报告中展示。

仓库中的测试只能使用合成作品、合成金额和合成日期；不得加入真实书名、远端 ID、截图、浏览器配置或收益导出文件。

## Dashboard 输出

`dashboard` 子命令将本契约映射为 OpenCreator Dashboard `1.0.0` 契约，只输出匿名聚合值、7/30/90 天趋势、新鲜度和生成时间。字段缺失保持 `null`，不会被改写为零；过期快照输出 `status: stale`。
