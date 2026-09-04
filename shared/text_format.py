"""AI 서술형 출력 다듬기.

Gemini 가 JSON 모드에서 문단 구분 없이 한 줄로 뱉는 경우가 많아,
문장 종결 기준으로 끊어 2~3문장씩 문단으로 묶어준다.
이미 줄바꿈이 있으면 그대로 둔다.
"""
import re

_SENTENCE = re.compile(r"[^.!?…]*[.!?…]+[\"'”’)\]]*|\S[^.!?…]*$")


def paragraphize(text: str, sentences_per_paragraph: int = 3) -> str:
    t = (text or "").strip()
    if not t or "\n" in t:
        return t
    sentences = [s.strip() for s in _SENTENCE.findall(t) if s.strip()]
    if len(sentences) <= sentences_per_paragraph:
        return t
    paragraphs = [
        " ".join(sentences[i : i + sentences_per_paragraph])
        for i in range(0, len(sentences), sentences_per_paragraph)
    ]
    return "\n\n".join(paragraphs)
