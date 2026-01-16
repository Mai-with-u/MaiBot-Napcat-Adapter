# Command Arguments

```python
Seg.type = "command"
```

所有命令执行后都会通过自定义消息类型 `command_response` 返回响应，格式如下：

```python
{
    "command_name": "命令名称",
    "success": True/False,  # 是否执行成功
    "timestamp": 1234567890.123,  # 时间戳
    "data": {...},  # 返回数据（成功时）
    "error": "错误信息"  # 错误信息（失败时）
}
```

插件需要注册 `command_response` 自定义消息处理器来接收命令响应。

---

## 操作类命令

### 群聊禁言
```python
Seg.data: Dict[str, Any] = {
    "name": "GROUP_BAN",
    "args": {
        "qq_id": "用户QQ号",
        "duration": "禁言时长（秒）"
    },
}
```
其中，群聊ID将会通过Group_Info.group_id自动获取。

**当`duration`为 0 时相当于解除禁言。**

### 群聊全体禁言
```python
Seg.data: Dict[str, Any] = {
    "name": "GROUP_WHOLE_BAN",
    "args": {
        "enable": "是否开启全体禁言（True/False）"
    },
}
```
其中，群聊ID将会通过Group_Info.group_id自动获取。

`enable`的参数需要为boolean类型，True表示开启全体禁言，False表示关闭全体禁言。

### 群聊踢人
将指定成员从群聊中踢出，可选拉黑。

```python
Seg.data: Dict[str, Any] = {
    "name": "GROUP_KICK",
    "args": {
        "group_id": 123456789,  # 可选，如果在群聊上下文中可从 group_info 自动获取
        "user_id": 12345678,  # 必需，用户QQ号
        "reject_add_request": False  # 可选，是否群拉黑，默认 False
    },
}
```

### 批量踢出群成员
批量将多个成员从群聊中踢出，可选拉黑。

```python
Seg.data: Dict[str, Any] = {
    "name": "GROUP_KICK_MEMBERS",
    "args": {
        "group_id": 123456789,  # 可选，如果在群聊上下文中可从 group_info 自动获取
        "user_id": [12345678, 87654321],  # 必需，用户QQ号数组
        "reject_add_request": False  # 可选，是否群拉黑，默认 False
    },
}
```

### 戳一戳
```python
Seg.data: Dict[str, Any] = {
    "name": "SEND_POKE",
    "args": {
        "qq_id": "目标QQ号"
    }
}
```

### 撤回消息
```python
Seg.data: Dict[str, Any] = {
    "name": "DELETE_MSG",
    "args": {
        "message_id": "消息所对应的message_id"
    }
}
```
其中message_id是消息的实际qq_id，于新版的mmc中可以从数据库获取（如果工作正常的话）

### 给消息贴表情
```python
Seg.data: Dict[str, Any] = {
    "name": "SET_MSG_EMOJI_LIKE",
    "args": {
        "message_id": "消息ID",
        "emoji_id": "表情ID"
    }
}
```

### 设置群名
设置指定群的群名称。

```python
Seg.data: Dict[str, Any] = {
    "name": "SET_GROUP_NAME",
    "args": {
        "group_id": 123456789,  # 可选，如果在群聊上下文中可从 group_info 自动获取
        "group_name": "新群名"  # 必需，新的群名称
    }
}
```

### 设置账号信息
设置Bot自己的QQ账号资料。

```python
Seg.data: Dict[str, Any] = {
    "name": "SET_QQ_PROFILE",
    "args": {
        "nickname": "新昵称",  # 必需，昵称
        "personal_note": "个性签名",  # 可选，个性签名
        "sex": "male"  # 可选，性别："male" | "female" | "unknown"
    }
}
```

**返回数据示例：**
```python
{
    "result": 0,  # 结果码，0为成功
    "errMsg": ""  # 错误信息
}
```

---

## 查询类命令

