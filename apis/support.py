"""NapCat API 端点的公共辅助能力。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, TypeAlias

from maibot_sdk import API

from ..napcat_types import NapCatActionParamsInput, NapCatActionResponse, NapCatIdInput

if TYPE_CHECKING:
    from ..services import NapCatActionService, NapCatQueryService


NapCatApiIdInput: TypeAlias = NapCatIdInput
NapCatApiParamsInput: TypeAlias = NapCatActionParamsInput


class NapCatApiSupportMixin:
    """NapCat API 端点共享辅助逻辑。"""

    _action_service: Optional["NapCatActionService"]
    _query_service: Optional["NapCatQueryService"]

    def _ensure_runtime_components(self) -> None:
        """确保运行时组件已经初始化。"""
        raise NotImplementedError

    @staticmethod
    def _coerce_int(value: object, field_name: str, expectation: str) -> int:
        """将受支持的输入值转换为整数。

        Args:
            value: 待转换的值。
            field_name: 字段名，用于错误提示。
            expectation: 期望的取值描述，例如“正整数”。

        Returns:
            int: 转换后的整数值。

        Raises:
            ValueError: 当值无法转换为整数时抛出。
        """
        if isinstance(value, bool):
            raise ValueError(f"{field_name} 必须是{expectation}")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            try:
                return int(value)
            except (OverflowError, ValueError) as exc:
                raise ValueError(f"{field_name} 必须是{expectation}") from exc
        if isinstance(value, str):
            normalized_value = value.strip()
            if not normalized_value:
                raise ValueError(f"{field_name} 必须是{expectation}")
            try:
                return int(normalized_value)
            except ValueError as exc:
                raise ValueError(f"{field_name} 必须是{expectation}") from exc
        raise ValueError(f"{field_name} 必须是{expectation}")

    def _require_query_service(self) -> "NapCatQueryService":
        """返回当前可用的 NapCat 查询服务。

        Returns:
            NapCatQueryService: 已初始化的查询服务。

        Raises:
            RuntimeError: 当查询服务尚未初始化时抛出。
        """
        self._ensure_runtime_components()
        query_service = self._query_service
        if query_service is None:
            raise RuntimeError("NapCat 查询服务尚未初始化")
        return query_service

    def _require_action_service(self) -> "NapCatActionService":
        """返回当前可用的 NapCat 动作服务。

        Returns:
            NapCatActionService: 已初始化的动作服务。

        Raises:
            RuntimeError: 当动作服务尚未初始化时抛出。
        """
        self._ensure_runtime_components()
        action_service = self._action_service
        if action_service is None:
            raise RuntimeError("NapCat 动作服务尚未初始化")
        return action_service

    @staticmethod
    def _normalize_positive_int(value: object, field_name: str) -> int:
        """将任意值规范化为正整数。

        Args:
            value: 待规范化的值。
            field_name: 字段名，用于错误提示。

        Returns:
            int: 规范化后的正整数。

        Raises:
            ValueError: 当值无法转换为正整数时抛出。
        """
        normalized_value = NapCatApiSupportMixin._coerce_int(value, field_name, "正整数")
        if normalized_value <= 0:
            raise ValueError(f"{field_name} 必须是正整数")
        return normalized_value

    @staticmethod
    def _normalize_non_negative_int(value: object, field_name: str) -> int:
        """将任意值规范化为非负整数。

        Args:
            value: 待规范化的值。
            field_name: 字段名，用于错误提示。

        Returns:
            int: 规范化后的非负整数。

        Raises:
            ValueError: 当值无法转换为非负整数时抛出。
        """
        normalized_value = NapCatApiSupportMixin._coerce_int(value, field_name, "非负整数")
        if normalized_value < 0:
            raise ValueError(f"{field_name} 必须是非负整数")
        return normalized_value

    @staticmethod
    def _normalize_bool(value: object, field_name: str) -> bool:
        """将任意值规范化为布尔值。

        Args:
            value: 待规范化的值。
            field_name: 字段名，用于错误提示。

        Returns:
            bool: 规范化后的布尔值。

        Raises:
            ValueError: 当值不是布尔值时抛出。
        """
        if not isinstance(value, bool):
            raise ValueError(f"{field_name} 必须是布尔值")
        return value

    @staticmethod
    def _normalize_non_empty_string(value: object, field_name: str) -> str:
        """将任意值规范化为非空字符串。

        Args:
            value: 待规范化的值。
            field_name: 字段名，用于错误提示。

        Returns:
            str: 规范化后的字符串。

        Raises:
            ValueError: 当值为空时抛出。
        """
        normalized_value = str(value or "").strip()
        if not normalized_value:
            raise ValueError(f"{field_name} 不能为空")
        return normalized_value

    @classmethod
    def _normalize_user_id_list(cls, values: object, field_name: str) -> List[int]:
        """将任意值规范化为用户号列表。

        Args:
            values: 待规范化的值。
            field_name: 字段名，用于错误提示。

        Returns:
            List[int]: 规范化后的用户号列表。

        Raises:
            ValueError: 当值不是非空数组时抛出。
        """
        if not isinstance(values, list) or not values:
            raise ValueError(f"{field_name} 必须是非空数组")
        return [cls._normalize_positive_int(value, field_name) for value in values]

    @staticmethod
    def _normalize_params(params: NapCatApiParamsInput) -> Dict[str, Any]:
        """将动作参数规范化为可变字典。

        Args:
            params: 调用方提供的参数对象。

        Returns:
            Dict[str, Any]: 规范化后的参数字典。

        Raises:
            ValueError: 当 ``params`` 不是映射对象时抛出。
        """
        if params is None:
            return {}
        if not isinstance(params, Mapping):
            raise ValueError("params 必须是对象")
        return {str(key): value for key, value in params.items()}

    async def _call_napcat_action(
        self,
        action_name: str,
        params: NapCatApiParamsInput = None,
    ) -> NapCatActionResponse:
        """调用 NapCat 动作并返回原始响应。

        Args:
            action_name: NapCat 动作名称。
            params: 传递给 NapCat 的动作参数。

        Returns:
            Dict[str, Any]: NapCat 返回的原始响应字典。
        """
        normalized_action_name = self._normalize_non_empty_string(action_name, "action_name")
        normalized_params = self._normalize_params(params)
        return await self._require_action_service().call_action(normalized_action_name, normalized_params)

    async def _call_napcat_action_data(
        self,
        action_name: str,
        params: NapCatApiParamsInput = None,
    ) -> Any:
        """调用 NapCat 动作并返回 ``data`` 字段。

        Args:
            action_name: NapCat 动作名称。
            params: 传递给 NapCat 的动作参数。

        Returns:
            Any: NapCat 响应中的 ``data`` 字段。
        """
        normalized_action_name = self._normalize_non_empty_string(action_name, "action_name")
        normalized_params = self._normalize_params(params)
        return await self._require_action_service().call_action_data(normalized_action_name, normalized_params)

    @API("adapter.napcat.action.call", description="调用任意 OneBot 动作", version="1", public=True)
    async def api_call_action(
        self,
        action_name: str = "",
        params: NapCatApiParamsInput = None,
    ) -> NapCatActionResponse:
        """调用任意 OneBot 动作。

        Args:
            action_name: OneBot 动作名称。
            params: 动作参数。

        Returns:
            Dict[str, Any]: NapCat 返回的原始响应字典。
        """
        return await self._call_napcat_action(action_name, params)

    @API(
        "adapter.napcat.action.call_data", description="调用任意 OneBot 动作并返回 data 字段", version="1", public=True
    )
    async def api_call_action_data(
        self,
        action_name: str = "",
        params: NapCatApiParamsInput = None,
    ) -> Any:
        """调用任意 OneBot 动作并返回 ``data`` 字段。

        Args:
            action_name: OneBot 动作名称。
            params: 动作参数。

        Returns:
            Any: NapCat 响应中的 ``data`` 字段。
        """
        return await self._call_napcat_action_data(action_name, params)
