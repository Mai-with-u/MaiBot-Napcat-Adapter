"""
配置管理器 - 处理 ChatConfig 的读写
"""

import tomlkit
from typing import Literal, List, Dict, Any
from src.config import global_config
from src.logger import logger

CONFIG_FILE_PATH = "config.toml"


def get_chat_config() -> Dict[str, Any]:
    """获取当前 ChatConfig 配置"""
    chat = global_config.chat
    return {
        "group_list_type": chat.group_list_type,
        "group_list": list(chat.group_list),
        "private_list_type": chat.private_list_type,
        "private_list": list(chat.private_list),
    }


def update_group_list_type(value: Literal["whitelist", "blacklist"]) -> bool:
    """更新群聊列表类型"""
    try:
        global_config.chat.group_list_type = value
        return True
    except Exception as e:
        logger.error(f"更新 group_list_type 失败: {e}")
        return False


def update_group_list(value: List[int]) -> bool:
    """更新群聊列表"""
    try:
        global_config.chat.group_list = value
        return True
    except Exception as e:
        logger.error(f"更新 group_list 失败: {e}")
        return False


def update_private_list_type(value: Literal["whitelist", "blacklist"]) -> bool:
    """更新私聊列表类型"""
    try:
        global_config.chat.private_list_type = value
        return True
    except Exception as e:
        logger.error(f"更新 private_list_type 失败: {e}")
        return False


def update_private_list(value: List[int]) -> bool:
    """更新私聊列表"""
    try:
        global_config.chat.private_list = value
        return True
    except Exception as e:
        logger.error(f"更新 private_list 失败: {e}")
        return False


def save_config_to_file() -> bool:
    """将当前配置保存到文件"""
    try:
        # 读取现有配置文件以保留注释和格式
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            config_doc = tomlkit.load(f)

        # 更新 chat 配置
        if "chat" not in config_doc:
            config_doc["chat"] = tomlkit.table()

        config_doc["chat"]["group_list_type"] = global_config.chat.group_list_type
        config_doc["chat"]["group_list"] = global_config.chat.group_list
        config_doc["chat"]["private_list_type"] = global_config.chat.private_list_type
        config_doc["chat"]["private_list"] = global_config.chat.private_list

        # 写回文件
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(config_doc))

        logger.info("[WebUI] 配置已保存到文件")
        return True
    except Exception as e:
        logger.error(f"[WebUI] 保存配置到文件失败: {e}")
        return False

