---
name: novel-studio
description: Plan, draft, continue, revise, review, migrate, package, and create covers for short-, medium-, or long-form Chinese fiction. Use when Codex needs to start or maintain a novel project, design characters or worldbuilding, create full/volume/chapter outlines, write or repair chapters, run automated publication-readiness pilots and blind full-text reviews, reduce formulaic or AI-like prose through evidence-based authenticity revision, migrate a novel-planner project, prepare platform-facing synopsis copy, or produce a cover through $codex-gpt-image without any pen name or author attribution.
---

# Novel Studio

把中文小说创作视为“读者体验与人物选择驱动的创作 + 可验证的连续性管理”。使用 Markdown 正文与 frontmatter 作为唯一权威数据；索引、上下文包、分析指标和审稿报告都是可再生证据，不得反向覆盖正文事实。

## 核心约束

- 先写清读者为何翻开、为何继续和最终得到什么，再选择结构。不要把商业钩子等同于谜团。
- 从成长、关系、经营、信息、体验、主题、任务中选择一个主驱动，可选一个副驱动。
- 仅当驱动包含“信息”或用户明确要求悬疑时，才强制规划谜团、线索和揭露。
- 让人物在压力下作出带代价的具体选择；不要把人物写成流程执行器、作者观点接口或永远正确的理性人。
- 每章必须给目标读者可感知的回报，但回报可以是关系变化、情绪余韵、生活质感、成长、收益、信息或任务进展，不强制危机、反转、悬念和章章钩子。
- 把全书总字数当作结构结果，不把章节最低字数当作补写命令。章节不足时只允许增加有因果的场景、合并章节或回改大纲，禁止在高潮后追加复盘、表格、计划和主题解释凑字。
- 先规划再写正文；用户已经提供可执行细纲时，直接提取章节控制卡，不重复要求规划或暂停。
- 不把“首次埋设、首次展示或阶段回响”误记为最终兑现。续写前必须审计 `状态/待兑现.md`，并把全部非终态项优先注入上下文；不得只凭上一章或查询词召回长线事实。
- 章节需通过确定性校验与阅读接受门禁后再提交状态。审稿意见只能写入报告，不能混进正文。
- 把“去 AI 味”作为真实性修订，不做来源检测或分数优化；机器只定位候选证据，语境裁决和盲读复审决定是否返修。
- 仅把 `status: active` 的 `设定/文风档案.md` 作为正文约束；文件缺失或未激活时保持当前写作流程，不阻断规划、写作、审查或迁移。单书校准默认由隔离模型上下文盲评，不要求用户选择样稿。
- 使用 subagent 写作时采用“主 Agent 总编裁决 + 固定写手顺序创作 + 两类独立审稿并行”的调度；不得并行撰写相邻章节，具体见 `references/chapter-workflow.md`。
- 投稿、出版或五万字以上的完整作品必须先通过自动试写门禁和纯正文阶段盲读。用户负责创作方向与外部提交授权，不作为逐章或每批次的常规质检员；只有继续执行必须改变题材、结局或核心设定时才请求用户决策。
- 审稿者只写报告，不得修改正文。正文和场景返修始终交给同一卷的固定写手；不得把审查解释、连续性辩护或项目术语补进小说。
- 保留用户已有正文、设定和事实。审查普通 TXT/Markdown 或非 v2 项目时默认只读，不启动三章试写、不回写原稿；只有用户明确要求规范化或改稿时，才在新目录建立 v2 项目或隔离副本。迁移与回归测试也必须写入新目录。
- 封面必须显式使用 `$codex-gpt-image` 一次生成完整画面与作品书名；禁止“无字底图＋本地叠字”、后期补字或程序化替换书名。有语义、可合理辨识的可见文字只能是 `作品.md` 中的规范书名，严禁笔名、作者名、署名、账号、Logo、水印和附加文案；不可读环境纹理由人工结合读者观感裁决。
- `$codex-gpt-image` 是封面路由的可选外部依赖。缺失时只说明封面能力不可用并给出安装依赖提示，不得以其他图片工具或本地叠字绕过；规划、写作、审查、迁移和正文打包继续正常执行。

## 请求路由

