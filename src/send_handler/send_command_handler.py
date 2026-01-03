from maim_message import GroupInfo
from typing import Any, Dict, Tuple, Callable, Optional

from src import CommandType


# 全局命令处理器注册表（在类外部定义以避免循环引用）
_command_handlers: Dict[str, Dict[str, Any]] = {}


def register_command(command_type: CommandType, require_group: bool = True):
    """装饰器：注册命令处理器

    Args:
        command_type: 命令类型
        require_group: 是否需要群聊信息，默认为True

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        _command_handlers[command_type.name] = {
            "handler": func,
            "require_group": require_group,
        }
        return func

    return decorator


class SendCommandHandleClass:
    @classmethod
    def handle_command(cls, raw_command_data: Dict[str, Any], group_info: Optional[GroupInfo]):
        """统一命令处理入口

        Args:
            raw_command_data: 原始命令数据
            group_info: 群聊信息（可选）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params) 用于发送给NapCat

        Raises:
            RuntimeError: 命令类型未知或处理失败
        """
        command_name: str = raw_command_data.get("name")

        if command_name not in _command_handlers:
            raise RuntimeError(f"未知的命令类型: {command_name}")

        try:
            handler_info = _command_handlers[command_name]
            handler = handler_info["handler"]
            require_group = handler_info["require_group"]

            # 检查群聊信息要求
            if require_group and not group_info:
                raise ValueError(f"命令 {command_name} 需要在群聊上下文中使用")

            # 调用处理器
            args = raw_command_data.get("args", {})
            return handler(args, group_info)

        except Exception as e:
            raise RuntimeError(f"处理命令 {command_name} 时出错: {str(e)}") from e

    # ============ 命令处理器（使用装饰器注册）============

    @staticmethod
    @register_command(CommandType.GROUP_BAN, require_group=True)
    def handle_ban_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理封禁命令

        Args:
            args: 参数字典 {"qq_id": int, "duration": int}
            group_info: 群聊信息（对应目标群聊）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        duration: int = int(args["duration"])
        user_id: int = int(args["qq_id"])
        group_id: int = int(group_info.group_id)
        if duration < 0:
            raise ValueError("封禁时间必须大于等于0")
        if not user_id or not group_id:
            raise ValueError("封禁命令缺少必要参数")
        if duration > 2592000:
            raise ValueError("封禁时间不能超过30天")
        return (
            CommandType.GROUP_BAN.value,
            {
                "group_id": group_id,
                "user_id": user_id,
                "duration": duration,
            },
        )

    @staticmethod
    @register_command(CommandType.GROUP_WHOLE_BAN, require_group=True)
    def handle_whole_ban_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理全体禁言命令

        Args:
            args: 参数字典 {"enable": bool}
            group_info: 群聊信息（对应目标群聊）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        enable = args["enable"]
        assert isinstance(enable, bool), "enable参数必须是布尔值"
        group_id: int = int(group_info.group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        return (
            CommandType.GROUP_WHOLE_BAN.value,
            {
                "group_id": group_id,
                "enable": enable,
            },
        )

    @staticmethod
    @register_command(CommandType.GROUP_KICK, require_group=False)
    def handle_kick_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理群成员踢出命令

        Args:
            args: 参数字典 {"group_id": int, "user_id": int, "reject_add_request": bool (可选)}
            group_info: 群聊信息（可选，可自动获取 group_id）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("群踢人命令缺少参数")
        
        # 优先从 args 获取 group_id，否则从 group_info 获取
        group_id = args.get("group_id")
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        user_id = args.get("user_id")
        
        if not group_id:
            raise ValueError("群踢人命令缺少必要参数: group_id")
        if not user_id:
            raise ValueError("群踢人命令缺少必要参数: user_id")
        
        group_id = int(group_id)
        user_id = int(user_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        if user_id <= 0:
            raise ValueError("用户ID无效")
        
        # reject_add_request 是可选参数，默认 False
        reject_add_request = args.get("reject_add_request", False)
        
        return (
            CommandType.GROUP_KICK.value,
            {
                "group_id": group_id,
                "user_id": user_id,
                "reject_add_request": bool(reject_add_request),
            },
        )

    @staticmethod
    @register_command(CommandType.GROUP_KICK_MEMBERS, require_group=False)
    def handle_kick_members_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理批量踢出群成员命令

        Args:
            args: 参数字典 {"group_id": int, "user_id": List[int], "reject_add_request": bool (可选)}
            group_info: 群聊信息（可选，可自动获取 group_id）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("批量踢人命令缺少参数")
        
        # 优先从 args 获取 group_id，否则从 group_info 获取
        group_id = args.get("group_id")
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        user_id = args.get("user_id")
        
        if not group_id:
            raise ValueError("批量踢人命令缺少必要参数: group_id")
        if not user_id:
            raise ValueError("批量踢人命令缺少必要参数: user_id")
        
        # 验证 user_id 是数组
        if not isinstance(user_id, list):
            raise ValueError("user_id 必须是数组类型")
        if len(user_id) == 0:
            raise ValueError("user_id 数组不能为空")
        
        # 转换并验证每个 user_id
        user_id_list = []
        for uid in user_id:
            try:
                uid_int = int(uid)
                if uid_int <= 0:
                    raise ValueError(f"用户ID无效: {uid}")
                user_id_list.append(uid_int)
            except (ValueError, TypeError) as e:
                raise ValueError(f"用户ID格式错误: {uid} - {str(e)}") from None
        
        group_id = int(group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        
        # reject_add_request 是可选参数，默认 False
        reject_add_request = args.get("reject_add_request", False)
        
        return (
            CommandType.GROUP_KICK_MEMBERS.value,
            {
                "group_id": group_id,
                "user_id": user_id_list,
                "reject_add_request": bool(reject_add_request),
            },
        )

    @staticmethod
    @register_command(CommandType.SEND_POKE, require_group=False)
    def handle_poke_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理戳一戳命令

        Args:
            args: 参数字典 {"qq_id": int}
            group_info: 群聊信息（可选，私聊时为None）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        user_id: int = int(args["qq_id"])
        if group_info is None:
            group_id = None
        else:
            group_id: int = int(group_info.group_id)
            if group_id <= 0:
                raise ValueError("群组ID无效")
        if user_id <= 0:
            raise ValueError("用户ID无效")
        return (
            CommandType.SEND_POKE.value,
            {
                "group_id": group_id,
                "user_id": user_id,
            },
        )

    @staticmethod
    @register_command(CommandType.SET_GROUP_NAME, require_group=False)
    def handle_set_group_name_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """设置群名

        Args:
            args: 参数字典 {"group_id": int, "group_name": str}
            group_info: 群聊信息（可选，可自动获取 group_id）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("设置群名命令缺少参数")
        
        # 优先从 args 获取 group_id，否则从 group_info 获取
        group_id = args.get("group_id")
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        group_name = args.get("group_name")
        
        if not group_id:
            raise ValueError("设置群名命令缺少必要参数: group_id")
        if not group_name:
            raise ValueError("设置群名命令缺少必要参数: group_name")
        
        group_id = int(group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        
        return (
            CommandType.SET_GROUP_NAME.value,
            {
                "group_id": group_id,
                "group_name": str(group_name),
            },
        )

    @staticmethod
    @register_command(CommandType.DELETE_MSG, require_group=False)
    def delete_msg_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理撤回消息命令

        Args:
            args: 参数字典 {"message_id": int}
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        try:
            message_id = int(args["message_id"])
            if message_id <= 0:
                raise ValueError("消息ID无效")
        except KeyError:
            raise ValueError("缺少必需参数: message_id") from None
        except (ValueError, TypeError) as e:
            raise ValueError(f"消息ID无效: {args['message_id']} - {str(e)}") from None

        return (CommandType.DELETE_MSG.value, {"message_id": message_id})

    @staticmethod
    @register_command(CommandType.SET_QQ_PROFILE, require_group=False)
    def handle_set_qq_profile_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """设置账号信息

        Args:
            args: 参数字典 {"nickname": str, "personal_note": str (可选), "sex": str (可选)}
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("设置账号信息命令缺少参数")

        nickname = args.get("nickname")
        if not nickname:
            raise ValueError("设置账号信息命令缺少必要参数: nickname")

        params = {"nickname": str(nickname)}
        
        # 可选参数
        if "personal_note" in args:
            params["personal_note"] = str(args["personal_note"])
        
        if "sex" in args:
            sex = str(args["sex"]).lower()
            if sex not in ["male", "female", "unknown"]:
                raise ValueError(f"性别参数无效: {sex}，必须为 male/female/unknown 之一")
            params["sex"] = sex

        return (CommandType.SET_QQ_PROFILE.value, params)

    @staticmethod
    @register_command(CommandType.AI_VOICE_SEND, require_group=True)
    def handle_ai_voice_send_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理AI语音发送命令

        Args:
            args: 参数字典 {"character": str, "text": str}
            group_info: 群聊信息

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not group_info or not group_info.group_id:
            raise ValueError("AI语音发送命令必须在群聊上下文中使用")
        if not args:
            raise ValueError("AI语音发送命令缺少参数")

        group_id: int = int(group_info.group_id)
        character_id = args.get("character")
        text_content = args.get("text")

        if not character_id or not text_content:
            raise ValueError(f"AI语音发送命令参数不完整: character='{character_id}', text='{text_content}'")

        return (
            CommandType.AI_VOICE_SEND.value,
            {
                "group_id": group_id,
                "text": text_content,
                "character": character_id,
            },
        )

    @staticmethod
    @register_command(CommandType.MESSAGE_LIKE, require_group=False)
    def handle_message_like_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """处理给消息贴表情命令

        Args:
            args: 参数字典 {"message_id": int, "emoji_id": int}
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("消息贴表情命令缺少参数")

        message_id = args.get("message_id")
        emoji_id = args.get("emoji_id")
        if not message_id:
            raise ValueError("消息贴表情命令缺少必要参数: message_id")
        if not emoji_id:
            raise ValueError("消息贴表情命令缺少必要参数: emoji_id")

        message_id = int(message_id)
        emoji_id = int(emoji_id)
        if message_id <= 0:
            raise ValueError("消息ID无效")
        if emoji_id <= 0:
            raise ValueError("表情ID无效")

        return (
            CommandType.MESSAGE_LIKE.value,
            {
                "message_id": message_id,
                "emoji_id": emoji_id,
                "set": True,
            },
        )

    # ============ 查询类命令处理器 ============

    @staticmethod
    @register_command(CommandType.GET_LOGIN_INFO, require_group=False)
    def handle_get_login_info_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取登录号信息（Bot自身信息）

        Args:
            args: 参数字典（无需参数）
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        return (CommandType.GET_LOGIN_INFO.value, {})

    @staticmethod
    @register_command(CommandType.GET_STRANGER_INFO, require_group=False)
    def handle_get_stranger_info_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取陌生人信息

        Args:
            args: 参数字典 {"user_id": int}
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("获取陌生人信息命令缺少参数")

        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("获取陌生人信息命令缺少必要参数: user_id")

        user_id = int(user_id)
        if user_id <= 0:
            raise ValueError("用户ID无效")

        return (
            CommandType.GET_STRANGER_INFO.value,
            {"user_id": user_id},
        )

    @staticmethod
    @register_command(CommandType.GET_FRIEND_LIST, require_group=False)
    def handle_get_friend_list_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取好友列表

        Args:
            args: 参数字典 {"no_cache": bool} (可选，默认 false)
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        # no_cache 参数是可选的，默认为 false
        no_cache = args.get("no_cache", False) if args else False
        
        return (CommandType.GET_FRIEND_LIST.value, {"no_cache": bool(no_cache)})

    @staticmethod
    @register_command(CommandType.GET_GROUP_INFO, require_group=False)
    def handle_get_group_info_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取群信息

        Args:
            args: 参数字典 {"group_id": int} 或从 group_info 自动获取
            group_info: 群聊信息（可选）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        # 优先从 args 获取，否则从 group_info 获取
        group_id = args.get("group_id") if args else None
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        if not group_id:
            raise ValueError("获取群信息命令缺少必要参数: group_id")

        group_id = int(group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")

        return (
            CommandType.GET_GROUP_INFO.value,
            {"group_id": group_id},
        )

    @staticmethod
    @register_command(CommandType.GET_GROUP_DETAIL_INFO, require_group=False)
    def handle_get_group_detail_info_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取群详细信息

        Args:
            args: 参数字典 {"group_id": int} 或从 group_info 自动获取
            group_info: 群聊信息（可选）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        # 优先从 args 获取，否则从 group_info 获取
        group_id = args.get("group_id") if args else None
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        if not group_id:
            raise ValueError("获取群详细信息命令缺少必要参数: group_id")

        group_id = int(group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")

        return (
            CommandType.GET_GROUP_DETAIL_INFO.value,
            {"group_id": group_id},
        )

    @staticmethod
    @register_command(CommandType.GET_GROUP_LIST, require_group=False)
    def handle_get_group_list_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取群列表

        Args:
            args: 参数字典 {"no_cache": bool} (可选，默认 false)
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        # no_cache 参数是可选的，默认为 false
        no_cache = args.get("no_cache", False) if args else False
        
        return (CommandType.GET_GROUP_LIST.value, {"no_cache": bool(no_cache)})

    @staticmethod
    @register_command(CommandType.GET_GROUP_AT_ALL_REMAIN, require_group=False)
    def handle_get_group_at_all_remain_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取群@全体成员剩余次数

        Args:
            args: 参数字典 {"group_id": int} 或从 group_info 自动获取
            group_info: 群聊信息（可选）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        # 优先从 args 获取，否则从 group_info 获取
        group_id = args.get("group_id") if args else None
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        if not group_id:
            raise ValueError("获取群@全体成员剩余次数命令缺少必要参数: group_id")

        group_id = int(group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")

        return (
            CommandType.GET_GROUP_AT_ALL_REMAIN.value,
            {"group_id": group_id},
        )

    @staticmethod
    @register_command(CommandType.GET_GROUP_MEMBER_INFO, require_group=False)
    def handle_get_group_member_info_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取群成员信息

        Args:
            args: 参数字典 {"group_id": int, "user_id": int, "no_cache": bool} 或 group_id 从 group_info 自动获取
            group_info: 群聊信息（可选）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("获取群成员信息命令缺少参数")

        # 优先从 args 获取，否则从 group_info 获取
        group_id = args.get("group_id")
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        user_id = args.get("user_id")
        no_cache = args.get("no_cache", False)
        
        if not group_id:
            raise ValueError("获取群成员信息命令缺少必要参数: group_id")
        if not user_id:
            raise ValueError("获取群成员信息命令缺少必要参数: user_id")

        group_id = int(group_id)
        user_id = int(user_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")
        if user_id <= 0:
            raise ValueError("用户ID无效")

        return (
            CommandType.GET_GROUP_MEMBER_INFO.value,
            {
                "group_id": group_id,
                "user_id": user_id,
                "no_cache": bool(no_cache),
            },
        )

    @staticmethod
    @register_command(CommandType.GET_GROUP_MEMBER_LIST, require_group=False)
    def handle_get_group_member_list_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取群成员列表

        Args:
            args: 参数字典 {"group_id": int, "no_cache": bool} 或 group_id 从 group_info 自动获取
            group_info: 群聊信息（可选）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        # 优先从 args 获取，否则从 group_info 获取
        group_id = args.get("group_id") if args else None
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        
        no_cache = args.get("no_cache", False) if args else False
        
        if not group_id:
            raise ValueError("获取群成员列表命令缺少必要参数: group_id")

        group_id = int(group_id)
        if group_id <= 0:
            raise ValueError("群组ID无效")

        return (
            CommandType.GET_GROUP_MEMBER_LIST.value,
            {
                "group_id": group_id,
                "no_cache": bool(no_cache),
            },
        )

    @staticmethod
    @register_command(CommandType.GET_MSG, require_group=False)
    def handle_get_msg_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取消息详情

        Args:
            args: 参数字典 {"message_id": int}
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("获取消息命令缺少参数")

        message_id = args.get("message_id")
        if not message_id:
            raise ValueError("获取消息命令缺少必要参数: message_id")

        message_id = int(message_id)
        if message_id <= 0:
            raise ValueError("消息ID无效")

        return (
            CommandType.GET_MSG.value,
            {"message_id": message_id},
        )

    @staticmethod
    @register_command(CommandType.GET_FORWARD_MSG, require_group=False)
    def handle_get_forward_msg_command(args: Dict[str, Any], group_info: Optional[GroupInfo]) -> Tuple[str, Dict[str, Any]]:
        """获取合并转发消息

        Args:
            args: 参数字典 {"message_id": str}
            group_info: 群聊信息（不使用）

        Returns:
            Tuple[str, Dict[str, Any]]: (action, params)
        """
        if not args:
            raise ValueError("获取合并转发消息命令缺少参数")

        message_id = args.get("message_id")
        if not message_id:
            raise ValueError("获取合并转发消息命令缺少必要参数: message_id")

        return (
            CommandType.GET_FORWARD_MSG.value,
            {"message_id": str(message_id)},
        )
