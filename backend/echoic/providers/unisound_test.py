"""unisound provider 离线自测(不联网)。

运行(backend 目录下): python -m echoic.providers.unisound_test
覆盖: 官方示例响应解析、错误码映射、缺配置报错、注册表登记。
"""

from types import SimpleNamespace
from unittest import mock

from echoic import available_providers
from echoic.providers.unisound import UnisoundProvider, _parse_response

# 云知声官方文档的响应示例(单词 smart,E 模式)
SAMPLE = {
    "version": "full 1.0",
    "score": 88.66,
    "EvalType": "general",
    "lines": [
        {
            "sample": "smart",
            "usertext": "smart",
            "begin": 0,
            "end": 1.321,
            "score": 88.66,
            "fluency": 91.868,
            "integrity": 100,
            "pronunciation": 88.561,
            "words": [
                {
                    "StressOfWord": 1,
                    "phonetic": "smɑːt",
                    "text": "smart",
                    "type": 2,
                    "begin": 0.411,
                    "end": 1.301,
                    "volume": 7.479,
                    "score": 8.995,
                    "subwords": [
                        {"subtext": "s", "volume": 7.397, "begin": 0.411, "end": 0.541, "score": 8.355},
                        {"subtext": "m", "volume": 9, "begin": 0.541, "end": 0.681, "score": 9.798},
                        {"subtext": "ɑː", "volume": 6.492, "begin": 0.681, "end": 0.921, "score": 9.425},
                        {"subtext": "t", "volume": 7.025, "begin": 0.921, "end": 1.301, "score": 8.937},
                    ],
                }
            ],
        }
    ],
}


def test_parse_official_sample():
    r = _parse_response(SAMPLE)
    assert abs(r.accuracy_score - 88.561) < 1e-6
    assert abs(r.fluency_score - 91.868) < 1e-6
    assert abs(r.completeness_score - 100) < 1e-6
    assert len(r.word_scores) == 1
    w = r.word_scores[0]
    assert w.word == "smart"
    assert abs(w.accuracy_score - 89.95) < 0.01  # 8.995 × 10
    assert w.expected_phonemes == "smɑːt"
    assert w.actual_phonemes == "smɑːt"
    assert len(w.phoneme_scores) == 4
    assert all(
        abs(s / 10 - o) < 0.01
        for s, o in zip(w.phoneme_scores, [8.355, 9.798, 9.425, 8.937])
    )


def test_parse_empty_raises():
    try:
        _parse_response({"lines": []})
        raise AssertionError("应抛 ValueError")
    except ValueError:
        pass


def test_error_code_mapping():
    p = UnisoundProvider({"appkey": "k", "secret": "s"})
    resp = SimpleNamespace(
        status_code=200,
        json=lambda: {"errcode": 44851, "errmsg": "bad key"},
        text='{"errcode": 44851}',
    )
    with mock.patch(
        "echoic.providers.unisound.requests.post", return_value=resp
    ), mock.patch("builtins.open", mock.mock_open(read_data=b"")):
        try:
            p.score("fake.wav", "hello")
            raise AssertionError("应抛 RuntimeError")
        except RuntimeError as e:
            assert "44851" in str(e) and "秘钥" in str(e)


def test_missing_config_raises():
    try:
        UnisoundProvider({}).score("x.wav", "hello")
        raise AssertionError("应抛 ValueError")
    except ValueError:
        pass


def test_registered():
    assert "unisound" in available_providers()


if __name__ == "__main__":
    test_parse_official_sample()
    test_parse_empty_raises()
    test_error_code_mapping()
    test_missing_config_raises()
    test_registered()
    print("unisound_test: 全部通过")
