"""Provider 注册表。新增 provider:实现 ScoringProvider 子类后在此登记一行。"""

from .base import (
    ScoringProvider,
    available_providers,
    get_provider,
    register_provider,
)
from .mock import MockProvider
from .unisound import UnisoundProvider

register_provider(MockProvider)
register_provider(UnisoundProvider)

__all__ = [
    "ScoringProvider",
    "MockProvider",
    "UnisoundProvider",
    "available_providers",
    "get_provider",
    "register_provider",
]
