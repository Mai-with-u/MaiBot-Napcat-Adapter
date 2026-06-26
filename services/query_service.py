"""NapCat QQ 平台查询服务。"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from ..napcat_types import NapCatActionParams, NapCatActionResponse, NapCatPayloadDict, NapCatPayloadList
from .action_service import NapCatActionService


class NapCatQueryService:
    """NapCat QQ 平台查询与管理动作服务。"""

    def __init__(self, action_service: NapCatActionService, logger: Any) -> None:
        """初始化查询服务。

        Args:
            action_service: NapCat 底层动作服务。
            logger: 插件日志对象。
        """
        self._action_service = action_service
        self._logger = logger

    async def call_action(self, action_name: str, params: NapCatActionParams) -> NapCatActionResponse:
        """调用 OneBot 动作并要求返回成功结果。

        Args:
            action_name: OneBot 动作名称。
            params: 动作参数。

        Returns:
            NapCatActionResponse: NapCat 返回的原始响应字典。
        """
        return await self._action_service.call_action(action_name, params)

    async def call_action_data(self, action_name: str, params: NapCatActionParams) -> Any:
        """调用 OneBot 动作并返回 ``data`` 字段。

        Args:
            action_name: OneBot 动作名称。
            params: 动作参数。

        Returns:
            Any: NapCat 响应中的 ``data`` 字段。
        """
        return await self._action_service.call_action_data(action_name, params)

    async def get_login_info(self) -> Optional[NapCatPayloadDict]:
        """获取当前登录账号信息。

        Returns:
            Optional[NapCatPayloadDict]: 登录信息字典；返回值不是字典时为 ``None``。
        """
        response_data = await self._safe_call_action_data("get_login_info", {})
        return response_data if isinstance(response_data, dict) else None

    async def get_stranger_info(self, user_id: str, no_cache: bool = False) -> Optional[NapCatPayloadDict]:
        """获取陌生人信息。

        Args:
            user_id: 用户号。
            no_cache: 是否禁用缓存。

        Returns:
            Optional[NapCatPayloadDict]: 陌生人信息字典；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data(
            "get_stranger_info",
            {"user_id": user_id, "no_cache": bool(no_cache)},
        )
        return response_data if isinstance(response_data, dict) else None

    async def get_friend_list(self, no_cache: bool = False) -> Optional[NapCatPayloadList]:
        """获取好友列表。

        Args:
            no_cache: 是否禁用缓存。

        Returns:
            Optional[NapCatPayloadList]: 好友信息列表；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data("get_friend_list", {"no_cache": bool(no_cache)})
        return self._normalize_payload_list(response_data, action_name="get_friend_list")

    async def get_group_info(self, group_id: str) -> Optional[NapCatPayloadDict]:
        """获取群信息。

        Args:
            group_id: 群号。

        Returns:
            Optional[NapCatPayloadDict]: 群信息字典；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data("get_group_info", {"group_id": group_id})
        return response_data if isinstance(response_data, dict) else None

    async def get_group_detail_info(self, group_id: str) -> Optional[NapCatPayloadDict]:
        """获取群详细信息。

        Args:
            group_id: 群号。

        Returns:
            Optional[NapCatPayloadDict]: 群详细信息字典；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data("get_group_detail_info", {"group_id": group_id})
        return response_data if isinstance(response_data, dict) else None

    async def get_group_list(self, no_cache: bool = False) -> Optional[NapCatPayloadList]:
        """获取群列表。

        Args:
            no_cache: 是否禁用缓存。

        Returns:
            Optional[NapCatPayloadList]: 群信息列表；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data("get_group_list", {"no_cache": bool(no_cache)})
        return self._normalize_payload_list(response_data, action_name="get_group_list")

    async def get_group_at_all_remain(self, group_id: str) -> Optional[NapCatPayloadDict]:
        """获取群 @ 全体成员剩余次数。

        Args:
            group_id: 群号。

        Returns:
            Optional[NapCatPayloadDict]: 剩余次数信息；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data("get_group_at_all_remain", {"group_id": group_id})
        return response_data if isinstance(response_data, dict) else None

    async def get_group_member_info(
        self,
        group_id: str,
        user_id: str,
        no_cache: bool = True,
    ) -> Optional[NapCatPayloadDict]:
        """获取群成员信息。

        Args:
            group_id: 群号。
            user_id: 用户号。
            no_cache: 是否禁用缓存。

        Returns:
            Optional[NapCatPayloadDict]: 群成员信息字典；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data(
            "get_group_member_info",
            {"group_id": group_id, "user_id": user_id, "no_cache": bool(no_cache)},
        )
        return response_data if isinstance(response_data, dict) else None

    async def get_group_member_list(self, group_id: str, no_cache: bool = False) -> Optional[NapCatPayloadList]:
        """获取群成员列表。

        Args:
            group_id: 群号。
            no_cache: 是否禁用缓存。

        Returns:
            Optional[NapCatPayloadList]: 群成员信息列表；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data(
            "get_group_member_list",
            {"group_id": group_id, "no_cache": bool(no_cache)},
        )
        return self._normalize_payload_list(response_data, action_name="get_group_member_list")

    async def get_message_detail(self, message_id: str) -> Optional[NapCatPayloadDict]:
        """获取消息详情。

        Args:
            message_id: 消息 ID。

        Returns:
            Optional[NapCatPayloadDict]: 消息详情字典；失败时返回 ``None``。
        """
        response_data = await self._safe_call_action_data("get_msg", {"message_id": message_id})
        return response_data if isinstance(response_data, dict) else None

    async def get_forward_message(
        self,
        message_id: Optional[str] = None,
        forward_id: Optional[str] = None,
    ) -> Optional[NapCatPayloadDict]:
        """获取合并转发消息详情。

        Args:
            message_id: 转发消息 ID。
            forward_id: NapCat 官方文档中的兼容字段 ``id``。

        Returns:
            Optional[NapCatPayloadDict]: 合并转发消息详情；失败时返回 ``None``。
        """
        params: NapCatActionResponse = {}
        if message_id:
            params["message_id"] = message_id
        if forward_id:
            params["id"] = forward_id
        if not params:
            raise ValueError("message_id 或 id 至少提供一个")

        response_data = await self._safe_call_action_data("get_forward_msg", params)
        return self._normalize_forward_payload(response_data)

    async def get_record_detail(
        self,
        file_name: Optional[str] = None,
        file_id: Optional[str] = None,
        out_format: str = "wav",
    ) -> Optional[NapCatPayloadDict]:
        """获取语音文件详情。

        Args:
            file_name: 语音文件名。
            file_id: 可选文件 ID。
            out_format: 输出格式。

        Returns:
            Optional[NapCatPayloadDict]: 语音详情字典；失败时返回 ``None``。
        """
        params: NapCatActionResponse = {}
        if file_name:
            params["file"] = file_name
        if file_id:
            params["file_id"] = file_id
        if out_format:
            params["out_format"] = out_format
        if not params.get("file") and not params.get("file_id"):
            raise ValueError("file 或 file_id 至少提供一个")

        response_data = await self._safe_call_action_data("get_record", params)
        return response_data if isinstance(response_data, dict) else None

    async def set_group_ban(self, group_id: int, user_id: int, duration: int) -> NapCatActionResponse:
        """设置群成员禁言。

        Args:
            group_id: 群号。
            user_id: 用户号。
            duration: 禁言秒数。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "set_group_ban",
            {"group_id": group_id, "user_id": user_id, "duration": duration},
        )

    async def set_group_whole_ban(self, group_id: int, enable: bool) -> NapCatActionResponse:
        """设置群全体禁言。

        Args:
            group_id: 群号。
            enable: 是否开启全体禁言。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "set_group_whole_ban",
            {"group_id": group_id, "enable": bool(enable)},
        )

    async def set_group_kick(
        self,
        group_id: int,
        user_id: int,
        reject_add_request: bool = False,
    ) -> NapCatActionResponse:
        """踢出群成员。

        Args:
            group_id: 群号。
            user_id: 用户号。
            reject_add_request: 是否拒绝再次加群。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "set_group_kick",
            {
                "group_id": group_id,
                "user_id": user_id,
                "reject_add_request": bool(reject_add_request),
            },
        )

    async def set_group_kick_members(
        self,
        group_id: int,
        user_ids: List[int],
        reject_add_request: bool = False,
    ) -> NapCatActionResponse:
        """批量踢出群成员。

        Args:
            group_id: 群号。
            user_ids: 用户号列表。
            reject_add_request: 是否拒绝再次加群。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "set_group_kick_members",
            {
                "group_id": group_id,
                "user_id": user_ids,
                "reject_add_request": bool(reject_add_request),
            },
        )

    async def send_poke(
        self,
        user_id: int,
        group_id: Optional[int] = None,
        target_id: Optional[int] = None,
    ) -> NapCatActionResponse:
        """发送戳一戳。

        Args:
            user_id: 目标用户号。
            group_id: 可选群号；私聊时为空。
            target_id: NapCat 官方 ``send_poke`` 动作支持的目标 ID。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        params: NapCatActionResponse = {"user_id": user_id}
        if group_id is not None:
            params["group_id"] = group_id
        if target_id is not None:
            params["target_id"] = target_id
        return await self.call_action("send_poke", params)

    async def delete_message(self, message_id: int) -> NapCatActionResponse:
        """撤回消息。

        Args:
            message_id: 消息 ID。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action("delete_msg", {"message_id": message_id})

    async def send_group_ai_record(self, group_id: int, character: str, text: str) -> NapCatActionResponse:
        """发送群 AI 语音。

        Args:
            group_id: 群号。
            character: 角色标识。
            text: 语音文本。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "send_group_ai_record",
            {"group_id": group_id, "character": character, "text": text},
        )

    async def set_message_emoji_like(
        self,
        message_id: int,
        emoji_id: int,
        set_like: bool = True,
    ) -> NapCatActionResponse:
        """给消息贴表情或取消表情。

        Args:
            message_id: 消息 ID。
            emoji_id: 表情 ID。
            set_like: 是否设置为已贴表情。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "set_msg_emoji_like",
            {"message_id": message_id, "emoji_id": emoji_id, "set": bool(set_like)},
        )

    async def set_group_name(self, group_id: int, group_name: str) -> NapCatActionResponse:
        """设置群名称。

        Args:
            group_id: 群号。
            group_name: 新群名称。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        return await self.call_action(
            "set_group_name",
            {"group_id": group_id, "group_name": group_name},
        )

    async def set_qq_profile(
        self,
        nickname: str,
        personal_note: str = "",
        sex: str = "",
    ) -> NapCatActionResponse:
        """设置 QQ 账号资料。

        Args:
            nickname: 新昵称。
            personal_note: 个性签名。
            sex: 性别，支持 ``male``、``female``、``unknown``。

        Returns:
            NapCatActionResponse: NapCat 原始响应字典。
        """
        params: NapCatActionResponse = {"nickname": nickname}
        if personal_note:
            params["personal_note"] = personal_note
        if sex:
            params["sex"] = sex
        return await self.call_action("set_qq_profile", params)

    async def download_binary(self, url: str) -> Optional[bytes]:
        """下载远程二进制资源。

        Args:
            url: 资源 URL。

        Returns:
            Optional[bytes]: 下载到的二进制内容；失败时返回 ``None``。
        """
        return await self._action_service.download_binary(url)

    async def _safe_call_action_data(self, action_name: str, params: NapCatActionParams) -> Any:
        """安全调用 OneBot 动作并返回 ``data`` 字段。

        Args:
            action_name: OneBot 动作名称。
            params: 动作参数。

        Returns:
            Any: 响应中的 ``data`` 字段；失败时返回 ``None``。
        """
        return await self._action_service.safe_call_action_data(action_name, params)

    def _normalize_payload_list(self, response_data: Any, action_name: str) -> Optional[NapCatPayloadList]:
        """将列表类响应归一化为字典列表。

        NapCat 在不同版本或不同动作下，``data`` 可能直接返回列表，
        也可能再包一层字典，例如 ``{\"members\": [...]}``。

        Args:
            response_data: 原始 ``data`` 字段。
            action_name: 当前动作名称。

        Returns:
            Optional[NapCatPayloadList]: 归一化后的列表；无法识别时返回 ``None``。
        """

        if isinstance(response_data, list):
            return [dict(item) for item in response_data if isinstance(item, Mapping)]

        if not isinstance(response_data, Mapping):
            self._logger.warning(
                "NapCat 列表接口返回了无法识别的数据类型: action=%s type=%s payload=%r",
                action_name,
                type(response_data).__name__,
                response_data,
            )
            return None

        for key in (
            "list",
            "items",
            "members",
            "member_list",
            "group_list",
            "friend_list",
            "friends",
            "records",
            "rows",
            "data",
        ):
            candidate = response_data.get(key)
            if isinstance(candidate, list):
                return [dict(item) for item in candidate if isinstance(item, Mapping)]

        for candidate in response_data.values():
            if isinstance(candidate, list):
                return [dict(item) for item in candidate if isinstance(item, Mapping)]

        self._logger.warning(
            "NapCat 列表接口返回了无法归一化的字典结构: action=%s payload=%r",
            action_name,
            response_data,
        )
        return None

    def _normalize_forward_payload(self, response_data: Any) -> Optional[NapCatPayloadDict]:
        """将合并转发响应归一化为统一字典结构。

        NapCat 的 ``get_forward_msg`` 在不同版本下，``data`` 可能直接返回节点列表，
        也可能返回 ``{\"messages\": [...]}``，甚至包在 ``content`` 字段中。

        Args:
            response_data: ``get_forward_msg`` 的原始 ``data`` 字段。

        Returns:
            Optional[NapCatPayloadDict]: 归一化后的转发消息详情；失败时返回 ``None``。
        """
        if isinstance(response_data, list):
            return {"messages": [dict(item) for item in response_data if isinstance(item, Mapping)]}

        if not isinstance(response_data, Mapping):
            self._logger.warning(
                "NapCat 转发接口返回了无法识别的数据类型: type=%s payload=%r",
                type(response_data).__name__,
                response_data,
            )
            return None

        direct_messages = response_data.get("messages")
        if isinstance(direct_messages, list):
            return dict(response_data)

        direct_content = response_data.get("content")
        if isinstance(direct_content, list):
            return {"messages": [dict(item) for item in direct_content if isinstance(item, Mapping)]}

        nested_data = response_data.get("data")
        if isinstance(nested_data, Mapping):
            nested_messages = nested_data.get("messages")
            if isinstance(nested_messages, list):
                return {"messages": [dict(item) for item in nested_messages if isinstance(item, Mapping)]}

            nested_content = nested_data.get("content")
            if isinstance(nested_content, list):
                return {"messages": [dict(item) for item in nested_content if isinstance(item, Mapping)]}

        self._logger.warning("NapCat 转发接口未返回可识别的转发节点列表: payload=%r", response_data)
        return None
