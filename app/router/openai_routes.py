"""
OpenAI 兼容路由模块

提供 OpenAI API 兼容的端点，包括：
- /v1/models - 模型列表
- /v1/chat/completions - 聊天完成
- /v1/embeddings - 文本嵌入
- /v1/keys/list - 密钥列表（管理端点）
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.config.config import settings
from app.core.security import SecurityService
from app.domain.openai_models import (
    ChatRequest,
    EmbeddingRequest,
)
from app.handler.error_handler import handle_route_errors
from app.handler.retry_handler import RetryHandler
from app.log.logger import get_openai_logger
from app.service.chat.openai_chat_service import OpenAIChatService
from app.service.embedding.embedding_service import EmbeddingService
from app.service.key.key_manager import KeyManager, get_key_manager_instance
from app.service.model.model_service import ModelService
from app.utils.helpers import redact_key_for_logging

router = APIRouter()
logger = get_openai_logger()

security_service = SecurityService()
model_service = ModelService()
embedding_service = EmbeddingService()


async def get_key_manager():
    """获取密钥管理器实例"""
    return await get_key_manager_instance()


async def get_next_working_key_wrapper(
    key_manager: KeyManager = Depends(get_key_manager),
):
    """获取下一个可用的 API key"""
    return await key_manager.get_next_working_key()


async def get_openai_chat_service(key_manager: KeyManager = Depends(get_key_manager)):
    """获取 OpenAI 聊天服务实例"""
    return OpenAIChatService(settings.BASE_URL, key_manager)


@router.get("/v1/models")
@router.get("/hf/v1/models")
async def list_models(
    allowed_token=Depends(security_service.verify_authorization),
    key_manager: KeyManager = Depends(get_key_manager),
):
    """
    获取可用的模型列表

    返回上游 API 提供的模型列表，过滤掉配置中指定的模型。
    """
    operation_name = "list_models"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling models list request")
        logger.info(f"Using allowed token: {allowed_token}")
        return await model_service.get_models()


@router.post("/v1/chat/completions")
@router.post("/hf/v1/chat/completions")
@RetryHandler(key_arg="api_key")
async def chat_completion(
    request: ChatRequest,
    allowed_token=Depends(security_service.verify_authorization),
    api_key: str = Depends(get_next_working_key_wrapper),
    key_manager: KeyManager = Depends(get_key_manager),
    chat_service: OpenAIChatService = Depends(get_openai_chat_service),
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

        if not await model_service.check_model_support(request.model):
            raise HTTPException(
                status_code=400, detail=f"Model {request.model} is not supported"
            )

        raw_response = await chat_service.create_chat_completion(request, api_key)

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


@router.post("/v1/embeddings")
@router.post("/hf/v1/embeddings")
async def embedding(
    request: EmbeddingRequest,
    allowed_token=Depends(security_service.verify_authorization),
    key_manager: KeyManager = Depends(get_key_manager),
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
        response = await embedding_service.create_embedding(
            request=request, api_key=api_key
        )
        return response


@router.get("/v1/keys/list")
@router.get("/hf/v1/keys/list")
async def get_keys_list(
    _=Depends(security_service.verify_auth_token),
    key_manager: KeyManager = Depends(get_key_manager),
):
    """
    获取 API key 列表（管理端点）

    需要管理 Token 认证，返回有效和无效的 API key 列表。
    """
    operation_name = "get_keys_list"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling keys list request")
        keys_status = await key_manager.get_keys_by_status()
        return {
            "status": "success",
            "data": {
                "valid_keys": keys_status["valid_keys"],
                "invalid_keys": keys_status["invalid_keys"],
            },
            "total": len(keys_status["valid_keys"]) + len(keys_status["invalid_keys"]),
        }
