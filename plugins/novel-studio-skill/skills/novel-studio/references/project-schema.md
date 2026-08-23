# 项目数据契约

## 原则

- 把 Markdown 正文和 YAML frontmatter 作为唯一权威数据。
- 把 `索引/`、上下文包和检索结果视为派生物；允许删除并重建。
- 为角色、地点、剧情线和章节分配稳定的 ASCII kebab-case ID。
- 先通过校验再更新 `状态/`；不要让失败草稿污染现行事实。

## 标准目录

```text
{书名}/
├── 作品.md
├── 设定/
│   ├── 题材定位.md
│   ├── 读者契约.md
│   ├── 文风档案.md        # 可选启用；新项目默认 inactive
│   ├── 角色/
│   └── 世界观/
├── 大纲/
│   ├── 总纲.md
│   ├── 卷纲/
│   └── 细纲/
├── 正文/
├── 状态/
│   ├── 当前状态.md
│   ├── 时间线.md
│   ├── 关系.md
│   └── 待兑现.md
├── 索引/
├── 报告/
└── 封面/
```

## 最小 frontmatter

`作品.md` 必须包含：

```yaml
schema-version: 2
type: novel-project
id: book-xxxx
title: 书名
scope: short
complexity: light
primary-driver: experiential
secondary-driver: ""
target-words: 20000
serialization: false
planning-horizon: full
continuity-level: light
status: planning
cover-author-attribution: forbidden
```

`title` 只能是作品标题，不得拼接作者、笔名或署名。初始化、迁移、项目校验和封面脚本会共同拒绝“作者：”“笔名：”“某某著”“by 某某”等显式署名格式；封面前仍须与投稿平台的规范书名逐字人工比对。

`设定/文风档案.md` 是可选创作约束，不是必需文件。新项目和新迁移目标可创建 `status: inactive` 的空模板；通过隔离模型盲评或用户明确覆盖后才能改为 `active`。旧项目缺少该文件时必须保持原行为，校验器不得因此报错。文风档案不能覆盖正文事实、人物设定或读者契约。

角色文件建议包含 `type: character`、`id`、`name`、`status`、`relationships`。死亡角色增加 `died-in`。地点使用 `type: location`。卷纲使用 `type: arc` 和 `id`。

主要角色文件可增加创作字段：`desire`、`fear`、`shame`、`debt`、`contradiction`、`stress-behavior`、`verbal-avoidance`、`private-agenda`、`legitimate-counter-interest`。它们用于产生行为和潜台词，不属于必须逐项写入正文的说明。

章节文件必须包含：

```yaml
type: chapter
id: chapter-001
number: 1
title: 章名
status: draft
pov: character-id
characters: [character-id]
mentions: []
locations: [location-id]
arcs-advanced: [arc-id]
allow-deceased-present: []
word-count: 0
```

闪回或特殊叙事中确需让已死亡角色在场时，把角色 ID 显式加入 `allow-deceased-present`，不要关闭全局校验。

v2 项目的章节 `status` 只能为 `draft`、`author-reviewed`、`reader-reviewed`、`revised`、`accepted`。`accepted` 必须形成从第 1 章开始的连续前缀，且 `状态/当前状态.md` 的 `last-accepted-chapter` 必须等于该前缀末章。

每个 v2 `accepted` 章节必须存在 `报告/章节审查/{chapter-id}.json`，记录 1–3 轮审查、作者/首次读者/文体/独立复审结果和最终正文 body 哈希。使用 `record_chapter_review.py` 固定生成；正文随后变化时校验会要求重新审查。schema-version 1 的旧项目保持可读可迁移，但只对这些新证据输出兼容警告。

章节控制卡写入 `大纲/细纲/` 或当轮工作记录，可使用 `reader_reward`、`active_pressure`、`human_cost`、`counter_logic`、`choice`、`memory_point`、`local_closure`、`carryover_debt`、`forbidden_pattern`、`promise_delta`、`stage_momentum`。后两项用于核对标题承诺的可见行动和阶段状态变化；新建或重写控制卡必须填写，旧项目可以在工作记录中派生，不因未迁移旧卡构成确定性硬错。控制卡是规划输入，不是第二套权威状态；审稿报告不得混入章节正文。

