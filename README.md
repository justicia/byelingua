# Byelingua

**SO MANY COUNTRIES. SO MANY LANGUAGES. I SIMPLY CAN’T.**

Byelingua 是一个按国家整理国际媒体内容的双语阅读与个人订阅平台。公共访客可以使用中文或英语浏览文章；使用邀请码注册的用户可以保存自己的订阅网站、选择内容语言，并获得自动抓取、翻译和文章历史记录。

线上地址：[https://www.bye-lingua.site](https://www.bye-lingua.site)

## 当前功能

### 公共阅读

- 按国家浏览公共订阅文章。
- 中文、英语界面切换。
- 公共文章保存中英文标题和正文。
- 显示当前启用的公共订阅网站。
- 自动跳过已经处理过的重复文章。
- 独立文章页面展示完整译文，并保留原文链接。

### 注册用户

- Supabase Email + Password 登录。
- 公开注册，但必须提供有效邀请码。
- 每位用户最多添加 3 个个人订阅网站或 RSS。
- 永久保存偏好的内容语言。
- 中文和英语为公共语言；其他支持语言供登录用户选择。
- 每次手动更新最多处理 3 篇文章。
- 试运行账户每天可手动更新一次。
- 系统每天法国时间上午 9:00 自动更新一次。
- 个人文章与公共文章分开保存。

### 管理员后台

- 添加、编辑、启用、停用和删除公共订阅网站。
- 单独更新一个来源或一键检查全部公共来源。
- 添加网站后尝试立即发布第一篇新文章。
- 删除文章并清除去重记录，以允许后续重新同步。
- 重新抓取和翻译已有文章。
- 分批补全旧文章的中英文标题和正文。
- 用户可使用邀请码创建账户。
- 手动导入微信公众号文章。

### 微信公众号工具

微信公众号文章由独立部署的 `wechat-article-exporter` 管理：

- 部署平台：Cloudflare Workers。
- 数据存储：Cloudflare KV。
- 访问控制：Cloudflare Access。
- 仅指定管理员邮箱可以登录。
- 导出的文章可由管理员整理后导入 Byelingua。

该工具与本仓库分开部署，管理员入口不要设置为公开页面。

## 技术架构

| 部分 | 技术 |
| --- | --- |
| 前端 | 原生 HTML、CSS、JavaScript |
| API | Python Serverless Functions |
| 部署 | Vercel |
| 公共文章、配置与运行状态 | Supabase |
| 用户、个人订阅与使用记录 | Supabase |
| 登录 | Supabase Auth 邮箱 OTP |
| 翻译与摘要 | OpenAI API |
| 登录邮件 | Supabase Custom SMTP + Resend |
| 定时任务 | Vercel Cron |
| 微信公众号导出后台 | Cloudflare Workers + KV + Access |

## 项目结构

```text
byelingua/
├── api/
│   ├── index.py              # 主 API、抓取、翻译、用户和管理员操作
│   └── cron.py               # Vercel 定时任务入口
├── article.html              # 独立文章阅读页
├── index.html                # 主页面和管理界面
├── requirements.txt          # Python 依赖
├── supabase_schema.sql       # Supabase 基础表和 RLS 策略
├── supabase_bilingual_migration.sql
│                              # 双语与用户订阅相关迁移
├── test_api.py               # API 单元测试
├── vercel.json               # Vercel Functions 与 Cron 配置
└── README.md
```

`index-complete-bilingual.html` 是本地未跟踪的历史/测试文件，不是生产入口，不应提交到仓库。

## 本地运行

要求：Python 3.11 或更高版本；可选安装 Vercel CLI 以模拟 Serverless Functions。

```powershell
python -m pip install -r requirements.txt
python -m unittest -v test_api.py
vercel dev
```

不要在浏览器端或 Git 仓库中保存任何服务端密钥。

## Supabase 设置

1. 创建 Supabase 项目。
2. 在 Supabase SQL Editor 中执行 `supabase_schema.sql`。
3. 再执行 `supabase_bilingual_migration.sql`。
4. 在 Authentication 中启用 Email + Password 登录。
5. 浏览器公开注册保持关闭；账户由服务端验证邀请码后通过 Admin API 创建。
6. 将 Site URL 和允许的 Redirect URL 设置为 `https://www.bye-lingua.site`。
7. 使用 Resend 或其他服务配置 Supabase Custom SMTP。

数据库使用 Row Level Security，登录用户只能读取自己的资料、订阅、文章和使用记录。`SUPABASE_SERVICE_ROLE_KEY` 只能放在服务端环境变量中。

## Vercel 环境变量

在 Vercel 项目的 Environment Variables 中配置以下变量。变量值不要写进 README、Git 提交或前端代码。

| 变量 | 用途 |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `OPENAI_MODEL` | 可选，默认 `gpt-5-mini` |
| `ADMIN_PASSWORD` | Byelingua 管理员后台密码 |
| `CRON_SECRET` | 定时任务认证密钥 |
| `SUPABASE_URL` | Supabase 项目 URL |
| `SUPABASE_PUBLISHABLE_KEY` | 前端可使用的 Publishable Key |
| `SUPABASE_SERVICE_ROLE_KEY` | 仅服务端使用的高权限密钥 |
| `RESEND_API_KEY` | Resend API 密钥（如服务端邮件功能需要） |
| `EMAIL_FROM` | 发件人，例如 `Byelingua <login@auth.example.com>` |
| `MAX_ARTICLES` | 可选，公共文章最大保存数量，默认 200 |

修改环境变量后需要重新部署 Vercel，变更才会生效。

## 自动更新规则

`vercel.json` 配置了两个 UTC Cron：

```text
07:00 UTC — 法国夏令时 09:00
08:00 UTC — 法国冬令时 09:00
```

`api/cron.py` 和服务端日期判断会确保每天只执行正确时区对应的一次任务。

自动任务会：

1. 轮流检查启用的公共订阅来源。
2. 自动跳过重复 URL 或已经处理过的文章。
3. 为符合条件的登录用户更新个人订阅。
4. 每位用户每次最多新增 3 篇个人文章。
5. 自动更新不消耗用户当天的手动更新额度。

## 公共来源管理

管理员登录后可以添加、编辑、停用、删除或单独更新来源，也可以一键检查全部启用来源。保存新网站时系统会尝试发布第一篇文章。某些网站可能拒绝服务器抓取或返回 403；优先使用官方 RSS，没有 RSS 时再使用网页解析。

## 去重与 OpenAI 调用

- 系统先检查历史记录，再决定是否抓取和调用 OpenAI。
- 同一 URL 已存在时不会重复翻译。
- 相同文章的已有语言译文会尽量复用。
- 删除文章时只有选择“允许重新同步”才会同时清除去重记录。
- 管理员重新翻译和补全旧文章会产生新的 OpenAI API 使用量。

## 部署

生产部署由 GitHub 的 `main` 分支触发：

```powershell
git add .
git commit -m "Describe the change"
git push
```

推送后在 Vercel 的 Deployments 页面确认部署成功，再测试首页、双语界面、邮箱登录、管理员操作、定时任务和文章去重。

## 安全注意事项

- 不要提交 `.env`、API Key、管理员密码或 Service Role Key。
- `SUPABASE_SERVICE_ROLE_KEY` 绝不能发送给浏览器。
- 微信公众号后台必须始终受 Cloudflare Access 保护。
- Cloudflare Preview URL 也应设为 Restricted。
- 公开错误信息不要包含密钥、内部请求头或完整服务端响应。
- 密钥疑似泄露时立即轮换，并重新部署。

## 当前状态与下一步

当前已完成：公共中英双语阅读、邀请码注册、Email + Password 登录与密码重置、每用户三个个人订阅、语言偏好持久化、每次最多三篇、每日法国时间 9 点自动更新、Daily Digest、公共订阅管理和管理员微信公众号导出后台。

建议下一步：

1. 通过受保护的服务端接口将微信公众号导出结果导入 Byelingua。
2. 为订阅计划增加付费状态、额度和 Stripe 支付。
3. 增加失败来源监控、抓取日志和管理员通知。
4. 将大型 `index.html` 拆分为独立 CSS、JavaScript 和组件文件。
5. 增加端到端测试，覆盖登录、订阅、翻译和管理员操作。

## License

当前仓库尚未声明开源许可证。在添加 LICENSE 文件前，请不要假定代码可被第三方复制、修改或重新发布。
