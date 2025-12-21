"""
路由配置模块

负责设置和配置应用程序的所有路由，包括：
- API 路由（OpenAI 兼容）
- 管理页面路由
- 健康检查路由
- 统计 API 路由
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config.config import settings
from app.core.security import verify_auth_token
from app.log.logger import get_routes_logger
from app.router import (
    config_routes,
    error_log_routes,
    key_routes,
    openai_compatiable_routes,
    openai_routes,
    provider_routes,
    scheduler_routes,
    stats_routes,
    version_routes,
)
from app.service.key.key_manager import get_key_manager_instance
from app.service.stats.stats_service import StatsService
from app.utils.static_version import get_static_url

logger = get_routes_logger()

templates = Jinja2Templates(directory="app/templates")
# 设置模板全局变量
templates.env.globals["static_url"] = get_static_url


def setup_routers(app: FastAPI) -> None:
    """
    设置应用程序的路由

    Args:
        app: FastAPI 应用程序实例
    """
    # 多提供商路由（必须在 openai_routes 之前注册，以便正确处理默认提供商）
    # 当配置了自定义提供商时，/v1/* 路由会使用默认提供商的配置
    app.include_router(provider_routes.router)

    # OpenAI 兼容路由（保留原有路由以保持向后兼容）
    # 注意：由于 provider_routes 已经注册了 /v1/* 路由，这些路由只在没有配置提供商时生效
    app.include_router(openai_routes.router)
    app.include_router(openai_compatiable_routes.router)

    # 管理路由
    app.include_router(config_routes.router)
    app.include_router(error_log_routes.router)
    app.include_router(scheduler_routes.router)
    app.include_router(stats_routes.router)
    app.include_router(version_routes.router)
    app.include_router(key_routes.router)

    # 页面路由
    setup_page_routes(app)

    # 健康检查和统计路由
    setup_health_routes(app)
    setup_api_stats_routes(app)


def setup_page_routes(app: FastAPI) -> None:
    """
    设置页面相关的路由

    Args:
        app: FastAPI 应用程序实例
    """

    @app.get("/", response_class=HTMLResponse)
    async def auth_page(request: Request):
        """认证页面"""
        return templates.TemplateResponse("auth.html", {"request": request})

    @app.post("/auth")
    async def authenticate(request: Request):
        """处理认证请求"""
        try:
            form = await request.form()
            auth_token = form.get("auth_token")
            if not auth_token:
                logger.warning("Authentication attempt with empty token")
                return RedirectResponse(url="/", status_code=302)

            if verify_auth_token(auth_token):
                logger.info("Successful authentication")
                response = RedirectResponse(url="/keys", status_code=302)
                response.set_cookie(
                    key="auth_token",
                    value=auth_token,
                    httponly=True,
                    max_age=settings.ADMIN_SESSION_EXPIRE,
                )
                return response
            logger.warning("Failed authentication attempt with invalid token")
            return RedirectResponse(url="/", status_code=302)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return RedirectResponse(url="/", status_code=302)

    @app.get("/keys", response_class=HTMLResponse)
    async def keys_page(request: Request):
        """密钥管理页面"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to keys page")
                return RedirectResponse(url="/", status_code=302)

            # 获取默认提供商的密钥统计
            key_manager = await get_key_manager_instance()
            keys_status = await key_manager.get_keys_by_status()
            default_valid = len(keys_status["valid_keys"])
            default_invalid = len(keys_status["invalid_keys"])

            # 获取所有自定义提供商的密钥统计
            from app.service.provider.provider_key_manager import get_provider_key_manager
            provider_key_manager = await get_provider_key_manager()
            providers_status = await provider_key_manager.get_all_providers_status()

            # 计算所有提供商的总和
            total_valid = default_valid
            total_invalid = default_invalid
            for provider_name, status in providers_status.items():
                total_valid += status.get("valid_keys_count", 0)
                total_invalid += status.get("invalid_keys_count", 0)

            total_keys = total_valid + total_invalid
            valid_key_count = total_valid
            invalid_key_count = total_invalid

            stats_service = StatsService()
            api_stats = await stats_service.get_api_usage_stats()
            logger.info(f"API stats retrieved: {api_stats}")

            logger.info(f"Keys status retrieved successfully. Total keys: {total_keys}")
            return templates.TemplateResponse(
                "keys_status.html",
                {
                    "request": request,
                    "valid_keys": {},
                    "invalid_keys": {},
                    "total_keys": total_keys,
                    "valid_key_count": valid_key_count,
                    "invalid_key_count": invalid_key_count,
                    "api_stats": api_stats,
                },
            )
        except Exception as e:
            logger.error(f"Error retrieving keys status or API stats: {str(e)}")
            return templates.TemplateResponse(
                "keys_status.html",
                {
                    "request": request,
                    "valid_keys": {},
                    "invalid_keys": {},
                    "total_keys": 0,
                    "valid_key_count": 0,
                    "invalid_key_count": 0,
                    "api_stats": {
                        "calls_1m": {"total": 0, "success": 0, "failure": 0},
                        "calls_1h": {"total": 0, "success": 0, "failure": 0},
                        "calls_24h": {"total": 0, "success": 0, "failure": 0},
                        "calls_month": {"total": 0, "success": 0, "failure": 0},
                    },
                },
            )

    @app.get("/config", response_class=HTMLResponse)
    async def config_page(request: Request):
        """配置编辑页面"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to config page")
                return RedirectResponse(url="/", status_code=302)

            logger.info("Config page accessed successfully")
            return templates.TemplateResponse(
                "config_editor.html", {"request": request}
            )
        except Exception as e:
            logger.error(f"Error accessing config page: {str(e)}")
            raise

    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        """错误日志页面"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to logs page")
                return RedirectResponse(url="/", status_code=302)

            logger.info("Logs page accessed successfully")
            return templates.TemplateResponse("error_logs.html", {"request": request})
        except Exception as e:
            logger.error(f"Error accessing logs page: {str(e)}")
            raise


