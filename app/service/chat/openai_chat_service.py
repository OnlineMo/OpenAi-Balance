# app/services/chat_service.py
"""
OpenAI 聊天服务模块

提供聊天完成功能，直接转发 OpenAI 格式请求到上游 API。
支持流式和非流式响应，以及自动重试机制。
"""

import datetime
import time
from typing import Any, AsyncGenerator, Dict, Union

from app.config.config import settings
from app.database.services import (
    add_error_log,
    add_request_log,
)
from app.domain.openai_models import ChatRequest
from app.log.logger import get_openai_logger
from app.service.client.api_client import OpenaiApiClient
from app.service.key.key_manager import KeyManager

logger = get_openai_logger()


class OpenAIChatService:
    """
    OpenAI 聊天服务

    直接转发 OpenAI 格式的请求到上游 API，支持：
    - 流式和非流式聊天完成
    - 自动重试机制
    - 请求日志记录

    Attributes:
        api_client: OpenAI API 客户端
        key_manager: API 密钥管理器
    """

    def __init__(self, base_url: str = None, key_manager: KeyManager = None):
        """
        初始化聊天服务

        Args:
            base_url: API 基础 URL，默认使用配置中的 BASE_URL
            key_manager: 密钥管理器实例
        """
        self.api_client = OpenaiApiClient(base_url or settings.BASE_URL, settings.TIME_OUT)
        self.key_manager = key_manager

    def _prepare_payload(self, request: ChatRequest) -> Dict[str, Any]:
        """
        准备请求 payload

        Args:
            request: 聊天请求对象

        Returns:
            符合 OpenAI API 格式的请求体
        """
        payload = request.model_dump(exclude_none=True)
        # 移除不支持的参数
        payload.pop("top_k", None)
        return payload

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
        payload = self._prepare_payload(request)

        if request.stream:
            return self._handle_stream_completion(request.model, payload, api_key)
        return await self._handle_normal_completion(request.model, payload, api_key)

    async def _handle_normal_completion(
        self, model: str, payload: Dict[str, Any], api_key: str
    ) -> Dict[str, Any]:
        """
        处理非流式聊天完成

        Args:
            model: 模型名称
            payload: 请求体
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
            response = await self.api_client.generate_content(payload, api_key)
            is_success = True
            status_code = 200
            return response

        except Exception as e:
            is_success = False
            status_code = e.args[0] if e.args else 500
            error_log_msg = e.args[1] if len(e.args) > 1 else str(e)
            logger.error(f"API call failed for model {model}: {error_log_msg}")

            await add_error_log(
                gemini_key=api_key,
                model_name=model,
                error_type="openai-chat-non-stream",
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
                f"Normal completion finished - Model: {model}, Success: {is_success}, Latency: {latency_ms}ms"
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
        self, model: str, payload: Dict[str, Any], api_key: str
    ) -> AsyncGenerator[str, None]:
        """
        处理流式聊天完成，支持自动重试

        Args:
            model: 模型名称
            payload: 请求体
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
                    if line:
                        yield f"{line}\n"

                logger.info(
                    f"Streaming completed successfully for model: {model}, Attempt: {retries + 1}"
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
                    f"Streaming API call failed: {error_log_msg}. Attempt {retries} of {max_retries}"
                )

                await add_error_log(
                    gemini_key=current_attempt_key,
                    model_name=model,
                    error_type="openai-chat-stream",
                    error_log=error_log_msg,
                    error_code=status_code,
                    request_msg=(
                        payload if settings.ERROR_LOG_RECORD_REQUEST_BODY else None
                    ),
                    request_datetime=request_datetime,
                )

                # 尝试切换 API key
                if self.key_manager:
                    new_api_key = await self.key_manager.handle_api_failure(
                        current_attempt_key, retries
                    )
                    if new_api_key and new_api_key != current_attempt_key:
                        final_api_key = new_api_key
                        logger.info(f"Switched to new API key for next attempt")
                    elif not new_api_key:
                        logger.error(
                            f"No valid API key available after {retries} retries"
                        )
                        raise
                else:
                    logger.error("KeyManager not available, cannot switch API key")
                    break

                if retries >= max_retries:
                    logger.error(
                        f"Max retries ({max_retries}) reached for streaming model {model}"
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
