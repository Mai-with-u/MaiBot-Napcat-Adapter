"""NapCat 适配器内部共享类型。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional, TypeAlias

from typing_extensions import NotRequired, TypedDict


class NapCatIncomingSegment(TypedDict):
    """NapCat / OneBot 入站消息段结构。"""

    type: str
    data: Mapping[str, Any]


class NapCatHostMessageSegment(TypedDict):
    """适配器转换后写入 Host 的消息段结构。"""

    type: str
    data: Any
    hash: NotRequired[str]
    binary_data_base64: NotRequired[str]


NapCatActionParams: TypeAlias = Mapping[str, Any]
NapCatActionParamsInput: TypeAlias = Optional[Mapping[str, Any]]
NapCatActionResponse: TypeAlias = Dict[str, Any]
NapCatIdInput: TypeAlias = int | str
NapCatMutablePayload: TypeAlias = MutableMapping[str, Any]
NapCatOptionalIdInput: TypeAlias = int | str | None
NapCatPayload: TypeAlias = Mapping[str, Any]
NapCatPayloadDict: TypeAlias = Dict[str, Any]
NapCatPayloadList: TypeAlias = List[Dict[str, Any]]
NapCatIncomingSegments: TypeAlias = List[NapCatIncomingSegment]
NapCatSegment: TypeAlias = NapCatHostMessageSegment
NapCatSegments: TypeAlias = List[NapCatHostMessageSegment]
