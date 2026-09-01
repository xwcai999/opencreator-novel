# 蛙蛙执行就绪投稿包（schema v2）

投稿包是 Skill 与页面执行引擎之间唯一的文件契约。Skill 负责整理事实并生成/预检投稿包；页面执行引擎只消费投稿包，不补写、猜测或替换业务字段。

## 版本选择与兼容边界

| 输入 | 用途 | 兼容范围 | 输出要求 |
|---|---|---|---|
| `schema_version: 2` | 新的执行就绪投稿包 | 严格检查 `type`、`campaign`、`workflow`、业务字段和本地文件 | 新生成材料必须使用 v2；不自动降级 |
| `schema_version: 1` | 历史投稿元数据 | 由 Python 本地预检按旧平面字段解释，可缺少 v2 的 `type`、`campaign`、`workflow`，并保留旧字段别名/相对路径兼容 | 只作为本地输入兼容；进入页面工作流前显式整理为 v2 |
| 未提供 `schema_version` | 无版本 legacy 平面元数据 | 由 Python 本地预检按旧调用方边界解释；仍须通过必填材料、真实文件和路径安全检查 | 只作为本地输入兼容；进入页面工作流前显式整理为 v2 |
| 其他版本或损坏的 v2 | 不支持 | 失败关闭，不猜测迁移 | — |

这里的投稿包版本号只指本契约。`wawa.stats.v1` 是可选的统计数据契约，`wawa-category-snapshot`/`wawa-tag-snapshot` 是分类标签事实库契约；它们不能填入投稿包的 `schema_version`，也不能互相替代。

legacy 输入即使被内部规范化，也不会改写原始 JSON。为兼容旧调用方，预检结果继续提供 `mode`、`rules`、`page_verification`、`word_count`、`word_count_source` 和可选的 `wawa_snapshot`；v2 的严格字段以本文为准。

## v2 规范结构

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
  "cover": "D:\\allowed\\cover.png",
  "manuscript": "D:\\allowed\\manuscript.txt",
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

### 字段规则

- `schema_version` 必须是数字 `2`，`type` 必须是 `wawa-submission-package`。
- `title`、`pen_name`、`summary`、`channel`、`status`、`category`、`categories`、`tags`、`cover` 和 `manuscript` 是 v2 投稿包的业务必填字段。作品名不超过 80 字符，简介必须是正式内容且不超过 500 字；“暂无简介”等占位内容不能通过材料预检。
- `category` 是短篇/长篇入口类型；`categories` 是固定快照中的完整三级路径。两者是不同字段，不可互相替代。男频/女频的路径根必须匹配频道，全频才可使用固定树中的其他合法根。
- `tags` 只放固定标签快照中的页面标签，最多 10 个且不可重复；作者自定义值单独放 `custom_tags`，最多 5 个、每个不超过 30 字符且不可重复，不能把自定义值伪装成固定标签。页面引擎还会按当前活动配置决定是否允许创建自定义标签。
- `campaign` 必须是对象，`name` 非空，`match_mode` 固定为 `exact`。`code` 可为空，只有从实时页面活动列表确认后才写入；禁止猜测、默认选择第一项或使用测试活动码。
- `workflow` 必须是 `{ "mode": "page_prefill", "final_submit": "human_only" }`。任何其他值都阻断；执行引擎没有代点最终提交或勾选版权协议的动作。
- `word_count` 可选，仅作为本地估算或展示信息；不能用声明字数替代缺失、损坏或无法解析的正文，且本地字数不得阻断用户主动触发的 `prepare`。最终以页面回读的解析字数和提示为准。

### 真实文件与允许根目录

- `cover`、`manuscript` 和 `history_achievement_images` 中的路径必须指向本地真实存在的普通文件；目录、断链、远端 URL、Data URI 和只填写 `size_bytes` 的声明都不算文件。
- v2 路径写成绝对路径。校验时先解析路径，再要求解析后的真实路径位于调用方允许的根目录内；页面引擎使用配置中的 `storage.allowedRoots`，本地预检使用其声明的 `base_dir`/允许根。任何 `..` 越界或符号链接指向根目录外的路径都必须拒绝。
- Python 本地预检使用平台级频道与分类事实；页面引擎可通过运行配置进一步收窄允许频道、活动和自定义标签策略。配置收窄属于部署门禁，不能反向扩大本地预检已拒绝的范围。
- 扩展名、实际文件大小和文件内容都要校验：封面/证明图必须是允许格式且具有对应图片结构；TXT 必须可读；DOCX 必须是可解析的 OOXML 文档。旧式 `.doc` 不能靠改扩展名或声明字数冒充可解析正文。
- 记录中的 `size_bytes` 只能作为提示，实际文件系统 `stat` 和内容读取结果优先。预检结果应避免泄漏机器绝对路径；投稿包本身只在受控的本地允许根目录中使用。

legacy 输入可继续使用旧的相对路径，按旧调用方声明的 metadata 根解析；上述真实文件、文件格式/大小和 containment 安全要求不因 legacy 而取消。

## 统计快照与页面 `snapshot` 参数不是同一契约

旧统计兼容 API 使用 `validate_submission()` 的 `snapshot`、`snapshot_path`、`snapshot_now`，或预检 CLI 的 `--snapshot`（别名 `--snapshot-path`）和 `--snapshot-now`。它只接受可选的 `$wawa-source` `wawa.stats.v1` 本地快照，用于 TTL/新鲜度、脱敏和 `wawa_snapshot` 聚合；不会填写或覆盖投稿包字段。统计快照无效或过期时标记未消费/未实时复核，不把部分数据当成投稿事实。

页面入口 `scripts/run_page_workflow.py` 的 `--snapshot` 是另一含义：只在 `taxonomy-sync` 动作中指定分类快照文件路径，供 `wawa-category-snapshot` 更新使用。不要把 `wawa.stats.v1` 传给 `taxonomy-sync --snapshot`，也不要把页面工作流参数当作统计 API；`dry-run`/`prepare` 只消费投稿包。

## 执行结果

执行引擎可以补充本地文件校验、页面字数回读和状态日志，但不得回写投稿包或替换作者事实。日志和公开状态不得包含 Cookie、请求头、浏览器存储、账号标识或未经脱敏的统计/作品信息。`prepare` 只表示已预填并停在最终提交前；最终复核和提交始终由用户在可见页面中亲自完成。
