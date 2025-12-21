from contextlib import asynccontextmanager
from fastapi import HTTPException
import logging

@asynccontextmanager
async def handle_route_errors(logger: logging.Logger, operation_name: str, success_message: str = None, failure_message: str = None):
    """
    一个异步上下文管理器，用于统一处理 FastAPI 路由中的常见错误和日志记录。

    Args:
        logger: 用于记录日志的 Logger 实例。
        operation_name: 操作的名称，用于日志记录和错误详情。
        success_message: 操作成功时记录的自定义消息 (可选)。
        failure_message: 操作失败时记录的自定义消息 (可选)。
    """
    default_success_msg = f"{operation_name} request successful"
    default_failure_msg = f"{operation_name} request failed"

    logger.info("-" * 50 + operation_name + "-" * 50)
    try:
        yield
        logger.info(success_message or default_success_msg)
    except HTTPException as http_exc:
        # 如果已经是 HTTPException，直接重新抛出，保留原始状态码和详情
        logger.error(f"{failure_message or default_failure_msg}: {http_exc.detail} (Status: {http_exc.status_code})")
        raise http_exc
    except Exception as e:
        # 对于其他所有异常，记录错误并抛出标准的 500 错误
        logger.error(f"{failure_message or default_failure_msg}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error during {operation_name}"
        ) from e