| 用户意图 | 执行模式 | 必读参考 |
| --- | --- | --- |
| 开书、构思、简介、总纲、卷纲、细纲 | 规划 | `references/planning-workflow.md`、`references/genre-drivers.md`、`references/reader-experience.md` |
| 写一章、续写、日更、写某场景 | 章节写作 | `references/chapter-workflow.md`、`references/reader-experience.md`、当前题材驱动 |
| 修改章节、改纲、检查逻辑、审稿、去 AI 味 | 修订审查 | `references/revision-review.md`、`references/authenticity-revision.md`、`references/quality-gates.md` |
| 跨章趋势、阶段复盘、终稿审查 | 阶段审查 | `references/stage-review.md`、`references/quality-gates.md` |
| 选择正文模型、固定写手、建立或调整文风 | 模型与文风 | `references/model-policy.md`、`references/style-profile.md`、`references/style-calibration.md` |
| 初始化项目、检查目录、建立索引 | 项目维护 | `references/project-schema.md` |
| 从旧 `novel-planner` 项目迁移 | 安全迁移 | `references/migration.md` |
| 审查普通 TXT/Markdown 或其他非 v2 现有稿件 | 只读稿件审查 | `references/revision-review.md`、`references/stage-review.md`；需要项目级连续性时再读取 `references/project-schema.md` 并在新目录规范化 |
| 生成或修改封面 | 封面 | `references/cover-workflow.md`，并显式使用 `$codex-gpt-image` |
| 审查 Skill 的来源、授权或安全边界 | 方法审计 | `references/method-sources.md` |

投稿、出版、完整全本或五万字以上项目还必须读取 `references/publication-readiness.md`；它叠加在规划、章节写作和阶段审查之上，不替代对应参考。

只读取当前任务对应的参考文件。所有参考文件都从本文件直接可达，不沿多层链接继续加载。

## 篇幅与复杂度

同时确定 `scope` 与 `complexity`：

- `scope`: `short`、`medium`、`long`。
- `complexity`: `light`、`standard`、`extended`。

| 篇幅 | 默认规划范围 | 审查节奏 |
| --- | --- | --- |
| `short` | 一次规划完整故事、场景和结局 | 每章轻量接受；中点和终稿阶段审查 |
| `medium` | 完整总纲，当前篇章与后续 3–5 章细化 | 每章接受；每 5–6 章阶段审查 |
| `long` | 全书方向 + 当前卷完整 + 后续 5–10 章 | 每章接受；通用阶段审查每 8–10 章及卷末执行；出版/投稿项目叠加每 6 章窗口 |

复杂度负责“读取与证据深度”，不改变题材结构：

| 复杂度 | 上下文与审查执行 |
| --- | --- |
| `light` | 读者契约、当前状态、细纲、最近前章；控制卡与三类审查可合并呈现；默认上下文包 12k 字符 |
| `standard` | 再读取相关人物/关系/待兑现项；单独保留章节审查证据；默认上下文包 24k 字符 |
| `extended` | 再读取相关世界规则、多线状态和阶段冷线；卷末/阶段报告必须保留；默认上下文包 36k 字符 |

不要只按字数判断复杂度。轻量短篇不得被迫创建长篇级文字报告，但 v2 项目的 accepted 章节仍须保留一份小型机器证据；多时间线短篇可使用 `extended`。

## 项目状态优先级

处理已有项目时依次读取：

1. `作品.md`
2. `状态/当前状态.md`
3. 当前卷纲/篇章纲与目标章节细纲
4. 最近一章正文
5. 与本章直接相关的人物、地点、关系和待兑现项
6. `设定/读者契约.md`
7. 如存在且 `status: active`，读取 `设定/文风档案.md`

不要把聊天记忆、生成计划、分析指标或旧审查报告当作现行事实。需要压缩上下文时运行：

```powershell
python scripts/build_context_pack.py --project-root <项目目录> --chapter <章节号> --query "<本章任务>"
```

## 确定性工具

