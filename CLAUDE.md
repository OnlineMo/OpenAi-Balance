# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

OpenAI Balance 是一个 Python FastAPI 应用程序，提供 OpenAI API 的代理和负载均衡功能。支持多提供商配置、多 API 密钥管理、自动轮询、失败计数和状态监控。

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式运行（自动重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用启动脚本
./start.sh        # Linux/macOS
start.bat         # Windows

# 运行测试
python -m pytest tests/ -v

# Docker
docker-compose up -d
```

## 架构

### 请求流程

```
Client Request
    ↓
AuthMiddleware (Cookie/Token 认证)
    ↓
SmartRoutingMiddleware (URL 规范化)
    ↓
Router (provider_routes → openai_routes)
    ↓
ProviderService / OpenAIChatService
    ↓
KeyManager (密钥轮询)
    ↓
Upstream API
```

### 核心组件

**入口和生命周期**
- `app/main.py` - 应用入口，加载 `.env`
- `app/core/application.py` - `create_app()` 工厂函数，管理生命周期

**多提供商系统** (`app/service/provider/`)
- `provider_manager.py` - `ProviderManager` 单例，管理所有提供商的初始化和获取
- `provider_service.py` - `ProviderService` 封装单个提供商的 API 调用
- `provider_key_manager.py` - `ProviderKeyManager` 为每个提供商维护独立的 KeyManager

**密钥管理**
- `app/service/key/key_manager.py` - `KeyManager` 单例，轮询密钥并跟踪失败计数
- 密钥在连续失败 `MAX_FAILURES` 次后自动禁用

**路由注册顺序**（重要）
```python
# app/router/routes.py - 顺序决定路由优先级
app.include_router(provider_routes.router)      # 多提供商路由优先
app.include_router(openai_routes.router)        # 向后兼容
app.include_router(openai_compatiable_routes.router)
```

**配置系统**
- `app/config/config.py` - Pydantic `Settings` 类
- 配置从 `.env` 加载，启动时与数据库双向同步（数据库值优先）

### 路由规则

| 路由模式 | 提供商 |
|---------|--------|
| `/v1/*` | 默认提供商 |
| `/{provider}/v1/*` | 指定提供商 |
| `/hf/v1/*`, `/hf/{provider}/v1/*` | HuggingFace 格式 |
| `/openai/v1/*`, `/openai/{provider}/v1/*` | OpenAI 格式 |

### 数据库

- 支持 MySQL 和 SQLite（`DATABASE_TYPE` 配置）
- 模型：Settings, ErrorLogs, RequestLogs
- 异步连接：`app/database/connection.py`

## 关键配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `API_KEYS` | `[]` | API 密钥列表 |
| `ALLOWED_TOKENS` | `[]` | 允许的认证 token |
| `BASE_URL` | `https://api.openai.com/v1` | 上游 API 基础 URL |
| `DEFAULT_PROVIDER` | `default` | 默认提供商名称 |
| `PROVIDERS_CONFIG` | `[]` | 多提供商配置 (JSON) |
| `MAX_FAILURES` | `3` | 密钥最大失败次数 |
| `MAX_RETRIES` | `3` | 最大重试次数 |

## CI/CD

### GitHub Actions 工作流

**文件:** `.github/workflows/docker-publish.yml`

**功能:**
- 当推送 `v*` 格式的标签时自动触发（如 `v1.2.0`）
- 构建多平台镜像（linux/amd64, linux/arm64）
- 推送到 `onlinemo/openai-balance:版本号` 和 `onlinemo/openai-balance:latest`
- 使用 GitHub Actions 缓存加速构建
- 自动创建 GitHub Release

**所需 Secrets:**
- `DOCKERHUB_USERNAME` - Docker Hub 用户名
- `DOCKERHUB_TOKEN` - Docker Hub 访问令牌

**发布新版本:**
```bash
# 更新 VERSION 文件
echo "1.3.0" > VERSION

# 提交更改
git add VERSION
git commit -m "Bump version to 1.3.0"
git push

# 创建并推送标签触发构建
git tag v1.3.0
git push origin v1.3.0
```

## 代码规范

- 所有模块、类和公共函数使用中文文档字符串
- 所有函数参数和返回值使用类型注解
- 所有 I/O 操作使用 `async/await`
- 使用 `asyncio.Lock()` 保护共享状态

## Git 提交规范

- **不要在提交信息中署名 Claude 或添加 Co-Authored-By**
- 提交信息使用简洁的英文描述
- 不要添加 emoji 或 "Generated with Claude Code" 等标记
