from typing import Dict
import json
from src.logger import logger
from maim_message import MessageBase, Router


# 消息大小限制 (字节)
# WebSocket 服务端限制为 100MB，这里设置 95MB 留一点余量
MAX_MESSAGE_SIZE_BYTES = 95 * 1024 * 1024  # 95MB
MAX_MESSAGE_SIZE_KB = MAX_MESSAGE_SIZE_BYTES / 1024
MAX_MESSAGE_SIZE_MB = MAX_MESSAGE_SIZE_KB / 1024


class MessageSending:
    """
    负责把消息发送到麦麦
    """

    maibot_router: Router = None

    def __init__(self):
        pass

    async def message_send(self, message_base: MessageBase) -> bool:
        """
        发送消息
        Parameters:
            message_base: MessageBase: 消息基类，包含发送目标和消息内容等信息
        """
        try:
            # 计算消息大小用于调试
            msg_dict = message_base.to_dict()
            msg_json = json.dumps(msg_dict, ensure_ascii=False)
            msg_size_bytes = len(msg_json.encode('utf-8'))
            msg_size_kb = msg_size_bytes / 1024
            msg_size_mb = msg_size_kb / 1024
            
            logger.debug(f"发送消息大小: {msg_size_kb:.2f} KB")
            
            # 检查消息是否超过大小限制
            if msg_size_bytes > MAX_MESSAGE_SIZE_BYTES:
                logger.error(
                    f"消息大小 ({msg_size_mb:.2f} MB) 超过限制 ({MAX_MESSAGE_SIZE_MB:.0f} MB)，"
                    f"消息已被丢弃以避免连接断开"
                )
                logger.warning(
                    f"被丢弃的消息来源: platform={message_base.message_info.platform}, "
                    f"group_id={message_base.message_info.group_info.group_id if message_base.message_info.group_info else 'N/A'}, "
                    f"user_id={message_base.message_info.user_info.user_id if message_base.message_info.user_info else 'N/A'}"
                )
                return False
            
            if msg_size_kb > 1024:  # 超过 1MB 时警告
                logger.warning(f"发送的消息较大 ({msg_size_mb:.2f} MB)，可能导致传输延迟")
            
            send_status = await self.maibot_router.send_message(message_base)
            if not send_status:
                raise RuntimeError("可能是路由未正确配置或连接异常")
            logger.debug("消息发送成功")
            return send_status
        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}")
            logger.error("请检查与MaiBot之间的连接")
            return False
        
    async def send_custom_message(self, custom_message: Dict, platform: str, message_type: str) -> bool:
        """
        发送自定义消息
        """
        try:
            await self.maibot_router.send_custom_message(platform=platform, message_type_name=message_type, message=custom_message)
            return True
        except Exception as e:
            logger.error(f"发送自定义消息失败: {str(e)}")
            logger.error("请检查与MaiBot之间的连接")
            return False


message_send_instance = MessageSending()
