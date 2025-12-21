"""
提供商服务模块

封装单个提供商的 API 调用功能。
"""

import datetime
import random
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx

from app.config.provider_config import ProviderConfig
from app.database.services import add_error_log, add_request_log
from app.domain.openai_models import ChatRequest
from app.log.logger import get_api_client_logger
from app.service.key.key_manager import KeyManager

logger = get_api_client_logger()


class ProviderService:
    """
    提供商服务

    封装单个提供商的所有 API 调用，包括：
    - 聊天完成（流式和非流式）
    - 模型列表获取
    - 文本嵌入

    Attributes:
        config: 提供商配置
        key_manager: 密钥管理器
    """

    def __init__(self, config: ProviderConfig, key_manager: KeyManager):
        """
        初始化提供商服务

        Args:
            config: 提供商配置
            key_manager: 密钥管理器
        """
        self.config = config
        self.key_manager = key_manager

    def _get_proxy(self, api_key: str, proxies: List[str], use_consistency_hash: bool) -> Optional[str]:
        """
        根据配置获取代理地址

        Args:
            api_key: API 密钥
            proxies: 代理列表
            use_consistency_hash: 是否使用一致性哈希

        Returns:
            代理地址，如果没有配置代理则返回 None
        """
        if not proxies:
            return None

        if use_consistency_hash:
            proxy = proxies[hash(api_key) % len(proxies)]
        else:
            proxy = random.choice(proxies)

        logger.debug(f"Provider '{self.config.name}' using proxy: {proxy}")
        return proxy

    def _prepare_headers(self, api_key: str) -> Dict[str, str]:
        """
        准备请求头

        Args:
            api_key: API 密钥

        Returns:
            请求头字典
        """
        headers = {"Authorization": f"Bearer {api_key}"}
        if self.config.custom_headers:
            headers.update(self.config.custom_headers)
            logger.debug(
                f"Provider '{self.config.name}' using custom headers: {list(self.config.custom_headers.keys())}"
            )
        return headers

    async def get_models(
        self, api_key: str = None, proxies: List[str] = None, use_consistency_hash: bool = True
    ) -> Dict[str, Any]:
        """
        获取可用模型列表

        Args:
            api_key: API 密钥，如果不提供则从配置或 key_manager 获取
            proxies: 代理列表
            use_consistency_hash: 是否使用一致性哈希选择代理

        Returns:
            包含模型列表的字典

        Raises:
            Exception: 当 API 调用失败时
        """
        if not api_key:
            # 优先使用配置的 model_request_key
            if self.config.model_request_key:
                api_key = self.config.model_request_key
                logger.debug(f"Provider '{self.config.name}' using configured model_request_key for models request")
            else:
                api_key = await self.key_manager.get_first_valid_key()

        if not api_key:
            raise Exception(500, f"No valid API key available for provider '{self.config.name}'")

        timeout = httpx.Timeout(timeout=30)
        proxy_to_use = self._get_proxy(api_key, proxies or [], use_consistency_hash)
        headers = self._prepare_headers(api_key)

        async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
            url = f"{self.config.base_url}/models"
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                error_content = response.text
                logger.error(
                    f"Provider '{self.config.name}' get models failed: {response.status_code}, {error_content}"
                )
                raise Exception(response.status_code, error_content)
            return response.json()

    async def create_chat_completion(
        self,
        request: ChatRequest,
        api_key: str = None,
        proxies: List[str] = None,
        use_consistency_hash: bool = True,
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        创建聊天完成

        Args:
            request: 聊天请求对象
            api_key: API 密钥，如果不提供则从 key_manager 获取
            proxies: 代理列表
            use_consistency_hash: 是否使用一致性哈希选择代理

        Returns:
            非流式：返回完整响应字典
            流式：返回 SSE 格式的异步生成器
        """
        if not api_key:
            api_key = await self.key_manager.get_next_working_key()

        if not api_key:
            raise Exception(500, f"No valid API key available for provider '{self.config.name}'")

        payload = self._prepare_payload(request)

        if request.stream:
            return self._handle_stream_completion(
                request.model, payload, api_key, proxies or [], use_consistency_hash
            )
        return await self._handle_normal_completion(
            request.model, payload, api_key, proxies or [], use_consistency_hash
        )

    def _prepare_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """
        准备请求 payload

        Args:
            request: 聊天请求对象

        Returns:
            符合 OpenAI API 格式的请求体
        """
        payload = request.model_dump(exclude_none=True)
        payload.pop("top_k", None)
        return payload

    async def _handle_normal_completion(
        self,
        model: str,
        payload: Dict[str, Any],
        api_key: str,
        proxies: List[str],
        use_consistency_hash: bool,
    ) -> Dict[str, Any]:
        """
        处理非流式聊天完成

        Args:
            model: 模型名称
            payload: 请求体
            api_key: API 密钥
            proxies: 代理列表
            use_consistency_hash: 是否使用一致性哈希选择代理

        Returns:
            聊天完成响应

        Raises:
            Exception: 当 API 调用失败时
        """
        start_time = time.perf_counter()
        request_datetime = datetime.datetime.now()
        is_success = False
        status_code = None

        timeout = httpx.Timeout(self.config.timeout, read=self.config.timeout)
        proxy_to_use = self._get_proxy(api_key, proxies, use_consistency_hash)
        headers = self._prepare_headers(api_key)

        try:
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
                url = f"{self.config.base_url}/chat/completions"
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    error_content = response.text
                    logger.error(
                        f"Provider '{self.config.name}' API call failed - Status: {response.status_code}, Content: {error_content}"
                    )
                    raise Exception(response.status_code, error_content)
                is_success = True
                status_code = 200
                return response.json()

        except Exception as e:
            is_success = False
            status_code = e.args[0] if e.args else 500
            error_log_msg = e.args[1] if len(e.args) > 1 else str(e)
            logger.error(
                f"Provider '{self.config.name}' API call failed for model {model}: {error_log_msg}"
            )

            from app.config.config import settings
            await add_error_log(
                gemini_key=api_key,
                model_name=model,
                error_type=f"{self.config.name}-chat-non-stream",
                error_log=error_log_msg,
                error_code=status_code,
                request_msg=payload if settings.ERROR_LOG_RECORD_REQUEST_BODY else None,
                request_datetime=request_datetime,
            )
            raise e

        finally:
            end_time = time.perf_counter()
            latency_ms = int((end_time - start_time) * 1000)
            logger.info(
                f"Provider '{self.config.name}' normal completion finished - Model: {model}, Success: {is_success}, Latency: {latency_ms}ms"
            )

            await add_request_log(
                model_name=model,
                api_key=api_key,
                is_success=is_success,
                status_code=status_code,
                latency_ms=latency_ms,
                request_time=request_datetime,
            )

    async def _handle_stream_completion(
        self,
        model: str,
        payload: Dict[str, Any],
        api_key: str,
        proxies: List[str],
        use_consistency_hash: bool,
    ) -> AsyncGenerator[str, None]:
        """
        处理流式聊天完成，支持自动重试

        Args:
            model: 模型名称
            payload: 请求体
            api_key: API 密钥
            proxies: 代理列表
            use_consistency_hash: 是否使用一致性哈希选择代理

        Yields:
            SSE 格式的响应行

        Raises:
            Exception: 当所有重试都失败时
        """
        retries = 0
        max_retries = self.config.max_retries
        is_success = False
        status_code = None
        final_api_key = api_key

        timeout = httpx.Timeout(self.config.timeout, read=self.config.timeout)

        while retries < max_retries:
            start_time = time.perf_counter()
            request_datetime = datetime.datetime.now()
            current_attempt_key = final_api_key

            proxy_to_use = self._get_proxy(current_attempt_key, proxies, use_consistency_hash)
            headers = self._prepare_headers(current_attempt_key)

            try:
                async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
                    url = f"{self.config.base_url}/chat/completions"
                    async with client.stream(
                        method="POST", url=url, json=payload, headers=headers
                    ) as response:
                        if response.status_code != 200:
                            error_content = await response.aread()
                            error_msg = error_content.decode("utf-8")
                            logger.error(
                                f"Provider '{self.config.name}' stream API call failed - Status: {response.status_code}, Content: {error_msg}"
                            )
                            raise Exception(response.status_code, error_msg)
                        async for line in response.aiter_lines():
                            if line:
                                yield f"{line}\n"

                logger.info(
                    f"Provider '{self.config.name}' streaming completed successfully for model: {model}, Attempt: {retries + 1}"
                )
                is_success = True
                status_code = 200
                break

            except Exception as e:
                retries += 1
                is_success = False
                status_code = e.args[0] if e.args else 500
                error_log_msg = e.args[1] if len(e.args) > 1 else str(e)
                logger.warning(
                    f"Provider '{self.config.name}' streaming API call failed: {error_log_msg}. Attempt {retries} of {max_retries}"
                )

                from app.config.config import settings
                await add_error_log(
                    gemini_key=current_attempt_key,
                    model_name=model,
                    error_type=f"{self.config.name}-chat-stream",
                    error_log=error_log_msg,
                    error_code=status_code,
                    request_msg=payload if settings.ERROR_LOG_RECORD_REQUEST_BODY else None,
                    request_datetime=request_datetime,
                )

                # 尝试切换 API key
                new_api_key = await self.key_manager.handle_api_failure(
                    current_attempt_key, retries
                )
                if new_api_key and new_api_key != current_attempt_key:
                    final_api_key = new_api_key
                    logger.info(
                        f"Provider '{self.config.name}' switched to new API key for next attempt"
                    )
                elif not new_api_key:
                    logger.error(
                        f"Provider '{self.config.name}' no valid API key available after {retries} retries"
                    )
                    raise

                if retries >= max_retries:
                    logger.error(
                        f"Provider '{self.config.name}' max retries ({max_retries}) reached for streaming model {model}"
                    )
                    raise

            finally:
                end_time = time.perf_counter()
                latency_ms = int((end_time - start_time) * 1000)
                await add_request_log(
                    model_name=model,
                    api_key=current_attempt_key,
                    is_success=is_success,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    request_time=request_datetime,
                )

    async def create_embeddings(
        self,
        payload: Dict[str, Any],
        api_key: str = None,
        proxies: List[str] = None,
        use_consistency_hash: bool = True,
    ) -> Dict[str, Any]:
        """
        创建文本嵌入

        Args:
            payload: 请求体，包含 input 和 model 字段
            api_key: API 密钥，如果不提供则从 key_manager 获取
            proxies: 代理列表
            use_consistency_hash: 是否使用一致性哈希选择代理

        Returns:
            嵌入响应

        Raises:
            Exception: 当 API 调用失败时
        """
        if not api_key:
            api_key = await self.key_manager.get_next_working_key()

        if not api_key:
            raise Exception(500, f"No valid API key available for provider '{self.config.name}'")

        timeout = httpx.Timeout(self.config.timeout, read=self.config.timeout)
        proxy_to_use = self._get_proxy(api_key, proxies or [], use_consistency_hash)
        headers = self._prepare_headers(api_key)

        async with httpx.AsyncClient(timeout=timeout, proxy=proxy_to_use) as client:
            url = f"{self.config.base_url}/embeddings"
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                error_content = response.text
                logger.error(
                    f"Provider '{self.config.name}' embedding API call failed - Status: {response.status_code}, Content: {error_content}"
                )
                raise Exception(response.status_code, error_content)
            return response.json()
