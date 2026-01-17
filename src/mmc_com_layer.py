from maim_message import Router, RouteConfig, TargetConfig, MessageBase
from .config import global_config
from .logger import logger, custom_logger
from .send_handler.main_send_handler import send_handler
from .recv_handler.message_sending import message_send_instance
from maim_message.client import create_client_config, WebSocketClient
from maim_message.message import APIMessageBase
from typing import Dict, Any
import importlib.metadata

# 检查 maim_message 版本是否支持 MessageConverter (>= 0.6.2)
try:
    maim_message_version = importlib.metadata.version("maim_message")
    version_int = [int(x) for x in maim_message_version.split(".")]
    HAS_MESSAGE_CONVERTER = version_int >= [0, 6, 2]
except (importlib.metadata.PackageNotFoundError, ValueError):
    HAS_MESSAGE_CONVERTER = False

# router = Router(route_config, custom_logger)
# router will be initialized in mmc_start_com
router = None


class APIServerWrapper:
    """
    Wrapper to make WebSocketClient compatible with legacy Router interface
    """
    def __init__(self, client: WebSocketClient):
        self.client = client
        self.platform = global_config.maibot_server.platform_name

    def register_class_handler(self, handler):
        # In API Server mode, we register the on_message callback in config, 
        # but here we might need to bridge it if the handler structure is different.
        # However, WebSocketClient config handles on_message. 
        # The legacy Router.register_class_handler registers a handler for received messages.
        # We need to adapt the callback style.
        pass

    async def send_message(self, message: MessageBase) -> bool:
        # 使用 MessageConverter 转换 Legacy MessageBase 到 APIMessageBase
        # 接收场景：Adapter 收到来自 Napcat 的消息，发送给 MaiMBot
        # group_info/user_info 是消息发送者信息，放入 sender_info
        from maim_message import MessageConverter
        
        api_message = MessageConverter.to_api_receive(
            message=message,
            api_key=global_config.maibot_server.api_key,
            platform=message.message_info.platform or self.platform,
        )
        return await self.client.send_message(api_message)

    async def send_custom_message(self, platform: str, message_type_name: str, message: Dict) -> bool:
        return await self.client.send_custom_message(message_type_name, message)

    async def run(self):
        await self.client.start()
        await self.client.connect()

    async def stop(self):
        await self.client.stop()

# Global variable to hold the communication object (Router or Wrapper)
router = None

async def _legacy_message_handler_adapter(message: APIMessageBase, metadata: dict):
    # Adapter to call the legacy handler with dict as expected by main_send_handler
    # send_handler.handle_message expects a dict.
    # We need to convert APIMessageBase back to dict legacy format if possible.
    # Or check what handle_message expects.
    # main_send_handler.py: handle_message takes raw_message_base_dict: dict
    # and does MessageBase.from_dict(raw_message_base_dict).
    
    # So we need to serialize APIMessageBase to a dict that looks like legacy MessageBase dict.
    # This might be tricky if structures diverged.
    # Let's try `to_dict()` if available, otherwise construct it.
    
    # Inspecting APIMessageBase structure from docs:
    # APIMessageBase has message_info, message_segment, message_dim.
    # Legacy MessageBase has message_info, message_segment.
    
    # We can try to construct the dict.
    data = {
        "message_info": {
            "id": message.message_info.message_id,
            "timestamp": message.message_info.time,
            "group_info": {}, # Fill if available
            "user_info": {}, # Fill if available
        },
        "message_segment": {
            "type": message.message_segment.type,
            "data": message.message_segment.data
        }
    }
    # Note: This is an approximation. Ideally we should check strict compatibility.
    # However, for the adapter -> bot direction (sending to napcat), 
    # the bot sends messages to adapter? No, Adapter sends to Bot?
    # mmc_com_layer seems to be for Adapter talking to MaiBot Core.
    # recv_handler/message_sending.py uses this router to send TO MaiBot.
    # The `register_class_handler` in `mmc_start_com` suggests MaiBot sends messages TO Adapter?
    # Wait, `send_handler.handle_message` seems to be handling messages RECEIVED FROM MaiBot.
    # So `router` is bidirectional.
    
    # If explicit to_dict is needed:
    await send_handler.handle_message(data)

async def mmc_start_com():
    global router
    config = global_config.maibot_server

    if config.enable_api_server and HAS_MESSAGE_CONVERTER:
        logger.info("使用 API-Server 模式连接 MaiBot")

        # Create legacy adapter handler
        # We need to define the on_message callback here to bridge to send_handler
        async def on_message_bridge(message: APIMessageBase, metadata: Dict[str, Any]):
            # 使用 MessageConverter 转换 APIMessageBase 到 Legacy MessageBase
            # 发送场景：收到来自 MaiMBot 的回复消息，需要发送给 Napcat
            # receiver_info 包含消息接收者信息，需要提取到 group_info/user_info
            try:
                from maim_message import MessageConverter

                legacy_message = MessageConverter.from_api_send(message)
                msg_dict = legacy_message.to_dict()

                await send_handler.handle_message(msg_dict)

            except Exception as e:
                logger.error(f"消息桥接转换失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

        client_config = create_client_config(
            url=config.base_url,
            api_key=config.api_key,
            platform=config.platform_name,
            on_message=on_message_bridge,
            custom_logger=custom_logger  # 传入自定义logger
        )

        client = WebSocketClient(client_config)
        router = APIServerWrapper(client)
        message_send_instance.maibot_router = router
        await router.run()

    else:
        logger.info("使用 Legacy WebSocket 模式连接 MaiBot")
        route_config = RouteConfig(
            route_config={
                config.platform_name: TargetConfig(
                    url=f"ws://{config.host}:{config.port}/ws",
                    token=None,
                )
            }
        )
        router = Router(route_config, custom_logger)
        router.register_class_handler(send_handler.handle_message)
        message_send_instance.maibot_router = router
        await router.run()


async def mmc_stop_com():
    if router:
        await router.stop()
