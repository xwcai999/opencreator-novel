# 原生书名封面工作流

`$codex-gpt-image` 是本路由的可选外部依赖，不随 Novel Studio 分发。开始封面任务前先确认宿主已安装并可调用该 Skill；若不可用，停止封面路由并说明依赖，不影响小说规划、写作、审查、迁移或正文打包。

依赖说明：`$codex-gpt-image` 是封面路由的可选外部依赖。若依赖缺失或不可用，仅封面功能不可用；不得绕过该依赖或改用其他方式生成、补写封面，其余规划、写作、审查、迁移和项目维护功能继续执行。

## 不可覆盖约束

- 必须使用 `$codex-gpt-image` 一次生成完整封面画面与书名；最终交付图的文字像素必须来自该次模型生成。
- 禁止“无字底图＋本地叠字”、后期补字、局部程序化改字或调用 `render_cover_title.py` 产出新封面。
- 有语义、可合理辨识的可见文字白名单只有 `作品.md` 中的规范书名；不得把笔名、作者名、账号、署名、Logo、水印或其他自由文本传入可见文字要求。
- 书名错字、漏字、多字，或出现署名、副标题、宣传语、平台标识等可辨识附加文字时，整张候选图作废并通过 `$codex-gpt-image` 重新生成；不得在本地修字。环境道具上的不可读纹理不单独构成拒绝理由，由人工结合缩略图阅读体验判断。

## 流程

1. 从 `作品.md` 读取规范书名，从题材、主驱动、核心情绪和平台提炼美术方向。
2. 创建 `封面/cover-prompt.md`，逐字引用书名并明确：
   - 书名必须由图片模型与画面一次生成；
   - 只允许该书名作为可见文字；
   - 禁止作者名、笔名、署名、账号、Logo、水印、字母、数字和其他伪文字；
   - 指定书名字体气质、位置、行数和缩略图可读性。
3. 按 `$codex-gpt-image` 流程检查 Codex OAuth，调用 `gpt-image-2` 直接生成完整候选封面。优先保存为版本化路径，例如 `封面/cover-native-v2.png`；不要先生成无字底图。
4. 人工逐字核对候选图中的书名与 `作品.md`。书名错误或出现可辨识附加文案时重新生成整张图片，不做局部或本地文字修复；不可读环境纹理按读者是否会误认成署名或宣传语裁决。
5. 为通过视觉复核的候选生成 `model-native-title` 清单：

```powershell
python scripts/record_generated_cover.py --project-root <项目目录> --image <项目目录/封面/cover-native-v2.png> --prompt-file <项目目录/封面/cover-prompt.md> --model gpt-image-2
```

6. 运行白名单校验。存在独立 OCR 时传入 OCR 文本且结果必须与书名完全一致；无 OCR 时仍须人工逐字复核并保留警告：

```powershell
python scripts/validate_cover_text.py --project-root <项目目录> --image <项目目录/封面/cover-native-v2.png> --prompt-file <项目目录/封面/cover-prompt.md> --ocr-text "<独立OCR结果>" --manual-review-passed --output <项目目录/报告/封面/validation.json>
```

7. 验证通过后才能把候选复制为 `封面/cover.png`，再为 `cover.png` 记录清单并复验。复制不得改变图片像素或叠加文字。

`record_generated_cover.py` 与 `validate_cover_text.py` 都从 `作品.md` 读取书名，不接受 `--title`、作者、笔名、副标题或自由文字参数。`render_cover_title.py` 仅保留旧项目兼容，产物属于 `deterministic-overlay`，新工作流校验必须拒绝。

## 交付

报告最终封面路径、模型、Codex OAuth、`model-native-title`、图片哈希、可见文字白名单、OCR状态和人工视觉复核结果。不要展示或记录 OAuth token。
