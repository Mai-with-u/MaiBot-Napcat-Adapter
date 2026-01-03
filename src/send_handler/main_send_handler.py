from typing import Any, Dict, Optional
import time
from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
)
from src.logger import logger
from .send_command_handler import SendCommandHandleClass
from .send_message_handler import SendMessageHandleClass
from .nc_sending import nc_message_sender
from src.recv_handler.message_sending import message_send_instance


class SendHandler:
    def __init__(self):
        pass

    async def handle_message(self, raw_message_base_dict: dict) -> None:
        raw_message_base: MessageBase = MessageBase.from_dict(raw_message_base_dict)
        message_segment: Seg = raw_message_base.message_segment
        logger.info("接收到来自MaiBot的消息，处理中")
        if message_segment.type == "command":
            return await self.send_command(raw_message_base)
        else:
            return await self.send_normal_message(raw_message_base)

    async def send_command(self, raw_message_base: MessageBase) -> None:
        """
        处理命令类
        """
        logger.info("处理命令中")
        message_info: BaseMessageInfo = raw_message_base.message_info
        message_segment: Seg = raw_message_base.message_segment
        group_info: GroupInfo = message_info.group_info
        seg_data: Dict[str, Any] = message_segment.data
        command_name = seg_data.get('name', 'UNKNOWN')
        
        try:
            command, args_dict = SendCommandHandleClass.handle_command(seg_data, group_info)
        except Exception as e:
            logger.error(f"处理命令时出错: {str(e)}")
            # 发送错误响应给麦麦
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=False,
                error=str(e)
            )
            return

        if not command or not args_dict:
            logger.error("命令或参数缺失")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=False,
                error="命令或参数缺失"
            )
            return None

        response = await nc_message_sender.send_message_to_napcat(command, args_dict)
        
        # 根据响应状态发送结果给麦麦
        if response.get("status") == "ok":
            logger.info(f"命令 {command_name} 执行成功")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=True,
                data=response.get("data")
            )
        else:
            logger.warning(f"命令 {command_name} 执行失败，napcat返回：{str(response)}")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=False,
                error=str(response),
                data=response.get("data")  # 有些错误响应也可能包含部分数据
            )

    async def _send_command_response(
        self, 
        platform: str, 
        command_name: str, 
        success: bool, 
        data: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> None:
        """发送命令响应回麦麦
        
        Args:
            platform: 平台标识
            command_name: 命令名称
            success: 是否执行成功
            data: 返回数据（成功时）
            error: 错误信息（失败时）
        """
        response_data = {
            "command_name": command_name,
            "success": success,
            "timestamp": time.time()
        }
        
        if data is not None:
            response_data["data"] = data
        if error:
            response_data["error"] = error
        
        try:
            await message_send_instance.send_custom_message(
                custom_message=response_data,
                platform=platform,
                message_type="command_response"
            )
            logger.debug(f"已发送命令响应: {command_name}, success={success}")
        except Exception as e:
            logger.error(f"发送命令响应失败: {e}")

    async def send_normal_message(self, raw_message_base: MessageBase) -> None:
        """
        处理普通消息发送
        """
        logger.info("处理普通信息中")
        message_info: BaseMessageInfo = raw_message_base.message_info
        message_segment: Seg = raw_message_base.message_segment
        group_info: GroupInfo = message_info.group_info
        user_info: UserInfo = message_info.user_info
        target_id: int = None
        action: str = None
        id_name: str = None
        processed_message: list = []
        try:
            processed_message = SendMessageHandleClass.process_seg_recursive(message_segment)
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}")
            return

        if not processed_message:
            logger.critical("现在暂时不支持解析此回复！")
            return None

        if group_info and user_info:
            logger.debug("发送群聊消息")
            target_id = group_info.group_id
            action = "send_group_msg"
            id_name = "group_id"
        elif user_info:
            logger.debug("发送私聊消息")
            target_id = user_info.user_id
            action = "send_private_msg"
            id_name = "user_id"
        else:
            logger.error("无法识别的消息类型")
            return
        logger.info("尝试发送到napcat")
        response = await nc_message_sender.send_message_to_napcat(
            action,
            {
                id_name: target_id,
                "message": processed_message,
            },
        )
        if response.get("status") == "ok":
            logger.info("消息发送成功")
            qq_message_id = response.get("data", {}).get("message_id")
            await nc_message_sender.message_sent_back(raw_message_base, qq_message_id)
        else:
            logger.warning(f"消息发送失败，napcat返回：{str(response)}")

send_handler = SendHandler()