# app/services/chat/api_client.py
"""
OpenAI API 客户端模块

提供与 OpenAI 兼容 API 的通信功能，支持：
- 聊天完成（流式和非流式）
- 模型列表获取
- 文本嵌入
- 代理支持（包括代理管理器集成）
"""

import random
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from app.config.config import settings
from app.core.constants import DEFAULT_TIMEOUT
from app.log.logger import get_api_client_logger

logger = get_api_client_logger()


# 用于同步获取代理的辅助函数
def _get_proxy_sync(api_key: str) -> Optional[str]:
    """同步方式获取代理地址（用于不支持异步的场景）"""
    if not settings.PROXIES:
        return None

    if settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY:
        proxy = settings.PROXIES[hash(api_key) % len(settings.PROXIES)]
    else:
        proxy = random.choice(settings.PROXIES)

    return proxy


class ApiClient(ABC):
    """API客户端基类"""

    @abstractmethod
    async def generate_content(
        self, payload: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def stream_generate_content(
        self, payload: Dict[str, Any], api_key: str
    ) -> AsyncGenerator[str, None]:
        pass


class OpenaiApiClient(ApiClient):
    """
    OpenAI API 客户端

    支持标准 OpenAI API 格式，可配置自定义 BASE_URL 以支持其他兼容服务。

    Attributes:
        base_url: API 基础 URL，默认为 https://api.openai.com/v1
        timeout: 请求超时时间（秒）
    """

    def __init__(self, base_url: str = None, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url or settings.BASE_URL
        self.timeout = timeout

    async def _get_proxy(self, api_key: str) -> Optional[str]:
        """
        根据配置获取代理地址

        如果启用了代理自动检测，使用 ProxyManager 获取可用代理。
        否则使用传统的一致性哈希或随机选择方式。
        """
        if not settings.PROXIES:
            return None

        # 如果启用了代理自动检测，使用 ProxyManager
        if settings.PROXY_AUTO_CHECK_ENABLED:
            try:
                from app.service.proxy.proxy_manager import get_proxy_manager
                proxy_manager = await get_proxy_manager()
                proxy = await proxy_manager.get_proxy_for_key(api_key)
                if proxy:
                    logger.debug(f"Using proxy from ProxyManager: {proxy}")
                    return proxy
            except Exception as e:
                logger.warning(f"Failed to get proxy from ProxyManager: {e}, falling back to default")

        # 回退到传统方式
        if settings.PROXIES_USE_CONSISTENCY_HASH_BY_API_KEY:
            proxy = settings.PROXIES[hash(api_key) % len(settings.PROXIES)]
        else:
            proxy = random.choice(settings.PROXIES)

        logger.debug(f"Using proxy: {proxy}")
        return proxy

    async def _record_proxy_result(self, proxy: str, success: bool):
        """
        记录代理使用结果

        Args:
            proxy: 代理地址
            success: 是否成功
        """
        if not proxy or not settings.PROXY_AUTO_CHECK_ENABLED:
            return

        try:
            from app.service.proxy.proxy_manager import get_proxy_manager
            proxy_manager = await get_proxy_manager()
            if success:
                await proxy_manager.record_proxy_success(proxy)
            else:
                await proxy_manager.record_proxy_failure(proxy)
        except Exception as e:
            logger.warning(f"Failed to record proxy result: {e}")

    def _prepare_headers(self, api_key: str) -> Dict[str, str]:
        """准备请求头，包含认证信息和自定义头"""
        headers = {"Authorization": f"Bearer {api_key}"}
        if settings.CUSTOM_HEADERS:
            headers.update(settings.CUSTOM_HEADERS)
            logger.debug(f"Using custom headers: {list(settings.CUSTOM_HEADERS.keys())}")
        return headers

    async def get_models(self, api_key: str) -> Dict[str, Any]:
        """
        获取可用模型列表

        Args:
            api_key: API 密钥

        Returns:
            包含模型列表的字典

        Raises:
            Exception: 当 API 调用失败时
        """
        timeout = httpx.Timeout(timeout=30)
        proxy_to_use = await self._get_proxy(api_key)
        headers = self._prepare_headers(api_key)

        try:
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
                url = f"{self.base_url}/models"
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    error_content = response.text
                    logger.error(f"获取模型列表失败: {response.status_code}, {error_content}")
                    await self._record_proxy_result(proxy_to_use, False)
                    raise Exception(response.status_code, error_content)
                await self._record_proxy_result(proxy_to_use, True)
                return response.json()
        except Exception as e:
            await self._record_proxy_result(proxy_to_use, False)
            raise

    async def generate_content(
        self, payload: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        """
        非流式聊天完成

        Args:
            payload: 请求体，符合 OpenAI chat/completions 格式
            api_key: API 密钥

        Returns:
            聊天完成响应

        Raises:
            Exception: 当 API 调用失败时
        """
        timeout = httpx.Timeout(self.timeout, read=self.timeout)
        proxy_to_use = await self._get_proxy(api_key)
        headers = self._prepare_headers(api_key)

        try:
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
                url = f"{self.base_url}/chat/completions"
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    error_content = response.text
                    logger.error(
                        f"API call failed - Status: {response.status_code}, Content: {error_content}"
                    )
                    await self._record_proxy_result(proxy_to_use, False)
                    raise Exception(response.status_code, error_content)
                await self._record_proxy_result(proxy_to_use, True)
                return response.json()
        except Exception as e:
            await self._record_proxy_result(proxy_to_use, False)
            raise

    async def stream_generate_content(
        self, payload: Dict[str, Any], api_key: str
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天完成

        Args:
            payload: 请求体，符合 OpenAI chat/completions 格式
            api_key: API 密钥

        Yields:
            SSE 格式的响应行

        Raises:
            Exception: 当 API 调用失败时
        """
        timeout = httpx.Timeout(self.timeout, read=self.timeout)
        proxy_to_use = await self._get_proxy(api_key)
        headers = self._prepare_headers(api_key)

        try:
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
                url = f"{self.base_url}/chat/completions"
                async with client.stream(
                    method="POST", url=url, json=payload, headers=headers
                ) as response:
                    if response.status_code != 200:
                        error_content = await response.aread()
                        error_msg = error_content.decode("utf-8")
                        logger.error(
                            f"Stream API call failed - Status: {response.status_code}, Content: {error_msg}"
                        )
                        await self._record_proxy_result(proxy_to_use, False)
                        raise Exception(response.status_code, error_msg)
                    await self._record_proxy_result(proxy_to_use, True)
                    async for line in response.aiter_lines():
                        yield line
        except Exception as e:
            await self._record_proxy_result(proxy_to_use, False)
            raise

    async def create_embeddings(
        self, payload: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        """
        创建文本嵌入

        Args:
            payload: 请求体，包含 input 和 model 字段
            api_key: API 密钥

        Returns:
            嵌入响应

        Raises:
            Exception: 当 API 调用失败时
        """
        timeout = httpx.Timeout(self.timeout, read=self.timeout)
        proxy_to_use = await self._get_proxy(api_key)
        headers = self._prepare_headers(api_key)

        try:
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
                url = f"{self.base_url}/embeddings"
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    error_content = response.text
                    logger.error(
                        f"Embedding API call failed - Status: {response.status_code}, Content: {error_content}"
                    )
                    await self._record_proxy_result(proxy_to_use, False)
                    raise Exception(response.status_code, error_content)
                await self._record_proxy_result(proxy_to_use, True)
                return response.json()
        except Exception as e:
            await self._record_proxy_result(proxy_to_use, False)
            raise
