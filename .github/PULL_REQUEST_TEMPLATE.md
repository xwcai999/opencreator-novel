## 变更摘要 / Summary

<!-- 说明做了什么、为什么做，以及不在范围内的内容。 Describe what changed, why, and what is out of scope. -->

## 变更范围 / Scope

- [ ] Skill 或脚本 / Skill or scripts
- [ ] 插件 manifest / Plugin manifest
- [ ] 文档或治理文件 / Documentation or governance
- [ ] 测试 / Tests

## 验证 / Validation

<!-- 粘贴实际运行的命令和结果摘要。 List commands actually run and summarize results. -->

- [ ] `python -m json.tool plugins/novel-studio-skill/.codex-plugin/plugin.json`
- [ ] `python -m unittest discover -s tests -p "test_*.py" -v`
- [ ] 已完成与本次改动相关的 Skill/plugin frontmatter、manifest 和自包含校验 / Relevant self-contained checks pass

## 文档与来源 / Docs and sources

- [ ] 面向用户的改动已同步 `README.md` 与 `README.zh-CN.md` / User-facing changes are synchronized in both bilingual READMEs
- [ ] 新增或调整外部方法已更新 `THIRD_PARTY_NOTICES.md` / External method changes are recorded in third-party notices
- [ ] 未写入本机绝对路径或依赖不可用的系统 validator / No machine-specific paths or unavailable system validators are required

## 安全与数据 / Security and data

- [ ] 未提交用户稿件、凭据、密钥、私人数据、缓存或派生运行产物 / No manuscripts, credentials, secrets, private data, caches, or generated artifacts are included
- [ ] 没有隐藏联网、自动下载、权限提升、宽泛覆盖或递归删除 / No hidden network calls, automatic downloads, privilege escalation, broad overwrites, or recursive deletion
- [ ] 外部封面集成（如涉及）仍为显式可选，且仓库不保存认证信息 / External cover integration, if any, remains explicit and optional without stored credentials

## 残余风险与回滚 / Risks and rollback

<!-- 说明已知限制、兼容性影响和如何回滚。 Note known limitations, compatibility impact, and rollback plan. -->
