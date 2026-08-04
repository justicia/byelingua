# Byelingua 部署设置

这个版本是单人使用，不开放用户注册。管理订阅时使用一个管理员密码。

## 1. Vercel Framework Preset

在 Vercel 项目 Settings → Build and Deployment 中，将 Framework Preset 保持为 `Other`。

## 2. 创建轻量存储

进入 Vercel 项目的 Storage 页面：

1. 点击 Create Database。
2. 选择 Blob。
3. 创建 Private Blob Store，并连接当前项目。
4. Vercel 会自动加入 `BLOB_READ_WRITE_TOKEN`，不要复制到代码中。

## 3. 配置环境变量

在 Vercel 项目的 Environment Variables 中添加：

- `ADMIN_PASSWORD`：自己设置的管理密码。
- `CRON_SECRET`：另一条随机且足够长的密码，用于保护每日任务。
- `RESEND_API_KEY`：从 Resend 获取的 API Key。
- `DIGEST_TO_EMAIL`：接收每日简报的邮箱。
- `EMAIL_FROM`：可选。没有验证域名时可使用 `Byelingua <onboarding@resend.dev>`。

保留现有的 `OPENAI_API_KEY`。所有变量至少选择 Production，然后重新部署。

## 4. 每日运行时间

`vercel.json` 当前设置为每天 `06:00 UTC` 运行。Vercel Hobby 套餐可能在 06:00–06:59 UTC 之间执行。

## 5. 首次使用

1. 打开网站根地址。
2. 点击“输入管理密码”。
3. 输入 `ADMIN_PASSWORD`。
4. 添加一个 RSS 地址。
5. 点击“立即生成并发送”测试完整流程。

管理密码只保存在当前浏览器标签页的 sessionStorage，关闭标签页后会清除。
