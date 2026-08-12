---
name: wawa-submission
description: Prepare and locally pre-check Wawa Writer (蛙蛙写作) long-form submission materials. Use when Codex needs to adapt an existing $novel-studio project, or perform a standalone offline metadata-plus-manuscript pre-check without a novel project. Never present it as an official Wawa tool or as a guarantee of platform acceptance or signing.
---

# 蛙蛙投稿材料与离线预检

本 Skill 是非官方的材料适配与本地预检工具，不代表蛙蛙写作，也不自动登录、上传、勾选协议、提交或签约。它只整理作者提供的事实，并检查本地文件与元数据；“本地预检通过”不等于页面接受、平台审核通过或正式签约。

## 双模式路由

先判断安装形态，再选择唯一模式；不要把两个模式拼成第三套小说工作流。

### 集成模式（同仓插件）

当 `novel-studio-skill` 插件已安装且任务需要项目级规划、审稿、封面或连续性证据时：

1. 需要新建或改写小说时，调用 `$novel-studio` 完成创作工作流；本 Skill 只负责蛙蛙字段、材料单和预检，不复制项目 schema、连续性台账或审稿流程。
2. 完成投稿材料时，读取 `$novel-studio` 的 `作品.md`、正文、封面和已有报告；只把可证明事实映射到元数据，缺失的笔名、三级类目、版权或成绩证明标为“待确认”。
3. 运行本 Skill 的预检脚本时可传 `--project-root`，但仍应显式传 `--manuscript`（除非脚本契约另有说明）；项目适配器只读取投稿相关文件，不替代 `$novel-studio` 的完整项目校验。

### 独立模式（只复制本 Skill）

当用户只安装 `skills/wawa-submission/`，或没有标准小说项目时：

1. 仅接收一个元数据 JSON 和一个本地投稿稿件（`.docx` 或 `.txt`）；不要求、也不要创建 Novel Studio 项目目录。平台可能接受旧式 `.doc`，但本地标准库无法可靠解析，须先转换为真实 DOCX 或 TXT。
2. 只做离线材料预检：字段完整性、简介长度、三级类目是否由用户提供、封面/证明文件路径与大小、稿件扩展名和本地字数估算。
3. 不调用 `$novel-studio`，不读取或猜测项目设定、章节台账、审稿报告，不把独立预检结果写成项目级连续性或出版就绪认证。

独立模式命令：

```powershell
python <本 Skill 目录>/scripts/validate_submission.py `
  --metadata <元数据.json> --manuscript <投稿稿件.txt> --json
```

集成模式命令（已有项目时）：

```powershell
python <本 Skill 目录>/scripts/validate_submission.py `
  --metadata <元数据.json> --project-root <小说项目目录> `
  --manuscript <投稿稿件.txt> --json
```

只传实际存在的路径；不要为了“通过”伪造字数、状态、类目、笔名、收益或证明图片。

## 工作流

1. 读取 `references/wawa-fields.md`，先检查其规则缓存元数据。`checked_at` 距当前日期超过 `stale_after`（默认 7 天）时，规则一律标记“未实时复核”，不能据此声称页面仍有效。
2. 读取 `references/wawa-genres.md`，将其中内容当作非官方、来源授权不完整的选题示例；不得把示例词冒充蛙蛙后台官方类目。三级类目和标签只能填写用户在当前页面看到并确认的原文。
3. 读取 `assets/submission-material-template.md`，从权威作品文件或用户输入提取书名、笔名、频道、状态、简介和文件路径；无法证明的值保留“待确认”。
4. 运行预检脚本，区分 `errors`、`blockers` 和 `warnings`。本地 TXT 字数只是估算，页面解析结果优先。
5. 输出材料单、阻断项/待确认项/非阻断风险，以及本次预检的输入、时间和规则来源。修复材料层问题后可重跑；不要修改正文事实来迎合字段。

## 规则分层（必须分开记录）

- **公开页正式签约口径：**蛙蛙写作公开投稿提示目前写明长篇达到 **10 万字**方可正式签约；这是公开页的当前缓存陈述，仍需提交前实时复核，不是签约保证。
- **历史表单观察值：**旧快照曾观察到“连载约 2 万字、完结约 3 万字”的状态化表单校验。它不是公开页的正式签约口径，也不是当前一定存在的门槛；只能作为历史风险提示，不能替代实时页面结果。

材料单必须分别记录：公开页正式签约口径、历史 2/3 万观察值、当前页面解析字数、页面状态和实际错误提示。不要把 10 万、2 万、3 万合并成一个“平台门槛”，也不要把任何一个数字写成接受或签约承诺。

## 输出要求

交付以下三部分：

- 可复制填写的投稿材料单（正文来源、封面、作品名、笔名、投稿入口、长篇分类、频道、状态、三级类目、标签、正式简介、可选成绩证明）；
- 阻断项、待确认项、非阻断风险，并注明是本地检查还是实时页面证据；
- 预检 JSON/人类可读摘要，包含字数来源、规则 `checked_at`、`source`、`confidence`、`stale_after`。

简介必须是正式内容且不超过页面当前限制；“暂无简介”等占位内容始终视为阻断。三级类目、标签、授权选项和账号归属无法由本地文件证明时，必须待用户在当前页面确认。

## 安全边界

- 本 Skill 与蛙蛙写作无隶属、背书或官方授权；不要使用“官方工具”“保证签约”“一键投稿”等表述。
- 不自动登录、保存密码或 token，不自动打开提交动作，不自动上传正文、封面或成绩证明；如用户另行授权页面操作，也必须先明确范围并把本 Skill 的本地预检与页面动作分开报告。
- 不伪造笔名归属、历史成绩、收益、签约凭证、截图、完结状态、字数或正文；不在仓库加入截图、Logo、收益数据或真实稿件。
- 不因表单适配改写小说正文、设定或项目事实；创作、连续性和审稿问题交回 `$novel-studio`（仅集成模式）。
- 页面不可访问或缓存过期时，明确写“未实时复核”；不要把缓存字段当成永久接口文档。
