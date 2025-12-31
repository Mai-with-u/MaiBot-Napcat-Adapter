"""
WebUI 路由定义
"""

import json
import hmac
import time
from collections import defaultdict
from aiohttp import web
from src.config import global_config
from src.logger import logger
from .config_manager import (
    get_chat_config,
    update_group_list_type,
    update_group_list,
    update_private_list_type,
    update_private_list,
    save_config_to_file,
)
from .static import get_index_html

# 登录失败记录：IP -> (失败次数, 最后失败时间)
_login_failures: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
# 最大允许失败次数
MAX_LOGIN_FAILURES = 5
# 锁定时间（秒）
LOCKOUT_TIME = 300  # 5分钟


def get_client_ip(request: web.Request) -> str:
    """获取客户端 IP 地址"""
    # 优先从 X-Forwarded-For 获取（如果在反向代理后面）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # 否则从直接连接获取
    peername = request.transport.get_extra_info("peername")
    if peername:
        return peername[0]
    return "unknown"


def is_ip_locked(ip: str) -> bool:
    """检查 IP 是否被锁定"""
    failures, last_failure_time = _login_failures[ip]
    if failures >= MAX_LOGIN_FAILURES:
        # 检查是否还在锁定期内
        if time.time() - last_failure_time < LOCKOUT_TIME:
            return True
        else:
            # 锁定期已过，重置计数
            _login_failures[ip] = (0, 0.0)
    return False


def record_login_failure(ip: str):
    """记录登录失败"""
    failures, _ = _login_failures[ip]
    _login_failures[ip] = (failures + 1, time.time())


def reset_login_failures(ip: str):
    """重置登录失败计数"""
    _login_failures[ip] = (0, 0.0)


def get_configured_token() -> str:
    """获取配置的 token"""
    if global_config.web_ui:
        return global_config.web_ui.token or ""
    return ""


def secure_compare(a: str, b: str) -> bool:
    """安全的字符串比较，防止时序攻击"""
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def verify_token(request: web.Request) -> bool:
    """验证请求中的 token"""
    configured_token = get_configured_token()
    if not configured_token:
        return True  # 未配置 token，无需验证

    # 从 Authorization header 获取 token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        request_token = auth_header[7:]
        return secure_compare(request_token, configured_token)
    return False


async def index_handler(request: web.Request) -> web.Response:
    """返回主页面"""
    return web.Response(text=get_index_html(), content_type="text/html")


async def verify_token_handler(request: web.Request) -> web.Response:
    """验证 token 接口"""
    configured_token = get_configured_token()
    client_ip = get_client_ip(request)

    # 如果未配置 token，直接返回成功
    if not configured_token:
        return web.json_response({"success": True, "message": "无需验证", "required": False})

    # 检查 IP 是否被锁定
    if is_ip_locked(client_ip):
        remaining_time = int(LOCKOUT_TIME - (time.time() - _login_failures[client_ip][1]))
        logger.warning(f"[WebUI] IP {client_ip} 登录尝试被拒绝（已锁定，剩余 {remaining_time} 秒）")
        return web.json_response({
            "success": False,
            "message": f"登录尝试次数过多，请在 {remaining_time} 秒后重试",
            "required": True
        }, status=429)

    try:
        data = await request.json()
        input_token = data.get("token", "")

        if secure_compare(input_token, configured_token):
            reset_login_failures(client_ip)
            logger.info(f"[WebUI] Token 验证成功 (IP: {client_ip})")
            return web.json_response({"success": True, "message": "验证成功", "required": True})
        else:
            record_login_failure(client_ip)
            failures, _ = _login_failures[client_ip]
            remaining_attempts = MAX_LOGIN_FAILURES - failures
            logger.warning(f"[WebUI] Token 验证失败 (IP: {client_ip}, 剩余尝试次数: {remaining_attempts})")
            return web.json_response({"success": False, "message": "Token 错误", "required": True}, status=401)
    except json.JSONDecodeError:
        return web.json_response({"success": False, "message": "无效的请求数据"}, status=400)


async def check_auth_handler(request: web.Request) -> web.Response:
    """检查是否需要验证以及当前 token 是否有效"""
    configured_token = get_configured_token()

    if not configured_token:
        return web.json_response({"required": False, "valid": True})

    if verify_token(request):
        return web.json_response({"required": True, "valid": True})
    else:
        return web.json_response({"required": True, "valid": False})


async def get_config_handler(request: web.Request) -> web.Response:
    """获取当前配置"""
    if not verify_token(request):
        return web.json_response({"success": False, "error": "未授权"}, status=401)

    config = get_chat_config()
    return web.json_response(config)


async def update_config_handler(request: web.Request) -> web.Response:
    """更新配置"""
    if not verify_token(request):
        return web.json_response({"success": False, "error": "未授权"}, status=401)

    try:
        data = await request.json()

        field = data.get("field")
        value = data.get("value")

        if field is None or value is None:
            return web.json_response({"success": False, "error": "缺少 field 或 value 参数"}, status=400)

        success = False
        message = ""

        if field == "group_list_type":
            if value not in ["whitelist", "blacklist"]:
                return web.json_response({"success": False, "error": "group_list_type 必须是 whitelist 或 blacklist"}, status=400)
            success = update_group_list_type(value)
            message = f"群聊列表类型已更新为: {value}"

        elif field == "group_list":
            if not isinstance(value, list):
                return web.json_response({"success": False, "error": "group_list 必须是数组"}, status=400)
            # 确保所有元素都是整数
            try:
                value = [int(v) for v in value]
            except (ValueError, TypeError):
                return web.json_response({"success": False, "error": "group_list 中的元素必须是数字"}, status=400)
            success = update_group_list(value)
            message = f"群聊列表已更新，共 {len(value)} 个群组"

        elif field == "private_list_type":
            if value not in ["whitelist", "blacklist"]:
                return web.json_response({"success": False, "error": "private_list_type 必须是 whitelist 或 blacklist"}, status=400)
            success = update_private_list_type(value)
            message = f"私聊列表类型已更新为: {value}"

        elif field == "private_list":
            if not isinstance(value, list):
                return web.json_response({"success": False, "error": "private_list 必须是数组"}, status=400)
            # 确保所有元素都是整数
            try:
                value = [int(v) for v in value]
            except (ValueError, TypeError):
                return web.json_response({"success": False, "error": "private_list 中的元素必须是数字"}, status=400)
            success = update_private_list(value)
            message = f"私聊列表已更新，共 {len(value)} 个用户"

        else:
            return web.json_response({"success": False, "error": f"未知的字段: {field}"}, status=400)

        if success:
            # 保存配置到文件
            save_config_to_file()
            logger.info(f"[WebUI] {message}")
            return web.json_response({"success": True, "message": message, "config": get_chat_config()})
        else:
            return web.json_response({"success": False, "error": "更新配置失败"}, status=500)

    except json.JSONDecodeError:
        return web.json_response({"success": False, "error": "无效的 JSON 数据"}, status=400)
    except Exception as e:
        logger.error(f"[WebUI] 更新配置时发生错误: {e}")
        return web.json_response({"success": False, "error": str(e)}, status=500)


def setup_routes(app: web.Application):
    """设置路由"""
    app.router.add_get("/", index_handler)
    app.router.add_get("/api/auth/check", check_auth_handler)
    app.router.add_post("/api/auth/verify", verify_token_handler)
    app.router.add_get("/api/config", get_config_handler)
    app.router.add_post("/api/config", update_config_handler)
