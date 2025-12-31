"""
WebUI 应用 - 基于 aiohttp 的 Web 服务器
"""

import asyncio
from aiohttp import web
from typing import Optional
from src.logger import logger
from src.config import global_config
from .routes import setup_routes

_runner: Optional[web.AppRunner] = None
_site: Optional[web.TCPSite] = None


def get_webui_config():
    """获取 WebUI 配置"""
    if global_config.web_ui:
        return global_config.web_ui.host, global_config.web_ui.port
    return "0.0.0.0", 8096  # 默认值


def is_webui_enabled() -> bool:
    """检查 WebUI 是否启用"""
    if global_config.web_ui:
        return global_config.web_ui.enable
    return True  # 默认启用


async def start_webui():
    """启动 WebUI 服务"""
    global _runner, _site

    # 检查是否启用 WebUI
    if not is_webui_enabled():
        logger.info("WebUI 已禁用，跳过启动")
        return

    host, port = get_webui_config()

    app = web.Application()
    setup_routes(app)

    _runner = web.AppRunner(app)
    await _runner.setup()
    _site = web.TCPSite(_runner, host, port)
    await _site.start()

    logger.info(f"WebUI 已启动，访问地址: http://{host}:{port}")


async def stop_webui():
    """停止 WebUI 服务"""
    global _runner
    if _runner:
        await _runner.cleanup()
        logger.info("WebUI 已停止")


# 兼容 router 接口
webui_router = None

