import re
import time
import json
import asyncio
import websockets as Server
from typing import Tuple, Optional

from src.logger import logger
from src.config import global_config
from src.database import BanUser, db_manager, is_identical
from .qq_emoji_list import qq_face
from . import NoticeType, ACCEPT_FORMAT
from .message_sending import message_send_instance
from .message_handler import message_handler
from maim_message import FormatInfo, UserInfo, GroupInfo, Seg, BaseMessageInfo, MessageBase

from src.utils import (
    get_group_info,
    get_group_member_list, 
    get_member_info,
    get_self_info,
    get_stranger_info,
    read_ban_list,
)

notice_queue: asyncio.Queue[MessageBase] = asyncio.Queue(maxsize=100)
unsuccessful_notice_queue: asyncio.Queue[MessageBase] = asyncio.Queue(maxsize=3)


class NoticeHandler:
    banned_list: list[BanUser] = []  # 当前仍在禁言中的用户列表
    lifted_list: list[BanUser] = []  # 已经自然解除禁言

    def __init__(self):
        self.server_connection: Server.ServerConnection = None

    async def set_server_connection(self, server_connection: Server.ServerConnection) -> None:
        """设置Napcat连接"""
        self.server_connection = server_connection

        while self.server_connection.state != Server.State.OPEN:
            await asyncio.sleep(0.5)
        self.banned_list, self.lifted_list = await read_ban_list(self.server_connection)

        asyncio.create_task(self.auto_lift_detect())
        asyncio.create_task(self.send_notice())
        asyncio.create_task(self.handle_natural_lift())

    def _ban_operation(self, group_id: int, user_id: Optional[int] = None, lift_time: Optional[int] = None) -> None:
        """
        将用户禁言记录添加到self.banned_list中
        如果是全体禁言，则user_id为0
        """
        if user_id is None:
            user_id = 0  # 使用0表示全体禁言
            lift_time = -1
        ban_record = BanUser(user_id=user_id, group_id=group_id, lift_time=lift_time)
        for record in self.banned_list:
            if is_identical(record, ban_record):
                self.banned_list.remove(record)
                self.banned_list.append(ban_record)
                db_manager.create_ban_record(ban_record)  # 作为更新
                return
        self.banned_list.append(ban_record)
        db_manager.create_ban_record(ban_record)  # 添加到数据库

    def _lift_operation(self, group_id: int, user_id: Optional[int] = None) -> None:
        """
        从self.lifted_group_list中移除已经解除全体禁言的群
        """
        if user_id is None:
            user_id = 0  # 使用0表示全体禁言
        ban_record = BanUser(user_id=user_id, group_id=group_id, lift_time=-1)
        self.lifted_list.append(ban_record)
        db_manager.delete_ban_record(ban_record)  # 删除数据库中的记录

    async def handle_notice(self, raw_message: dict) -> None:
        notice_type = raw_message.get("notice_type")
        # message_time: int = raw_message.get("time")
        message_time: float = time.time()  # 应可乐要求，现在是float了

        group_id = raw_message.get("group_id")
        user_id = raw_message.get("user_id")
        target_id = raw_message.get("target_id")

        handled_message: Seg = None
        user_info: UserInfo = None
        system_notice: bool = False

        match notice_type:
            case NoticeType.friend_recall:
                operator_id = raw_message.get("operator_id")
                ts = raw_message.get("time")
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "未知时间"
                logger.info(f"好友 {operator_id} 撤回一条消息")
                logger.info(f"撤回消息ID：{raw_message.get('message_id')}, 撤回时间：{time_str}")
                return
            case NoticeType.group_recall:
                operator_id = raw_message.get("operator_id")
                ts = raw_message.get("time")
                time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "未知时间"
                logger.info(f"群内用户 {operator_id} 撤回一条消息")
                logger.info(f"撤回消息ID：{raw_message.get('message_id')}, 撤回时间：{time_str}")
                return
            case NoticeType.notify:
                sub_type = raw_message.get("sub_type")
                match sub_type:
                    case NoticeType.Notify.poke:
                        if global_config.chat.enable_poke and await message_handler.check_allow_to_chat(
                            user_id, group_id, False, False
                        ):
                            logger.info("处理戳一戳消息")
                            await self.handle_poke_notify(raw_message, group_id, user_id)
                        else:
                            logger.warning("戳一戳消息被禁用，取消戳一戳处理")
                        return
                    case _:
                        logger.warning(f"不支持的notify类型: {notice_type}.{sub_type}")
            case NoticeType.group_ban:
                sub_type = raw_message.get("sub_type")
                match sub_type:
                    # 私聊输入状态（“对方正在输入...”）
                    case "input_status":
                        user_id = raw_message.get("user_id")
                        group_id = raw_message.get("group_id", 0)
                        event_type = raw_message.get("event_type")
                        status_text = raw_message.get("status_text", "")
                        # 仅手机私聊有效
                        if not group_id or group_id == 0:
                            if status_text:
                                logger.info(f"用户 {user_id} {status_text}")
                            else:
                                status_map = {1: "正在输入中", 2: "已刷新聊天页面"}
                                logger.info(f"用户 {user_id} {status_map.get(event_type, '输入状态变更')}")
                        return
                    case NoticeType.GroupBan.ban:
                        if not await message_handler.check_allow_to_chat(user_id, group_id, True, False):
                            return None
                        logger.info("处理群禁言")
                        handled_message, user_info = await self.handle_ban_notify(raw_message, group_id)
                        system_notice = True
                    case NoticeType.GroupBan.lift_ban:
                        if not await message_handler.check_allow_to_chat(user_id, group_id, True, False):
                            return None
                        logger.info("处理解除群禁言")
                        handled_message, user_info = await self.handle_lift_ban_notify(raw_message, group_id)
                        system_notice = True
                    case _:
                        logger.warning(f"不支持的group_ban类型: {notice_type}.{sub_type}")
            case "group_admin":
                sub_type = raw_message.get("sub_type")
                group_id = raw_message.get("group_id")
                user_id = raw_message.get("user_id")
                self_id = raw_message.get("self_id")
                if user_id and user_id != 0:
                    member_info = await get_member_info(self.server_connection, group_id, user_id)
                    nickname = member_info.get("nickname") if member_info and member_info.get("nickname") else "QQ用户"
                else:
                    nickname = "系统"
                if user_id == 0:
                    try:
                        member_list = await get_group_member_list(self.server_connection, group_id)
                        if member_list and isinstance(member_list, list):
                            owner = next((m for m in member_list if m.get("role") == "owner"), None)
                            if owner:
                                owner_id = owner.get("user_id")
                                owner_name = owner.get("nickname") or owner.get("card") or str(owner.get("user_id"))
                                text = f"群主变更为 {owner_name}"
                                logger.info(f"群 {group_id} 群主变更为 {owner_id}")
                            else:
                                text = "群主变更"
                                logger.error(f"群 {group_id} 群主变更（未找到新群主）")
                        else:
                            text = "群主变更"
                            logger.error(f"群 {group_id} 查询群成员列表失败")
                    except Exception as e:
                        text = "群主变更"
                        logger.error(f"群 {group_id} 查询新群主失败: {e}")
                elif user_id == self_id:
                    if sub_type == "set":
                        text = "（你）被设置为管理员"
                    elif sub_type == "unset":
                        text = "（你）被取消管理员"
                    else:
                        text = f"管理员状态变更: {sub_type}"
                    logger.info(f"群 {group_id} Bot{text.replace('（你）', '')}")
                else:
                    if sub_type == "set":
                        text = "被设置为管理员"
                    elif sub_type == "unset":
                        text = "被取消管理员"
                    else:
                        text = f"管理员状态变更: {sub_type}"
                    logger.info(f"群 {group_id} 用户 {user_id} {text}")
                handled_message = Seg(type="text", data=text)
                user_info = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=user_id,
                    user_nickname=nickname,
                    user_cardname=None,
                )
                system_notice = True
            case "group_increase":
                sub_type = raw_message.get("sub_type")
                group_id = raw_message.get("group_id")
                user_id = raw_message.get("user_id")
                operator_id = raw_message.get("operator_id")
                self_id = raw_message.get("self_id")
                member_info = await get_member_info(self.server_connection, group_id, user_id)
                nickname = member_info.get("nickname") if member_info and member_info.get("nickname") else "QQ用户"
                operator_name = "系统"
                if operator_id and operator_id != 0:
                    operator_info = await get_member_info(self.server_connection, group_id, operator_id)
                    if operator_info and operator_info.get("nickname"):
                        operator_name = operator_info.get("nickname")
                    else:
                        operator_name = str(operator_id)
                if user_id == self_id:
                    if sub_type == "invite":
                        text = f"（你）被 {operator_name} 邀请加入"
                        logger.info(f"群 {group_id} Bot被 {operator_id} 邀请加入")
                    elif sub_type == "approve":
                        text = f"（你）通过 {operator_name} 审批加入"
                        logger.info(f"群 {group_id} Bot通过 {operator_id} 审批加入")
                    else:
                        text = f"（你）加入群（方式: {sub_type}）"
                        logger.info(f"群 {group_id} Bot{text.replace('（你）', '')}")
                else:
                    if sub_type == "invite":
                        text = f"被 {operator_name} 邀请加入"
                        logger.info(f"群 {group_id} 用户 {user_id} 被 {operator_id} 邀请加入")
                    elif sub_type == "approve":
                        text = f"通过 {operator_name} 审批加入"
                        logger.info(f"群 {group_id} 用户 {user_id} 被 {operator_id} 审批加入")
                    else:
                        text = f"加入群（方式: {sub_type}）"
                        logger.info(f"群 {group_id} 用户 {user_id} {text}")
                handled_message = Seg(type="text", data=text)
                user_info = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=user_id,
                    user_nickname=nickname,
                    user_cardname=None,
                )
                system_notice = True
            case "group_decrease":
                sub_type = raw_message.get("sub_type")
                group_id = raw_message.get("group_id")
                user_id = raw_message.get("user_id")
                operator_id = raw_message.get("operator_id")
                self_id = raw_message.get("self_id")
                member_info = await get_stranger_info(self.server_connection, user_id)
                nickname = member_info.get("nickname") if member_info and member_info.get("nickname") else "QQ用户"
                operator_name = "系统"
                if operator_id and operator_id != 0:
                    operator_info = await get_member_info(self.server_connection, group_id, operator_id)
                    if operator_info and operator_info.get("nickname"):
                        operator_name = operator_info.get("nickname")
                    else:
                        operator_name = str(operator_id)
                if sub_type == "disband":
                    nickname = operator_name
                    text = "群已被解散"
                    logger.info(f"群 {group_id} 已被 {operator_id} 解散")
                elif user_id == self_id:
                    if sub_type == "leave":
                        text = "（你）退出了群"
                        logger.info(f"群 {group_id} Bot退出了群")
                    elif sub_type == "kick":
                        text = f"（你）被 {operator_name} 移出"
                        logger.info(f"群 {group_id} Bot被 {operator_id} 移出")
                    else:
                        text = f"（你）离开群（方式: {sub_type}）"
                        logger.info(f"群 {group_id} Bot离开群（方式: {sub_type}）")
                else:
                    if sub_type == "leave":
                        text = f"退出了群"
                        logger.info(f"群 {group_id} 用户 {user_id} {text}")
                    elif sub_type == "kick":
                        text = f"被 {operator_name} 移出"
                        logger.info(f"群 {group_id} 用户 {user_id} 被 {operator_id} 移出")
                    else:
                        text = f"离开群（方式: {sub_type}）"
                        logger.info(f"群 {group_id} 用户 {user_id} {text}")
                handled_message = Seg(type="text", data=text)
                user_info = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=user_id,
                    user_nickname=nickname,
                    user_cardname=None,
                )
                system_notice = True
            case "essence":
                self_id = raw_message.get("self_id")
                group_id = raw_message.get("group_id")
                sub_type = raw_message.get("sub_type")
                message_id = raw_message.get("message_id")
                operator_id = raw_message.get("operator_id")
                sender_id = raw_message.get("sender_id", 0)
                user_id = raw_message.get("user_id", 0)
                operator_name = "系统"
                if operator_id and operator_id != 0:
                    operator_info = await get_member_info(self.server_connection, group_id, operator_id)
                    if operator_info:
                        operator_name = (
                            operator_info.get("nickname")
                            or operator_info.get("card")
                            or str(operator_id)
                        )
                if sub_type == "add":
                    if sender_id == 0:
                        text = f"将 一条消息（ID: {message_id}）设为精华"
                        logger.info(f"群 {group_id} 消息（ID: {message_id}）被 {operator_id} 设为精华")
                    else:
                        if user_id == self_id:
                            text = f"将 {sender_name}（你）的消息设为精华"
                            logger.info(f"群 {group_id} Bot的消息被 {operator_id} 设为精华")
                        else:
                            text = f"将 {sender_name} 的消息设为精华"
                            logger.info(f"群 {group_id} 用户 {sender_id} 的消息被 {operator_id} 设为精华")
                else:
                    text = f"精华消息事件：{sub_type}"
                logger.info(f"群 {group_id} 消息（ID: {message_id}）被 {operator_id} 设为精华")
                handled_message = Seg(type="text", data=text)
                user_info = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=operator_id,
                    user_nickname=operator_name,
                    user_cardname=None,
                )
                system_notice = True
            case "group_card":
                group_id = raw_message.get("group_id")
                user_id = raw_message.get("user_id")
                self_id = raw_message.get("self_id")
                member_info = await get_member_info(self.server_connection, group_id, user_id)
                nickname = member_info.get("nickname") if member_info and member_info.get("nickname") else str(user_id)
                old_card = raw_message.get("card_old") or nickname
                new_card = raw_message.get("card_new") or "(默认)"
                if new_card == "(默认)" or new_card == nickname:
                    return
                if user_id == self_id:
                    text = f"（你）群卡片被修改为：{old_card} → {new_card}"
                    logger.info(f"群 {group_id} Bot的群名片被修改为：{old_card} → {new_card}")
                else:
                    text = f"群卡片被修改为：{old_card} → {new_card}"
                    logger.info(f"群 {group_id} 用户 {user_id} 的群名片被修改为：{old_card} → {new_card}")
                handled_message = Seg(type="text", data=text)
                user_info = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=user_id,
                    user_nickname=nickname,
                    user_cardname=new_card,
                )
                system_notice = True
            case "group_msg_emoji_like":
                group_id = raw_message.get("group_id")
                user_id = raw_message.get("user_id")
                likes = raw_message.get("likes", [])
                member_info = await get_member_info(self.server_connection, group_id, user_id)
                nickname = member_info.get("nickname") if member_info and member_info.get("nickname") else str(user_id)
                emoji_list = []
                for like in likes:
                    emoji_id = str(like.get("emoji_id"))
                    count = like.get("count", 1)
                    if emoji_id in qq_face:
                        emoji_text = qq_face[emoji_id]
                    else:
                        emoji_text = f"[未知表情 {emoji_id}]"
                        logger.warning(f"不支持的表情：{emoji_id}")
                    emoji_list.append(f"{emoji_text} ×{count}")
                emoji_text_joined = "，".join(emoji_list) if emoji_list else "无"
                text = f"回应了你的消息：{emoji_text_joined}"
                logger.info(f"群 {group_id} 用户 {user_id} 回应了你的消息：{emoji_text_joined}")
                handled_message = Seg(type="text", data=text)
                user_info = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=user_id,
                    user_nickname=nickname,
                    user_cardname=None,
                )
                system_notice = True
            case _:
                logger.warning(f"不支持的notice类型: {notice_type}")
                return None
        if not handled_message or not user_info:
            logger.warning("notice处理失败或不支持")
            return None

        group_info: GroupInfo = None
        if group_id:
            fetched_group_info = await get_group_info(self.server_connection, group_id)
            group_name: str = None
            if fetched_group_info:
                group_name = fetched_group_info.get("group_name")
            else:
                logger.warning("无法获取notice消息所在群的名称")
            group_info = GroupInfo(
                platform=global_config.maibot_server.platform_name,
                group_id=group_id,
                group_name=group_name,
            )

        message_info: BaseMessageInfo = BaseMessageInfo(
            platform=global_config.maibot_server.platform_name,
            message_id="notice",
            time=message_time,
            user_info=user_info,
            group_info=group_info,
            template_info=None,
            format_info=FormatInfo(
                content_format=["text", "notify"],
                accept_format=ACCEPT_FORMAT,
            ),
            additional_config={"target_id": target_id},  # 在这里塞了一个target_id，方便mmc那边知道被戳的人是谁
        )

        message_base: MessageBase = MessageBase(
            message_info=message_info,
            message_segment=handled_message,
            raw_message=json.dumps(raw_message),
        )

        if system_notice:
            await self.put_notice(message_base)
        else:
            logger.info("发送到Maibot处理通知信息")
            await message_send_instance.message_send(message_base)

    async def handle_poke_notify(
        self, raw_message: dict, group_id: int, user_id: int
    ) -> Tuple[Seg | None, UserInfo | None]:
        # sourcery skip: merge-comparisons, merge-duplicate-blocks, remove-redundant-if, remove-unnecessary-else, swap-if-else-branches
        self_info: dict = await get_self_info(self.server_connection)
        if not self_info:
            logger.error("自身信息获取失败")
            return None, None

        self_id = raw_message.get("self_id")
        target_id = raw_message.get("target_id")
        sender_id = raw_message.get("sender_id") or user_id
        raw_info: list = raw_message.get("raw_info")

        if group_id:
            sender_info = await get_member_info(self.server_connection, group_id, sender_id)
            target_info = await get_member_info(self.server_connection, group_id, target_id)
        else:
            sender_info = await get_stranger_info(self.server_connection, sender_id)
            target_info = await get_stranger_info(self.server_connection, target_id)

        target_name = target_info.get("nickname") if target_info and target_info.get("nickname") else "未知目标"
        sender_name = sender_info.get("nickname") if sender_info and sender_info.get("nickname") else "QQ用户"

        # 解析 raw_info 文本
        text_str = ""
        if isinstance(raw_info, list) and len(raw_info) > 0:
            try:
                parts = []
                for item in raw_info:
                    if isinstance(item, dict):
                        val = (item.get("txt") or item.get("name") or "").strip()
                        if val and not all(ch in " \n\t" for ch in val):
                            parts.append(val)
                text_str = "".join(parts).strip()
            except Exception as e:
                logger.warning(f"原始 raw_info 解析失败: {e}")
        else:
            text_str = ""

        # ---------------------
        # 识别动作（仅识别开头的、前后相同的 “X了X”）
        # 例：拍了拍、戳了戳、摸了摸；不会识别“用了它”、“看了看他”等
        # ---------------------
        # 只在文本最前面查找一次动作
        m = re.match(r'^\s*([\u4e00-\u9fa5])了\1', text_str)
        if m:
            action = m.group(0)  # 如 “拍了拍”
            has_action = True
            text_str = text_str[len(action):].strip()  # 移除前缀动作
        else:
            action = "拍了拍"
            has_action = False

        # 剩余部分作为描述性后缀
        suffix = text_str.strip()

        # 生成标准格式句子
        text_str = f"{action} {target_name}{(' ' + suffix) if suffix else ''}".strip()
        text_str = " ".join(text_str.split())

        # 构造消息段和用户信息
        seg_data: Seg = Seg(type="text", data=text_str)
        user_info: UserInfo = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id,
            user_nickname=sender_name,
            user_cardname=sender_info.get("card") if sender_info else None,
        )

        # 提前过滤事件（空对象防御）
        if not seg_data or not user_info:
            return None, None

        # 判断是否需要发送（别人戳Bot / Bot戳别人 / 别人戳别人）
        send_group_info = None
        if group_id:
            fetched_group_info = await get_group_info(self.server_connection, group_id)
            group_name = fetched_group_info.get("group_name") if fetched_group_info else None
            send_group_info = GroupInfo(
                platform=global_config.maibot_server.platform_name,
                group_id=group_id,
                group_name=group_name,
            )

        await message_send_instance.message_send(
            MessageBase(
                message_info=BaseMessageInfo(
                    platform=global_config.maibot_server.platform_name,
                    message_id="poke",
                    time=time.time(),
                    user_info=user_info,
                    group_info=send_group_info,
                    template_info=None,
                    format_info=FormatInfo(
                        content_format=["text"],
                        accept_format=ACCEPT_FORMAT,
                    ),
                ),
                message_segment=seg_data,
                raw_message=json.dumps(raw_message),
            )
        )

        return seg_data, user_info

    async def handle_ban_notify(self, raw_message: dict, group_id: int) -> Tuple[Seg, UserInfo] | Tuple[None, None]:
        if not group_id:
            logger.error("群ID不能为空，无法处理禁言通知")
            return None, None

        # 计算user_info
        operator_id = raw_message.get("operator_id")
        operator_nickname: str = None
        operator_cardname: str = None

        member_info: dict = await get_member_info(self.server_connection, group_id, operator_id)
        if member_info:
            operator_nickname = member_info.get("nickname")
            operator_cardname = member_info.get("card")
        else:
            logger.warning("无法获取禁言执行者的昵称，消息可能会无效")
            operator_nickname = "QQ用户"

        operator_info: UserInfo = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=operator_id,
            user_nickname=operator_nickname,
            user_cardname=operator_cardname,
        )

        # 计算Seg
        user_id = raw_message.get("user_id")
        banned_user_info: UserInfo = None
        user_nickname: str = "QQ用户"
        user_cardname: str = None
        sub_type: str = None

        duration = raw_message.get("duration")
        if duration is None:
            logger.error("禁言时长不能为空，无法处理禁言通知")
            return None, None

        if user_id == 0:  # 为全体禁言
            sub_type: str = "whole_ban"
            self._ban_operation(group_id)
        else:  # 为单人禁言
            # 获取被禁言人的信息
            sub_type: str = "ban"
            fetched_member_info: dict = await get_member_info(self.server_connection, group_id, user_id)
            if fetched_member_info:
                user_nickname = fetched_member_info.get("nickname")
                user_cardname = fetched_member_info.get("card")
            banned_user_info: UserInfo = UserInfo(
                platform=global_config.maibot_server.platform_name,
                user_id=user_id,
                user_nickname=user_nickname,
                user_cardname=user_cardname,
            )
            self._ban_operation(group_id, user_id, int(time.time() + duration))

        seg_data: Seg = Seg(
            type="notify",
            data={
                "sub_type": sub_type,
                "duration": duration,
                "banned_user_info": banned_user_info.to_dict() if banned_user_info else None,
            },
        )

        return seg_data, operator_info

    async def handle_lift_ban_notify(
        self, raw_message: dict, group_id: int
    ) -> Tuple[Seg, UserInfo] | Tuple[None, None]:
        if not group_id:
            logger.error("群ID不能为空，无法处理解除禁言通知")
            return None, None

        # 计算user_info
        operator_id = raw_message.get("operator_id")
        operator_nickname: str = None
        operator_cardname: str = None

        member_info: dict = await get_member_info(self.server_connection, group_id, operator_id)
        if member_info:
            operator_nickname = member_info.get("nickname")
            operator_cardname = member_info.get("card")
        else:
            logger.warning("无法获取解除禁言执行者的昵称，消息可能会无效")
            operator_nickname = "QQ用户"

        operator_info: UserInfo = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=operator_id,
            user_nickname=operator_nickname,
            user_cardname=operator_cardname,
        )

        # 计算Seg
        sub_type: str = None
        user_nickname: str = "QQ用户"
        user_cardname: str = None
        lifted_user_info: UserInfo = None

        user_id = raw_message.get("user_id")
        if user_id == 0:  # 全体禁言解除
            sub_type = "whole_lift_ban"
            self._lift_operation(group_id)
        else:  # 单人禁言解除
            sub_type = "lift_ban"
            # 获取被解除禁言人的信息
            fetched_member_info: dict = await get_member_info(self.server_connection, group_id, user_id)
            if fetched_member_info:
                user_nickname = fetched_member_info.get("nickname")
                user_cardname = fetched_member_info.get("card")
            else:
                logger.warning("无法获取解除禁言消息发送者的昵称，消息可能会无效")
            lifted_user_info: UserInfo = UserInfo(
                platform=global_config.maibot_server.platform_name,
                user_id=user_id,
                user_nickname=user_nickname,
                user_cardname=user_cardname,
            )
            self._lift_operation(group_id, user_id)

        seg_data: Seg = Seg(
            type="notify",
            data={
                "sub_type": sub_type,
                "lifted_user_info": lifted_user_info.to_dict() if lifted_user_info else None,
            },
        )
        return seg_data, operator_info

    async def put_notice(self, message_base: MessageBase) -> None:
        """
        将处理后的通知消息放入通知队列
        """
        if notice_queue.full() or unsuccessful_notice_queue.full():
            logger.warning("通知队列已满，可能是多次发送失败，消息丢弃")
        else:
            await notice_queue.put(message_base)

    async def handle_natural_lift(self) -> None:
        while True:
            if len(self.lifted_list) != 0:
                lift_record = self.lifted_list.pop()
                group_id = lift_record.group_id
                user_id = lift_record.user_id

                db_manager.delete_ban_record(lift_record)  # 从数据库中删除禁言记录

                seg_message: Seg = await self.natural_lift(group_id, user_id)

                fetched_group_info = await get_group_info(self.server_connection, group_id)
                group_name: str = None
                if fetched_group_info:
                    group_name = fetched_group_info.get("group_name")
                else:
                    logger.warning("无法获取notice消息所在群的名称")
                group_info = GroupInfo(
                    platform=global_config.maibot_server.platform_name,
                    group_id=group_id,
                    group_name=group_name,
                )

                message_info: BaseMessageInfo = BaseMessageInfo(
                    platform=global_config.maibot_server.platform_name,
                    message_id="notice",
                    time=time.time(),
                    user_info=None,  # 自然解除禁言没有操作者
                    group_info=group_info,
                    template_info=None,
                    format_info=None,
                )

                message_base: MessageBase = MessageBase(
                    message_info=message_info,
                    message_segment=seg_message,
                    raw_message=json.dumps(
                        {
                            "post_type": "notice",
                            "notice_type": "group_ban",
                            "sub_type": "lift_ban",
                            "group_id": group_id,
                            "user_id": user_id,
                            "operator_id": None,  # 自然解除禁言没有操作者
                        }
                    ),
                )

                await self.put_notice(message_base)
                await asyncio.sleep(0.5)  # 确保队列处理间隔
            else:
                await asyncio.sleep(5)  # 每5秒检查一次

    async def natural_lift(self, group_id: int, user_id: int) -> Seg | None:
        if not group_id:
            logger.error("群ID不能为空，无法处理解除禁言通知")
            return None

        if user_id == 0:  # 理论上永远不会触发
            return Seg(
                type="notify",
                data={
                    "sub_type": "whole_lift_ban",
                    "lifted_user_info": None,
                },
            )

        user_nickname: str = "QQ用户"
        user_cardname: str = None
        fetched_member_info: dict = await get_member_info(self.server_connection, group_id, user_id)
        if fetched_member_info:
            user_nickname = fetched_member_info.get("nickname")
            user_cardname = fetched_member_info.get("card")

        lifted_user_info: UserInfo = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=user_id,
            user_nickname=user_nickname,
            user_cardname=user_cardname,
        )

        return Seg(
            type="notify",
            data={
                "sub_type": "lift_ban",
                "lifted_user_info": lifted_user_info.to_dict(),
            },
        )

    async def auto_lift_detect(self) -> None:
        while True:
            if len(self.banned_list) == 0:
                await asyncio.sleep(5)
                continue
            for ban_record in self.banned_list:
                if ban_record.user_id == 0 or ban_record.lift_time == -1:
                    continue
                if ban_record.lift_time <= int(time.time()):
                    # 触发自然解除禁言
                    logger.info(f"检测到用户 {ban_record.user_id} 在群 {ban_record.group_id} 的禁言已解除")
                    self.lifted_list.append(ban_record)
                    self.banned_list.remove(ban_record)
            await asyncio.sleep(5)

    async def send_notice(self) -> None:
        """
        发送通知消息到Napcat
        """
        while True:
            if not unsuccessful_notice_queue.empty():
                to_be_send: MessageBase = await unsuccessful_notice_queue.get()
                try:
                    send_status = await message_send_instance.message_send(to_be_send)
                    if send_status:
                        unsuccessful_notice_queue.task_done()
                    else:
                        await unsuccessful_notice_queue.put(to_be_send)
                except Exception as e:
                    logger.error(f"发送通知消息失败: {str(e)}")
                    await unsuccessful_notice_queue.put(to_be_send)
                await asyncio.sleep(1)
                continue
            to_be_send: MessageBase = await notice_queue.get()
            try:
                send_status = await message_send_instance.message_send(to_be_send)
                if send_status:
                    notice_queue.task_done()
                else:
                    await unsuccessful_notice_queue.put(to_be_send)
            except Exception as e:
                logger.error(f"发送通知消息失败: {str(e)}")
                await unsuccessful_notice_queue.put(to_be_send)
            await asyncio.sleep(1)


notice_handler = NoticeHandler()
