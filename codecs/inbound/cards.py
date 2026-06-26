"""NapCat 入站 JSON 卡片解析辅助。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING

import hashlib
import json
import re

from ...qq_emoji_list import QQ_FACE
from ...napcat_types import NapCatSegment, NapCatSegments

if TYPE_CHECKING:
    from ...services import NapCatQueryService


class NapCatInboundCardMixin:
    """封装入站 JSON 卡片与预览内容转换逻辑。"""

    if TYPE_CHECKING:
        _query_service: NapCatQueryService

        @staticmethod
        def _build_text_segment(text: str) -> NapCatSegment: ...

        @staticmethod
        def _encode_binary(binary_data: bytes) -> str: ...

    async def _build_json_segments(
        self,
        segment_data: Mapping[str, Any],
        *,
        platform_card_payloads: Optional[List[Dict[str, Any]]] = None,
    ) -> NapCatSegments:
        """将 JSON 卡片最佳努力转换为消息段列表。

        Args:
            segment_data: OneBot ``json`` 段的 ``data`` 字典。

        Returns:
            NapCatSegments: 转换后的消息段列表。
        """
        json_data = str(segment_data.get("data") or "").strip()
        if not json_data:
            return [self._build_text_segment("[json]")]

        try:
            parsed_json = json.loads(json_data)
        except Exception:
            return [self._build_text_segment("[json]")]

        if not isinstance(parsed_json, Mapping):
            return [self._build_text_segment("[json]")]

        app_name = str(parsed_json.get("app") or "").strip()
        meta = parsed_json.get("meta", {})
        if not isinstance(meta, Mapping):
            meta = {}

        if app_name == "com.tencent.mannounce":
            return [self._build_mannounce_segment(meta)]

        if app_name in {"com.tencent.music.lua", "com.tencent.structmsg"}:
            music_segments = self._build_music_card_segments(meta)
            if music_segments:
                return music_segments

        if app_name == "com.tencent.miniapp_01":
            if platform_card_payloads is not None:
                platform_card_payloads.append(
                    {
                        "type": "miniapp_card",
                        "app": app_name,
                        "payload": dict(parsed_json),
                    }
                )
            return await self._build_preview_text_segments(
                self._build_miniapp_text(meta),
                self._extract_preview_url(meta, "detail_1"),
            )

        if app_name == "com.tencent.giftmall.giftark":
            gift_text = self._build_gift_text(meta)
            if gift_text:
                return [self._build_text_segment(gift_text)]

        if app_name == "com.tencent.contact.lua":
            return [self._build_text_segment(self._build_contact_text(meta, "推荐联系人"))]

        if app_name == "com.tencent.troopsharecard":
            return [self._build_text_segment(self._build_contact_text(meta, "推荐群聊"))]

        if app_name == "com.tencent.tuwen.lua":
            return await self._build_preview_text_segments(
                self._build_news_text(meta, default_tag="图文分享"),
                self._extract_preview_url(meta, "news"),
            )

        if app_name == "com.tencent.feed.lua":
            return await self._build_preview_text_segments(
                self._build_feed_text(meta),
                self._extract_preview_url(meta, "feed", field_name="cover"),
            )

        if app_name == "com.tencent.template.qqfavorite.share":
            return await self._build_preview_text_segments(
                self._build_favorite_text(meta),
                self._extract_preview_url(meta, "news"),
            )

        if app_name == "com.tencent.miniapp.lua":
            return await self._build_preview_text_segments(
                self._build_simple_title_text(meta, "miniapp", "QQ空间"),
                self._extract_preview_url(meta, "miniapp"),
            )

        if app_name == "com.tencent.forum":
            forum_segments = await self._build_forum_segments(meta)
            if forum_segments:
                return forum_segments

        if app_name == "com.tencent.map":
            location_text = self._build_location_text(meta)
            if location_text:
                return [self._build_text_segment(location_text)]

        if app_name == "com.tencent.together":
            together_text = self._build_together_text(meta)
            if together_text:
                return [self._build_text_segment(together_text)]

        prompt = str(parsed_json.get("prompt") or "").strip()
        if not prompt and isinstance(meta, Mapping):
            prompt = str(meta.get("prompt") or "").strip()
        text = prompt or app_name or "json"
        return [self._build_text_segment(f"[json:{text}]")]

    def _build_mannounce_segment(self, meta: Mapping[str, Any]) -> NapCatSegment:
        """构造群公告文本段。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            NapCatSegment: 群公告文本段。
        """
        mannounce = meta.get("mannounce", {})
        if not isinstance(mannounce, Mapping):
            mannounce = {}

        title = str(mannounce.get("title") or "").strip()
        text = str(mannounce.get("text") or "").strip()
        encode_flag = mannounce.get("encode")
        if encode_flag == 1:
            title = self._safe_base64_decode(title)
            text = self._safe_base64_decode(text)

        if title and text:
            content = f"[{title}]：{text}"
        elif title:
            content = f"[{title}]"
        elif text:
            content = text
        else:
            content = "[群公告]"
        return self._build_text_segment(content)

    def _build_music_card_segments(self, meta: Mapping[str, Any]) -> NapCatSegments:
        """构造音乐卡片文本段。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            NapCatSegments: 音乐卡片转换后的消息段列表。
        """
        music = meta.get("music", {})
        if not isinstance(music, Mapping):
            return []

        title = str(music.get("title") or "").strip()
        singer = str(music.get("desc") or music.get("singer") or "").strip()
        tag = str(music.get("tag") or "音乐分享").strip()
        text_parts: List[str] = [f"[{tag}]"]
        if title:
            text_parts.append(title)
        if singer:
            text_parts.append(f"- {singer}")
        content = " ".join(text_parts).strip() or "[音乐分享]"
        return [self._build_text_segment(content)]

    async def _build_preview_text_segments(
        self,
        text: str,
        preview_url: str,
    ) -> NapCatSegments:
        """构造“文本 + 预览图”消息段列表。

        Args:
            text: 主文本内容。
            preview_url: 预览图地址。

        Returns:
            NapCatSegments: 转换后的消息段列表。
        """
        segments: NapCatSegments = [self._build_text_segment(text or "[卡片消息]")]
        image_segment = await self._build_remote_image_segment(preview_url)
        if image_segment is not None:
            segments.append(image_segment)
        return segments

    async def _build_remote_image_segment(self, image_url: str) -> Optional[NapCatSegment]:
        """从远端图片地址构造图片消息段。

        Args:
            image_url: 图片地址。

        Returns:
            Optional[NapCatSegment]: 成功时返回图片消息段，否则返回 ``None``。
        """
        normalized_url = str(image_url or "").strip()
        if not normalized_url:
            return None

        binary_data = await self._query_service.download_binary(normalized_url)
        if not binary_data:
            return None

        return {
            "type": "image",
            "data": "",
            "hash": hashlib.sha256(binary_data).hexdigest(),
            "binary_data_base64": self._encode_binary(binary_data),
        }

    def _build_miniapp_text(self, meta: Mapping[str, Any]) -> str:
        """构造小程序分享文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            str: 小程序分享文本。
        """
        detail = meta.get("detail_1", {})
        if not isinstance(detail, Mapping):
            return "[小程序]"
        title = str(detail.get("title") or "").strip()
        desc = str(detail.get("desc") or "").strip()
        if title and desc:
            return f"[小程序] {title}：{desc}"
        if title:
            return f"[小程序] {title}"
        if desc:
            return f"[小程序] {desc}"
        return "[小程序]"

    def _build_gift_text(self, meta: Mapping[str, Any]) -> str:
        """构造礼物卡片文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            str: 礼物卡片文本。
        """
        giftark = meta.get("giftark", {})
        if not isinstance(giftark, Mapping):
            return "[赠送礼物]"
        gift_name = str(giftark.get("title") or "礼物").strip()
        desc = str(giftark.get("desc") or "").strip()
        if desc:
            return f"[赠送礼物: {gift_name}] {desc}"
        return f"[赠送礼物: {gift_name}]"

    def _build_contact_text(self, meta: Mapping[str, Any], default_tag: str) -> str:
        """构造推荐联系人或群聊文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。
            default_tag: 默认标签文本。

        Returns:
            str: 推荐对象文本。
        """
        contact = meta.get("contact", {})
        if not isinstance(contact, Mapping):
            return f"[{default_tag}]"
        name = str(contact.get("nickname") or "未知对象").strip()
        tag = str(contact.get("tag") or default_tag).strip() or default_tag
        return f"[{tag}] {name}"

    def _build_news_text(self, meta: Mapping[str, Any], default_tag: str) -> str:
        """构造图文分享文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。
            default_tag: 默认标签文本。

        Returns:
            str: 图文分享文本。
        """
        news = meta.get("news", {})
        if not isinstance(news, Mapping):
            return f"[{default_tag}]"
        title = str(news.get("title") or "未知标题").strip()
        desc = str(news.get("desc") or "").replace("[图片]", "").strip()
        tag = str(news.get("tag") or default_tag).strip() or default_tag
        if tag and title and tag in title:
            title = self._trim_card_title(title.replace(tag, "", 1))
        if desc:
            return f"[{tag}] {title}：{desc}"
        return f"[{tag}] {title}".strip()

    def _build_feed_text(self, meta: Mapping[str, Any]) -> str:
        """构造群相册分享文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            str: 群相册分享文本。
        """
        feed = meta.get("feed", {})
        if not isinstance(feed, Mapping):
            return "[群相册]"
        title = str(feed.get("title") or "群相册").strip()
        tag = str(feed.get("tagName") or "群相册").strip() or "群相册"
        desc = str(feed.get("forwardMessage") or "").strip()
        if tag and title and tag in title:
            title = self._trim_card_title(title.replace(tag, "", 1))
        if desc:
            return f"[{tag}] {title}：{desc}"
        return f"[{tag}] {title}".strip()

    def _build_favorite_text(self, meta: Mapping[str, Any]) -> str:
        """构造 QQ 收藏分享文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            str: QQ 收藏分享文本。
        """
        news = meta.get("news", {})
        if not isinstance(news, Mapping):
            return "[QQ收藏]"
        desc = str(news.get("desc") or "").replace("[图片]", "").strip()
        tag = str(news.get("tag") or "QQ收藏").strip() or "QQ收藏"
        if desc:
            return f"[{tag}] {desc}"
        return f"[{tag}]"

    def _build_simple_title_text(
        self,
        meta: Mapping[str, Any],
        key: str,
        default_tag: str,
    ) -> str:
        """构造简单标题类卡片文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。
            key: 子对象键名。
            default_tag: 默认标签文本。

        Returns:
            str: 简单标题文本。
        """
        nested_payload = meta.get(key, {})
        if not isinstance(nested_payload, Mapping):
            return f"[{default_tag}]"
        title = str(nested_payload.get("title") or "未知标题").strip()
        tag = str(nested_payload.get("tag") or default_tag).strip() or default_tag
        return f"[{tag}] {title}".strip()

    async def _build_forum_segments(self, meta: Mapping[str, Any]) -> NapCatSegments:
        """构造 QQ 频道帖子消息段。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            NapCatSegments: 频道帖子转换后的消息段列表。
        """
        detail = meta.get("detail", {})
        if not isinstance(detail, Mapping):
            return []

        feed = detail.get("feed", {})
        poster = detail.get("poster", {})
        channel_info = detail.get("channel_info", {})
        if not isinstance(feed, Mapping) or not isinstance(poster, Mapping) or not isinstance(channel_info, Mapping):
            return []

        guild_name = str(channel_info.get("guild_name") or "").strip()
        nick = str(poster.get("nick") or "QQ用户").strip() or "QQ用户"
        title = self._extract_forum_title(feed)
        face_content = self._extract_forum_face_text(feed)

        text_prefix = "[频道帖子]"
        if guild_name:
            text_prefix = f"{text_prefix} [{guild_name}]"
        text_content = f"{text_prefix}{nick}:{title}{face_content}"
        segments: NapCatSegments = [self._build_text_segment(text_content)]

        images = feed.get("images", [])
        if not isinstance(images, list):
            return segments

        for image_item in images:
            if not isinstance(image_item, Mapping):
                continue
            image_segment = await self._build_remote_image_segment(str(image_item.get("pic_url") or "").strip())
            if image_segment is not None:
                segments.append(image_segment)
        return segments

    def _extract_forum_title(self, feed: Mapping[str, Any]) -> str:
        """提取 QQ 频道帖子标题。

        Args:
            feed: 频道帖子 ``feed`` 数据。

        Returns:
            str: 帖子标题。
        """
        title_payload = feed.get("title", {})
        if not isinstance(title_payload, Mapping):
            return "帖子"
        contents = title_payload.get("contents", [])
        if not isinstance(contents, list) or not contents:
            return "帖子"
        first_content = contents[0]
        if not isinstance(first_content, Mapping):
            return "帖子"
        text_content = first_content.get("text_content", {})
        if not isinstance(text_content, Mapping):
            return "帖子"
        return str(text_content.get("text") or "帖子").strip() or "帖子"

    def _extract_forum_face_text(self, feed: Mapping[str, Any]) -> str:
        """提取 QQ 频道帖子中的表情文本。

        Args:
            feed: 频道帖子 ``feed`` 数据。

        Returns:
            str: 合并后的表情文本。
        """
        contents_payload = feed.get("contents", {})
        if not isinstance(contents_payload, Mapping):
            return ""
        contents = contents_payload.get("contents", [])
        if not isinstance(contents, list):
            return ""

        face_text_parts: List[str] = []
        for item in contents:
            if not isinstance(item, Mapping):
                continue
            emoji_content = item.get("emoji_content", {})
            if not isinstance(emoji_content, Mapping):
                continue
            emoji_id = str(emoji_content.get("id") or "").strip()
            if emoji_id in QQ_FACE:
                face_text_parts.append(QQ_FACE[emoji_id])
        return "".join(face_text_parts)

    def _build_location_text(self, meta: Mapping[str, Any]) -> str:
        """构造位置分享文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            str: 位置分享文本。
        """
        location = meta.get("Location.Search", {})
        if not isinstance(location, Mapping):
            return "[位置]"
        name = str(location.get("name") or "未知地点").strip()
        address = str(location.get("address") or "").strip()
        if address:
            return f"[位置] {address} · {name}"
        return f"[位置] {name}"

    def _build_together_text(self, meta: Mapping[str, Any]) -> str:
        """构造“一起听歌”文本。

        Args:
            meta: JSON 卡片 ``meta`` 数据。

        Returns:
            str: 一起听歌文本。
        """
        invite = meta.get("invite", {})
        if not isinstance(invite, Mapping):
            return "[一起听歌]"
        title = str(invite.get("title") or "一起听歌").strip() or "一起听歌"
        summary = str(invite.get("summary") or "").strip()
        if summary:
            return f"[{title}] {summary}"
        return f"[{title}]"

    def _extract_preview_url(
        self,
        meta: Mapping[str, Any],
        key: str,
        field_name: str = "preview",
    ) -> str:
        """从卡片元数据中提取预览图地址。

        Args:
            meta: JSON 卡片 ``meta`` 数据。
            key: 子对象键名。
            field_name: 预览图字段名。

        Returns:
            str: 预览图地址；不存在时返回空字符串。
        """
        nested_payload = meta.get(key, {})
        if not isinstance(nested_payload, Mapping):
            return ""
        return str(nested_payload.get(field_name) or "").strip()

    @staticmethod
    def _trim_card_title(title: str) -> str:
        """清理卡片标题两侧的常见分隔符。

        Args:
            title: 原始标题文本。

        Returns:
            str: 清理后的标题文本。
        """
        return re.sub(r"^[：:\s\-—]+|[：:\s\-—]+$", "", str(title or "").strip())

    @staticmethod
    def _safe_base64_decode(encoded_text: str) -> str:
        """安全地解码 Base64 文本。

        Args:
            encoded_text: 待解码的 Base64 文本。

        Returns:
            str: 解码结果；失败时返回原始文本。
        """
        normalized_text = str(encoded_text or "").strip()
        if not normalized_text:
            return ""
        try:
            import base64

            return base64.b64decode(normalized_text).decode("utf-8", errors="ignore")
        except Exception:
            return normalized_text
