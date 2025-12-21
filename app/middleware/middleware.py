"""
中间件配置模块，负责设置和配置应用程序的中间件
"""

import re
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

# from app.middleware.request_logging_middleware import RequestLoggingMiddleware
from app.middleware.smart_routing_middleware import SmartRoutingMiddleware
from app.core.constants import API_VERSION
from app.core.security import verify_auth_token
from app.log.logger import get_middleware_logger

logger = get_middleware_logger()

# 匹配自定义提供商路径的正则表达式: /{provider}/v1/*
PROVIDER_PATH_PATTERN = re.compile(r'^/[a-zA-Z0-9_-]+/v1(/.*)?$')


class AuthMiddleware(BaseHTTPMiddleware):
    """
    认证中间件，处理未经身份验证的请求
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 允许特定路径绕过身份验证
        bypass_auth = (
            path in ["/", "/auth"]
            or path.startswith("/static")
            or path.startswith("/gemini")
            or path.startswith("/v1")
            or path.startswith(f"/{API_VERSION}")
            or path.startswith("/health")
            or path.startswith("/hf")
            or path.startswith("/openai")
            or path.startswith("/api/version/check")
            or path.startswith("/vertex-express")
            or path.startswith("/upload")
            # 匹配自定义提供商路径: /{provider}/v1/*
            or PROVIDER_PATH_PATTERN.match(path)
        )

        if not bypass_auth:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning(f"Unauthorized access attempt to {path}")
                return RedirectResponse(url="/")
            logger.debug("Request authenticated successfully")

        response = await call_next(request)
        return response


def setup_middlewares(app: FastAPI) -> None:
    """
    设置应用程序的中间件

    Args:
        app: FastAPI应用程序实例
    """
    # 添加智能路由中间件（必须在认证中间件之前）
    app.add_middleware(SmartRoutingMiddleware)

    # 添加认证中间件
    app.add_middleware(AuthMiddleware)

    # 添加请求日志中间件（可选，默认注释掉）
    # app.add_middleware(RequestLoggingMiddleware)

    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,
    )
