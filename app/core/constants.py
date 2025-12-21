"""
常量定义模块
"""

# API相关常量
API_VERSION = "v1"  # API 版本
DEFAULT_TIMEOUT = 300  # 秒
MAX_RETRIES = 3  # 最大重试次数

# 模型相关常量
SUPPORTED_ROLES = ["user", "assistant", "system"]
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 8192
DEFAULT_TOP_P = 0.9
DEFAULT_TOP_K = 40

# 图像处理相关常量
DATA_URL_PATTERN = r"data:([^;]+);base64,(.+)"
IMAGE_URL_PATTERN = r"!\[([^\]]*)\]\(([^)]+)\)"
VALID_IMAGE_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"]
