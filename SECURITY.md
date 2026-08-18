# 安全策略

## 报告漏洞

请不要通过公开 issue、PR、讨论区或日志粘贴安全漏洞、凭据或可利用细节。优先使用仓库 GitHub 页面的 **Security → Advisories → Report a vulnerability**（Private vulnerability reporting）提交私密报告。

如果仓库没有启用该入口，请按照仓库 **Security** 页面提供的 Security advisory 指引申请私密沟通渠道；本文件不虚构或猜测电子邮箱地址。若只能看到公开入口，也只提交不含漏洞细节的私密渠道请求，等待维护者回复后再传递证据。

报告应包含受影响的文件/版本、复现步骤、影响范围和安全的最小复现材料。请在报告中移除用户稿件、API key、访问令牌、私钥和个人信息。维护者确认并修复后，会在适当范围内通过 GitHub advisory 或发布说明披露状态。

## 支持范围

默认关注当前默认分支及最近一次发布版本。旧版本若仍在使用，请在私密报告中说明版本和环境；是否回补修复由维护者根据影响和可维护性决定。

## 默认安全边界

- 本地脚本默认在用户明确指定的项目根目录、迁移目标或派生报告目录内运行，并遵循最小权限；不递归删除、不宽泛覆盖、不自动提升权限，也不把源项目当作可写目标。
- 校验、检索、分析和真实性扫描等脚本默认只读；写入操作应有明确的目标路径和用户意图，且不得写入仓库外的隐含目录。
- 外部封面集成是可选且显式触发的工作流（例如用户指定的 `$codex-gpt-image`）；本仓库脚本不把它作为隐藏网络依赖，不读取、保存或打印认证信息。
- 不要在测试 fixture、CI 输出或文档示例中使用真实凭据、用户内容或内部网络地址。

如发现脚本违反上述边界，即使尚未形成可利用漏洞，也请按本文件的私密流程报告。

## Wawa Writer offline boundary

Wawa Writer support is deliberately offline and unofficial: it must not request or store platform credentials, automate login, scrape authenticated pages, upload manuscripts, or submit works. `$wawa-source` may read only a user-provided local snapshot and must redact identifiers before Dashboard export. Browser profiles, Cookies, session databases, raw collector logs, real account snapshots, and collectors are prohibited from the repository and release archives.

## 蛙蛙写作离线边界

蛙蛙写作能力明确保持离线且非官方：不得索取或保存平台凭据，不得自动登录、抓取已认证页面、上传稿件或提交作品。`$wawa-source` 只可读取用户提供的本地快照，并必须在导出 Dashboard 数据前移除标识。浏览器 Profile、Cookie、会话数据库、原始采集日志、真实账号快照及采集器均不得进入仓库或 Release 压缩包。
