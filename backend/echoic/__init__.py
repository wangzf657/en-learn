"""Echoic — 发音评分库(云 API 对接壳)。

统一入口 `score_recording()` 经 provider 注册表分发到具体 API 实现;
后台配置决定用哪家。内置 mock 供联调/冒烟;真实 provider 的选型与
对接规范见 docs/scoring-api-research.md 与 docs/scoring-provider-design.md。
"""

from .providers import (
    MockProvider,
    ScoringProvider,
    available_providers,
    get_provider,
    register_provider,
)
from .schemas import ScoringResult, WordScore


def score_recording(
    recording_path: str,
    reference_text: str,
    provider: str = "mock",
    options: dict | None = None,
    language: str | None = None,
) -> ScoringResult:
    """用户录音 vs 参考文本 → 三维分数 + 逐词逐音素得分。

    provider 名与 options(密钥等)由宿主从后台配置读出后传入。
    返回 ScoringResult;model_dump() 即 JSON-ready。
    """
    return get_provider(provider, options).score(
        recording_path, reference_text, language
    )


__all__ = [
    "score_recording",
    "ScoringResult",
    "WordScore",
    "ScoringProvider",
    "MockProvider",
    "available_providers",
    "get_provider",
    "register_provider",
]
