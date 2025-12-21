from fastapi import APIRouter, Depends, Request
from app.service.key.key_manager import KeyManager, get_key_manager_instance
from app.service.provider.provider_key_manager import get_provider_key_manager
from app.core.security import verify_auth_token
from app.config.config import settings
from app.domain.openai_models import ChatRequest
from app.service.chat.openai_chat_service import OpenAIChatService
from app.log.logger import get_key_manager_logger
from fastapi.responses import JSONResponse

router = APIRouter()
logger = get_key_manager_logger()

@router.get("/api/keys")
async def get_keys_paginated(
    request: Request,
    page: int = 1,
    limit: int = 10,
    search: str = None,
    fail_count_threshold: int = None,
    status: str = "all",  # 'valid', 'invalid', 'all'
    provider: str = None,  # 提供商名称，None 或 'all' 表示所有提供商，'default' 表示默认提供商
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Get paginated, filtered, and searched keys.
    当配置了自定义提供商时，不返回默认提供商的密钥。
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    # 收集所有密钥及其提供商信息
    # 格式: {key: {"fail_count": int, "provider": str}}
    all_keys_info = {}

    # 获取所有自定义提供商的密钥状态
    provider_key_manager = await get_provider_key_manager()
    providers_status = await provider_key_manager.get_all_providers_status()
    has_custom_providers = len(providers_status) > 0

    # 如果是 "all" 或未指定，获取所有提供商的密钥
    if not provider or provider == "all":
        # 只有在没有自定义提供商时才获取默认提供商的密钥
        if not has_custom_providers:
            default_keys = await key_manager.get_all_keys_with_fail_count()
            if status == "valid":
                for key, fail_count in default_keys["valid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
            elif status == "invalid":
                for key, fail_count in default_keys["invalid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
            else:
                for key, fail_count in default_keys["valid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
                for key, fail_count in default_keys["invalid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}

        # 获取所有自定义提供商的密钥
        for provider_name, pstatus in providers_status.items():
            # 跳过名为 "default" 的提供商（避免重复）
            if provider_name.lower() == "default":
                continue
            keys_status = pstatus["keys_status"]
            if status == "valid":
                for key, fail_count in keys_status.get("valid_keys", {}).items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": provider_name}
            elif status == "invalid":
                for key, fail_count in keys_status.get("invalid_keys", {}).items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": provider_name}
            else:
                for key, fail_count in keys_status.get("valid_keys", {}).items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": provider_name}
                for key, fail_count in keys_status.get("invalid_keys", {}).items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": provider_name}
    elif provider == "default":
        # 只有在没有自定义提供商时才获取默认提供商的密钥
        if not has_custom_providers:
            default_keys = await key_manager.get_all_keys_with_fail_count()
            if status == "valid":
                for key, fail_count in default_keys["valid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
            elif status == "invalid":
                for key, fail_count in default_keys["invalid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
            else:
                for key, fail_count in default_keys["valid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
                for key, fail_count in default_keys["invalid_keys"].items():
                    all_keys_info[key] = {"fail_count": fail_count, "provider": "default"}
    else:
        # 获取指定提供商的密钥
        manager = await provider_key_manager.get_manager(provider)
        if not manager:
            return JSONResponse(status_code=404, content={"detail": f"Provider '{provider}' not found"})
        provider_keys = await manager.get_all_keys_with_fail_count()
        if status == "valid":
            for key, fail_count in provider_keys["valid_keys"].items():
                all_keys_info[key] = {"fail_count": fail_count, "provider": provider}
        elif status == "invalid":
            for key, fail_count in provider_keys["invalid_keys"].items():
                all_keys_info[key] = {"fail_count": fail_count, "provider": provider}
        else:
            for key, fail_count in provider_keys["valid_keys"].items():
                all_keys_info[key] = {"fail_count": fail_count, "provider": provider}
            for key, fail_count in provider_keys["invalid_keys"].items():
                all_keys_info[key] = {"fail_count": fail_count, "provider": provider}

    # Further filtering (search and fail_count_threshold)
    filtered_keys = {}
    for key, info in all_keys_info.items():
        search_match = True
        if search:
            search_match = search.lower() in key.lower()

        fail_count_match = True
        if fail_count_threshold is not None:
            fail_count_match = info["fail_count"] >= fail_count_threshold

        if search_match and fail_count_match:
            filtered_keys[key] = info

    # Pagination
    keys_list = list(filtered_keys.items())
    total_items = len(keys_list)
    start_index = (page - 1) * limit
    end_index = start_index + limit
    paginated_keys_list = keys_list[start_index:end_index]

    # 构建返回结果，保持向后兼容
    # keys: {key: fail_count} 用于向后兼容
    # keys_info: {key: {fail_count, provider}} 用于新功能
    paginated_keys = {}
    paginated_keys_info = {}
    for key, info in paginated_keys_list:
        paginated_keys[key] = info["fail_count"]
        paginated_keys_info[key] = info

    return {
        "keys": paginated_keys,
        "keys_info": paginated_keys_info,
        "total_items": total_items,
        "total_pages": (total_items + limit - 1) // limit if total_items > 0 else 1,
        "current_page": page,
        "provider": provider or "all",
    }

@router.get("/api/keys/all")
async def get_all_keys(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Get all keys (both valid and invalid) for bulk operations.
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    all_keys_with_status = await key_manager.get_all_keys_with_fail_count()

    return {
        "valid_keys": list(all_keys_with_status["valid_keys"].keys()),
        "invalid_keys": list(all_keys_with_status["invalid_keys"].keys()),
        "total_count": len(all_keys_with_status["valid_keys"]) + len(all_keys_with_status["invalid_keys"])
    }

@router.get("/api/keys/providers")
async def get_all_providers_keys(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    Get all keys grouped by provider.
    当配置了自定义提供商时，不返回默认提供商的密钥。
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    # 获取所有提供商的密钥状态
    provider_key_manager = await get_provider_key_manager()
    providers_status = await provider_key_manager.get_all_providers_status()
    has_custom_providers = len(providers_status) > 0

    result = {
        "providers": {}
    }

    # 只有在没有自定义提供商时才返回默认提供商
    if not has_custom_providers:
        default_keys_status = await key_manager.get_all_keys_with_fail_count()
        result["default"] = {
            "name": "default",
            "path": "",
            "base_url": "",
            "keys_status": default_keys_status,
            "total_keys": len(key_manager.api_keys),
            "valid_keys_count": len(default_keys_status.get("valid_keys", {})),
            "invalid_keys_count": len(default_keys_status.get("invalid_keys", {})),
        }

    for provider_name, status in providers_status.items():
        result["providers"][provider_name] = {
            "name": provider_name,
            "path": status["config"].get("path", ""),
            "base_url": status["config"].get("base_url", ""),
            "keys_status": status["keys_status"],
            "total_keys": status["total_keys"],
            "valid_keys_count": status["valid_keys_count"],
            "invalid_keys_count": status["invalid_keys_count"],
        }

    return result


@router.post("/api/keys/verify/{key:path}")
async def verify_key(
    request: Request,
    key: str,
    provider: str = None,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    验证单个 API 密钥是否有效。

    Args:
        key: 要验证的 API 密钥
        provider: 提供商名称，默认为 default
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        # 确定使用哪个提供商
        if provider and provider != "default":
            # 使用指定提供商
            provider_key_manager = await get_provider_key_manager()
            manager = await provider_key_manager.get_manager(provider)
            if not manager:
                return {"success": False, "error": f"Provider '{provider}' not found"}

            # 获取提供商配置
            from app.service.provider.provider_manager import get_provider_manager
            provider_manager = await get_provider_manager()
            provider_service = await provider_manager.get_service(provider)
            if not provider_service:
                return {"success": False, "error": f"Provider service '{provider}' not found"}

            base_url = provider_service.config.base_url
            test_model = provider_service.config.test_model or settings.TEST_MODEL
            target_key_manager = manager
        else:
            # 使用默认提供商
            base_url = settings.BASE_URL
            test_model = settings.TEST_MODEL
            target_key_manager = key_manager

        # 创建聊天服务进行验证
        chat_service = OpenAIChatService(base_url, target_key_manager)

        # 构造测试请求
        chat_request = ChatRequest(
            model=test_model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=10,
            stream=False,
        )

        # 执行验证
        await chat_service.create_chat_completion(chat_request, key)

        # 验证成功，重置失败计数
        await target_key_manager.reset_key_failure_count(key)
        logger.info(f"Key verification successful, failure count reset")

        return {"success": True, "status": "valid", "message": "密钥验证成功"}

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Key verification failed: {error_msg}")
        return {"success": False, "status": "invalid", "error": error_msg}


@router.post("/api/keys/reset-fail-count/{key:path}")
async def reset_key_fail_count(
    request: Request,
    key: str,
    provider: str = None,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    重置单个 API 密钥的失败计数。

    Args:
        key: 要重置的 API 密钥
        provider: 提供商名称，默认为 default
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        # 确定使用哪个提供商
        if provider and provider != "default":
            provider_key_manager = await get_provider_key_manager()
            manager = await provider_key_manager.get_manager(provider)
            if not manager:
                return {"success": False, "message": f"Provider '{provider}' not found"}
            target_key_manager = manager
        else:
            target_key_manager = key_manager

        # 重置失败计数
        result = await target_key_manager.reset_key_failure_count(key)

        if result:
            logger.info(f"Key failure count reset successfully")
            return {"success": True, "message": "失败计数重置成功"}
        else:
            return {"success": False, "message": "未找到该密钥"}

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to reset key failure count: {error_msg}")
        return {"success": False, "message": error_msg}


@router.get("/api/keys/stats")
async def get_keys_stats(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    获取所有提供商的密钥统计信息。
    当配置了自定义提供商时，不统计默认提供商的密钥。
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    # 获取所有自定义提供商的统计
    provider_key_manager = await get_provider_key_manager()
    providers_status = await provider_key_manager.get_all_providers_status()
    has_custom_providers = len(providers_status) > 0

    total_keys = 0
    total_valid = 0
    total_invalid = 0

    # 只有在没有自定义提供商时才统计默认提供商
    default_valid = 0
    default_invalid = 0
    if not has_custom_providers:
        default_keys = await key_manager.get_all_keys_with_fail_count()
        default_valid = len(default_keys.get("valid_keys", {}))
        default_invalid = len(default_keys.get("invalid_keys", {}))
        total_keys = default_valid + default_invalid
        total_valid = default_valid
        total_invalid = default_invalid

    for provider_name, status in providers_status.items():
        total_keys += status.get("total_keys", 0)
        total_valid += status.get("valid_keys_count", 0)
        total_invalid += status.get("invalid_keys_count", 0)

    result = {
        "total_keys": total_keys,
        "valid_keys": total_valid,
        "invalid_keys": total_invalid,
        "providers": {
            name: {
                "total": status.get("total_keys", 0),
                "valid": status.get("valid_keys_count", 0),
                "invalid": status.get("invalid_keys_count", 0),
            }
            for name, status in providers_status.items()
        }
    }

    # 只有在没有自定义提供商时才返回默认提供商统计
    if not has_custom_providers:
        result["default"] = {
            "total": default_valid + default_invalid,
            "valid": default_valid,
            "invalid": default_invalid,
        }

    return result


@router.post("/api/keys/verify-batch")
async def verify_keys_batch(
    request: Request,
    key_manager: KeyManager = Depends(get_key_manager_instance),
):
    """
    批量验证 API 密钥。

    Request body:
        keys: List[str] - 要验证的密钥列表
        provider: str (optional) - 提供商名称
    """
    auth_token = request.cookies.get("auth_token")
    if not auth_token or not verify_auth_token(auth_token):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    try:
        body = await request.json()
        keys_to_verify = body.get("keys", [])
        provider = body.get("provider", None)

        if not keys_to_verify:
            return {"successful_keys": [], "failed_keys": {}, "valid_count": 0, "invalid_count": 0}

        # 确定使用哪个提供商
        if provider and provider != "default" and provider != "all":
            from app.service.provider.provider_key_manager import get_provider_key_manager
            from app.service.provider.provider_manager import get_provider_manager
            provider_key_manager = await get_provider_key_manager()
            manager = await provider_key_manager.get_manager(provider)
            if not manager:
                return {"successful_keys": [], "failed_keys": {k: {"error_code": "PROVIDER_NOT_FOUND", "error_message": f"Provider '{provider}' not found"} for k in keys_to_verify}, "valid_count": 0, "invalid_count": len(keys_to_verify)}

            provider_manager = await get_provider_manager()
            provider_service = await provider_manager.get_service(provider)
            if not provider_service:
                return {"successful_keys": [], "failed_keys": {k: {"error_code": "SERVICE_NOT_FOUND", "error_message": f"Provider service '{provider}' not found"} for k in keys_to_verify}, "valid_count": 0, "invalid_count": len(keys_to_verify)}

            base_url = provider_service.config.base_url
            test_model = provider_service.config.test_model or settings.TEST_MODEL
            target_key_manager = manager
        else:
            base_url = settings.BASE_URL
            test_model = settings.TEST_MODEL
            target_key_manager = key_manager

        successful_keys = []
        failed_keys = {}

        for key in keys_to_verify:
            try:
                chat_service = OpenAIChatService(base_url, target_key_manager)
                chat_request = ChatRequest(
                    model=test_model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=10,
                    stream=False,
                )
                await chat_service.create_chat_completion(chat_request, key)
                await target_key_manager.reset_key_failure_count(key)
                successful_keys.append(key)
                logger.info(f"Batch verification: Key verified successfully")
            except Exception as e:
                error_msg = str(e)
                # 尝试提取错误码
                error_code = "UNKNOWN"
                if "429" in error_msg:
                    error_code = "429"
                elif "401" in error_msg:
                    error_code = "401"
                elif "403" in error_msg:
                    error_code = "403"
                elif "400" in error_msg:
                    error_code = "400"
                elif "500" in error_msg:
                    error_code = "500"
                failed_keys[key] = {"error_code": error_code, "error_message": error_msg}
                logger.warning(f"Batch verification: Key verification failed: {error_msg}")

        return {
            "successful_keys": successful_keys,
            "failed_keys": failed_keys,
            "valid_count": len(successful_keys),
            "invalid_count": len(failed_keys)
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Batch verification failed: {error_msg}")
        return JSONResponse(status_code=500, content={"detail": error_msg})
