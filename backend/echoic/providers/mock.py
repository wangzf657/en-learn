from ..schemas import ScoringResult, WordScore
from .base import ScoringProvider


class MockProvider(ScoringProvider):
    """固定分数的假 provider:联调前端/冒烟测试用,不读音频、无网络。

    分数值与 docs/design.md §5 示例一致,便于对文档核对。
    """

    name = "mock"

    def score(
        self,
        recording_path: str,
        reference_text: str,
        language: str | None = None,
    ) -> ScoringResult:
        word_scores = [
            WordScore(
                word=w,
                accuracy_score=85.0,
                expected_phonemes="mɒk",
                actual_phonemes="mɒk",
                phoneme_scores=[85.0, 80.0, 90.0],
            )
            for w in reference_text.split()
        ]
        return ScoringResult(
            accuracy_score=82.5,
            fluency_score=78.0,
            completeness_score=90.0,
            word_scores=word_scores,
        )