### 获取登录号信息
获取Bot自身的账号信息。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_LOGIN_INFO",
    "args": {}
}
```

**返回数据示例：**
```python
{
    "user_id": 12345678,
    "nickname": "Bot昵称"
}
```

### 获取陌生人信息
```python
Seg.data: Dict[str, Any] = {
    "name": "GET_STRANGER_INFO",
    "args": {
        "user_id": "用户QQ号"
    }
}
```

**返回数据示例：**
```python
{
    "user_id": 12345678,
    "nickname": "用户昵称",
    "sex": "male/female/unknown",
    "age": 0
}
```

### 获取好友列表
获取Bot的好友列表。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_FRIEND_LIST",
    "args": {
        "no_cache": False  # 可选，是否不使用缓存，默认 False
    }
}
```

**返回数据示例：**
```python
[
    {
        "user_id": 12345678,
        "nickname": "好友昵称",
        "remark": "备注名",
        "sex": "male",  # "male" | "female" | "unknown"
        "age": 18,
        "qid": "QID字符串",
        "level": 64,
        "login_days": 365,
        "birthday_year": 2000,
        "birthday_month": 1,
        "birthday_day": 1,
        "phone_num": "电话号码",
        "email": "邮箱",
        "category_id": 0,  # 分组ID
        "categoryName": "我的好友",  # 分组名称
        "categoryId": 0
    },
    ...
]
```

### 获取群信息
获取指定群的详细信息。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_GROUP_INFO",
    "args": {
        "group_id": 123456789  # 可选，如果在群聊上下文中可从 group_info 自动获取
    }
}
```

**返回数据示例：**
```python
{
    "group_id": "123456789",  # 群号（字符串）
    "group_name": "群名称",
    "group_remark": "群备注",
    "group_all_shut": 0,  # 群全员禁言状态（0=未禁言）
    "member_count": 100,  # 当前成员数量
    "max_member_count": 500  # 最大成员数量
}
```

### 获取群详细信息
获取指定群的详细信息（与 GET_GROUP_INFO 类似，可能提供更实时的数据）。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_GROUP_DETAIL_INFO",
    "args": {
        "group_id": 123456789  # 可选，如果在群聊上下文中可从 group_info 自动获取
    }
}
```

**返回数据示例：**
```python
{
    "group_id": 123456789,  # 群号（数字）
    "group_name": "群名称",
    "group_remark": "群备注",
    "group_all_shut": 0,  # 群全员禁言状态（0=未禁言）
    "member_count": 100,  # 当前成员数量
    "max_member_count": 500  # 最大成员数量
}
```

### 获取群列表
获取Bot加入的所有群列表。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_GROUP_LIST",
    "args": {
        "no_cache": False  # 可选，是否不使用缓存，默认 False
    }
}
```

**返回数据示例：**
```python
[
    {
        "group_id": "123456789",  # 群号（字符串）
        "group_name": "群名称",
        "group_remark": "群备注",
        "group_all_shut": 0,  # 群全员禁言状态
        "member_count": 100,  # 当前成员数量
        "max_member_count": 500  # 最大成员数量
    },
    ...
]
```

### 获取群@全体成员剩余次数
查询指定群的@全体成员剩余使用次数。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_GROUP_AT_ALL_REMAIN",
    "args": {
        "group_id": 123456789  # 可选，如果在群聊上下文中可从 group_info 自动获取
    }
}
```

**返回数据示例：**
```python
{
    "can_at_all": True,  # 是否可以@全体成员
    "remain_at_all_count_for_group": 10,  # 群剩余@全体成员次数
    "remain_at_all_count_for_uin": 5  # Bot剩余@全体成员次数
}
```

