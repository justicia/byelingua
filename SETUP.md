# Byelingua 部署设置

Byelingua 会按国家抓取公开网站或 RSS，将新文章翻译或摘要后保存到网站。中国栏目还支持手动导入微信公众号文章并保存多语言全文译文。

## 微信公众号文章

1. 登录管理模式，点击“＋ 微信文章”。
2. 粘贴 `mp.weixin.qq.com` 文章链接并选择一种目标语言。
3. 如果微信阻止 Vercel 读取页面，再粘贴标题、公众号名称和原文全文作为备用内容。
4. 同一链接再次选择已有语言时会直接复用结果，不会重复调用 OpenAI；选择另一语言会只新增该语言的译文。

公开展示全文译文前，请确认你拥有原文和译文的发布授权。

## Vercel 设置

1. 在 Vercel 导入 GitHub 仓库，Framework Preset 选择 `Other`。
2. 在 Storage 中创建并连接一个 Private Blob Store。Vercel 会自动添加 `BLOB_READ_WRITE_TOKEN`。
3. 在 Environment Variables 中设置：
   - `OPENAI_API_KEY`：OpenAI Platform API 密钥。
   - `ADMIN_PASSWORD`：网站订阅管理密码。
   - `CRON_SECRET`：Vercel 定时任务访问密钥。
   - `OPENAI_MODEL`：可选，默认 `gpt-5-mini`。
   - `SUPABASE_URL`：Supabase 项目地址。
   - `SUPABASE_PUBLISHABLE_KEY`：浏览器端 Publishable key。
   - `SUPABASE_SERVICE_ROLE_KEY`：服务端 `sb_secret_...` Secret key，只能存放在 Vercel。
   - `RESEND_API_KEY`、`DIGEST_TO_EMAIL`、`EMAIL_FROM`：可选；仅在需要邮件简报时设置。
4. 重新部署项目。

## 使用方法

1. 打开网站，首页会按国家显示已处理的文章。
2. 点击“管理员入口”，输入 `ADMIN_PASSWORD`。
3. 添加普通网站首页或 RSS 地址；国家可以自动识别，也可以手动选择。
4. 为每个来源选择摘要/全文翻译和输出语言。
5. 点击“立即更新”，或等待每天的定时任务。

默认包含 BackstageClassical、Scherzo 和 Slipped Disc。已有 Blob 配置不会被默认值覆盖；如部署过旧版本，可在管理区手动添加这些来源。

## 邀请制账户

1. 在 Supabase SQL Editor 运行 `supabase_schema.sql`。
2. 管理员在网站控制台输入受邀邮箱并创建账户。
3. 受邀用户点击“邮箱验证码登录”，获取并输入验证码。
4. 试运行账户默认最多 3 个网站、每天更新 1 次、每月处理 100,000 字符。
5. 删除订阅网站不会删除已经生成的个人历史文章。
