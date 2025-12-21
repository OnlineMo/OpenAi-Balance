"""
模型服务模块

提供模型列表获取和模型验证功能。
支持使用 MODEL_REQUEST_KEY 或 API_KEYS[0] 获取模型列表。
"""

from typing import Any, Dict, Optional

from app.config.config import settings
from app.log.logger import get_model_logger
from app.service.client.api_client import OpenaiApiClient

logger = get_model_logger()


class ModelService:
    """
    模型服务

    提供从上游 API 获取模型列表的功能。
    """

    def _get_model_request_key(self) -> Optional[str]:
        """
        获取用于模型请求的 API key

        优先使用 MODEL_REQUEST_KEY，如果未设置则使用 ALLOWED_TOKENS 中的第一个。

        Returns:
            API key 或 None（如果没有可用的 key）
        """
        if settings.MODEL_REQUEST_KEY:
            return settings.MODEL_REQUEST_KEY
        if settings.ALLOWED_TOKENS:
            return settings.ALLOWED_TOKENS[0]
        return None

    async def get_models(self, api_key: str = None) -> Optional[Dict[str, Any]]:
        """
        获取可用模型列表

        Args:
            api_key: 可选的 API key，如果不提供则使用默认 key

        Returns:
            模型列表字典，格式符合 OpenAI API 规范
        """
        key_to_use = api_key or self._get_model_request_key()

        if not key_to_use:
            logger.error("没有可用的 API key 来获取模型列表")
            return None

        api_client = OpenaiApiClient(base_url=settings.BASE_URL)

        try:
            models_response = await api_client.get_models(key_to_use)

            if models_response is None:
                logger.error("从 API 客户端获取模型列表失败")
                return None

            # 过滤掉配置中指定的模型
            if settings.FILTERED_MODELS:
                filtered_data = []
                for model in models_response.get("data", []):
                    model_id = model.get("id", "")
                    if model_id not in settings.FILTERED_MODELS:
                        filtered_data.append(model)
                    else:
                        logger.debug(f"Filtered out model: {model_id}")
                models_response["data"] = filtered_data

            return models_response

        except Exception as e:
            logger.error(f"获取模型列表时出错: {e}")
            return None

    async def check_model_support(self, model: str) -> bool:
        """
        检查模型是否被支持（未被过滤）

        Args:
            model: 模型名称

        Returns:
            True 如果模型被支持，False 如果被过滤
        """
        if not model or not isinstance(model, str):
            return False

        model = model.strip()
        return model not in settings.FILTERED_MODELS
