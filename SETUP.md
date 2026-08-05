# Byelingua 部署设置

Byelingua 会按国家抓取音乐媒体，将新文章翻译或摘要后保存到网站，并可选发送邮件简报。

## Vercel 设置

1. 在 Vercel 导入 GitHub 仓库，Framework Preset 选择 `Other`。
2. 在 Storage 中创建并连接一个 Private Blob Store。Vercel 会自动添加 `BLOB_READ_WRITE_TOKEN`。
3. 在 Environment Variables 中设置：
   - `OPENAI_API_KEY`：OpenAI Platform API 密钥。
   - `ADMIN_PASSWORD`：网站订阅管理密码。
   - `CRON_SECRET`：Vercel 定时任务访问密钥。
   - `OPENAI_MODEL`：可选，默认 `gpt-5-mini`。
   - `RESEND_API_KEY`、`DIGEST_TO_EMAIL`、`EMAIL_FROM`：可选；仅在需要邮件简报时设置。
4. 重新部署项目。

## 使用方法

1. 打开网站，首页会按国家显示已处理的文章。
2. 点击“管理订阅”，输入 `ADMIN_PASSWORD`。
3. 添加普通网站首页或 RSS 地址；国家可以自动识别，也可以手动选择。
4. 为每个来源选择摘要/全文翻译和输出语言。
5. 点击“立即更新”，或等待每天的定时任务。

默认包含 BackstageClassical、Scherzo 和 Slipped Disc。已有 Blob 配置不会被默认值覆盖；如部署过旧版本，可在管理区手动添加这些来源。
