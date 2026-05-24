# Render 部署指南

## 架构

```
Browser → Next.js (Render) → FastAPI (Render) → Supabase
              ↕ Clerk Auth
```

两个独立的 Render Web Service：
- **literature-juicer** — Next.js 前端（Node.js）
- **literature-juicer-api** — FastAPI 后端（Python）

---

## 前置条件

1. **Supabase** 项目已创建，`supabase/schema.sql` 已执行
2. **Clerk** 应用已创建，Email + Password 认证已启用
3. **DeepSeek** API Key 已获取
4. **GitHub** 仓库已推送最新代码

---

## 部署步骤

### 1. 连接 GitHub 仓库

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New** → **Blueprint**
3. 选择 GitHub 仓库 `literature-juicer`
4. Render 会自动检测 `render.yaml` 并创建两个服务

### 2. 配置后端环境变量

在 `literature-juicer-api` 服务的 **Environment** 页面设置：

| 变量 | 值 | 来源 |
|------|-----|------|
| `DEEPSEEK_API_KEY` | `sk-xxx` | [DeepSeek Platform](https://platform.deepseek.com) |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Dashboard → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | `eyJxxx` | Supabase Dashboard → Settings → API |
| `CLERK_JWKS_URL` | `https://xxx.clerk.accounts.dev/.well-known/jwks.json` | Clerk Dashboard → API Keys |
| `CLERK_SECRET_KEY` | `sk_test_xxx` | Clerk Dashboard → API Keys |
| `CORS_ORIGINS` | `https://literature-juicer.onrender.com` | 前端部署后的域名 |

可选：
| 变量 | 默认值 |
|------|--------|
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | `deepseek-chat` |

### 3. 配置前端环境变量

在 `literature-juicer` 服务的 **Environment** 页面设置：

| 变量 | 值 | 来源 |
|------|-----|------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_test_xxx` | Clerk Dashboard → API Keys |
| `CLERK_SECRET_KEY` | `sk_test_xxx` | Clerk Dashboard → API Keys |
| `NEXT_PUBLIC_API_URL` | `https://literature-juicer-api.onrender.com` | 后端部署后的域名 |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Dashboard |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJxxx` | Supabase Dashboard → Settings → API |

已预设（无需修改）：
- `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`
- `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`
- `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/`
- `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/`

### 4. 配置 Clerk Dashboard

在 Clerk Dashboard → **Configure** → **Paths** 中设置：

**Allowed Redirect URLs**:
```
https://literature-juicer.onrender.com/sign-in
https://literature-juicer.onrender.com/sign-up
https://literature-juicer.onrender.com/
```

**CORS Origins**（如果 Clerk 需要）:
```
https://literature-juicer.onrender.com
```

### 5. 触发部署

1. 在 Render Dashboard 中对两个服务分别点击 **Manual Deploy** → **Deploy latest commit**
2. 等待构建完成（前端约 2-3 分钟，后端约 1-2 分钟）

---

## 部署后验证

- [ ] 后端健康检查：`curl https://literature-juicer-api.onrender.com/health` → 返回 `ok`
- [ ] 前端页面加载：访问 `https://literature-juicer.onrender.com` → 显示 Clerk 登录页
- [ ] 注册/登录：Clerk 流程正常
- [ ] 额度显示：登录后显示 "剩余额度：3 / 3"
- [ ] PDF 上传：上传 PDF → SSE 进度 → Excel 下载
- [ ] 邀请系统：获取邀请码 → 邀请链接可访问

---

## 常见问题

### 前端构建失败

```
Error: Module not found: Can't resolve '@clerk/nextjs'
```

**解决**：检查 `package.json` 中 `@clerk/nextjs` 版本，确保 `npm install` 成功。

### 后端启动失败

```
ModuleNotFoundError: No module named 'backend'
```

**解决**：确保 `rootDir` 为 `.`（仓库根目录），`requirements.txt` 在根目录。

### CORS 错误

```
Access to fetch at 'https://xxx-api.onrender.com' from origin 'https://xxx.onrender.com' has been blocked
```

**解决**：在后端环境变量中设置 `CORS_ORIGINS=https://literature-juicer.onrender.com`

### Clerk 认证失败

```
auth() timeout after 15s
```

**解决**：检查 `CLERK_SECRET_KEY` 和 `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` 是否正确。

### 冷启动慢

Render 免费服务在无请求时会休眠，首次请求需要 30-60 秒唤醒。升级到付费计划可避免。

---

## 服务 URL 格式

| 服务 | URL 格式 |
|------|----------|
| 前端 | `https://literature-juicer.onrender.com` |
| 后端 | `https://literature-juicer-api.onrender.com` |

Render 会根据 `render.yaml` 中的 `name` 字段自动生成域名。
