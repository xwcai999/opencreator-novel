# 页面连接工作流

本工作流把执行就绪投稿包交给本机 Playwright 引擎。它只支持登录、读取活动、离线预检、预填、状态和取消，不支持最终提交。页面入口只消费 schema v2；schema v1 或无 `schema_version` 的平面 legacy 元数据由本地预检兼容读取，进入页面流程前必须显式整理为 v2 投稿包，不能在页面层静默猜测或改写业务字段。

页面入口先调用 Python 预检验证 v2 契约、真实图片结构和 DOCX OOXML，再由页面引擎检查文件扩展名、大小以及是否落在配置的 `storage.allowedRoots` 内；`..` 越界、断链、目录、远端 URL、Data URI 和符号链接均不能绕过这两层检查。元数据中的 `size_bytes` 不能冒充文件。

两层门禁职责不同：Python 预检验证平台级字段和材料事实；页面引擎再按当前部署配置收窄 `allowedChannels`、标签数量和是否允许创建自定义标签。运行配置可以更严格，但不能放宽 Python 已拒绝的材料。若页面引擎因当前活动配置阻断，应保留其明确原因，不把它误报成 Python 预检失败。

## 入口

```powershell
python <Skill目录>/scripts/run_page_workflow.py <action> [参数]
```

动作：

- `campaigns --allow-live`：读取当前活动。
- `taxonomy-sync --allow-live [--snapshot <分类快照路径>]`：从当前官方创建页资源完整刷新三级类目快照，并同步页面执行引擎配置；不登录、不上传、不提交。
- `login --allow-live`：打开隔离会话供用户登录。
- `dry-run --metadata <投稿包.json>`：离线验证。
- `prepare --metadata <投稿包.json> --campaign-code <实时活动码> --allow-live`：预填并停在最终提交前。
- `status [--run-id <运行ID>]`：读取状态。
- `cancel --run-id <运行ID>`：结束运行。

页面操作必须由当前用户明确要求；`prepare` 会向蛙蛙上传正文和封面。`taxonomy-sync` 只读取官方公开页面资源并原子更新本地分类快照。验证码、登录过期、安全验证、风控、非白名单域名或页面结构变化均立即停止并交还人工。

## `snapshot` 参数的专属含义

本入口的 `--snapshot` 是动作相关参数，**只用于 `taxonomy-sync`**：它指定 `wawa-category-snapshot` 分类快照的写入/替换路径，不是统计数据输入。不要把 `$wawa-source` 的 `wawa.stats.v1` 文件传给 `taxonomy-sync --snapshot`，也不要在 `dry-run` 或 `prepare` 中用它传递统计快照。

旧统计快照兼容 API 属于本地 Python 预检，不属于页面工作流：调用 `validate_submission()` 时使用 `snapshot`、`snapshot_path`、`snapshot_now`，命令行使用 `validate_submission.py --snapshot`（别名 `--snapshot-path`）和 `--snapshot-now`。它只生成可选的 `wawa_snapshot` 新鲜度/聚合结果，不填写或覆盖投稿包字段；统计快照无效或过期时不阻断材料预检。两条数据流必须分开执行、分开记录。

## 引擎发现

优先级：

1. 命令行 `--engine` 指定的入口文件；
2. 环境变量 `WAWA_SUBMISSION_ENGINE`；
3. 当前工作区标准入口 `D:\\claw\\scripts\\wawa-submission-playwright\\wawa-submission-playwright.mjs`。

入口必须是实际存在的 `wawa-submission-playwright.mjs`。不得把浏览器 Cookie、storageState 或日常 Chrome profile 复制进投稿包。metadata 文件本身及其引用的文件都必须通过允许根目录校验；页面引擎配置中的允许根是运行边界，不应通过改写路径或跟随越界链接规避。

## 人工最终提交

`prepare` 成功只表示字段和文件已填入页面，并停留在最终提交前；它不表示已提交、已签约或平台接受。用户必须在可见页面重新检查作品名、笔名、活动、分类、标签、简介、文件、页面解析字数和平台提示，然后亲自决定是否点击最终提交。流程没有自动提交动作，必须保持 `workflow.final_submit: human_only`，也不代勾版权协议。
