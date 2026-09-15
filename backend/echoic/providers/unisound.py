"""云知声(Unisound)AI 开放平台口语评测 provider(HTTP 接口)。

文档: https://ai.unisound.com/doc/sacalleval/http.html

要点:
- 表单字段顺序必须 text → mode → voice(requests 的 data 先于 files,天然满足)
- 鉴权 header: `appkey: AppKey@AppSecret`,无签名;`session-id` 用 uuid
- WAV(16k/16bit/单声道)与 pcm 同走 /eval/pcm 路径,与前端录音格式一致,零转码
- 词级/音素分为 0–10 制,×10 归一到 0–100;行级 pronunciation/fluency/integrity 为百分制原值
- 端口注意: 官网文档 HTTP 为 80,Gitee wiki 为 8085;默认 80,不通时经 base_url 覆盖

options(宿主从后台配置传入):
    appkey / secret     — 必填,控制台应用详情页获取
    base_url            — 默认 http://edu.hivoice.cn/eval;中文评测换 cn-edu 前缀
    mode                — 评测模式,默认 E(单词/句子跟读,含逐词逐音素分;篇章用 C)
    score_coefficient   — 可选,0.6~1.9,越大打分越松;不配则用服务端默认
"""

import uuid

import requests

from ..schemas import ScoringResult, WordScore
from .base import ScoringProvider

DEFAULT_BASE_URL = "http://edu.hivoice.cn/eval"

# 常见错误码 → 可读原因;完整表见 Gitee wiki「教育云平台错误码整理」
_ERRCODES = {
    40961: "appkey 无效",
    44811: "appkey 未在访问白名单",
    44850: "appkey 超出使用期限",
    44851: "appkey 秘钥不正确(需 AppKey@AppSecret 形式)",
    53249: "请求数据格式错误(multipart 字段/顺序)",
    53250: "音频 URL 30 秒未取到",
    53251: "音频 URL 资源不存在",
    57345: "云知声评测引擎连接失败",
    57351: "参考文本过长",
    64003: "text JSON 格式不合法",
    65528: "参考文本为空",
    65529: "参考文本无效(仅标点)",
    65532: "语音过短(不足 20ms)",
    65533: "appkey 错误",
    65534: "session-id 超长(限 64)",
}


def _parse_response(payload: dict) -> ScoringResult:
    """官方响应 JSON → ScoringResult;多行文本按行取均值。"""
    lines = payload.get("lines") or []
    if not lines:
        raise ValueError(f"云知声返回无评分数据: {payload}")

    def mean(key: str) -> float:
        vals = [ln[key] for ln in lines if isinstance(ln.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else 0.0

    word_scores: list[WordScore] = []
    for ln in lines:
        for w in ln.get("words") or []:
            # 词类型: 2 正常词 / 1 漏词(计 0 分);空格/标点/静音/多读等跳过
            if w.get("type") not in (1, 2):
                continue
            subs = w.get("subwords") or []
            word_scores.append(
                WordScore(
                    word=str(w.get("text") or ""),
                    accuracy_score=float(w.get("score") or 0) * 10,
                    expected_phonemes=str(w.get("phonetic") or ""),
                    actual_phonemes="".join(str(s.get("subtext") or "") for s in subs),
                    phoneme_scores=[float(s.get("score") or 0) * 10 for s in subs],
                )
            )
    return ScoringResult(
        accuracy_score=mean("pronunciation"),
        fluency_score=mean("fluency"),
        completeness_score=mean("integrity"),
        word_scores=word_scores,
    )


class UnisoundProvider(ScoringProvider):
    name = "unisound"

    def score(
        self,
        recording_path: str,
        reference_text: str,
        language: str | None = None,
    ) -> ScoringResult:
        appkey = self.options.get("appkey")
        secret = self.options.get("secret")
        if not (appkey and secret):
            raise ValueError("unisound provider 缺少 appkey/secret 配置")
        base_url = str(self.options.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        mode = str(self.options.get("mode") or "E")
        headers = {
            "session-id": str(uuid.uuid4()),
            "appkey": f"{appkey}@{secret}",
        }
        if self.options.get("score_coefficient"):
            headers["score-coefficient"] = str(self.options["score_coefficient"])
        if language == "zh":  # 中文评测引擎;mode 必须为 E
            headers["X-EngineType"] = "oral.zh_CH"
        # 官方客户端超时公式 3+(n-10)/5 秒;取下限 10s 给上传留余量
        n_words = len(reference_text.split())
        timeout = max(10.0, 3 + (n_words - 10) / 5)
        try:
            with open(recording_path, "rb") as f:
                resp = requests.post(
                    f"{base_url}/pcm",
                    headers=headers,
                    data={"text": reference_text, "mode": mode},
                    files={"voice": ("voice.wav", f, "audio/wav")},
                    timeout=timeout,
                )
        except requests.RequestException as e:
            raise RuntimeError(f"云知声评测请求失败: {e}") from e
        try:
            payload = resp.json()
        except ValueError:
            raise RuntimeError(
                f"云知声返回非 JSON(HTTP {resp.status_code}): {resp.text[:200]!r}"
            ) from None
        errcode = payload.get("errcode") or payload.get("errCode") or 0
        if resp.status_code != 200 or errcode:
            reason = (
                _ERRCODES.get(errcode)
                or payload.get("errmsg")
                or f"HTTP {resp.status_code}"
            )
            raise RuntimeError(f"云知声评测失败(errcode={errcode}): {reason}")
        return _parse_response(payload)
