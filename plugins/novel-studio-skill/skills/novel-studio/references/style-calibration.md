# 单书文风启动校准

## 目标

为当前小说建立独立声音。不得读取、复制或继承其他小说的文风档案；模型版本也不能代替本书校准。默认由隔离模型评审样稿，不要求用户选择 A/B/C。

## 控制场景与候选

从本书读者契约、主角压力和前三章承诺中选择一个 600–1000 字的场景。固定 POV、人物目标、场景事实、必须动作、信息边界和结束节点；三个候选只能改变表达方式，不能改变剧情质量。

1. 使用同一控制卡生成三份正文，在叙事距离、句法节奏、对白潜台词、心理呈现和感官重点上形成可感差异。
2. 生成后随机映射为 A/B/C，删除模型名、风格说明、生成顺序和评价词。
3. 把纯正文保存为同一校准目录的 `candidate-a.md`、`candidate-b.md`、`candidate-c.md`。
4. 不要用不同剧情、结局、角色高光或信息量制造“文风差异”。

## 隔离模型盲评

复制 `assets/style-calibration-evaluation.json.tmpl` 为同目录的 `panel-evaluation.json`。使用至少 3 个且数量为奇数的隔离评审上下文；生成过任一候选的上下文不得参评。每个评审只接收控制卡、A/B/C 纯正文和以下统一量表：

- `target-reader-fit`：是否兑现目标读者期待。
- `voice-distinctiveness`：声音是否清楚、可辨认而非模板化。
- `cross-chapter-sustainability`：能否稳定支撑本书篇幅而不迅速疲劳。
- `character-elasticity`：能否承载不同人物、情绪和场景强度。
- `ai-artifact-risk`：套话、解释腔、整齐过度和机械节奏风险是否较低。

隐藏候选来源、风格标签和模型身份。每个评审独立给出 A/B/C 完整排序与简短理由，不查看其他评审输出。协调者按第一名 3 分、第二名 2 分、第三名 1 分汇总；最高分平票时，使用一个未参与生成或首轮评审的新隔离上下文，只对平票候选排序。不得由协调者任意指定胜者。

多个隔离上下文若使用同一底层模型，仍可能存在偏好相关性；在报告中如实记录，不能把模型票数表述成真实读者数据。

## 证据与草稿

复制 `assets/style-calibration-report.md.tmpl` 为 `报告/文风校准/<calibration-id>/calibration-report.md`，填写控制场景、评审限制和确定性胜者。按胜出样稿提炼同目录 `profile-draft.md`：

- 保持 `type: style-profile`、正确项目 ID、`profile-version: 1` 和 `status: inactive`。
- 完成叙事声音、场景表达和稳定偏好，不保留占位内容。
- 人物专属语言写入角色文件，不混入全书档案。
- 自动选择只允许 A/B/C；`mixed` 仅供用户明确覆盖时使用。

## 安全激活

模型评审默认路径先预览，再使用返回的当前档案哈希写入：

```powershell
python scripts/activate_style_profile.py --project-root <项目> --calibration-report <报告.md> --evaluation-file <panel-evaluation.json> --profile-draft <草稿.md>
python scripts/activate_style_profile.py --project-root <项目> --calibration-report <报告.md> --evaluation-file <panel-evaluation.json> --profile-draft <草稿.md> --expected-current-sha256 <哈希或missing> --apply
```

旧人工报告或用户主动覆盖时使用 `evaluation-mode: user`、`status: confirmed` 和 `--user-confirmed`；该兼容路径可以选择 `mixed`。首次激活后写手才能读取文风档案。重新校准仍须匹配当前 active 档案哈希，不自动漂移或回改旧正文。
