---
name: wawa-source
description: Import, validate, expire-check, aggregate, and redact local versioned Wawa statistics snapshots for offline dashboards. Never collect platform data, access an account, or submit content.
---

# 蛙蛙统计快照

本 Skill 只处理用户已经放在本地的、版本化 JSON 快照。它把快照当作“某个时间点的脱敏数据副本”，不代表蛙蛙写作官方接口、实时页面或平台认可的数据来源。

## 能力边界

- 读取本地 JSON，检查 `schema_version`、时间戳、TTL、数值范围、作品和趋势字段。
- 计算作品数、章节/字数、追读与收益汇总，以及 7/30/90 天窗口趋势。
- 默认输出脱敏视图：移除账号标识、远端作品 ID、书名、作者信息、路径和其他可识别字段，只保留匿名作品序号与统计值。
- 过期或无效快照必须显式标记，不能把旧快照包装成实时结果。
- 允许上层 Dashboard 消费聚合结果；Dashboard 应展示快照时间、过期状态和来源类型。

## 明确禁止

本 Skill 不联网，不实现浏览器自动化，不登录，不读取或保存 Cookie、密码、Token，不上传正文/封面，不提交作品，也不从页面推断缺失字段。任何“抓取”需求都必须先取得平台授权，并在本 Skill 之外设计独立连接器；当前版本没有该连接器。

## 快照工作流

1. 读取 `references/snapshot-schema.md`，确认输入是 `wawa.stats.v1` 契约。
2. 使用 `scripts/wawa_snapshot.py` 的 `load_snapshot` 或 CLI 导入本地 JSON；校验失败立即停止，不继续使用部分字段。
3. 以明确的 `now`（生产默认当前时间，测试使用固定时间）执行 TTL 判断。过期快照可以被诊断，但不能进入“新鲜数据”路径。
4. 对需要展示或写入报告的内容调用 `redact_snapshot`，再调用 `aggregate_snapshot` 生成 Dashboard 所需统计。
5. 输出中同时保留 `captured_at`、`expires_at`、`freshness`、`source.kind` 和校验错误/警告；不要只输出一组孤立数字。

CLI 示例（仅本地文件）：

```powershell
python <本 Skill 目录>/scripts/wawa_snapshot.py validate <快照.json> --now 2026-08-18T12:00:00+08:00
python <本 Skill 目录>/scripts/wawa_snapshot.py aggregate <快照.json> --redact --json
python <本 Skill 目录>/scripts/wawa_snapshot.py dashboard <快照.json> --days 30 --json
```

`wawa-submission` 可以选择性消费同一份快照，但统计快照不能补充或覆盖投稿材料、字数、笔名、类目或页面校验结果。
