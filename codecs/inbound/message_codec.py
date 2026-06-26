"""NapCat 入站消息编解码。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import uuid4

import hashlib
import time

from ...qq_emoji_list import QQ_FACE
from ...services import NapCatQueryService
from ...napcat_types import NapCatIncomingSegment, NapCatIncomingSegments, NapCatPayload, NapCatSegment, NapCatSegments
from ..notice.helpers import normalize_optional_string
from .cards import NapCatInboundCardMixin
from .text import NapCatInboundTextMixin


class NapCatInboundCodec(NapCatInboundCardMixin, NapCatInboundTextMixin):
    """NapCat 入站消息编码器。"""

    def __init__(self, logger: Any, query_service: NapCatQueryService) -> None:
        """初始化入站消息编码器。

        Args:
            logger: 插件日志对象。
            query_service: QQ 查询服务。
        """
        self._logger = logger
        self._query_service = query_service

    async def build_message_dict(
        self,
        payload: NapCatPayload,
        self_id: str,
        sender_user_id: str,
        sender: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """构造 Host 侧可接受的 ``MessageDict``。

        Args:
            payload: NapCat 原始消息事件。
            self_id: 当前机器人账号 ID。
            sender_user_id: 发送者用户 ID。
            sender: 发送者信息字典。

        Returns:
            Dict[str, Any]: 规范化后的 ``MessageDict``。
        """
        message_type = str(payload.get("message_type") or "").strip() or "private"
        group_id = str(payload.get("group_id") or "").strip()
        group_name = str(payload.get("group_name") or "").strip() or (f"group_{group_id}" if group_id else "")
        user_nickname = str(sender.get("nickname") or sender.get("card") or sender_user_id).strip() or sender_user_id
        user_cardname = str(sender.get("card") or "").strip() or None

        raw_message, is_at, platform_card_payloads = await self.convert_segments_with_metadata(payload, self_id)
        if not raw_message:
            raw_message = [self._build_text_segment("[unsupported]")]

        plain_text = self.build_plain_text(raw_message)
        timestamp_seconds = payload.get("time")
        if not isinstance(timestamp_seconds, (int, float)):
            timestamp_seconds = time.time()

        additional_config: Dict[str, Any] = {"self_id": self_id, "napcat_message_type": message_type}
        if group_id:
            additional_config["platform_io_target_group_id"] = group_id
        else:
            additional_config["platform_io_target_user_id"] = sender_user_id
        if platform_card_payloads:
            additional_config["platform_card_payloads"] = platform_card_payloads

        message_info: Dict[str, Any] = {
            "user_info": {
                "user_id": sender_user_id,
                "user_nickname": user_nickname,
                "user_cardname": user_cardname,
            },
            "additional_config": additional_config,
        }
        if group_id:
            message_info["group_info"] = {"group_id": group_id, "group_name": group_name}

        message_id = str(payload.get("message_id") or f"napcat-{uuid4().hex}").strip()
        return {
            "message_id": message_id,
            "timestamp": str(float(timestamp_seconds)),
            "platform": "qq",
            "message_info": message_info,
            "raw_message": raw_message,
            "is_mentioned": is_at,
            "is_at": is_at,
            "is_emoji": False,
            "is_picture": False,
            "is_command": plain_text.startswith("/"),
            "is_notify": False,
            "session_id": "",
            "processed_plain_text": plain_text,
            "display_message": plain_text,
        }

    async def convert_segments(self, payload: NapCatPayload, self_id: str) -> Tuple[NapCatSegments, bool]:
        """将 OneBot 消息段转换为 Host 消息段结构。

        Args:
            payload: OneBot 原始消息事件。
            self_id: 当前机器人账号 ID。

        Returns:
            Tuple[NapCatSegments, bool]: 转换后的消息段列表，以及是否 @ 到当前机器人。

        Raises:
            ValueError: 当载荷缺少结构化 ``message`` 段列表时抛出。
        """
        raw_message, is_at, _platform_card_payloads = await self.convert_segments_with_metadata(payload, self_id)
        return raw_message, is_at

    async def convert_segments_with_metadata(
        self,
        payload: NapCatPayload,
        self_id: str,
    ) -> Tuple[NapCatSegments, bool, List[Dict[str, Any]]]:
        """将 OneBot 消息段转换为 Host 消息段结构，并收集平台卡片元数据。

        Args:
            payload: OneBot 原始消息事件。
            self_id: 当前机器人账号 ID。

        Returns:
            Tuple[NapCatSegments, bool, List[Dict[str, Any]]]: 转换后的消息段列表、是否 @ 到当前机器人，
            以及不参与纯文本处理的平台卡片元数据。
        """
        message_payload = self._require_message_segments(payload)
        group_id = str(payload.get("group_id") or "").strip()
        platform_card_payloads: List[Dict[str, Any]] = []
        raw_message, is_at = await self._convert_incoming_segments(
            message_payload,
            self_id,
            group_id,
            platform_card_payloads=platform_card_payloads,
        )
        return raw_message, is_at, platform_card_payloads

    def _require_message_segments(self, payload: NapCatPayload) -> NapCatIncomingSegments:
        """从 NapCat 载荷中提取结构化消息段列表。

        Args:
            payload: NapCat / OneBot 原始载荷。

        Returns:
            NapCatIncomingSegments: 规范化后的结构化消息段列表。

        Raises:
            ValueError: 当 ``message`` 字段不是结构化段列表时抛出。
        """
        message_payload = payload.get("message")
        if not isinstance(message_payload, list):
            raise ValueError("NapCat 入站消息缺少结构化 message 段列表")

        normalized_segments = self._normalize_incoming_segments(message_payload)
        if not normalized_segments:
            raise ValueError("NapCat 入站消息未包含可识别的结构化消息段")
        return normalized_segments

    def _normalize_incoming_segments(self, message_payload: List[Any]) -> NapCatIncomingSegments:
        """规范化 NapCat / OneBot 原始消息段列表。

        Args:
            message_payload: 原始 ``message`` 字段值。

        Returns:
            NapCatIncomingSegments: 过滤并标准化后的消息段列表。
        """
        normalized_segments: NapCatIncomingSegments = []
        for segment in message_payload:
            if not isinstance(segment, Mapping):
                continue
            segment_type = str(segment.get("type") or "").strip()
            segment_data = segment.get("data", {})
            if not segment_type or not isinstance(segment_data, Mapping):
                continue
            normalized_segments.append(
                NapCatIncomingSegment(
                    type=segment_type,
                    data=dict(segment_data),
                )
            )
        return normalized_segments

    async def _convert_incoming_segments(
        self,
        message_payload: NapCatIncomingSegments,
        self_id: str,
        group_id: str,
        *,
        platform_card_payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[NapCatSegments, bool]:
        """将结构化 OneBot 消息段转换为 Host 消息段结构。

        Args:
            message_payload: NapCat / OneBot 结构化消息段列表。
            self_id: 当前机器人账号 ID。
            group_id: 当前消息所在群号；私聊消息为空字符串。

        Returns:
            Tuple[NapCatSegments, bool]: 转换后的消息段列表，以及是否 @ 到当前机器人。
        """
        converted_segments: NapCatSegments = []
        at_target_cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
        is_at = False
        for segment in message_payload:
            segment_type = str(segment.get("type") or "").strip()
            segment_data = segment.get("data", {})
            if not isinstance(segment_data, Mapping):
                segment_data = {}

            if segment_type == "text":
                if text_value := str(segment_data.get("text") or ""):
                    converted_segments.append(self._build_text_segment(text_value))
                continue

            if segment_type == "at":
                if target_user_id := str(segment_data.get("qq") or "").strip():
                    if target_user_id in at_target_cache:
                        target_user_nickname, target_user_cardname = at_target_cache[target_user_id]
                    else:
                        target_user_nickname, target_user_cardname = await self._resolve_at_target_info(
                            group_id=group_id,
                            target_user_id=target_user_id,
                        )
                        at_target_cache[target_user_id] = (target_user_nickname, target_user_cardname)

                    converted_segments.append(
                        {
                            "type": "at",
                            "data": {
                                "target_user_id": target_user_id,
                                "target_user_nickname": target_user_nickname,
                                "target_user_cardname": target_user_cardname,
                            },
                        }
                    )
                    if self_id and target_user_id == self_id:
                        is_at = True
                continue

            if segment_type == "reply":
                if reply_segment := await self._build_reply_segment(segment_data):
                    converted_segments.append(reply_segment)
                continue

            if segment_type == "face":
                converted_segments.append(self._build_face_text_segment(segment_data))
                continue

            if segment_type == "image":
                converted_segments.append(await self._build_image_like_segment(segment_data, is_emoji=False))
                continue

            if segment_type == "record":
                converted_segments.append(await self._build_record_segment(segment_data))
                continue

            if segment_type == "video":
                converted_segments.append(self._build_video_text_segment(segment_data))
                continue

            if segment_type == "file":
                converted_segments.append(self._build_file_text_segment(segment_data))
                continue

            if segment_type == "json":
                converted_segments.extend(
                    await self._build_json_segments(
                        segment_data,
                        platform_card_payloads=platform_card_payloads,
                    )
                )
                continue

            if segment_type == "forward":
                if forward_segment := await self._build_forward_segment(segment_data):
                    converted_segments.append(forward_segment)
                continue

            if segment_type in {"xml", "share"}:
                converted_segments.append(self._build_text_segment(f"[{segment_type}]"))

        return converted_segments, is_at

    async def _resolve_at_target_info(
        self,
        group_id: str,
        target_user_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """解析 ``at`` 目标的展示信息。

        Args:
            group_id: 当前消息所在群号；私聊消息为空字符串。
            target_user_id: 被 ``at`` 的用户号。

        Returns:
            Tuple[Optional[str], Optional[str]]: 依次返回 QQ 昵称和群昵称。
        """
        if not target_user_id or target_user_id == "all":
            return None, None

        target_user_nickname: Optional[str] = None
        target_user_cardname: Optional[str] = None

        if group_id:
            member_info = await self._query_service.get_group_member_info(group_id, target_user_id, no_cache=True)
            if member_info is not None:
                target_user_nickname = normalize_optional_string(member_info.get("nickname"))
                target_user_cardname = normalize_optional_string(member_info.get("card"))

        if target_user_nickname or target_user_cardname:
            return target_user_nickname, target_user_cardname

        stranger_info = await self._query_service.get_stranger_info(target_user_id)
        if stranger_info is None:
            return None, None

        return normalize_optional_string(stranger_info.get("nickname")), target_user_cardname

    @staticmethod
    def _build_text_segment(text: str) -> NapCatSegment:
        """构造一条纯文本 Host 消息段。

        Args:
            text: 文本内容。

        Returns:
            NapCatSegment: Host 侧纯文本消息段。
        """
        return {"type": "text", "data": text}

    async def _build_reply_segment(self, segment_data: Mapping[str, Any]) -> Optional[NapCatSegment]:
        """构造回复消息段。

        Args:
            segment_data: OneBot ``reply`` 段的 ``data`` 字典。

        Returns:
            Optional[NapCatSegment]: 转换后的回复消息段；缺少消息 ID 时返回 ``None``。
        """
        target_message_id = str(segment_data.get("id") or "").strip()
        if not target_message_id:
            return None

        message_detail = await self._query_service.get_message_detail(target_message_id)
        reply_payload: Dict[str, Any] = {"target_message_id": target_message_id}
        if message_detail is not None:
            sender = message_detail.get("sender", {})
            if not isinstance(sender, Mapping):
                sender = {}
            reply_payload["target_message_content"] = await self._build_reply_preview_text(message_detail)
            reply_payload["target_message_sender_id"] = (
                str(message_detail.get("user_id") or sender.get("user_id") or "").strip() or None
            )
            reply_payload["target_message_sender_nickname"] = str(sender.get("nickname") or "").strip() or None
            reply_payload["target_message_sender_cardname"] = str(sender.get("card") or "").strip() or None

        return {"type": "reply", "data": reply_payload}

    async def _build_reply_preview_text(self, message_detail: NapCatPayload) -> Optional[str]:
        """为回复引用构造结构化消息预览文本。

        Args:
            message_detail: ``get_msg`` 返回的消息详情。

        Returns:
            Optional[str]: 基于结构化消息段生成的预览文本；无法生成时返回 ``None``。
        """
        try:
            reply_segments, _ = await self.convert_segments(message_detail, "")
        except ValueError:
            return None

        if not reply_segments:
            return None
        return self.build_plain_text(reply_segments)

    async def _build_image_like_segment(
        self,
        segment_data: Mapping[str, Any],
        is_emoji: bool,
    ) -> NapCatSegment:
        """构造图片或表情消息段。

        Args:
            segment_data: OneBot ``image`` 段的 ``data`` 字典。
            is_emoji: 是否按表情组件处理。

        Returns:
            NapCatSegment: 转换后的图片或表情消息段。
        """
        subtype = self._normalize_numeric_segment_value(segment_data.get("sub_type"))
        actual_is_emoji = is_emoji or (subtype is not None and subtype not in {0, 4, 9})

        image_url = str(segment_data.get("url") or "").strip()
        binary_data = await self._query_service.download_binary(image_url)
        if not binary_data:
            return self._build_text_segment("[emoji]" if actual_is_emoji else "[image]")

        return {
            "type": "emoji" if actual_is_emoji else "image",
            "data": "",
            "hash": hashlib.sha256(binary_data).hexdigest(),
            "binary_data_base64": self._encode_binary(binary_data),
        }

    async def _build_record_segment(self, segment_data: Mapping[str, Any]) -> NapCatSegment:
        """构造语音消息段。

        Args:
            segment_data: OneBot ``record`` 段的 ``data`` 字典。

        Returns:
            NapCatSegment: 转换后的语音或占位文本消息段。
        """
        file_name = str(segment_data.get("file") or "").strip()
        file_id = str(segment_data.get("file_id") or "").strip() or None
        if not file_name:
            return self._build_text_segment("[voice]")

        record_detail = await self._query_service.get_record_detail(file_name=file_name, file_id=file_id)
        if record_detail is None:
            return self._build_text_segment("[voice]")

        record_base64 = str(record_detail.get("base64") or "").strip()
        if not record_base64:
            return self._build_text_segment("[voice]")

        try:
            binary_data = self._decode_binary(record_base64)
        except Exception:
            return self._build_text_segment("[voice]")

        return {
            "type": "voice",
            "data": "",
            "hash": hashlib.sha256(binary_data).hexdigest(),
            "binary_data_base64": self._encode_binary(binary_data),
        }

    def _build_face_text_segment(self, segment_data: Mapping[str, Any]) -> NapCatSegment:
        """构造 QQ 原生表情文本段。

        Args:
            segment_data: OneBot ``face`` 段的 ``data`` 字典。

        Returns:
            NapCatSegment: 转换后的文本消息段。
        """
        face_id = str(segment_data.get("id") or "").strip()
        face_text = QQ_FACE.get(face_id, "[表情]")
        return self._build_text_segment(face_text)

    def _build_video_text_segment(self, segment_data: Mapping[str, Any]) -> NapCatSegment:
        """构造视频消息的可读文本段。

        Args:
            segment_data: OneBot ``video`` 段的 ``data`` 字典。

        Returns:
            NapCatSegment: 转换后的文本消息段。
        """
        file_name = str(segment_data.get("file") or "").strip()
        file_size = str(segment_data.get("file_size") or "").strip()
        parts: List[str] = []
        if file_name:
            parts.append(f"文件: {file_name}")
        if file_size:
            parts.append(f"大小: {file_size}")
        if parts:
            return self._build_text_segment(f"[视频] {'，'.join(parts)}")
        return self._build_text_segment("[视频]")

    def _build_file_text_segment(self, segment_data: Mapping[str, Any]) -> NapCatSegment:
        """构造文件消息的可读文本段。

        Args:
            segment_data: OneBot ``file`` 段的 ``data`` 字典。

        Returns:
            NapCatSegment: 转换后的文本消息段。
        """
        file_name = str(segment_data.get("file") or segment_data.get("name") or "").strip()
        file_size = str(segment_data.get("file_size") or "").strip()
        file_url = str(segment_data.get("url") or "").strip()
        text_parts: List[str] = []
        if file_name:
            text_parts.append(file_name)
        if file_size:
            text_parts.append(f"大小: {file_size}")
        file_text = "[文件]"
        if text_parts:
            file_text = f"[文件] {'，'.join(text_parts)}"
        if file_url:
            file_text = f"{file_text}，链接: {file_url}"
        return self._build_text_segment(file_text)

    async def _build_forward_segment(self, segment_data: Mapping[str, Any]) -> Optional[NapCatSegment]:
        """构造合并转发消息段。

        Args:
            segment_data: OneBot ``forward`` 段的 ``data`` 字典。

        Returns:
            Optional[NapCatSegment]: 转换后的合并转发消息段；失败时返回 ``None``。
        """
        inline_messages = self._extract_forward_messages(segment_data)
        messages = inline_messages

        if messages is None:
            message_id = str(segment_data.get("id") or "").strip()
            if not message_id:
                return None

            forward_detail = await self._query_service.get_forward_message(message_id)
            if forward_detail is None:
                return self._build_text_segment("[forward]")

            messages = self._extract_forward_messages(forward_detail)

        if not isinstance(messages, list):
            return self._build_text_segment("[forward]")

        forward_nodes = await self._build_forward_nodes(messages)
        if not forward_nodes:
            return self._build_text_segment("[forward]")
        return {"type": "forward", "data": forward_nodes}

    def _extract_forward_messages(self, payload: Mapping[str, Any]) -> Optional[List[Any]]:
        """从转发载荷中提取节点列表。

        Args:
            payload: 转发段 ``data`` 或 ``get_forward_msg`` 返回的载荷。

        Returns:
            Optional[List[Any]]: 提取到的节点列表；当载荷中不存在节点列表时返回 ``None``。
        """
        direct_messages = payload.get("messages")
        if isinstance(direct_messages, list):
            return direct_messages

        direct_content = payload.get("content")
        if isinstance(direct_content, list):
            return direct_content

        nested_data = payload.get("data")
        if isinstance(nested_data, Mapping):
            nested_messages = nested_data.get("messages")
            if isinstance(nested_messages, list):
                return nested_messages

            nested_content = nested_data.get("content")
            if isinstance(nested_content, list):
                return nested_content

        return None

    async def _build_forward_nodes(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """将 NapCat 转发节点列表转换为 Host 转发节点列表。

        Args:
            messages: NapCat 返回的转发节点列表。

        Returns:
            List[Dict[str, Any]]: Host 侧可识别的转发节点列表。
        """
        forward_nodes: List[Dict[str, Any]] = []
        for forward_message in messages:
            if not isinstance(forward_message, Mapping):
                continue

            raw_content = self._extract_forward_node_content(forward_message)
            content_segments = await self._convert_forward_content(raw_content, "")
            sender = self._extract_forward_node_sender(forward_message)

            node_data = forward_message.get("data", {})
            if not isinstance(node_data, Mapping):
                node_data = {}

            forward_nodes.append(
                {
                    "user_id": str(
                        sender.get("user_id")
                        or sender.get("uin")
                        or node_data.get("user_id")
                        or node_data.get("uin")
                        or ""
                    ).strip()
                    or None,
                    "user_nickname": str(
                        sender.get("nickname")
                        or sender.get("name")
                        or node_data.get("nickname")
                        or node_data.get("name")
                        or "未知用户"
                    ),
                    "user_cardname": str(sender.get("card") or node_data.get("card") or "").strip() or None,
                    "message_id": str(
                        forward_message.get("message_id")
                        or forward_message.get("id")
                        or node_data.get("id")
                        or uuid4().hex
                    ),
                    "content": content_segments or [self._build_text_segment("[empty]")],
                }
            )
        return forward_nodes

    def _extract_forward_node_content(self, forward_message: Mapping[str, Any]) -> Any:
        """提取单个转发节点中的消息段列表。

        Args:
            forward_message: NapCat 返回的单个转发节点。

        Returns:
            Any: 原始消息段列表；不存在时返回空列表。
        """
        direct_content = forward_message.get("content")
        if isinstance(direct_content, list):
            return direct_content

        direct_message = forward_message.get("message")
        if isinstance(direct_message, list):
            return direct_message

        node_data = forward_message.get("data", {})
        if not isinstance(node_data, Mapping):
            return []

        nested_content = node_data.get("content")
        if isinstance(nested_content, list):
            return nested_content

        nested_message = node_data.get("message")
        if isinstance(nested_message, list):
            return nested_message

        return []

    def _extract_forward_node_sender(self, forward_message: Mapping[str, Any]) -> Mapping[str, Any]:
        """提取单个转发节点的发送者信息。

        Args:
            forward_message: NapCat 返回的单个转发节点。

        Returns:
            Mapping[str, Any]: 归一化后的发送者信息映射。
        """
        sender = forward_message.get("sender", {})
        if isinstance(sender, Mapping):
            return sender

        node_data = forward_message.get("data", {})
        if not isinstance(node_data, Mapping):
            return {}

        normalized_sender: Dict[str, Any] = {}
        user_id = str(node_data.get("user_id") or node_data.get("uin") or "").strip()
        nickname = str(node_data.get("nickname") or node_data.get("name") or "").strip()
        cardname = str(node_data.get("card") or "").strip()
        if user_id:
            normalized_sender["user_id"] = user_id
            normalized_sender["uin"] = user_id
        if nickname:
            normalized_sender["nickname"] = nickname
            normalized_sender["name"] = nickname
        if cardname:
            normalized_sender["card"] = cardname
        return normalized_sender

    async def _convert_forward_content(self, raw_content: Any, self_id: str) -> NapCatSegments:
        """转换转发节点内部的消息段列表。

        Args:
            raw_content: 转发节点原始内容。
            self_id: 当前机器人账号 ID。

        Returns:
            NapCatSegments: 转换后的消息段列表。
        """
        if not isinstance(raw_content, list):
            return []

        normalized_segments = self._normalize_incoming_segments(raw_content)
        if not normalized_segments:
            return []

        segments, _ = await self._convert_incoming_segments(normalized_segments, self_id, "")
        return segments
