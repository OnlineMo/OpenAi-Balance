"""
API 密钥管理模块

提供 API 密钥的轮询、失败计数和状态管理功能。
支持：
- 轮询获取下一个可用密钥
- 失败计数跟踪
- 自动禁用失败次数过多的密钥
"""

import asyncio
import random
from itertools import cycle
from typing import Dict, Union

from app.config.config import settings
from app.log.logger import get_key_manager_logger
from app.utils.helpers import redact_key_for_logging

logger = get_key_manager_logger()


class KeyManager:
    """
    API 密钥管理器

    管理 API 密钥的轮询和失败计数，自动禁用失败次数过多的密钥。

    Attributes:
        api_keys: API 密钥列表
        key_cycle: 密钥轮询迭代器
        key_failure_counts: 密钥失败计数字典
        MAX_FAILURES: 最大失败次数阈值
    """

    def __init__(self, api_keys: list):
        """
        初始化密钥管理器

        Args:
            api_keys: API 密钥列表
        """
        self.api_keys = api_keys
        self.key_cycle = cycle(api_keys) if api_keys else cycle([])
        self.key_cycle_lock = asyncio.Lock()
        self.failure_count_lock = asyncio.Lock()
        self.key_failure_counts: Dict[str, int] = {key: 0 for key in api_keys}
        self.MAX_FAILURES = settings.MAX_FAILURES

    async def get_next_key(self) -> str:
        """
        获取下一个 API key（轮询）

        Returns:
            下一个 API key
        """
        async with self.key_cycle_lock:
            return next(self.key_cycle)

    async def is_key_valid(self, key: str) -> bool:
        """
        检查 key 是否有效（失败次数未超过阈值）

        Args:
            key: API key

        Returns:
            True 如果 key 有效
        """
        async with self.failure_count_lock:
            return self.key_failure_counts.get(key, 0) < self.MAX_FAILURES

    async def reset_failure_counts(self):
        """重置所有 key 的失败计数"""
        async with self.failure_count_lock:
            for key in self.key_failure_counts:
                self.key_failure_counts[key] = 0

    async def reset_key_failure_count(self, key: str) -> bool:
        """
        重置指定 key 的失败计数

        Args:
            key: API key

        Returns:
            True 如果重置成功
        """
        async with self.failure_count_lock:
            if key in self.key_failure_counts:
                self.key_failure_counts[key] = 0
                logger.info(f"Reset failure count for key: {redact_key_for_logging(key)}")
                return True
            logger.warning(
                f"Attempt to reset failure count for non-existent key: {key}"
            )
            return False

    async def get_next_working_key(self) -> str:
        """
        获取下一个可用的 API key

        遍历所有 key，返回第一个失败次数未超过阈值的 key。
        如果所有 key 都不可用，返回第一个 key 作为 fallback。

        Returns:
            可用的 API key
        """
        if not self.api_keys:
            logger.warning("API key list is empty")
            return ""

        initial_key = await self.get_next_key()
        current_key = initial_key

        while True:
            if await self.is_key_valid(current_key):
                return current_key

            current_key = await self.get_next_key()
            if current_key == initial_key:
                return current_key

    async def handle_api_failure(self, api_key: str, retries: int) -> str:
        """
        处理 API 调用失败

        增加失败计数，如果未超过重试次数则返回下一个可用 key。

        Args:
            api_key: 失败的 API key
            retries: 当前重试次数

        Returns:
            下一个可用的 API key，如果超过重试次数则返回空字符串
        """
        async with self.failure_count_lock:
            if api_key in self.key_failure_counts:
                self.key_failure_counts[api_key] += 1
                if self.key_failure_counts[api_key] >= self.MAX_FAILURES:
                    logger.warning(
                        f"API key {redact_key_for_logging(api_key)} has failed {self.MAX_FAILURES} times"
                    )

        if retries < settings.MAX_RETRIES:
            return await self.get_next_working_key()
        else:
            return ""

    def get_fail_count(self, key: str) -> int:
        """
        获取指定密钥的失败次数

        Args:
            key: API key

        Returns:
            失败次数
        """
        return self.key_failure_counts.get(key, 0)

    async def get_all_keys_with_fail_count(self) -> dict:
        """
        获取所有 API key 及其失败次数

        Returns:
            包含 valid_keys、invalid_keys 和 all_keys 的字典
        """
        all_keys = {}
        async with self.failure_count_lock:
            for key in self.api_keys:
                all_keys[key] = self.key_failure_counts.get(key, 0)

        valid_keys = {k: v for k, v in all_keys.items() if v < self.MAX_FAILURES}
        invalid_keys = {k: v for k, v in all_keys.items() if v >= self.MAX_FAILURES}

        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys, "all_keys": all_keys}

    async def get_keys_by_status(self) -> dict:
        """
        获取分类后的 API key 列表

        Returns:
            包含 valid_keys 和 invalid_keys 的字典
        """
        valid_keys = {}
        invalid_keys = {}

        async with self.failure_count_lock:
            for key in self.api_keys:
                fail_count = self.key_failure_counts.get(key, 0)
                if fail_count < self.MAX_FAILURES:
                    valid_keys[key] = fail_count
                else:
                    invalid_keys[key] = fail_count

        return {"valid_keys": valid_keys, "invalid_keys": invalid_keys}

    async def get_first_valid_key(self) -> str:
        """
        获取第一个有效的 API key

        Returns:
            第一个有效的 API key
        """
        async with self.failure_count_lock:
            for key in self.api_keys:
                if self.key_failure_counts.get(key, 0) < self.MAX_FAILURES:
                    return key

        if self.api_keys:
            return self.api_keys[0]

        logger.warning("API key list is empty, cannot get first valid key.")
        return ""

    async def get_random_valid_key(self) -> str:
        """
        获取随机的有效 API key

        Returns:
            随机的有效 API key
        """
        valid_keys = []
        async with self.failure_count_lock:
            for key in self.api_keys:
                if self.key_failure_counts.get(key, 0) < self.MAX_FAILURES:
                    valid_keys.append(key)

        if valid_keys:
            return random.choice(valid_keys)

        if self.api_keys:
            logger.warning("No valid keys available, returning first key as fallback.")
            return self.api_keys[0]

        logger.warning("API key list is empty, cannot get random valid key.")
        return ""


