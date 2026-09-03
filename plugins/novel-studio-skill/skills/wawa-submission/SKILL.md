---
name: wawa-submission
description: Prepare Wawa Writer (蛙蛙写作) novel projects, emit execution-ready submission packages, and connect them to the local page-prefill engine without duplicating the novel creation workflow. Use when Codex needs to start a “蛙蛙” novel, prepare or audit completed submission materials, map a novel-studio project to the Wawa form, read active campaigns, log in, or prefill the official page for human review and final submission.
---

# 蛙蛙投稿适配

把本 Skill 视为 `novel-studio` 的平台适配层。复用 `$novel-studio` 的开书、规划、写作、审稿、封面、项目校验和投稿 TXT；不要复制或另建第二套小说工作流。

## 投稿包版本与兼容边界

- 新生成的执行就绪投稿包只能使用 `schema_version: 2`、`type: wawa-submission-package`，并满足 `campaign` 与 `workflow` 的严格契约；本 Skill 不再生成旧格式。
- `schema_version: 1` 或省略 `schema_version` 的平面元数据仍由 Python 本地预检作为 legacy 输入兼容。它们可以继续使用旧字段别名、相对路径以及缺少 `campaign`/`workflow` 的旧结构，但不能借兼容路径跳过必填材料、真实文件、格式/大小或路径安全检查，也不会被当作新包输出；进入页面工作流前必须显式整理为 schema v2。
- 版本化投稿包只接受已解析的本地文件路径：封面、正文和历史成绩证明必须是允许根目录内的真实普通文件；声明的 `size_bytes`、远端 URL、Data URI 或“文件名看起来存在”都不能替代实际文件。相对路径以调用方声明的根解析，页面引擎另按 `storage.allowedRoots` 做 containment 校验；符号链接不能逃逸允许根目录。
- legacy 预检继续保留旧结果字段（包括 `mode`、`rules`、`page_verification`、`word_count`、`word_count_source` 和可选的 `wawa_snapshot`），便于旧调用方读取；新包的规范字段以 `submission-package-schema.md` 为准。未知版本或损坏的 v2 契约必须失败关闭。

## 两种 `snapshot` 的含义（不要混用）

旧统计快照 API 与页面工作流恰好使用了同名参数，但属于两条完全独立的数据流：

| 场景 | 入口 | `snapshot` 的含义 | 可接受的数据 |
|---|---|---|---|
| 本地统计兼容 API | `validate_submission()` 的 `snapshot` / `snapshot_path` / `snapshot_now`，或预检 CLI 的 `--snapshot`（兼容别名 `--snapshot-path`）/`--snapshot-now` | 可选的本地统计快照；只校验 TTL、脱敏并生成 `wawa_snapshot` | `$wawa-source` 的 `wawa.stats.v1` |
| 页面工作流 | `run_page_workflow.py taxonomy-sync --snapshot <路径>` | 分类快照的输出/替换路径；供分类同步使用 | `wawa-category-snapshot`，不是统计数据 |

统计快照不得填写或覆盖书名、笔名、字数、简介、状态、类目、标签或页面回读；无效/过期统计只标记未消费，不阻断投稿材料。`dry-run` 与 `prepare` 只消费投稿包，不要把 `wawa.stats.v1` 通过页面工作流的 `--snapshot` 传入。详情见 `references/page-workflow.md`。

## 路由

### 蛙蛙开书

当用户说“蛙蛙开书”“按蛙蛙方向写一本”或同义请求时：

1. 读取 `references/wawa-genres.md`。
2. 把图片题材池作为首轮候选边界，并明确频道、目标读者和推荐题材。
3. 调用 `$novel-studio` 执行正常规划与开书流程；把平台、频道、题材依据和偏离风险写入现有 `设定/题材定位.md`，不要改造项目 schema。
4. 推荐题材不是强行套题。现有方向不在题材池时，说明偏离与代价；只有改变题材、核心受众或结局才暂停让用户决定。
5. 不把“推荐题材”伪装成页面三级小说类目。三级类目在投稿时按当前页面映射。

### 完本投稿

这是默认模式。用户提供项目目录、投稿 TXT/DOC/DOCX 或完整小说后：

1. 读取 `$novel-studio` 的 `作品.md`、当前状态、现有投稿就绪证据、封面和最终投稿正文。
2. 长篇 TXT 必须由 `$novel-studio` 的 `scripts/export_submission_txt.py` 从 `正文/` 权威章节重新导出；不要复用无法证明章节结构的旧 TXT。标题严格使用 `第1章 章名`，编码为 UTF-8 无 BOM，禁止 Markdown `#`、补零编号、中文数字编号、缺号或重复编号。
3. 先调用 `$novel-studio` 的现有项目校验，并按其篇幅规则执行相称的终稿审查：目标篇幅达到 5 万字时叠加 `publication-readiness.md`；低于 5 万字时不要强套五万字门禁。不要在本 Skill 重做连续性、盲审、封面生成或正文打包。
4. 读取 `references/wawa-fields.md`、`references/submission-package-schema.md` 和 `assets/submission-material-template.md`；按当前频道与题材查询 `references/wawa-categories.json` 的相关分支，并在 `references/wawa-tags.json` 中核对所选标签。不要为普通投稿把完整分类树全部展开到上下文，也不在每次投稿时重新抓取网页。
5. 从权威作品文件提取可证明的信息；笔名、历史成绩、截图和三级类目无法证明时标为“待确认”，禁止编造。
6. 按 `references/submission-package-schema.md` 生成 `schema_version: 2` 的执行就绪投稿包 JSON，并运行：

