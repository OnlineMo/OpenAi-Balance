"""
文本嵌入服务模块

提供文本嵌入功能，将文本转换为向量表示。
使用 OpenAI API 客户端进行嵌入请求。
"""

import datetime
import time
from typing import Any, Dict

from app.config.config import settings
from app.database.services import add_error_log, add_request_log
from app.domain.openai_models import EmbeddingRequest
from app.log.logger import get_embeddings_logger
from app.service.client.api_client import OpenaiApiClient

logger = get_embeddings_logger()


class EmbeddingService:
    """
    文本嵌入服务

    提供文本到向量的转换功能。
    """

    def __init__(self):
        self.api_client = OpenaiApiClient(settings.BASE_URL, settings.TIME_OUT)

    async def create_embedding(
        self, request: EmbeddingRequest, api_key: str
    ) -> Dict[str, Any]:
        """
        创建文本嵌入

        Args:
            request: 嵌入请求对象
            api_key: API 密钥

        Returns:
            嵌入响应字典

        Raises:
            Exception: 当 API 调用失败时
        """
        start_time = time.perf_counter()
        request_datetime = datetime.datetime.now()
        is_success = False
        status_code = None
        error_log_msg = ""

        # 准备日志用的请求信息（截断长文本）
        input_text = request.input
        if isinstance(input_text, list):
            request_msg_log = {
                "input_truncated": [
                    str(item)[:100] + "..." if len(str(item)) > 100 else str(item)
                    for item in input_text[:5]
                ]
            }
            if len(input_text) > 5:
                request_msg_log["input_truncated"].append("...")
        else:
            request_msg_log = {
                "input_truncated": (
                    input_text[:1000] + "..." if len(input_text) > 1000 else input_text
                )
            }

        try:
            payload = {
                "input": request.input,
                "model": request.model,
            }
            if request.encoding_format:
                payload["encoding_format"] = request.encoding_format
            if request.dimensions:
                payload["dimensions"] = request.dimensions

            response = await self.api_client.create_embeddings(payload, api_key)
            is_success = True
            status_code = 200
            return response

        except Exception as e:
            is_success = False
            status_code = e.args[0] if e.args else 500
            error_log_msg = e.args[1] if len(e.args) > 1 else str(e)
            logger.error(f"Error creating embedding: {error_log_msg}")
            raise e

        finally:
            end_time = time.perf_counter()
            latency_ms = int((end_time - start_time) * 1000)

            if not is_success:
                await add_error_log(
                    gemini_key=api_key,
                    model_name=request.model,
                    error_type="openai-embedding",
                    error_log=error_log_msg,
                    error_code=status_code,
                    request_msg=(
                        request_msg_log
                        if settings.ERROR_LOG_RECORD_REQUEST_BODY
                        else None
                    ),
                    request_datetime=request_datetime,
                )

            await add_request_log(
                model_name=request.model,
                api_key=api_key,
                is_success=is_success,
                status_code=status_code,
                latency_ms=latency_ms,
                request_time=request_datetime,
            )
