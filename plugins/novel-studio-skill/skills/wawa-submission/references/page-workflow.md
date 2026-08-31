# 页面连接工作流

本工作流把执行就绪投稿包交给本机 Playwright 引擎。它只支持登录、读取活动、离线预检、预填、状态和取消，不支持最终提交。

## 入口

```powershell
python <Skill目录>/scripts/run_page_workflow.py <action> [参数]
```

动作：

- `campaigns --allow-live`：读取当前活动。
- `taxonomy-sync --allow-live`：从当前官方创建页资源完整刷新三级类目快照，并同步页面执行引擎配置；不登录、不上传、不提交。
- `login --allow-live`：打开隔离会话供用户登录。
- `dry-run --metadata <投稿包.json>`：离线验证。
- `prepare --metadata <投稿包.json> --campaign-code <实时活动码> --allow-live`：预填并停在最终提交前。
- `status [--run-id <运行ID>]`：读取状态。
- `cancel --run-id <运行ID>`：结束运行。

页面操作必须由当前用户明确要求；`prepare` 会向蛙蛙上传正文和封面。`taxonomy-sync` 只读取官方公开页面资源并原子更新本地分类快照。验证码、登录过期、安全验证、风控、非白名单域名或页面结构变化均立即停止并交还人工。

## 引擎发现

优先级：

1. 命令行 `--engine` 指定的入口文件；
2. 环境变量 `WAWA_SUBMISSION_ENGINE`；
3. 当前工作区标准入口 `D:\\claw\\scripts\\wawa-submission-playwright\\wawa-submission-playwright.mjs`。

入口必须是实际存在的 `wawa-submission-playwright.mjs`。不得把浏览器 Cookie、storageState 或日常 Chrome profile 复制进投稿包。

## 人工最终提交

`prepare` 成功只表示字段和文件已填入页面。用户必须在可见页面重新检查作品名、笔名、活动、分类、标签、简介、文件和平台提示，然后亲自决定是否点击最终提交。

