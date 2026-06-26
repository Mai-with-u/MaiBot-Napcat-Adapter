"""NapCat 入站纯文本与二进制辅助。"""

from __future__ import annotations

from typing import Any, Mapping

import base64

from ...napcat_types import NapCatSegments


class NapCatInboundTextMixin:
    """封装入站纯文本与二进制辅助逻辑。"""

    def build_plain_text(self, raw_message: NapCatSegments) -> str:
        """从标准消息段中提取可展示的纯文本。

        Args:
            raw_message: 标准化后的消息段列表。

        Returns:
            str: 用于 Host 展示和命令判断的纯文本内容。
        """
        plain_text_parts: list[str] = []
        for item in raw_message:
            if not isinstance(item, Mapping):
                continue
            item_type = str(item.get("type") or "").strip()
            item_data = item.get("data")
            if item_type == "text":
                plain_text_parts.append(str(item_data or ""))
            elif item_type == "at" and isinstance(item_data, Mapping):
                at_target_name = str(
                    item_data.get("target_user_cardname")
                    or item_data.get("target_user_nickname")
                    or item_data.get("target_user_id")
                    or ""
                ).strip()
                if at_target_name:
                    plain_text_parts.append(f"@{at_target_name}")
            elif item_type == "reply":
                plain_text_parts.append("[reply]")
            elif item_type == "forward":
                plain_text_parts.append("[forward]")
            elif item_type in {"image", "emoji", "voice"}:
                plain_text_parts.append(f"[{item_type}]")

        plain_text = "".join(part for part in plain_text_parts if part).strip()
        return plain_text or "[unsupported]"

    @staticmethod
    def _encode_binary(binary_data: bytes) -> str:
        """将二进制内容编码为 Base64 字符串。

        Args:
            binary_data: 待编码的二进制内容。

        Returns:
            str: Base64 编码字符串。
        """
        return base64.b64encode(binary_data).decode("utf-8")

    @staticmethod
    def _decode_binary(binary_base64: str) -> bytes:
        """将 Base64 字符串解码为二进制内容。

        Args:
            binary_base64: Base64 字符串。

        Returns:
            bytes: 解码后的二进制内容。
        """
        return base64.b64decode(binary_base64)

    @staticmethod
    def _normalize_numeric_segment_value(value: Any) -> Any:
        """将可安全识别的数字字符串转为整数。

        Args:
            value: 原始字段值。

        Returns:
            Any: 规范化后的字段值。
        """
        if isinstance(value, str):
            stripped_value = value.strip()
            if stripped_value.isdigit():
                return int(stripped_value)
            return stripped_value
        return value
