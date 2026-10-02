"""验证群来源临时消息的私聊过滤、归属和出站路由。"""

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

import sys
import unittest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT.parent))
package = PLUGIN_ROOT.name
NapCatInboundCodec = import_module(f"{package}.codecs.inbound.message_codec").NapCatInboundCodec
NapCatOutboundCodec = import_module(f"{package}.codecs.outbound.message_codec").NapCatOutboundCodec
NapCatEventRouter = import_module(f"{package}.runtime.router").NapCatEventRouter
NapCatChatFilter = import_module(f"{package}.filters").NapCatChatFilter
NapCatChatConfig = import_module(f"{package}.config").NapCatChatConfig


class PrivateRoutingTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.payload = {
            "post_type": "message",
            "message_type": "private",
            "sub_type": "group",
            "group_id": 493175955,
            "temp_source": 0,
            "user_id": 1874317728,
            "self_id": 1731251906,
            "message_id": 978705044,
            "sender": {"nickname": "临时会话"},
            "message": [{"type": "text", "data": {"text": "介绍一下自己"}}],
        }
        self.codec = NapCatInboundCodec(Mock(), Mock())

    async def test_message_classification_and_reply_target(self) -> None:
        for message_type, has_source_group in [("private", True), ("private", False), ("group", True)]:
            with self.subTest(message_type=message_type, has_source_group=has_source_group):
                payload = dict(self.payload, message_type=message_type)
                if not has_source_group:
                    payload.pop("group_id")
                    payload["sub_type"] = "friend"
                message = await self.codec.build_message_dict(payload, "1731251906", "1874317728", payload["sender"])
                info = message["message_info"]
                extra = info["additional_config"]
                action, params = NapCatOutboundCodec().build_outbound_action(message, {})
                if message_type == "private":
                    self.assertNotIn("group_info", info)
                    self.assertNotIn("platform_io_target_group_id", extra)
                    self.assertEqual(action, "send_private_msg")
                    self.assertEqual(params["user_id"], "1874317728")
                    self.assertNotIn("group_id", params)
                    if has_source_group:
                        self.assertEqual(extra["napcat_temp_source_group_id"], "493175955")
                else:
                    self.assertEqual(info["group_info"]["group_id"], "493175955")
                    self.assertEqual(action, "send_group_msg")
                    self.assertEqual(params["group_id"], "493175955")

    async def test_temporary_message_uses_private_allowlist(self) -> None:
        for allow_private in [False, True]:
            with self.subTest(allow_private=allow_private):
                # 两个名单给出相反结果，防止误用来源群白名单放行临时私聊。
                chat = NapCatChatConfig(
                    enable_chat_list_filter=True,
                    group_list_type="whitelist",
                    group_list=[] if allow_private else ["493175955"],
                    private_list_type="whitelist",
                    private_list=["1874317728"] if allow_private else [],
                )
                settings = SimpleNamespace(
                    chat=chat,
                    filters=SimpleNamespace(ignore_self_message=True),
                    napcat_server=SimpleNamespace(connection_id="test"),
                )
                gateway = SimpleNamespace(route_message=AsyncMock(return_value=True))
                guard = SimpleNamespace(should_reject=AsyncMock(return_value=False))
                runtime = SimpleNamespace(
                    runtime_state=SimpleNamespace(report_connected=AsyncMock()),
                    chat_filter=NapCatChatFilter(Mock()),
                    official_bot_guard=guard,
                    inbound_codec=self.codec,
                    regex_filter=SimpleNamespace(is_message_allowed=Mock(return_value=True)),
                )
                router = NapCatEventRouter(gateway, Mock(), "test", lambda settings=settings: settings)
                router.bind_runtime(runtime)
                await router.handle_inbound_message(self.payload)
                if allow_private:
                    gateway.route_message.assert_awaited_once()
                    self.assertEqual(guard.should_reject.call_args.kwargs["group_id"], "")
                    message = gateway.route_message.call_args.kwargs["message"]
                    self.assertNotIn("group_info", message["message_info"])
                else:
                    gateway.route_message.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
