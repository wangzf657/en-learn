"""ScoringProvider 协议与注册表。

一家云 API 一个实现;注册表按名字分发,宿主(后台配置)只引用名字。
"""

from abc import ABC, abstractmethod

from ..schemas import ScoringResult

_REGISTRY: dict[str, type["ScoringProvider"]] = {}


def register_provider(cls: type["ScoringProvider"]) -> type["ScoringProvider"]:
    """登记 provider(幂等,同名覆盖——便于测试替换)。"""
    _REGISTRY[cls.name] = cls
    return cls


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def get_provider(name: str, options: dict | None = None) -> "ScoringProvider":
    try:
        return _REGISTRY[name](options)
    except KeyError:
        raise ValueError(
            f"未知评分 provider: {name!r},可选: {available_providers()}"
        ) from None


class ScoringProvider(ABC):
    """发音评分 provider 协议。

    子类需定义类属性 name(注册表键,后台配置引用它),并实现 score()。
    options(密钥/区域等)由宿主从后台配置读出后经 __init__ 注入,
    provider 只读不改。
    """

    name: str = ""

    def __init__(self, options: dict | None = None):
        self.options = options or {}

    @abstractmethod
    def score(
        self,
        recording_path: str,
        reference_text: str,
        language: str | None = None,
    ) -> ScoringResult:
        """对录音评分。实现约定:

        - 网络/认证/参数错误抛异常并带可读原因(宿主映射 5xx/配置错误)
        - 参考词没念出来计低分,不是报错
        - 分数为厂商原始校准分,不做任何二次变换
        """
