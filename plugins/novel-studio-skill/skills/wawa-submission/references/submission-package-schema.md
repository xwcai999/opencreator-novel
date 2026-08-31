# 蛙蛙执行就绪投稿包

投稿包是 Skill 与页面执行引擎之间唯一的文件契约。Skill 负责生成和校验；执行引擎只读取，不补写或猜测业务字段。

## 规范结构

```json
{
  "schema_version": 2,
  "type": "wawa-submission-package",
  "title": "作品名",
  "pen_name": "作者确认的笔名",
  "summary": "不超过500字的正式简介",
  "channel": "全频",
  "status": "完结",
  "category": "短篇",
  "categories": ["出版", "短篇", "现代都市"],
  "tags": ["现实情感", "现代"],
  "custom_tags": [],
  "cover": "D:\\absolute\\cover.png",
  "manuscript": "D:\\absolute\\manuscript.txt",
  "history_achievement_images": [],
  "campaign": {
    "name": "第一届「退款与退场」微观情感叙事大赛",
    "match_mode": "exact",
    "code": ""
  },
  "workflow": {
    "mode": "page_prefill",
    "final_submit": "human_only"
  }
}
```

## 契约规则

- `schema_version` 固定为 `2`，`type` 固定为 `wawa-submission-package`。
- 业务字段保持顶层结构，以兼容现有管理平台并让执行引擎直接消费。
- `category` 是短篇/长篇入口类型；`categories` 是固定快照中的完整三级路径，两者不可互相替代。
- `cover`、`manuscript` 和历史成绩图使用绝对路径；执行引擎还会执行允许根目录、扩展名和大小检查。
- `campaign.match_mode` 固定为 `exact`。`code` 已从实时页面确认时写入；未知时保持空字符串，运行 `campaigns` 后再显式选择，不得猜测或使用测试活动码。
- `workflow.mode` 固定为 `page_prefill`，`workflow.final_submit` 固定为 `human_only`。任何其他值都必须阻断。
- 字数不是契约必填项。可记录 `word_count` 作为信息，但本地校验和执行引擎不得据此阻止 `prepare`。
- 旧版无 `schema_version` 的平面元数据仅用于向后兼容；新生成材料必须使用本结构。

## 执行结果

执行引擎可以补充本地统计和页面回读结果，但不得回写投稿包。日志和公开状态不得包含 Cookie、请求头或浏览器存储。

