"""
调度任务模块

提供后台定时任务，包括：
- 检查失败的 API 密钥
- 自动删除旧的错误日志
- 自动删除旧的请求日志
- 自动检测代理可用性
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config.config import settings
from app.domain.openai_models import ChatRequest
from app.log.logger import Logger
from app.service.chat.openai_chat_service import OpenAIChatService
from app.service.error_log.error_log_service import delete_old_error_logs
from app.service.key.key_manager import get_key_manager_instance
from app.service.request_log.request_log_service import delete_old_request_logs_task
from app.utils.helpers import redact_key_for_logging

logger = Logger.setup_logger("scheduler")


async def check_failed_keys():
    """
    定时检查失败次数大于0的API密钥，并尝试验证它们。
    如果验证成功，重置失败计数；如果失败，增加失败计数。
    """
    logger.info("Starting scheduled check for failed API keys...")
    try:
        key_manager = await get_key_manager_instance()
        # 确保 KeyManager 已经初始化
        if not key_manager or not hasattr(key_manager, "key_failure_counts"):
            logger.warning(
                "KeyManager instance not available or not initialized. Skipping check."
            )
            return

        # 创建 OpenAIChatService 实例用于验证
        chat_service = OpenAIChatService(settings.BASE_URL, key_manager)

        # 获取需要检查的 key 列表 (失败次数 > 0)
        keys_to_check = []
        async with key_manager.failure_count_lock:
            failure_counts_copy = key_manager.key_failure_counts.copy()
            keys_to_check = [
                key for key, count in failure_counts_copy.items() if count > 0
            ]

        if not keys_to_check:
            logger.info("No keys with failure count > 0 found. Skipping verification.")
            return

        logger.info(
            f"Found {len(keys_to_check)} keys with failure count > 0 to verify."
        )

        for key in keys_to_check:
            log_key = redact_key_for_logging(key)
            logger.info(f"Verifying key: {log_key}...")
            try:
                # 构造测试请求（OpenAI 格式）
                chat_request = ChatRequest(
                    model=settings.TEST_MODEL,
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=10,
                    stream=False,
                )
                await chat_service.create_chat_completion(chat_request, key)
                logger.info(
                    f"Key {log_key} verification successful. Resetting failure count."
                )
                await key_manager.reset_key_failure_count(key)
            except Exception as e:
                logger.warning(
                    f"Key {log_key} verification failed: {str(e)}. Incrementing failure count."
                )
                async with key_manager.failure_count_lock:
                    if (
                        key in key_manager.key_failure_counts
                        and key_manager.key_failure_counts[key]
                        < key_manager.MAX_FAILURES
                    ):
                        key_manager.key_failure_counts[key] += 1
                        logger.info(
                            f"Failure count for key {log_key} incremented to {key_manager.key_failure_counts[key]}."
                        )
                    elif key in key_manager.key_failure_counts:
                        logger.warning(
                            f"Key {log_key} reached MAX_FAILURES ({key_manager.MAX_FAILURES}). Not incrementing further."
                        )

    except Exception as e:
        logger.error(
            f"An error occurred during the scheduled key check: {str(e)}", exc_info=True
        )


async def check_proxies():
    """
    定时检测所有代理的可用性。
    如果代理检测失败，增加失败计数；如果成功，重置失败计数。
    超过最大失败次数的代理将被暂时禁用，并解除与 API Key 的绑定。
    """
    if not settings.PROXY_AUTO_CHECK_ENABLED:
        logger.debug("Proxy auto check is disabled, skipping...")
        return

    if not settings.PROXIES:
        logger.debug("No proxies configured, skipping proxy check...")
        return

    logger.info("Starting scheduled proxy check...")

    try:
        from app.service.proxy.proxy_manager import get_proxy_manager
        from app.service.proxy.proxy_check_service import get_proxy_check_service

        proxy_manager = await get_proxy_manager()
        proxy_check_service = get_proxy_check_service()

        # 更新检测服务的配置
        proxy_check_service.CHECK_URL = settings.PROXY_CHECK_URL
        proxy_check_service.TIMEOUT_SECONDS = settings.PROXY_CHECK_TIMEOUT

        # 获取所有代理
        all_proxies = settings.PROXIES.copy()

        if not all_proxies:
            logger.info("No proxies to check.")
            return

        logger.info(f"Checking {len(all_proxies)} proxies...")

        # 批量检测代理
        results = await proxy_check_service.check_multiple_proxies(
            all_proxies,
            use_cache=False,  # 定时任务不使用缓存
            max_concurrent=5
        )

        # 处理检测结果
        available_count = 0
        disabled_count = 0

        for result in results:
            proxy = result.proxy
            await proxy_manager.update_last_check_time(proxy)

            if result.is_available:
                # 代理可用，重置失败计数
                await proxy_manager.reset_proxy(proxy)
                available_count += 1
                logger.debug(f"Proxy {proxy} is available (response time: {result.response_time}s)")
            else:
                # 代理不可用，记录失败
                was_disabled = await proxy_manager.record_proxy_failure(proxy)
                if was_disabled:
                    disabled_count += 1
                logger.warning(f"Proxy {proxy} check failed: {result.error_message}")

        # 获取最终状态
        status = await proxy_manager.get_proxy_status()

        logger.info(
            f"Proxy check completed: {available_count}/{len(all_proxies)} available, "
            f"{status['disabled']} disabled, {disabled_count} newly disabled"
        )

    except Exception as e:
        logger.error(
            f"An error occurred during the scheduled proxy check: {str(e)}", exc_info=True
        )


def setup_scheduler():
    """设置并启动 APScheduler"""
    scheduler = AsyncIOScheduler(timezone=str(settings.TIMEZONE))

    # 添加检查失败密钥的定时任务
    if settings.CHECK_INTERVAL_HOURS != 0:
        scheduler.add_job(
            check_failed_keys,
            "interval",
            hours=settings.CHECK_INTERVAL_HOURS,
            id="check_failed_keys_job",
            name="Check Failed API Keys",
        )
        logger.info(
            f"Key check job scheduled to run every {settings.CHECK_INTERVAL_HOURS} hour(s)."
        )

    # 添加自动删除错误日志的定时任务，每天凌晨0点执行
    scheduler.add_job(
        delete_old_error_logs,
        "cron",
        hour=0,
        minute=0,
        id="delete_old_error_logs_job",
        name="Delete Old Error Logs",
    )
    logger.info("Auto-delete error logs job scheduled to run daily at 00:00.")

    # 添加自动删除请求日志的定时任务，每天凌晨0点执行
    scheduler.add_job(
        delete_old_request_logs_task,
        "cron",
        hour=0,
        minute=0,
        id="delete_old_request_logs_job",
        name="Delete Old Request Logs",
    )
    logger.info(
        f"Auto-delete request logs job scheduled to run daily at 00:00, if enabled."
    )

    # 添加代理自动检测的定时任务
    if settings.PROXY_AUTO_CHECK_ENABLED and settings.PROXY_CHECK_INTERVAL_HOURS > 0:
        # 将小时转换为分钟，支持小数
        interval_minutes = int(settings.PROXY_CHECK_INTERVAL_HOURS * 60)
        if interval_minutes < 1:
            interval_minutes = 1  # 最小间隔1分钟

        scheduler.add_job(
            check_proxies,
            "interval",
            minutes=interval_minutes,
            id="check_proxies_job",
            name="Check Proxies Availability",
        )
        logger.info(
            f"Proxy check job scheduled to run every {settings.PROXY_CHECK_INTERVAL_HOURS} hour(s) "
            f"({interval_minutes} minutes)."
        )

    scheduler.start()
    logger.info("Scheduler started with all jobs.")
    return scheduler


# 全局 scheduler 实例
scheduler_instance = None


def start_scheduler():
    """启动调度器"""
    global scheduler_instance
    if scheduler_instance is None or not scheduler_instance.running:
        logger.info("Starting scheduler...")
        scheduler_instance = setup_scheduler()
    logger.info("Scheduler is already running.")


def stop_scheduler():
    """停止调度器"""
    global scheduler_instance
    if scheduler_instance and scheduler_instance.running:
        scheduler_instance.shutdown()
        logger.info("Scheduler stopped.")
