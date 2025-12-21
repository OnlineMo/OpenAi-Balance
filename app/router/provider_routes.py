"""
多提供商路由模块

提供多提供商支持的动态路由，包括：
- /v1/* - 默认提供商
- /{provider}/v1/* - 指定提供商
- /hf/v1/* - HuggingFace 格式默认提供商
- /hf/{provider}/v1/* - HuggingFace 格式指定提供商
- /openai/v1/* - OpenAI 格式默认提供商
- /openai/{provider}/v1/* - OpenAI 格式指定提供商
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import JSONResponse, StreamingResponse

from app.config.config import settings
from app.core.security import SecurityService
from app.domain.openai_models import ChatRequest, EmbeddingRequest
from app.handler.error_handler import handle_route_errors
from app.log.logger import get_openai_logger
from app.service.provider.provider_manager import ProviderManager, get_provider_manager
from app.service.provider.provider_service import ProviderService
from app.utils.helpers import redact_key_for_logging

router = APIRouter()
logger = get_openai_logger()

security_service = SecurityService()


async def get_manager() -> ProviderManager:
    """获取提供商管理器实例"""
    return await get_provider_manager()


async def get_provider_service(
    provider: Optional[str] = None,
    manager: ProviderManager = Depends(get_manager),
) -> ProviderService:
    """
    获取提供商服务

    Args:
        provider: 提供商名称或路径，如果为 None 则使用默认提供商

    Returns:
        ProviderService 实例

    Raises:
        HTTPException: 如果提供商不存在
    """
    if not manager.is_initialized:
        await manager.initialize()

    if provider is None or provider == "":
        service = await manager.get_default_service()
        if not service:
            raise HTTPException(
                status_code=503,
                detail="Default provider not available"
            )
        return service

    # 先尝试按名称查找
    service = await manager.get_service(provider)
    if service:
        return service

    # 再尝试按路径查找
    service = await manager.get_service_by_path(provider)
    if service:
        return service

    raise HTTPException(
        status_code=404,
        detail=f"Provider '{provider}' not found"
    )


# ==================== 默认提供商路由 ====================

@router.get("/v1/models")
async def list_models_default(
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """获取默认提供商的模型列表"""
    operation_name = "list_models_default"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling models list request for default provider '{service.config.name}'")
        return await service.get_models(
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


@router.post("/v1/chat/completions")
async def chat_completion_default(
    request: ChatRequest,
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """处理默认提供商的聊天完成请求"""
    return await _handle_chat_completion(request, service)


@router.post("/v1/embeddings")
async def embedding_default(
    request: EmbeddingRequest,
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """处理默认提供商的嵌入请求"""
    return await _handle_embedding(request, service)


# ==================== HuggingFace 格式默认提供商路由 ====================

@router.get("/hf/v1/models")
async def list_models_hf_default(
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """获取默认提供商的模型列表（HuggingFace 格式）"""
    operation_name = "list_models_hf_default"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling HF models list request for default provider '{service.config.name}'")
        return await service.get_models(
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


@router.post("/hf/v1/chat/completions")
async def chat_completion_hf_default(
    request: ChatRequest,
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """处理默认提供商的聊天完成请求（HuggingFace 格式）"""
    return await _handle_chat_completion(request, service)


@router.post("/hf/v1/embeddings")
async def embedding_hf_default(
    request: EmbeddingRequest,
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """处理默认提供商的嵌入请求（HuggingFace 格式）"""
    return await _handle_embedding(request, service)


# ==================== OpenAI 格式默认提供商路由 ====================

@router.get("/openai/v1/models")
async def list_models_openai_default(
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """获取默认提供商的模型列表（OpenAI 格式）"""
    operation_name = "list_models_openai_default"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling OpenAI models list request for default provider '{service.config.name}'")
        return await service.get_models(
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


@router.post("/openai/v1/chat/completions")
async def chat_completion_openai_default(
    request: ChatRequest,
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """处理默认提供商的聊天完成请求（OpenAI 格式）"""
    return await _handle_chat_completion(request, service)


@router.post("/openai/v1/embeddings")
async def embedding_openai_default(
    request: EmbeddingRequest,
    allowed_token=Depends(security_service.verify_authorization),
    service: ProviderService = Depends(get_provider_service),
):
    """处理默认提供商的嵌入请求（OpenAI 格式）"""
    return await _handle_embedding(request, service)


# ==================== 指定提供商路由 ====================

async def get_provider_service_by_path(
    provider: str = Path(..., description="提供商名称或路径"),
    manager: ProviderManager = Depends(get_manager),
) -> ProviderService:
    """根据路径参数获取提供商服务"""
    return await get_provider_service(provider, manager)


@router.get("/{provider}/v1/models")
async def list_models_provider(
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """获取指定提供商的模型列表"""
    service = await get_provider_service(provider, manager)
    operation_name = f"list_models_{provider}"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling models list request for provider '{service.config.name}'")
        return await service.get_models(
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


@router.post("/{provider}/v1/chat/completions")
async def chat_completion_provider(
    request: ChatRequest,
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """处理指定提供商的聊天完成请求"""
    service = await get_provider_service(provider, manager)
    return await _handle_chat_completion(request, service)


@router.post("/{provider}/v1/embeddings")
async def embedding_provider(
    request: EmbeddingRequest,
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """处理指定提供商的嵌入请求"""
    service = await get_provider_service(provider, manager)
    return await _handle_embedding(request, service)


# ==================== HuggingFace 格式指定提供商路由 ====================

@router.get("/hf/{provider}/v1/models")
async def list_models_hf_provider(
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """获取指定提供商的模型列表（HuggingFace 格式）"""
    service = await get_provider_service(provider, manager)
    operation_name = f"list_models_hf_{provider}"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling HF models list request for provider '{service.config.name}'")
        return await service.get_models(
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


@router.post("/hf/{provider}/v1/chat/completions")
async def chat_completion_hf_provider(
    request: ChatRequest,
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """处理指定提供商的聊天完成请求（HuggingFace 格式）"""
    service = await get_provider_service(provider, manager)
    return await _handle_chat_completion(request, service)


@router.post("/hf/{provider}/v1/embeddings")
async def embedding_hf_provider(
    request: EmbeddingRequest,
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """处理指定提供商的嵌入请求（HuggingFace 格式）"""
    service = await get_provider_service(provider, manager)
    return await _handle_embedding(request, service)


# ==================== OpenAI 格式指定提供商路由 ====================

@router.get("/openai/{provider}/v1/models")
async def list_models_openai_provider(
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """获取指定提供商的模型列表（OpenAI 格式）"""
    service = await get_provider_service(provider, manager)
    operation_name = f"list_models_openai_{provider}"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling OpenAI models list request for provider '{service.config.name}'")
        return await service.get_models(
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


@router.post("/openai/{provider}/v1/chat/completions")
async def chat_completion_openai_provider(
    request: ChatRequest,
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """处理指定提供商的聊天完成请求（OpenAI 格式）"""
    service = await get_provider_service(provider, manager)
    return await _handle_chat_completion(request, service)


@router.post("/openai/{provider}/v1/embeddings")
async def embedding_openai_provider(
    request: EmbeddingRequest,
    provider: str = Path(..., description="提供商名称或路径"),
    allowed_token=Depends(security_service.verify_authorization),
    manager: ProviderManager = Depends(get_manager),
):
    """处理指定提供商的嵌入请求（OpenAI 格式）"""
    service = await get_provider_service(provider, manager)
    return await _handle_embedding(request, service)


# ==================== 辅助函数 ====================

async def _handle_chat_completion(request: ChatRequest, service: ProviderService):
    """
    处理聊天完成请求的通用逻辑

    Args:
        request: 聊天请求
        service: 提供商服务

    Returns:
        聊天完成响应
    """
    operation_name = f"chat_completion_{service.config.name}"
    async with handle_route_errors(logger, operation_name):
        logger.info(
            f"Handling chat completion request for provider '{service.config.name}', model: {request.model}"
        )

        raw_response = await service.create_chat_completion(
            request=request,
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )

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


async def _handle_embedding(request: EmbeddingRequest, service: ProviderService):
    """
    处理嵌入请求的通用逻辑

    Args:
        request: 嵌入请求
        service: 提供商服务

    Returns:
        嵌入响应
    """
    operation_name = f"embedding_{service.config.name}"
    async with handle_route_errors(logger, operation_name):
        logger.info(
            f"Handling embedding request for provider '{service.config.name}', model: {request.model}"
        )

        payload = request.model_dump(exclude_none=True)
        return await service.create_embeddings(
            payload=payload,
            proxies=settings.PROXIES,
            use_consistency_hash=settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY,
        )


# ==================== 管理端点 ====================

@router.get("/v1/providers")
@router.get("/hf/v1/providers")
@router.get("/openai/v1/providers")
async def list_providers(
    _=Depends(security_service.verify_auth_token),
    manager: ProviderManager = Depends(get_manager),
):
    """
    获取所有提供商列表（管理端点）

    需要管理 Token 认证。
    """
    operation_name = "list_providers"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling providers list request")
        services = await manager.get_all_services()
        providers = []
        for name, service in services.items():
            providers.append({
                "name": service.config.name,
                "path": service.config.path,
                "base_url": service.config.base_url,
                "enabled": service.config.enabled,
                "is_default": name == manager.default_provider,
            })
        return {
            "status": "success",
            "data": providers,
            "default_provider": manager.default_provider,
            "total": len(providers),
        }


@router.get("/v1/providers/status")
@router.get("/hf/v1/providers/status")
@router.get("/openai/v1/providers/status")
async def providers_status(
    _=Depends(security_service.verify_auth_token),
    manager: ProviderManager = Depends(get_manager),
):
    """
    获取所有提供商的状态（管理端点）

    需要管理 Token 认证，返回每个提供商的密钥状态。
    """
    operation_name = "providers_status"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling providers status request")
        status = await manager.get_all_providers_status()
        return {
            "status": "success",
            "data": status,
            "default_provider": manager.default_provider,
        }