### 获取群成员信息
获取指定群成员的详细信息。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_GROUP_MEMBER_INFO",
    "args": {
        "group_id": 123456789,  # 可选，如果在群聊上下文中可从 group_info 自动获取
        "user_id": 12345678,  # 必需，用户QQ号
        "no_cache": False  # 可选，是否不使用缓存，默认 False
    }
}
```

**返回数据示例：**
```python
{
    "group_id": 123456789,
    "user_id": 12345678,
    "nickname": "昵称",
    "card": "群名片",
    "sex": "male",  # "male" | "female" | "unknown"
    "age": 18,
    "join_time": 1234567890,  # 加群时间戳
    "last_sent_time": 1234567890,  # 最后发言时间戳
    "level": 1,  # 群等级
    "qq_level": 64,  # QQ等级
    "role": "member",  # "owner" | "admin" | "member"
    "title": "专属头衔",
    "area": "地区",
    "unfriendly": False,  # 是否不友好
    "title_expire_time": 1234567890,  # 头衔过期时间
    "card_changeable": True,  # 名片是否可修改
    "shut_up_timestamp": 0,  # 禁言时间戳
    "is_robot": False,  # 是否机器人
    "qage": "10年"  # Q龄
}
```

### 获取群成员列表
获取指定群的所有成员列表。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_GROUP_MEMBER_LIST",
    "args": {
        "group_id": 123456789,  # 可选，如果在群聊上下文中可从 group_info 自动获取
        "no_cache": False  # 可选，是否不使用缓存，默认 False
    }
}
```

**返回数据示例：**
```python
[
    {
        "group_id": 123456789,
        "user_id": 12345678,
        "nickname": "昵称",
        "card": "群名片",
        "sex": "male",  # "male" | "female" | "unknown"
        "age": 18,
        "join_time": 1234567890,
        "last_sent_time": 1234567890,
        "level": 1,
        "qq_level": 64,
        "role": "member",  # "owner" | "admin" | "member"
        "title": "专属头衔",
        "area": "地区",
        "unfriendly": False,
        "title_expire_time": 1234567890,
        "card_changeable": True,
        "shut_up_timestamp": 0,
        "is_robot": False,
        "qage": "10年"
    },
    ...
]
```

### 获取消息详情
获取指定消息的完整详情信息。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_MSG",
    "args": {
        "message_id": 123456  # 必需，消息ID
    }
}
```

**返回数据示例：**
```python
{
    "self_id": 12345678,  # Bot自身ID
    "user_id": 87654321,  # 发送者ID
    "time": 1234567890,  # 时间戳
    "message_id": 123456,  # 消息ID
    "message_seq": 123456,  # 消息序列号
    "real_id": 123456,  # 真实消息ID
    "real_seq": "123456",  # 真实序列号（字符串）
    "message_type": "group",  # "private" | "group"
    "sub_type": "normal",  # 子类型
    "message_format": "array",  # 消息格式
    "post_type": "message",  # 事件类型
    "group_id": 123456789,  # 群号（群消息时存在）
    "sender": {
        "user_id": 87654321,
        "nickname": "昵称",
        "sex": "male",  # "male" | "female" | "unknown"
        "age": 18,
        "card": "群名片",  # 群消息时存在
        "level": "1",  # 群等级（字符串）
        "role": "member"  # "owner" | "admin" | "member"
    },
    "message": [...],  # 消息段数组
    "raw_message": "消息文本内容",  # 原始消息文本
    "font": 0  # 字体
}
```

### 获取合并转发消息
获取合并转发消息的所有子消息内容。

```python
Seg.data: Dict[str, Any] = {
    "name": "GET_FORWARD_MSG",
    "args": {
        "message_id": "7123456789012345678"  # 必需，合并转发消息ID（字符串）
    }
}
```

**返回数据示例：**
```python
{
    "messages": [
        {
            "sender": {
                "user_id": 87654321,
                "nickname": "昵称",
                "sex": "male",
                "age": 18,
                "card": "群名片",
                "level": "1",
                "role": "member"
            },
            "time": 1234567890,
            "message": [...]  # 消息段数组
        },
        ...
    ]
}
```