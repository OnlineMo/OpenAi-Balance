"""
配置热重载服务模块

监控 .env 文件变化并自动重载配置。
"""

import asyncio
import os
from pathlib import Path
from typing import Callable, Optional

from app.log.logger import get_application_logger

logger = get_application_logger()


class ConfigWatcher:
    """
    配置文件监控器

    监控 .env 文件的变化，当文件被修改时触发配置重载。

    Attributes:
        env_path: .env 文件路径
        check_interval: 检查间隔（秒）
        _last_mtime: 上次修改时间
        _running: 是否正在运行
        _task: 监控任务
        _reload_callback: 重载回调函数
    """

    def __init__(
        self,
        env_path: Optional[str] = None,
        check_interval: float = 5.0,
    ):
        """
        初始化配置监控器

        Args:
            env_path: .env 文件路径，默认为项目根目录下的 .env
            check_interval: 检查间隔（秒），默认 5 秒
        """
        if env_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            env_path = str(project_root / ".env")

        self.env_path = env_path
        self.check_interval = check_interval
        self._last_mtime: Optional[float] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reload_callback: Optional[Callable] = None

    def _get_file_mtime(self) -> Optional[float]:
        """获取文件修改时间"""
        try:
            if os.path.exists(self.env_path):
                return os.path.getmtime(self.env_path)
        except OSError as e:
            logger.warning(f"Failed to get mtime for {self.env_path}: {e}")
        return None

    async def _watch_loop(self):
        """监控循环"""
        logger.info(f"Config watcher started, monitoring: {self.env_path}")
        self._last_mtime = self._get_file_mtime()

        while self._running:
            try:
                await asyncio.sleep(self.check_interval)

                current_mtime = self._get_file_mtime()
                if current_mtime is None:
                    continue

                if self._last_mtime is not None and current_mtime > self._last_mtime:
                    logger.info(f".env file changed, triggering reload...")
                    self._last_mtime = current_mtime
                    await self._trigger_reload()
                elif self._last_mtime is None:
                    self._last_mtime = current_mtime

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in config watcher loop: {e}")

        logger.info("Config watcher stopped")

    async def _trigger_reload(self):
        """触发配置重载"""
        try:
            # 重新加载 .env 文件
            from dotenv import load_dotenv
            load_dotenv(self.env_path, override=True)
            logger.info(".env file reloaded")

            # 重新加载 settings
            from app.config.config import settings, reload_settings
            reload_settings()
            logger.info("Settings reloaded from environment")

            # 同步到数据库
            from app.config.config import sync_initial_settings
            await sync_initial_settings()
            logger.info("Settings synced to database")

            # 重新加载 KeyManager
            from app.service.key.key_manager import reset_key_manager, get_key_manager_instance
            await reset_key_manager()
            await get_key_manager_instance(settings.API_KEYS)
            logger.info("KeyManager reloaded")

            # 重新加载 ProviderManager
            from app.service.provider.provider_manager import get_provider_manager
            provider_manager = await get_provider_manager()
            await provider_manager.reload_config()
            logger.info("ProviderManager reloaded")

            # 调用自定义回调
            if self._reload_callback:
                if asyncio.iscoroutinefunction(self._reload_callback):
                    await self._reload_callback()
                else:
                    self._reload_callback()

            logger.info("Configuration hot reload completed successfully")

        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}", exc_info=True)

    def set_reload_callback(self, callback: Callable):
        """
        设置重载回调函数

        Args:
            callback: 配置重载后调用的函数
        """
        self._reload_callback = callback

    async def start(self):
        """启动监控"""
        if self._running:
            logger.warning("Config watcher is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self):
        """停止监控"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


# 单例实例
_config_watcher: Optional[ConfigWatcher] = None


def get_config_watcher() -> ConfigWatcher:
    """获取配置监控器单例"""
    global _config_watcher
    if _config_watcher is None:
        _config_watcher = ConfigWatcher()
    return _config_watcher


async def start_config_watcher():
    """启动配置监控器"""
    watcher = get_config_watcher()
    await watcher.start()


async def stop_config_watcher():
    """停止配置监控器"""
    watcher = get_config_watcher()
    await watcher.stop()