# 单例相关
_singleton_instance = None
_singleton_lock = asyncio.Lock()
_preserved_failure_counts: Union[Dict[str, int], None] = None
_preserved_old_api_keys_for_reset: Union[list, None] = None
_preserved_next_key_in_cycle: Union[str, None] = None


async def get_key_manager_instance(api_keys: list = None) -> KeyManager:
    """
    获取 KeyManager 单例实例

    如果尚未创建实例，将使用提供的 api_keys 初始化 KeyManager。
    如果已创建实例，则忽略 api_keys 参数，返回现有单例。
    如果在重置后调用，会尝试恢复之前的状态。

    Args:
        api_keys: API 密钥列表（仅在首次初始化时需要）

    Returns:
        KeyManager 单例实例

    Raises:
        ValueError: 如果首次初始化时未提供 api_keys
    """
    global _singleton_instance, _preserved_failure_counts, _preserved_old_api_keys_for_reset, _preserved_next_key_in_cycle

    async with _singleton_lock:
        if _singleton_instance is None:
            if api_keys is None:
                raise ValueError(
                    "API keys are required to initialize the KeyManager instance."
                )

            if not api_keys:
                logger.warning(
                    "Initializing KeyManager with an empty list of API keys."
                )

            _singleton_instance = KeyManager(api_keys)
            logger.info(
                f"KeyManager instance created with {len(api_keys)} API keys."
            )

            # 恢复失败计数
            if _preserved_failure_counts:
                current_failure_counts = {
                    key: 0 for key in _singleton_instance.api_keys
                }
                for key, count in _preserved_failure_counts.items():
                    if key in current_failure_counts:
                        current_failure_counts[key] = count
                _singleton_instance.key_failure_counts = current_failure_counts
                logger.info("Inherited failure counts for applicable keys.")
            _preserved_failure_counts = None

            # 调整 key_cycle 的起始点
            start_key_for_new_cycle = None
            if (
                _preserved_old_api_keys_for_reset
                and _preserved_next_key_in_cycle
                and _singleton_instance.api_keys
            ):
                try:
                    start_idx_in_old = _preserved_old_api_keys_for_reset.index(
                        _preserved_next_key_in_cycle
                    )

                    for i in range(len(_preserved_old_api_keys_for_reset)):
                        current_old_key_idx = (start_idx_in_old + i) % len(
                            _preserved_old_api_keys_for_reset
                        )
                        key_candidate = _preserved_old_api_keys_for_reset[
                            current_old_key_idx
                        ]
                        if key_candidate in _singleton_instance.api_keys:
                            start_key_for_new_cycle = key_candidate
                            break
                except ValueError:
                    logger.warning(
                        f"Preserved next key not found in preserved old API keys. "
                        "New cycle will start from the beginning."
                    )
                except Exception as e:
                    logger.error(
                        f"Error determining start key for new cycle: {e}. "
                        "New cycle will start from the beginning."
                    )

            if start_key_for_new_cycle and _singleton_instance.api_keys:
                try:
                    target_idx = _singleton_instance.api_keys.index(
                        start_key_for_new_cycle
                    )
                    for _ in range(target_idx):
                        next(_singleton_instance.key_cycle)
                    logger.info(
                        f"Key cycle advanced to: {start_key_for_new_cycle}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error advancing key cycle: {e}. Cycle will start from beginning."
                    )

            # 清理保存的状态
            _preserved_old_api_keys_for_reset = None
            _preserved_next_key_in_cycle = None

        return _singleton_instance


async def reset_key_manager_instance():
    """
    重置 KeyManager 单例实例

    保存当前实例的状态以供下一次初始化时恢复。
    """
    global _singleton_instance, _preserved_failure_counts, _preserved_old_api_keys_for_reset, _preserved_next_key_in_cycle

    async with _singleton_lock:
        if _singleton_instance:
            # 保存失败计数
            _preserved_failure_counts = _singleton_instance.key_failure_counts.copy()

            # 保存旧的 API keys 列表
            _preserved_old_api_keys_for_reset = _singleton_instance.api_keys.copy()

            # 保存 key_cycle 的下一个 key 提示
            try:
                if _singleton_instance.api_keys:
                    _preserved_next_key_in_cycle = (
                        await _singleton_instance.get_next_key()
                    )
                else:
                    _preserved_next_key_in_cycle = None
            except Exception as e:
                logger.error(f"Error preserving next key hint during reset: {e}")
                _preserved_next_key_in_cycle = None

            _singleton_instance = None
            logger.info(
                "KeyManager instance has been reset. State preserved for next instantiation."
            )
        else:
            logger.info(
                "KeyManager instance was not set, no reset action performed."
            )
