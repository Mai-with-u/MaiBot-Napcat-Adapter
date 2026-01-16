from enum import Enum
import tomlkit
import os
from .logger import logger


class CommandType(Enum):
    """命令类型"""

    # 操作类命令
    GROUP_BAN = "set_group_ban"  # 禁言用户
    GROUP_WHOLE_BAN = "set_group_whole_ban"  # 群全体禁言
    GROUP_KICK = "set_group_kick"  # 踢出群聊
    GROUP_KICK_MEMBERS = "set_group_kick_members"  # 批量踢出群成员
    SET_GROUP_NAME = "set_group_name"  # 设置群名
    SEND_POKE = "send_poke"  # 戳一戳
    DELETE_MSG = "delete_msg"  # 撤回消息
    AI_VOICE_SEND = "send_group_ai_record"  # 发送群AI语音
    SET_MSG_EMOJI_LIKE = "set_msg_emoji_like"  # 给消息贴表情
    SET_QQ_PROFILE = "set_qq_profile"  # 设置账号信息
    
    # 查询类命令
    GET_LOGIN_INFO = "get_login_info"  # 获取登录号信息
    GET_STRANGER_INFO = "get_stranger_info"  # 获取陌生人信息
    GET_FRIEND_LIST = "get_friend_list"  # 获取好友列表
    GET_GROUP_INFO = "get_group_info"  # 获取群信息
    GET_GROUP_DETAIL_INFO = "get_group_detail_info"  # 获取群详细信息
    GET_GROUP_LIST = "get_group_list"  # 获取群列表
    GET_GROUP_AT_ALL_REMAIN = "get_group_at_all_remain"  # 获取群@全体成员剩余次数
    GET_GROUP_MEMBER_INFO = "get_group_member_info"  # 获取群成员信息
    GET_GROUP_MEMBER_LIST = "get_group_member_list"  # 获取群成员列表
    GET_MSG = "get_msg"  # 获取消息
    GET_FORWARD_MSG = "get_forward_msg"  # 获取合并转发消息

    def __str__(self) -> str:
        return self.value


pyproject_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")
toml_data = tomlkit.parse(open(pyproject_path, "r", encoding="utf-8").read())
version = toml_data["project"]["version"]
logger.info(f"版本\n\nMaiBot-Napcat-Adapter 版本: {version}\n喜欢的话点个star喵~\n")
