"""
OpenAI 兼容路由模块（/openai 前缀）

提供 /openai/v1 前缀的 OpenAI API 兼容端点，包括：
- /openai/v1/models - 模型列表
- /openai/v1/chat/completions - 聊天完成
- /openai/v1/embeddings - 文本嵌入
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from app.config.config import settings
from app.core.security import SecurityService
from app.domain.openai_models import (
    ChatRequest,
    EmbeddingRequest,
)
from app.handler.error_handler import handle_route_errors
from app.handler.retry_handler import RetryHandler
from app.log.logger import get_openai_compatible_logger
from app.service.key.key_manager import KeyManager, get_key_manager_instance
from app.service.openai_compatiable.openai_compatiable_service import (
    OpenAICompatiableService,
)
from app.utils.helpers import redact_key_for_logging

router = APIRouter()
logger = get_openai_compatible_logger()

security_service = SecurityService()


async def get_key_manager():
    """获取密钥管理器实例"""
    return await get_key_manager_instance()


async def get_next_working_key_wrapper(
    key_manager: KeyManager = Depends(get_key_manager),
):
    """获取下一个可用的 API key"""
    return await key_manager.get_next_working_key()


async def get_openai_service(key_manager: KeyManager = Depends(get_key_manager)):
    """获取 OpenAI 兼容服务实例"""
    return OpenAICompatiableService(settings.BASE_URL, key_manager)


@router.get("/openai/v1/models")
async def list_models(
    allowed_token=Depends(security_service.verify_authorization),
    key_manager: KeyManager = Depends(get_key_manager),
    openai_service: OpenAICompatiableService = Depends(get_openai_service),
):
    """
    获取可用模型列表

    返回上游 API 提供的模型列表。
    """
    operation_name = "list_models"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling models list request")
        api_key = await key_manager.get_random_valid_key()
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(api_key)}")
        return await openai_service.get_models(api_key)


@router.post("/openai/v1/chat/completions")
@RetryHandler(key_arg="api_key")
async def chat_completion(
    request: ChatRequest,
    allowed_token=Depends(security_service.verify_authorization),
    api_key: str = Depends(get_next_working_key_wrapper),
    key_manager: KeyManager = Depends(get_key_manager),
    openai_service: OpenAICompatiableService = Depends(get_openai_service),
):
    """
    处理聊天完成请求

    支持流式和非流式响应，直接转发到上游 API。
    """
    operation_name = "chat_completion"

    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling chat completion request for model: {request.model}")
        logger.debug(f"Request: \n{request.model_dump_json(indent=2)}")
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(api_key)}")

        raw_response = await openai_service.create_chat_completion(request, api_key)

        if request.stream:
            try:
                # 尝试获取第一条数据，判断是正常 SSE 还是错误
                first_chunk = await raw_response.__anext__()
            except StopAsyncIteration:
                return StreamingResponse(raw_response, media_type="text/event-stream")
            except Exception as e:
                error_code = e.args[0] if e.args else 500
                error_msg = e.args[1] if len(e.args) > 1 else str(e)
                return JSONResponse(
                    content={"error": {"code": error_code, "message": error_msg}},
                    status_code=error_code,
                )

            # 如果以 "data:" 开头，代表正常 SSE
            if isinstance(first_chunk, str) and first_chunk.startswith("data:"):

                async def combined():
                    yield first_chunk
                    async for chunk in raw_response:
                        yield chunk

                return StreamingResponse(combined(), media_type="text/event-stream")
        else:
            return raw_response


@router.post("/openai/v1/embeddings")
async def embedding(
    request: EmbeddingRequest,
    allowed_token=Depends(security_service.verify_authorization),
    key_manager: KeyManager = Depends(get_key_manager),
    openai_service: OpenAICompatiableService = Depends(get_openai_service),
):
    """
    处理文本嵌入请求

    将文本转换为向量表示。
    """
    operation_name = "embedding"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling embedding request for model: {request.model}")
        api_key = await key_manager.get_next_working_key()
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(api_key)}")
        return await openai_service.create_embeddings(request, api_key)