## 待兑现台账 v2

`状态/待兑现.md` 使用 `ledger-version: 2`、`tracking-start-chapter` 与 `cold-after-chapters`。表格列固定为：

```text
ID | 类型 | 承诺 | 状态 | 首次出现 | 最近推进 | 兑现窗口 | 正文证据 | 禁止提前揭露 | 所属驱动
```

- 状态只允许 `planned`、`planted`、`reinforced`、`partial`、`active`、`fulfilled`、`dropped`。
- `planned` 表示尚未进入正文；`planted` 表示首次埋设；`reinforced` 表示已有回响；`partial` 表示只兑现一层；`active` 表示规则、代价或关系持续生效；只有全部承诺或最终真相完成后才用 `fulfilled`。
- 长钩、伏笔、悬疑、秘密、真相或线索标为 `fulfilled` 时，正文证据必须明确写出“最终兑现”或“完整揭示”。首次出现、首次证明、阶段闭环都不能替代最终兑现。
- 每项使用稳定 kebab-case ID。章节证据必须指向 accepted 正文；计划窗口可以指向未来章节、下一阶段、卷末或终局。
- 续写前运行 `expectation_ledger.py --target-chapter <下一章号>`。非法结构和超过兑现窗口的非终态项阻断；超过冷线阈值的项目告警并要求本轮规划明确处理。
- 从 `tracking-start-chapter` 起，章纲 frontmatter 必须包含 `expectations-advanced`、`expectations-fulfilled`、`expectations-forbidden` 与 `continuity-sources`。前三项引用台账 ID；`continuity-sources` 列出本章必须读取的角色、地点、规则、关系或时间线 Markdown，构建上下文时优先于词项检索注入。
- 旧台账保持兼容并输出迁移警告；新项目和显式迁移项目使用 v2 硬门禁。

## 工具语义

运行要求：Python 3.10+；当前权威封面清单与校验使用标准库。封面图像及书名必须由 `$codex-gpt-image` 一次生成，本 Skill 不接触其凭据。`render_cover_title.py` 仅为旧项目兼容并需要 Pillow；其后期叠字产物不能通过当前封面门禁。

- `init_project.py`：只创建新项目；目标目录非空时拒绝执行；创建默认 inactive 的文风档案，不自动启用。
- `validate_project.py`：只读取并输出错误/警告；不修改正文和状态。
- `record_chapter_review.py`：在四类审查通过后写入固定位置的接受证据；不修改正文或权威状态。同一 `chapter-id` 重审时允许覆盖旧审查报告，但必须基于当前正文 body 重新计算哈希并保留真实轮次与结论；不得在正文未变化时伪造新证据。
- `reindex_project.py`：从 Markdown 重建确定性 JSON 索引；重复运行结果应一致。
- `build_context_pack.py`：生成派生上下文包；不得回写状态。
- `expectation_ledger.py`：解析并审计待兑现生命周期，报告结构错误、逾期项与冷线。
- `retrieve_context.py`：执行零依赖词项/实体检索；不要宣称为语义向量 RAG。
- `analyze_prose_trends.py`：只读统计中文对白、段落、重复句式、章末和分析腔趋势；只输出证据，不判定文学好坏。
- `activate_style_profile.py`：校验单书匿名候选、模型盲评或人工覆盖证据与文风草稿；默认只预览，模型路径需可复算的评审 JSON，旧人工路径需显式确认，正式写入还必须匹配当前档案哈希并传入 `--apply`。
- `migrate_project.py`：从源目录复制到新目录；永不修改源项目。

派生输出使用固定隔离区：上下文包、检索和索引只能写 `索引/`；项目与封面校验报告只能写 `报告/`；封面 PNG 只能写 `封面/`。路径越界、扩展名不符或试图覆盖权威 Markdown 时脚本拒绝写入。
