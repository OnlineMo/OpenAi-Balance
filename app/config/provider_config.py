"""
提供商配置模型模块

定义多提供商配置的数据结构。
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """
    单个提供商配置

    Attributes:
        name: 提供商名称，如 openai, deepseek
        path: 路由路径标识，用于 URL 匹配
        base_url: API 基础 URL
        api_keys: API 密钥列表
        model_request_key: 用于获取模型列表的专用密钥（为空则使用第一个密钥）
        custom_headers: 自定义请求头
        timeout: 请求超时时间（秒）
        max_failures: 最大失败次数
        max_retries: 最大重试次数
        test_model: 用于测试密钥可用性的模型
        tools_code_execution_enabled: 是否启用代码执行工具
        enabled: 是否启用
    """

    name: str = Field(..., description="提供商名称，如 openai, deepseek")
    path: str = Field(..., description="路由路径标识，用于 URL 匹配")
    base_url: str = Field(..., description="API 基础 URL")
    api_keys: List[str] = Field(default_factory=list, description="API 密钥列表")
    model_request_key: str = Field(default="", description="用于获取模型列表的专用密钥")
    custom_headers: Dict[str, str] = Field(
        default_factory=dict, description="自定义请求头"
    )
    timeout: int = Field(default=300, description="请求超时时间（秒）")
    max_failures: int = Field(default=3, description="最大失败次数")
    max_retries: int = Field(default=3, description="最大重试次数")
    test_model: str = Field(default="", description="用于测试密钥可用性的模型")
    tools_code_execution_enabled: bool = Field(default=False, description="是否启用代码执行工具")
    enabled: bool = Field(default=True, description="是否启用")

    class Config:
        extra = "allow"


class ProvidersConfig(BaseModel):
    """
    多提供商配置

    Attributes:
        default_provider: 默认提供商名称
        providers: 提供商列表
    """

    default_provider: str = Field(
        default="default", description="默认提供商名称"
    )
    providers: List[ProviderConfig] = Field(
        default_factory=list, description="提供商列表"
    )
