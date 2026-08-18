# Privacy Policy / 隐私政策

Effective date / 生效日期：2026-08-11

## English

OpenCreator Novel is a local, file-based Codex Skill. The scripts bundled in this repository do not provide a hosted service, collect telemetry, create user accounts, read authentication tokens, or transmit manuscripts over the network. They read and write only the files and output paths selected by the user or the Codex host.

The optional cover workflow delegates image generation to a separately installed `$codex-gpt-image` Skill. That integration is not bundled here and is governed by the privacy terms of the service and Codex host used for generation. Review those terms before sending manuscript text, reference images, or personal information.

Do not commit private manuscripts, credentials, personal data, or unpublished submission materials to public repositories. Security issues should be reported as described in [SECURITY.md](SECURITY.md).

## 中文

OpenCreator Novel 是一个基于本地文件的 Codex Skill。本仓库内置脚本不提供托管服务，不收集遥测数据，不创建用户账户，不读取认证令牌，也不会通过网络传输小说正文。脚本只读写用户或 Codex 宿主明确选择的文件与输出路径。

可选封面流程会把图片生成交给另行安装的 `$codex-gpt-image` Skill。本项目不捆绑该集成；生成过程受所用服务及 Codex 宿主的隐私条款约束。发送正文、参考图或个人信息前，请先审阅相应条款。

请勿把私密稿件、凭据、个人数据或未公开投稿材料提交到公开仓库。安全问题请按 [SECURITY.md](SECURITY.md) 的方式报告。

### Wawa Writer submission boundary

OpenCreator's Wawa Writer (蛙蛙写作) workflows are unofficial and offline. They do not log in to Wawa, retain credentials, scrape pages, upload manuscripts, or submit works. The submission adapter validates local files selected by the user; the statistics source accepts only user-provided local JSON and emits redacted aggregates. It does not bundle a collector or retain work titles, remote identifiers, accounts, Cookies, tokens, or browser sessions in Dashboard output.

### 蛙蛙写作投稿边界

OpenCreator 的蛙蛙写作流程是非官方离线工具，不会登录蛙蛙写作、保存凭据、抓取页面、上传稿件或提交作品。投稿适配器只校验用户选择的本地文件；统计数据源只接受用户提供的本地 JSON，并输出脱敏聚合数据。公开包不含采集器，Dashboard 输出不保留作品名、远端标识、账号、Cookie、令牌或浏览器会话。
