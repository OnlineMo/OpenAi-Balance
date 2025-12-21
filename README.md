[阅读中文文档](README_ZH.md)

# OpenAI Balance - OpenAI API Proxy and Load Balancer

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.9%2B-blue.svg" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.100%2B-green.svg" alt="FastAPI"></a>
  <a href="https://www.uvicorn.org/"><img src="https://img.shields.io/badge/Uvicorn-running-purple.svg" alt="Uvicorn"></a>
  <a href="https://hub.docker.com/r/onlinemo/openai-balance"><img src="https://img.shields.io/docker/pulls/onlinemo/openai-balance.svg" alt="Docker Pulls"></a>
  <a href="https://github.com/OnlineMo/OpenAi-Balance"><img src="https://img.shields.io/github/stars/OnlineMo/OpenAi-Balance?style=social" alt="GitHub Stars"></a>
</p>

---

## 🙏 Acknowledgements

This project is modified from [gemini-balance](https://github.com/snailyp/gemini-balance) by [snailyp](https://github.com/snailyp). Special thanks for the excellent foundation!

**Author:** [OnlineMo](https://github.com/OnlineMo) | [Linux.do](https://linux.do/u/onlinemo)

---

## 📖 Project Introduction

**OpenAI Balance** is an application built with Python FastAPI, designed to provide proxy and load balancing functions for OpenAI-compatible APIs. It allows you to manage multiple API Keys and implement key rotation, authentication, model filtering, and status monitoring through simple configuration.

<details>
<summary>📂 View Project Structure</summary>

```plaintext
app/
├── config/       # Configuration management
├── core/         # Core application logic (FastAPI instance creation, middleware, etc.)
├── database/     # Database models and connections
├── domain/       # Business domain objects
├── exception/    # Custom exceptions
├── handler/      # Request handlers
├── log/          # Logging configuration
├── main.py       # Application entry point
├── middleware/   # FastAPI middleware
├── router/       # API routes (OpenAI compatible, status page, etc.)
├── scheduler/    # Scheduled tasks (e.g., Key status check)
├── service/      # Business logic services (chat, Key management, statistics, etc.)
├── static/       # Static files (CSS, JS)
├── templates/    # HTML templates (e.g., Key status page)
└── utils/        # Utility functions
```
</details>

---

## ✨ Feature Highlights

*   **Multi-Key Load Balancing**: Supports configuring multiple API Keys (`API_KEYS`) for automatic sequential polling.
*   **Multi-Provider Support**: Configure multiple upstream providers with independent API keys and routing paths.
*   **Visual Configuration**: Configurations modified through the admin backend take effect immediately without restarting.
*   **Hot Reload**: Automatically reloads configuration when `.env` file is modified.
*   **OpenAI API Compatibility**: Fully compatible with OpenAI API format, can be used as a drop-in replacement.
*   **Custom Upstream**: Support custom `BASE_URL` to proxy any OpenAI-compatible API service.
*   **Key Status Monitoring**: Provides a `/keys` page (authentication required) for real-time monitoring with provider filtering.
*   **Detailed Logging**: Provides detailed error logs for easy troubleshooting.
*   **Flexible Key Addition**: Add keys in batches with automatic deduplication, supports any key format.
*   **Failure Retry & Auto-Disable**: Automatically retries failed API requests (`MAX_RETRIES`) and disables keys after excessive failures (`MAX_FAILURES`).
*   **Proxy Support**: Supports HTTP/SOCKS5 proxies (`PROXIES`) with connectivity testing.
*   **Proxy Auto-Check**: Automatically checks proxy availability at scheduled intervals, disables failed proxies, and unbinds API keys from failed proxies.
*   **Docker Support**: Provides Docker images for both AMD and ARM architectures.

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

1.  **Get `docker-compose.yml`**:
    Download the `docker-compose.yml` file from the project repository.
2.  **Prepare `.env` file**:
    Copy `.env.example` to `.env` and configure it.
3.  **Start Services**:
    ```bash
    docker-compose up -d
    ```

### Option 2: Docker Hub (Recommended)

1.  **Pull Image from Docker Hub**:
    ```bash
    docker pull onlinemo/openai-balance:latest
    ```
2.  **Prepare `.env` file**:
    Copy `.env.example` to `.env` and configure it.
3.  **Run Container**:
    ```bash
    docker run -d -p 8000:8000 --name openai-balance \
    -v ./data:/app/data \
    --env-file .env \
    onlinemo/openai-balance:latest
    ```

### Option 3: Build from Source

1.  **Build Image**:
    ```bash
    docker build -t openai-balance .
    ```
2.  **Prepare `.env` file**:
    Copy `.env.example` to `.env` and configure it.
3.  **Run Container**:
    ```bash
    docker run -d -p 8000:8000 --name openai-balance \
    -v ./data:/app/data \
    --env-file .env \
    openai-balance:latest
    ```

### Option 4: Local Development

**Windows:**
```bash
# Double-click start.bat or run in command line
start.bat
```

**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

**Manual:**
```bash
git clone https://github.com/OnlineMo/OpenAi-Balance.git
cd OpenAi-Balance
pip install -r requirements.txt
cp .env.example .env
# Edit .env as needed
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Access the application at `http://localhost:8000`.

---

## ⚙️ API Endpoints

### OpenAI API Format

*   `GET /v1/models`: List available models.
*   `POST /v1/chat/completions`: Chat completion.
*   `POST /v1/embeddings`: Create text embeddings.

### Multi-Provider Endpoints

*   `GET /{provider}/v1/models`: List models for specific provider.
*   `POST /{provider}/v1/chat/completions`: Chat completion via specific provider.
*   `POST /{provider}/v1/embeddings`: Create embeddings via specific provider.

### Alternative Endpoints

*   `GET /hf/v1/models`: List models (HuggingFace compatible).
*   `POST /hf/v1/chat/completions`: Chat completion.
*   `POST /hf/v1/embeddings`: Create text embeddings.

*   `GET /openai/v1/models`: List models.
*   `POST /openai/v1/chat/completions`: Chat completion.
*   `POST /openai/v1/embeddings`: Create text embeddings.

---

<details>
<summary>📋 View Full Configuration List</summary>

| Configuration Item | Description | Default Value |
| :--- | :--- | :--- |
| **Database** | | |
| `DATABASE_TYPE` | `mysql` or `sqlite` | `sqlite` |
| `SQLITE_DATABASE` | Path for SQLite database file | `default_db` |
| `MYSQL_HOST` | MySQL host address | `localhost` |
| `MYSQL_PORT` | MySQL port | `3306` |
| `MYSQL_USER` | MySQL username | `your_db_user` |
| `MYSQL_PASSWORD` | MySQL password | `your_db_password` |
| `MYSQL_DATABASE` | MySQL database name | `defaultdb` |
| **API** | | |
| `API_KEYS` | **Required**, list of API keys | `[]` |
| `ALLOWED_TOKENS` | **Required**, list of access tokens | `[]` |
| `AUTH_TOKEN` | Admin token, defaults to the first of `ALLOWED_TOKENS` | |
| `BASE_URL` | Upstream API base URL | `https://api.openai.com/v1` |
| `MODEL_REQUEST_KEY` | Dedicated key for fetching model list | `""` |
| `TEST_MODEL` | Model for testing key validity | `gpt-4o-mini` |
| `FILTERED_MODELS` | Disabled models | `[]` |
| `MAX_FAILURES` | Max failures allowed per key | `3` |
| `MAX_RETRIES` | Max retries for failed API requests | `3` |
| `TIME_OUT` | Request timeout (seconds) | `300` |
| `PROXIES` | List of proxy servers | `[]` |
| **Proxy Auto-Check** | | |
| `PROXY_AUTO_CHECK_ENABLED` | Enable automatic proxy checking | `false` |
| `PROXY_CHECK_INTERVAL_HOURS` | Proxy check interval (hours, supports decimals) | `1` |
| `PROXY_MAX_FAILURES` | Max failures before disabling proxy | `3` |
| `PROXY_CHECK_URL` | URL for proxy connectivity test | `https://www.google.com` |
| `PROXY_CHECK_TIMEOUT` | Proxy check timeout (seconds) | `10` |
| **Multi-Provider** | | |
| `DEFAULT_PROVIDER` | Default provider name | `default` |
| `PROVIDERS_CONFIG` | Provider configuration list (JSON) | `[]` |
| **Logging** | | |
| `LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `ERROR_LOG_RECORD_REQUEST_BODY` | Record request body in error logs | `false` |
| `AUTO_DELETE_ERROR_LOGS_ENABLED` | Auto-delete error logs | `true` |
| `AUTO_DELETE_ERROR_LOGS_DAYS` | Error log retention period (days) | `7` |

</details>

---

## 🔧 Multi-Provider Configuration

You can configure multiple upstream providers in the admin panel or via `PROVIDERS_CONFIG`:

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

**Routing Rules:**
- `/v1/*` - Uses default provider
- `/{provider}/v1/*` - Uses specified provider (e.g., `/deepseek/v1/chat/completions`)
- `/hf/{provider}/v1/*` - HuggingFace format with specified provider
- `/openai/{provider}/v1/*` - OpenAI format with specified provider

---

## 🤝 Contributing

Pull Requests or Issues are welcome.

## License

This project is licensed under the [CC BY-NC 4.0](LICENSE) (Attribution-NonCommercial) license.
