# OpenAI Balance - OpenAI API 代理和负载均衡器

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.100%2B-green.svg" alt="FastAPI"></a>
  <a href="https://www.uvicorn.org/"><img src="https://img.shields.io/badge/Uvicorn-running-purple.svg" alt="Uvicorn"></a>
  <a href="https://hub.docker.com/r/onlinemo/openai-balance"><img src="https://img.shields.io/docker/pulls/onlinemo/openai-balance.svg" alt="Docker Pulls"></a>
  <a href="https://github.com/OnlineMo/OpenAi-Balance"><img src="https://img.shields.io/github/stars/OnlineMo/OpenAi-Balance?style=social" alt="GitHub Stars"></a>
</p>

---

## 🙏 致谢

本项目修改自 [snailyp](https://github.com/snailyp) 的 [gemini-balance](https://github.com/snailyp/gemini-balance)，特此感谢原作者提供的优秀基础！

**作者:** [OnlineMo](https://github.com/OnlineMo) | [Linux.do](https://linux.do/u/onlinemo)

---

## 📖 项目简介

**OpenAI Balance** 是一个基于 Python FastAPI 构建的应用程序，旨在提供 OpenAI 兼容 API 的代理和负载均衡功能。它允许您管理多个 API Key，并通过简单的配置实现 Key 的轮询、认证、模型过滤和状态监控。

<details>
<summary>📂 查看项目结构</summary>

```plaintext
app/
├── config/       # 配置管理
├── core/         # 核心应用逻辑 (FastAPI 实例创建, 中间件等)
├── database/     # 数据库模型和连接
├── domain/       # 业务领域对象
├── exception/    # 自定义异常
├── handler/      # 请求处理器
├── log/          # 日志配置
├── main.py       # 应用入口
├── middleware/   # FastAPI 中间件
├── router/       # API 路由 (OpenAI 兼容, 状态页等)
├── scheduler/    # 定时任务 (如 Key 状态检查)
├── service/      # 业务逻辑服务 (聊天, Key 管理, 统计等)
├── static/       # 静态文件 (CSS, JS)
├── templates/    # HTML 模板 (如 Key 状态页)
└── utils/        # 工具函数
```
</details>

---

## ✨ 功能亮点

*   **多 Key 负载均衡**: 支持配置多个 API Key (`API_KEYS`)，自动按顺序轮询使用，提高可用性和并发能力。
*   **多提供商支持**: 支持配置多个上游提供商，每个提供商独立的 API Key 和路由路径。
*   **可视化配置即时生效**: 通过管理后台修改配置后，无需重启服务即可生效。
*   **配置热重载**: 修改 `.env` 文件后自动重新加载配置，无需重启服务。
*   **OpenAI API 兼容**: 完全兼容 OpenAI API 格式，可作为直接替代使用。
*   **自定义上游**: 支持自定义 `BASE_URL`，可代理任何 OpenAI 兼容的 API 服务。
*   **Key 状态监控**: 提供 `/keys` 页面（需要认证），实时查看各 Key 的状态和使用情况，支持按提供商筛选。
*   **详细日志记录**: 提供详细的错误日志，方便排查问题。
*   **灵活的密钥添加**: 支持批量添加密钥，并自动去重，支持任意格式的密钥。
*   **失败重试与自动禁用**: 自动处理 API 请求失败，进行重试 (`MAX_RETRIES`)，并在 Key 失效次数过多时自动禁用 (`MAX_FAILURES`)。
*   **代理支持**: 支持配置 HTTP/SOCKS5 代理 (`PROXIES`)，支持代理连通性测试，方便在特殊网络环境下使用。
*   **代理自动检测**: 定时自动检测代理可用性，自动禁用失败的代理，并解除 API Key 与失败代理的绑定关系。
*   **Docker 支持**: 提供 AMD 和 ARM 架构的 Docker 镜像，方便快速部署。

---

## 🚀 快速开始

### 方式一：使用 Docker Compose (推荐)

1.  **下载 `docker-compose.yml`**:
    从项目仓库获取 `docker-compose.yml` 文件。
2.  **准备 `.env` 文件**:
    从 `.env.example` 复制一份并重命名为 `.env`，然后根据需求修改配置。
3.  **启动服务**:
    ```bash
    docker-compose up -d
    ```

### 方式二：从 Docker Hub 拉取 (推荐)

1.  **拉取镜像**:
    ```bash
    docker pull onlinemo/openai-balance:latest
    ```
2.  **准备 `.env` 文件**:
    从 `.env.example` 复制一份并重命名为 `.env`，然后根据需求修改配置。
3.  **运行容器**:
    ```bash
    docker run -d -p 8000:8000 --name openai-balance \
    -v ./data:/app/data \
    --env-file .env \
    onlinemo/openai-balance:latest
    ```

### 方式三：从源码构建

1.  **构建镜像**:
    ```bash
    docker build -t openai-balance .
    ```
2.  **准备 `.env` 文件**:
    从 `.env.example` 复制一份并重命名为 `.env`，然后根据需求修改配置。
3.  **运行容器**:
    ```bash
    docker run -d -p 8000:8000 --name openai-balance \
    -v ./data:/app/data \
    --env-file .env \
    openai-balance:latest
    ```

### 方式四：本地运行 (适用于开发)

**Windows:**
```bash
# 双击 start.bat 或在命令行运行
start.bat
```

**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

**手动运行:**
```bash
git clone https://github.com/OnlineMo/OpenAi-Balance.git
cd OpenAi-Balance
pip install -r requirements.txt
cp .env.example .env
# 根据需要编辑 .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

应用启动后，访问 `http://localhost:8000`。

---

## ⚙️ API 端点

### OpenAI API 格式

*   `GET /v1/models`: 列出可用模型。
*   `POST /v1/chat/completions`: 聊天补全。
*   `POST /v1/embeddings`: 创建文本嵌入。

### 多提供商端点

*   `GET /{provider}/v1/models`: 列出指定提供商的模型。
*   `POST /{provider}/v1/chat/completions`: 通过指定提供商进行聊天补全。
*   `POST /{provider}/v1/embeddings`: 通过指定提供商创建嵌入。

### 备用端点

*   `GET /hf/v1/models`: 列出模型（HuggingFace 兼容）。
*   `POST /hf/v1/chat/completions`: 聊天补全。
*   `POST /hf/v1/embeddings`: 创建文本嵌入。

*   `GET /openai/v1/models`: 列出模型。
*   `POST /openai/v1/chat/completions`: 聊天补全。
*   `POST /openai/v1/embeddings`: 创建文本嵌入。

---

<details>
<summary>📋 查看完整配置项列表</summary>

| 配置项 | 说明 | 默认值 |
| :--- | :--- | :--- |
| **数据库配置** | | |
| `DATABASE_TYPE` | 数据库类型: `mysql` 或 `sqlite` | `sqlite` |
| `SQLITE_DATABASE` | SQLite 数据库文件路径 | `default_db` |
| `MYSQL_HOST` | MySQL 数据库主机地址 | `localhost` |
| `MYSQL_PORT` | MySQL 数据库端口 | `3306` |
| `MYSQL_USER` | MySQL 数据库用户名 | `your_db_user` |
| `MYSQL_PASSWORD` | MySQL 数据库密码 | `your_db_password` |
| `MYSQL_DATABASE` | MySQL 数据库名称 | `defaultdb` |
| **API 相关配置** | | |
| `API_KEYS` | **必填**, API 密钥列表，用于负载均衡 | `[]` |
| `ALLOWED_TOKENS` | **必填**, 允许访问的 Token 列表 | `[]` |
| `AUTH_TOKEN` | 管理员 Token，不填则使用 `ALLOWED_TOKENS` 的第一个 | |
| `BASE_URL` | 上游 API 基础 URL | `https://api.openai.com/v1` |
| `MODEL_REQUEST_KEY` | 用于获取模型列表的专用 key | `""` |
| `TEST_MODEL` | 用于测试密钥可用性的模型 | `gpt-4o-mini` |
| `FILTERED_MODELS` | 被禁用的模型列表 | `[]` |
| `MAX_FAILURES` | 单个 Key 允许的最大失败次数 | `3` |
| `MAX_RETRIES` | API 请求失败时的最大重试次数 | `3` |
| `TIME_OUT` | 请求超时时间 (秒) | `300` |
| `PROXIES` | 代理服务器列表 | `[]` |
| **代理自动检测** | | |
| `PROXY_AUTO_CHECK_ENABLED` | 是否启用代理自动检测 | `false` |
| `PROXY_CHECK_INTERVAL_HOURS` | 代理检测间隔（小时，支持小数） | `1` |
| `PROXY_MAX_FAILURES` | 代理最大失败次数，超过后禁用 | `3` |
| `PROXY_CHECK_URL` | 代理检测目标 URL | `https://www.google.com` |
| `PROXY_CHECK_TIMEOUT` | 代理检测超时时间（秒） | `10` |
| **多提供商配置** | | |
| `DEFAULT_PROVIDER` | 默认提供商名称 | `default` |
| `PROVIDERS_CONFIG` | 提供商配置列表 (JSON 格式) | `[]` |
| **日志配置** | | |
| `LOG_LEVEL` | 日志级别: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `ERROR_LOG_RECORD_REQUEST_BODY` | 是否记录错误日志的请求体 | `false` |
| `AUTO_DELETE_ERROR_LOGS_ENABLED` | 是否自动删除错误日志 | `true` |
| `AUTO_DELETE_ERROR_LOGS_DAYS` | 错误日志保留天数 | `7` |

</details>

---

## 🔧 多提供商配置

您可以在管理后台或通过 `PROVIDERS_CONFIG` 配置多个上游提供商：

```json
[
  {
    "name": "openai",
    "path": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_keys": ["sk-xxx"],
    "enabled": true
  },
  {
    "name": "deepseek",
    "path": "deepseek",
    "base_url": "https://api.deepseek.com/v1",
    "api_keys": ["sk-yyy"],
    "enabled": true
  }
]
```

**路由规则:**
- `/v1/*` - 使用默认提供商
- `/{provider}/v1/*` - 使用指定提供商（如 `/deepseek/v1/chat/completions`）
- `/hf/{provider}/v1/*` - HuggingFace 格式，使用指定提供商
- `/openai/{provider}/v1/*` - OpenAI 格式，使用指定提供商

---

## 🤝 贡献

欢迎通过提交 Pull Request 或 Issue 来为项目做出贡献。

## 许可证

本项目采用 [CC BY-NC 4.0](LICENSE)（署名-非商业性使用）协议。
