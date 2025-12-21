"""
OpenAI 兼容服务模块

提供 OpenAI 兼容的 API 服务，包括聊天完成和文本嵌入。
直接转发请求到上游 API，支持自动重试机制。
"""

import datetime
import time
from typing import Any, AsyncGenerator, Dict, Union

from app.config.config import settings
from app.database.services import (
    add_error_log,
    add_request_log,
)
from app.domain.openai_models import ChatRequest, EmbeddingRequest
from app.log.logger import get_openai_compatible_logger
from app.service.client.api_client import OpenaiApiClient
from app.service.key.key_manager import KeyManager
from app.utils.helpers import redact_key_for_logging

logger = get_openai_compatible_logger()


class OpenAICompatiableService:
    """
    OpenAI 兼容服务

    提供与 OpenAI API 兼容的服务接口，支持：
    - 聊天完成（流式和非流式）
    - 文本嵌入
    - 模型列表获取
    """

    def __init__(self, base_url: str = None, key_manager: KeyManager = None):
        """
        初始化服务

        Args:
            base_url: API 基础 URL，默认使用配置中的 BASE_URL
            key_manager: 密钥管理器实例
        """
        self.key_manager = key_manager
        self.base_url = base_url or settings.BASE_URL
        self.api_client = OpenaiApiClient(self.base_url, settings.TIME_OUT)

    async def get_models(self, api_key: str) -> Dict[str, Any]:
        """
        获取可用模型列表

        Args:
            api_key: API 密钥

        Returns:
            模型列表字典
        """
        return await self.api_client.get_models(api_key)

    async def create_chat_completion(
        self,
        request: ChatRequest,
        api_key: str,
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        创建聊天完成

        Args:
            request: 聊天请求对象
            api_key: API 密钥

        Returns:
            非流式：返回完整响应字典
            流式：返回 SSE 格式的异步生成器
        """
        request_dict = request.model_dump()
        # 移除值为 None 的字段
        request_dict = {k: v for k, v in request_dict.items() if v is not None}
        # 删除 top_k 参数，OpenAI API 不支持
        request_dict.pop("top_k", None)

        if request.stream:
            return self._handle_stream_completion(request.model, request_dict, api_key)
        return await self._handle_normal_completion(
            request.model, request_dict, api_key
        )

    async def create_embeddings(
        self,
        request: EmbeddingRequest,
        api_key: str,
    ) -> Dict[str, Any]:
        """
        创建文本嵌入

        Args:
            request: 嵌入请求对象
            api_key: API 密钥

        Returns:
            嵌入响应字典
        """
        payload = {
            "input": request.input,
            "model": request.model,
        }
        if request.encoding_format:
            payload["encoding_format"] = request.encoding_format
        if request.dimensions:
            payload["dimensions"] = request.dimensions

        return await self.api_client.create_embeddings(payload, api_key)

    async def _handle_normal_completion(
        self, model: str, request: dict, api_key: str
    ) -> Dict[str, Any]:
        """
        处理非流式聊天完成

        Args:
            model: 模型名称
            request: 请求字典
            api_key: API 密钥

        Returns:
            聊天完成响应

        Raises:
            Exception: 当 API 调用失败时
        """
        start_time = time.perf_counter()
        request_datetime = datetime.datetime.now()
        is_success = False
        status_code = None

        try:
            response = await self.api_client.generate_content(request, api_key)
            is_success = True
            status_code = 200
            return response

        except Exception as e:
            is_success = False
            status_code = e.args[0] if e.args else 500
            error_log_msg = e.args[1] if len(e.args) > 1 else str(e)
            logger.error(f"Normal API call failed with error: {error_log_msg}")

            await add_error_log(
                gemini_key=api_key,
                model_name=model,
                error_type="openai-compatiable-non-stream",
                error_log=error_log_msg,
                error_code=status_code,
                request_msg=request if settings.ERROR_LOG_RECORD_REQUEST_BODY else None,
            )
            raise e

        finally:
            end_time = time.perf_counter()
            latency_ms = int((end_time - start_time) * 1000)
            await add_request_log(
                model_name=model,
                api_key=api_key,
                is_success=is_success,
                status_code=status_code,
                latency_ms=latency_ms,
                request_time=request_datetime,
            )

    async def _handle_stream_completion(
        self, model: str, payload: dict, api_key: str
    ) -> AsyncGenerator[str, None]:
        """
        处理流式聊天完成，支持自动重试

        Args:
            model: 模型名称
            payload: 请求字典
            api_key: API 密钥

        Yields:
            SSE 格式的响应行

        Raises:
            Exception: 当所有重试都失败时
        """
        retries = 0
        max_retries = settings.MAX_RETRIES
        is_success = False
        status_code = None
        final_api_key = api_key

        while retries < max_retries:
            start_time = time.perf_counter()
            request_datetime = datetime.datetime.now()
            current_attempt_key = final_api_key

            try:
                async for line in self.api_client.stream_generate_content(
                    payload, current_attempt_key
                ):
                    if line.startswith("data:"):
                        yield line + "\n\n"

                logger.info("Streaming completed successfully")
                is_success = True
                status_code = 200
                break

            except Exception as e:
                retries += 1
                is_success = False
                status_code = e.args[0] if e.args else 500
                error_log_msg = e.args[1] if len(e.args) > 1 else str(e)
                logger.warning(
                    f"Streaming API call failed with error: {error_log_msg}. Attempt {retries} of {max_retries}"
                )

                await add_error_log(
                    gemini_key=current_attempt_key,
                    model_name=model,
                    error_type="openai-compatiable-stream",
                    error_log=error_log_msg,
                    error_code=status_code,
                    request_msg=(
                        payload if settings.ERROR_LOG_RECORD_REQUEST_BODY else None
                    ),
                    request_datetime=request_datetime,
                )

                if self.key_manager:
                    new_api_key = await self.key_manager.handle_api_failure(
                        current_attempt_key, retries
                    )
                    if new_api_key:
                        final_api_key = new_api_key
                        logger.info(
                            f"Switched to new API key: {redact_key_for_logging(new_api_key)}"
                        )
                    else:
                        logger.error(
                            f"No valid API key available after {retries} retries."
                        )
                        raise
                else:
                    logger.error("KeyManager not available for retry logic.")
                    break

                if retries >= max_retries:
                    logger.error(f"Max retries ({max_retries}) reached for streaming.")
                    raise

            finally:
                end_time = time.perf_counter()
                latency_ms = int((end_time - start_time) * 1000)
                await add_request_log(
                    model_name=model,
                    api_key=final_api_key,
                    is_success=is_success,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    request_time=request_datetime,
                )