```powershell
# 初始化
python scripts/init_project.py --project-root <目录> --title "<书名>" --scope short --complexity light --primary-driver experiential

# 校验与索引
python scripts/validate_project.py --project-root <目录>
python scripts/reindex_project.py --project-root <目录>

# 续写前审计长线承诺、伏笔、持续代价与禁止揭露项
python scripts/expectation_ledger.py --project-root <目录> --target-chapter <下一章号>

# 章节四类审查通过后，记录与正文哈希绑定的接受证据，再提交权威状态
python scripts/record_chapter_review.py --project-root <目录> --chapter <章节号> --rounds 1 --author-passed --reader-passed --style-passed --rereview-passed

# 检索与迁移
python scripts/retrieve_context.py --project-root <目录> --query "<剧情问题>" --top-k 6
python scripts/migrate_project.py --source <旧目录> --target <新目录> --title "<书名>"

# 只读文体趋势证据
python scripts/analyze_prose_trends.py --project-root <目录> --json

# 只读真实性候选；只有确定性的流程泄漏可选择阻断退出
python scripts/scan_authenticity_artifacts.py --project-root <目录> --chapter <章节号> --json

# 隔离模型盲评单书匿名样稿后，先预览，再用返回的 current_profile_sha256 显式激活
python scripts/activate_style_profile.py --project-root <目录> --calibration-report <报告.md> --evaluation-file <评审.json> --profile-draft <档案草稿.md>
python scripts/activate_style_profile.py --project-root <目录> --calibration-report <报告.md> --evaluation-file <评审.json> --profile-draft <档案草稿.md> --expected-current-sha256 <哈希或missing> --apply
```

先读取 `references/project-schema.md` 再选择项目脚本参数。文体指标与真实性候选只用于定位要回看哪些章节，不得据此自动判好坏、判断文本来源或改写正文。

## 交付规则

- 只请求聊天方案时在聊天中交付，不擅自创建项目。
- 请求文件时写入目标项目或明确的暂存目录，并报告新增、修改和未触碰的文件。
- 新书规划包含一句话卖点、作品简介、短简介、标签、读者契约和前三章具体承诺。
- 投稿型长篇在自动试写、阶段盲读和整本投稿 TXT 盲读全部通过前，不得标记“全本质量通过”或进入最终投稿包装。
- 章节交付说明读者回报、人物选择与代价、审查轮次、接受结论和获准提交的状态变化。
- 审查先列硬错误，再列阅读阻断项，最后列工艺警告；不要用总分掩盖问题。
- 普通修订中同一章最多三轮“审查—定向修订”；出版/投稿叠加路径中同一根因层最多两轮。仍不通过时停止盲改，定位大纲、人物、场景或语言根因。
- 封面交付报告 `$codex-gpt-image`、`model-native-title` 生成模式、输出路径、可见文字白名单和验证结果，不展示或记录认证令牌。

## 参考导航

- `references/project-schema.md`：目录、frontmatter、权威数据与脚本语义。
- `references/genre-drivers.md`：七类叙事驱动和非悬疑结构选择。
- `references/planning-workflow.md`：短中长规划、读者契约与人物压力。
- `references/reader-experience.md`：读者奖励、章节控制卡和防案例化原则。
- `references/chapter-workflow.md`：写前、初稿、独立审查、修订与状态提交。
- `references/revision-review.md`：首次读者模拟、人物声音、逆向审稿和改纲。
- `references/authenticity-revision.md`：只读候选扫描、语境裁决、最小修订与盲读复审。
- `references/quality-gates.md`：硬错误、阅读阻断项、工艺警告与覆盖规则。
- `references/stage-review.md`：跨章趋势、审查频率与分析器使用。
- `references/model-policy.md`：正文、总编和审稿角色的模型选择与稳定性策略。
- `references/style-profile.md`：可选文风档案的激活、证据和更新规则。
- `references/style-calibration.md`：每本小说独立的 A/B/C 匿名样稿、隔离模型盲评与安全激活。
- `references/migration.md`：旧项目的无覆盖迁移。
- `references/cover-workflow.md`：Codex OAuth 原生书名图片生成及无笔名封面流程。
- `references/method-sources.md`：外部方法来源、许可证、采用与排除项。
- `references/publication-readiness.md`：投稿型长篇的自动试写、三类盲审、失败路由、阶段放行和整本纯 TXT 验收。
