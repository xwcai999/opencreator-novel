# 贡献指南

感谢参与 OpenCreator Novel。贡献应保持实现可审计、默认本地最小权限，并且不把用户项目数据带入仓库。

## 开始前

- 面向用户的改动必须同步更新双语 README：`README.md` 与 `README.zh-CN.md`。如果一份语言说明新增、删除或改名，另一份必须在同一变更中保持等价信息；代码示例、命令和安全限制也要同步。
- 先阅读 `plugins/novel-studio-skill/skills/novel-studio/references/method-sources.md` 及与改动相关的参考文件。引入外部方法时，更新 `THIRD_PARTY_NOTICES.md`，说明 URL、许可证状态、采用的抽象方法和明确排除项。
- 贡献只针对本仓库的 Skill、脚本、插件 manifest、文档和测试；不要把某个用户小说项目当作测试 fixture 提交。

## 本地验证

在 Ubuntu、Windows 或等价环境中，从仓库根目录运行：

```text
python -m pip install Pillow
python -m json.tool plugins/novel-studio-skill/.codex-plugin/plugin.json
python -m unittest discover -s tests -p "test_*.py" -v
```

提交前还要完成 Skill/plugin 校验：确认 `plugins/novel-studio-skill/.codex-plugin/plugin.json` 是有效 JSON，插件内的 `skills/novel-studio/SKILL.md` 具有成对的 YAML frontmatter 分隔线，并且 manifest 指向插件内存在的 `skills/` 目录。CI 中的校验是自包含的，不依赖开发机上的绝对路径或不可复现的系统级 Skill validator；若本机 validator 无法可靠调用，不要把本机路径写入工作流、文档或提交。

## 数据与安全边界

禁止提交：

- 用户稿件、章节草稿、人物设定、项目状态或任何来自用户项目的未脱敏内容；
- API key、访问令牌、私钥、`.env` 文件、浏览器会话、内部 URL 或带凭据的日志；
- `__pycache__/`、`.venv/`、`dist/`、`build/`、`*.egg-info/`、临时目录、备份目录和其他本地缓存/派生运行产物。

测试 fixture 应使用最小、虚构且可公开的文本。日志和截图提交前必须脱敏；发现凭据泄露时，先按 [`SECURITY.md`](SECURITY.md) 的私密报告流程处理，不要在 issue 或 PR 中公开。

## Pull Request 要求

PR 描述应说明变更范围、行为影响、验证命令和残余风险，并勾选 `.github/PULL_REQUEST_TEMPLATE.md` 中的清单。涉及方法来源或许可证的改动必须同时更新第三方通知；涉及用户可见行为或命令的改动必须同步双语 README。

不要引入隐藏联网、自动下载、权限提升、宽泛覆盖或递归删除。封面外部集成必须保持显式可选，并说明凭据不由本仓库保存。

### Wawa Writer boundary

Keep Wawa Writer support offline and unofficial. Tests and fixtures must use fictional local data; never add platform credentials, browser sessions, real account data, authenticated collectors, login automation, uploads, or submission calls. Missing metrics must remain `null`, not fabricated as zero.

### 蛙蛙写作边界

蛙蛙写作支持必须保持离线和非官方。测试与 fixture 只能使用虚构的本地数据；禁止加入平台凭据、浏览器会话、真实账户数据、已认证采集器、登录自动化、上传或投稿调用。缺失指标必须保持 `null`，不得伪造为 0。
