# 部署说明

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制 .env.example 或手动创建 .env）
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 启动服务（热重载）
uvicorn backend.main:app --reload

# 访问 http://127.0.0.1:8000
```

## 运行测试

```bash
pytest
```

## Render 部署

### 1. 准备 GitHub 仓库

确保以下文件已提交：
- `render.yaml` — 服务配置
- `requirements.txt` — Python 依赖
- `.gitignore` — 排除敏感文件

**不要提交**：`.env`、`database.db`、`uploads/`、`outputs/`

### 2. 在 Render 创建服务

1. 登录 [render.com](https://render.com)
2. New → Web Service → Connect GitHub repo
3. 选择仓库，Render 会自动识别 `render.yaml`

### 3. 配置环境变量

在 Render Dashboard → Environment 中添加：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（必填） |
| `DEEPSEEK_API_BASE_URL` | API 地址（可选，默认 `https://api.deepseek.com`） |
| `DEEPSEEK_MODEL` | 模型名称（可选，默认 `deepseek-chat`） |

### 4. 部署

点击 Deploy，等待构建完成。

### 注意事项

- **SQLite 限制**：Render 免费实例的文件系统是临时的，每次部署/重启会丢失数据库。卡密数据需要在部署后重新初始化。
- **初始化卡密**：部署后通过 Shell 运行 `python scripts/generate_beta_codes.py` 生成测试卡密。
- **持久化方案**：如需持久化数据库，考虑使用 Render 的 Persistent Disk 或迁移到 PostgreSQL。