```powershell
python <本 Skill 目录>/scripts/validate_submission.py --metadata <元数据.json> --project-root <小说项目目录> --manuscript <投稿文件> --json
```

只传实际存在的可选参数。将结果写入项目 `报告/蛙蛙投稿预检.json`，材料单写入 `报告/蛙蛙投稿材料.md`；没有标准项目时，写入用户指定目录。
7. 三级类目必须匹配固定分类快照中的完整路径；页面标签必须来自固定标签快照，自定义标签仍按页面长度规则单独记录。修复材料层问题后重跑，直到材料阻断项为零或明确列出需要用户补充的字段。字数只记录为本地估算和页面回读信息，不作为本地预检或预填阻断；声明字数不能替代缺失或无法解析的真实正文。

## 页面连接与预填

当用户要求连接页面、登录、读取活动或预填投稿表单时，读取 `references/page-workflow.md`，并通过本 Skill 的 `scripts/run_page_workflow.py` 调用已安装的页面执行引擎。Skill 是工作流入口；执行引擎只消费投稿包，不负责创作、补写材料或猜测缺失字段。页面引擎会再次核对投稿包及其真实文件是否落在配置的 `storage.allowedRoots` 内。

- `campaigns`：从官方页面会话读取当前活动。
- `taxonomy-sync`：在页面拒绝旧分类或用户明确要求刷新时，从官方创建页资源完整刷新三级类目快照并同步执行引擎配置；不上传、不提交。
- `login`：打开隔离的持久浏览器会话，由用户完成人工登录或验证码。
- `dry-run`：验证投稿包与本地文件，不访问页面。
- `prepare`：上传并预填到最终提交前，保留可见页面供用户检查。
- `status` / `cancel`：查看或结束本地运行。

活动必须用实时返回的活动码或唯一的精确活动名匹配；禁止默认选择活动列表第一项。用户主动触发 `prepare` 即表示认可当前稿件字数，本地工具不得以字数范围阻断。若官方页面自身拒绝，保留并展示页面原始提示。`prepare` 成功也只表示预填完成，不代表已提交、已签约或平台接受。

页面工作流没有 `submit`、确认协议或代点最终按钮的动作。最终提交始终由用户在可见页面中亲自完成。

## 固定分类与标签

- `references/wawa-categories.json` 是从官方创建页一次性提取的完整三级分类树，保留根节点、父子关系、页面值、来源脚本、抓取时间和来源脚本 SHA-256。
- `references/wawa-tags.json` 是用户确认截图中的固定页面标签白名单，保留原顺序、大小写和符号。
- 日常投稿只读取这两个本地快照，不为每本作品重复访问网页。
- 只有页面拒绝已有值、固定库无法覆盖作品或用户明确要求刷新时，才重新抓取并整体替换快照；禁止静默增补、删改或按记忆修正。
- 频道为男频或女频时，三级路径根节点必须与频道一致；全频可以选择固定树中的任一合法根路径。

## 规则优先级

1. 用户在当前任务中明确确认的事实。
2. 用户确认的固定标签快照与从蛙蛙官方创建页抓取的一次性分类快照。
3. 使用时实时核对的蛙蛙官方创建页与投稿页中除分类/标签候选库以外的动态字段。
4. `references/wawa-fields.md` 中带核对日期的缓存规则。

签约资格、活动口径和页面提交校验是不同层的信息。它们可以作为说明和页面回读结果展示，但不得替用户决定是否触发预填，也不得成为本地阻断。

## 输出

交付三部分：

- 可直接照表填写的投稿材料与符合 `schema_version: 2` 契约的投稿包；
- 阻断项、待确认项和非阻断风险；
- 复用的 `novel-studio` 校验证据及本次蛙蛙平台预检结果。

材料至少覆盖：正文来源、封面、作品名称、笔名、投稿入口、长篇分类、频道、作品状态、三级类目、标签、必填且不超过 500 字的正式简介，以及可选历史成绩证明。不得以“暂无简介”等占位内容通过预检。

## 安全边界

- 只有在用户明确要求页面操作时才运行 `login` 或 `prepare`；无论何种授权都不代点最终提交、不勾选版权协议。
- `workflow.final_submit` 必须保持 `human_only`；页面工作流没有自动提交动作。用户必须在可见页面中自行复核并亲自点击最终提交。
- 不伪造笔名归属、历史收益、签约凭证、截图、完结状态或正文数据。
- 不因表单适配修改正文事实；正文问题交回 `$novel-studio`。
- 页面不可访问时标注“未实时复核”，不要声称缓存规则仍是最新。