def setup_health_routes(app: FastAPI) -> None:
    """
    设置健康检查相关的路由

    Args:
        app: FastAPI 应用程序实例
    """

    @app.get("/health")
    async def health_check(request: Request):
        """健康检查端点"""
        logger.info("Health check endpoint called")
        return {"status": "healthy"}


def setup_api_stats_routes(app: FastAPI) -> None:
    """
    设置 API 统计相关的路由

    Args:
        app: FastAPI 应用程序实例
    """

    @app.get("/api/stats/details")
    async def api_stats_details(request: Request, period: str):
        """获取指定时间段内的 API 调用详情"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to API stats details")
                return {"error": "Unauthorized"}, 401

            logger.info(f"Fetching API call details for period: {period}")
            stats_service = StatsService()
            details = await stats_service.get_api_call_details(period)
            return details
        except ValueError as e:
            logger.warning(
                f"Invalid period requested for API stats details: {period} - {str(e)}"
            )
            return {"error": str(e)}, 400
        except Exception as e:
            logger.error(
                f"Error fetching API stats details for period {period}: {str(e)}"
            )
            return {"error": "Internal server error"}, 500

    @app.get("/api/stats/attention-keys")
    async def api_stats_attention_keys(
        request: Request, limit: int = 20, status_code: int = 429
    ):
        """返回最近24小时指定错误码次数最多的Key"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to attention-keys")
                return {"error": "Unauthorized"}, 401

            key_manager = await get_key_manager_instance()
            keys_status = await key_manager.get_keys_by_status()
            in_memory_keys = set(keys_status.get("valid_keys", [])) | set(
                keys_status.get("invalid_keys", [])
            )
            stats_service = StatsService()
            data = await stats_service.get_attention_keys_last_24h(
                in_memory_keys, limit, status_code
            )
            return data
        except Exception as e:
            logger.error(f"Error fetching attention keys: {e}")
            return {"error": "Internal server error"}, 500

    @app.get("/api/stats/key-details")
    async def api_stats_key_details(request: Request, key: str, period: str):
        """获取指定密钥在指定时间段内的调用详情"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to API key stats details")
                return {"error": "Unauthorized"}, 401

            logger.info(
                f"Fetching key call details for key=...{key[-4:] if key else ''}, period: {period}"
            )
            stats_service = StatsService()
            details = await stats_service.get_key_call_details(key, period)
            return details
        except ValueError as e:
            logger.warning(
                f"Invalid period requested for key stats details: {period} - {str(e)}"
            )
            return {"error": str(e)}, 400
        except Exception as e:
            logger.error(
                f"Error fetching key stats details for period {period}: {str(e)}"
            )
            return {"error": "Internal server error"}, 500
