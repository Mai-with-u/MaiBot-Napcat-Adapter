import time
import json
import asyncio
import websockets as Server
from typing import Tuple, Optional

from src.logger import logger
from src.config import global_config
from src.database import BanUser, db_manager, is_identical
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
                logger.info("好友撤回一条消息")
                logger.info(f"撤回消息ID：{raw_message.get('message_id')}, 撤回时间：{raw_message.get('time')}")
                logger.warning("暂时不支持撤回消息处理")
            case NoticeType.group_recall:
                logger.info("群内用户撤回一条消息")
                logger.info(f"撤回消息ID：{raw_message.get('message_id')}, 撤回时间：{raw_message.get('time')}")
                logger.warning("暂时不支持撤回消息处理")
            case NoticeType.notify:
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
                    case NoticeType.Notify.poke:
                        if global_config.chat.enable_poke and await message_handler.check_allow_to_chat(
                            user_id, group_id, False, False
                        ):
                            logger.info("处理戳了戳消息")
                            handled_message, user_info, is_target_self = await self.handle_poke_notify(
                                raw_message, group_id, user_id
                            )
                            # 提前过滤事件（bot戳别人/别人戳别人）
                            if not handled_message or not user_info:
                                return
                            if handled_message and user_info:
                                if is_target_self:
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
                                            message_segment=handled_message,
                                            raw_message=json.dumps(raw_message),
                                        )
                                    )
                                    return
                                else:
                                    logger.info("忽略其他事件")
                                    return
                        else:
                            logger.warning("戳了戳消息被禁用，取消戳了戳处理")
                            return
                    case _:
                        logger.warning(f"不支持的notify类型: {notice_type}.{sub_type}")
            case NoticeType.group_ban:
                sub_type = raw_message.get("sub_type")
                match sub_type:
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
                group_id = raw_message.get("group_id")
                sub_type = raw_message.get("sub_type")
                message_id = raw_message.get("message_id")
                operator_id = raw_message.get("operator_id")
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
                    text = f"{operator_name} 将 一条消息（ID: {message_id}）设为精华"
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
        raw_info: list = raw_message.get("raw_info")

        if group_id:
            user_qq_info: dict = await get_member_info(self.server_connection, group_id, user_id)
        else:
            user_qq_info: dict = await get_stranger_info(self.server_connection, user_id)

        user_name = user_qq_info.get("nickname") if user_qq_info and user_qq_info.get("nickname") else "QQ用户"
        user_cardname = user_qq_info.get("card") if user_qq_info else None

        if target_id == self_id:
            # 别人戳我 → 触发回应
            display_name = user_name
            target_name = self_info.get("nickname") or "我"

            first_txt: str = "戳了戳"
            second_txt: str = ""
            try:
                first_txt = raw_info[2].get("txt", "戳了戳")
                second_txt = raw_info[4].get("txt", "")
            except Exception as e:
                logger.warning(f"解析戳一戳消息失败: {str(e)}，将使用默认文本")

            text_str = f"{first_txt}{target_name}{second_txt}（这是QQ的一个功能，用于提及某人，但没那么明显）"
            seg_data: Seg = Seg(type="text", data=text_str)

            user_info: UserInfo = UserInfo(
                platform=global_config.maibot_server.platform_name,
                user_id=user_id,
                user_nickname=user_name,
                user_cardname=user_cardname,
            )
            return seg_data, user_info, True

        elif user_id == self_id:
            # bot戳别人 → 忽略，防止循环
            return None, None, False

        else:
            # 群内用户互戳、私聊他人戳他人 → 忽略
            return None, None, False

    async def handle_ban_notify(self, raw_message: dict, group_id: int) -> Tuple[Seg, UserInfo] | Tuple[None, None]:
        if not group_id:
            logger.error("群ID不能为空，无法处理禁言通知")
            return None, None

        # 计算user_info
        self_id = raw_message.get("self_id")
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

        # 生成可读 text 段
        fetched_group_info = await get_group_info(self.server_connection, group_id)
        group_name = fetched_group_info.get("group_name") if fetched_group_info else None

        # 全体禁言时不显示时间
        if duration == -1 or user_id == 0:
            human_time = ""
        else:
            # 智能格式化时长（天 / 时 / 分 / 秒）
            days = duration // 86400
            hours = (duration % 86400) // 3600
            mins = (duration % 3600) // 60
            secs = duration % 60
            parts = []
            if days > 0:
                parts.append(f"{days} 天")
            if hours > 0:
                parts.append(f"{hours} 小时")
            if mins > 0:
                parts.append(f"{mins} 分钟")
            if secs > 0:
                parts.append(f"{secs} 秒")
            human_time = " ".join(parts) if parts else "0 秒"

        display_target = banned_user_info.user_nickname if banned_user_info else None

        if user_id == self_id:
            display_target = f"{display_target} (我)"
            user = "Bot"
        else:
            user = f"用户 {user_id}"

        if user_id == 0:
            text_str = "开启了群禁言"
            logger.info(f"群 {group_id} {text_str}")
        elif human_time:
            text_str = f"禁言了 {display_target}（{human_time}）"
            logger.info(f"群 {group_id} {user} 被 {operator_id} 禁言（{human_time}）")
        else:
            text_str = f"禁言了 {display_target}"
            logger.info(f"群 {group_id} {user} 被 {operator_id} 禁言")

        text_seg = Seg(type="text", data=text_str)

        # 合并为 seglist：既有 notify（供程序用），也有 text（供所见日志/显示）
        notify_seg = seg_data
        return Seg(type="seglist", data=[notify_seg, text_seg]), operator_info

    async def handle_lift_ban_notify(
        self, raw_message: dict, group_id: int
    ) -> Tuple[Seg, UserInfo] | Tuple[None, None]:
        if not group_id:
            logger.error("群ID不能为空，无法处理解除禁言通知")
            return None, None

        # 计算user_info
        self_id = raw_message.get("self_id")
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

            # 防止自然检测重复触发：从banned_list中移除该用户
            for record in list(self.banned_list):
                if record.user_id == user_id and record.group_id == group_id:
                    self.banned_list.remove(record)
                    break

            # 同时也避免lifted_list重复添加
            for record in list(self.lifted_list):
                if record.user_id == user_id and record.group_id == group_id:
                    self.lifted_list.remove(record)
                    break

        seg_data: Seg = Seg(
            type="notify",
            data={
                "sub_type": sub_type,
                "lifted_user_info": lifted_user_info.to_dict() if lifted_user_info else None,
            },
        )
        
        # 可读 text 段
        fetched_group_info = await get_group_info(self.server_connection, group_id)
        group_name = fetched_group_info.get("group_name") if fetched_group_info else None
        display_target = lifted_user_info.user_nickname if lifted_user_info else None
        if display_target and user_id == self_id:
            display_target = f"{display_target} (我)"
        if not display_target:
            text_str = "解除了群禁言"
            logger.info(f"群 {group_id} {text_str}")
        else:
            text_str = f"{display_target} 已被解除禁言"
            logger.info(f"群 {group_id} 已解除 {user_id} 的禁言")
        text_seg = Seg(type="text", data=text_str)
        notify_seg = seg_data
        return Seg(type="seglist", data=[notify_seg, text_seg]), operator_info

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

                # 防御：防止同一用户重复自然解除
                for record in list(self.lifted_list):
                    if record.user_id == user_id and record.group_id == group_id:
                        logger.debug(f"检测到重复解除禁言请求（群{group_id} 用户{user_id}），跳过。")
                        continue

                # 跳过全体禁言记录
                if lift_record.user_id == 0 or lift_record.lift_time == -1:
                    continue

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

                system_user = UserInfo(
                    platform=global_config.maibot_server.platform_name,
                    user_id=0,
                    user_nickname="系统",
                    user_cardname=None,
                )
                
                message_info: BaseMessageInfo = BaseMessageInfo(
                    platform=global_config.maibot_server.platform_name,
                    message_id="notice",
                    time=time.time(),
                    user_info=system_user,  # 自然解除禁言没有操作者
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

        self_info = await get_self_info(self.server_connection)
        self_id = self_info.get("user_id") if self_info else None
        if self_id and user_id == self_id:
            user_nickname = f"{user_nickname} (我)"
        
        lifted_user_info: UserInfo = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=user_id,
            user_nickname=user_nickname,
            user_cardname=user_cardname,
        )

        fetched_group_info = await get_group_info(self.server_connection, group_id)
        group_name = fetched_group_info.get("group_name") if fetched_group_info else None
        notify_seg = Seg(
            type="notify",
            data={
                "sub_type": "lift_ban",
                "lifted_user_info": lifted_user_info.to_dict(),
            },
        )
        text_seg = Seg(type="text", data=f"解除了 {user_nickname} 的禁言")
        logger.info(f"群 {group_id} 用户 {user_id} 的禁言被系统解除")
        return Seg(type="seglist", data=[notify_seg, text_seg])

    async def auto_lift_detect(self) -> None:
        while True:
            self_info = await get_self_info(self.server_connection)
            self_id = self_info.get("user_id") if self_info else None
            if len(self.banned_list) == 0:
                await asyncio.sleep(5)
                continue
            for ban_record in list(self.banned_list):
                if ban_record.user_id == 0 or ban_record.lift_time == -1:
                    continue
                if ban_record.lift_time <= int(time.time()):
                    if ban_record.user_id == self_id:
                        logger.info(f"检测到 Bot 自身在群 {ban_record.group_id} 的禁言已解除")
                    else:
                        logger.info(f"检测到用户 {ban_record.user_id} 在群 {ban_record.group_id} 的禁言已解除")
                    self.lifted_list.append(ban_record)
                    self.banned_list.remove(ban_record)
            await asyncio.sleep(5)

    async def send_notice(self) -> None:
        """
        发送通知消息到Napcat
        """
        while True:
            try:
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
            except asyncio.CancelledError:
                logger.warning("send_notice 任务被取消，安全退出循环")
                break
            except Exception as e:
                logger.error(f"通知循环出现异常: {e}")
                await asyncio.sleep(3)


notice_handler = NoticeHandler()
