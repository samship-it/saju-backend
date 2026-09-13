"""AI 서술형 출력 다듬기.

Gemini 가 JSON 모드에서 문단 구분 없이 한 줄로 뱉는 경우가 많아,
문장 종결 기준으로 끊어 2~3문장씩 문단으로 묶어준다.
이미 줄바꿈이 있으면 그대로 둔다.
"""
import re

_SENTENCE = re.compile(r"[^.!?…]*[.!?…]+[\"'”’)\]]*|\S[^.!?…]*$")

# ── 한줄평(headline) 유효성 가드레일 ──
# 조건1: 10자 미만, 조건2: 인사말/감탄사만, 조건3: 특수문자로만 구성되거나 문장 미완성.
_GREETING_OR_INTERJECTION_ONLY = re.compile(
    r"^(안녕하세요|안녕|반갑습니다|반가워요|반가워|네|넵|아|와|휴|음|어|오|헉|엥|앗|와우|헐)"
    r"[\s,.!?~…]*$"
)
_HAS_MEANINGFUL_CHAR = re.compile(r"[가-힣a-zA-Z0-9]")
_DANGLING_CLAUSE_END = re.compile(
    r"(,|、|~|-|그리고|그래서|하지만|근데|그런데|고|며|는데|지만|어서|아서|니까|거나|든지)\s*$"
)


def first_sentence(text: str) -> str:
    """텍스트에서 첫 문장(또는 첫 줄)만 뽑는다. 프론트 firstSentence() 와 동일 규칙."""
    t = (text or "").strip()
    if not t:
        return ""
    m = re.match(r"^.*?[.!?。](?=\s|$)", t)
    return (m.group(0) if m else t.split("\n")[0]).strip()


def headline_invalid_reason(text: str) -> str:
    """헤드라인이 가드레일을 통과하지 못한 사유(사람이 읽는 로그용). 유효하면 빈 문자열."""
    t = (text or "").strip()
    if len(t) < 10:
        return f"길이 미달({len(t)}자, 최소 10자)"
    if _GREETING_OR_INTERJECTION_ONLY.match(t):
        return "인사말/감탄사만 포함"
    if not _HAS_MEANINGFUL_CHAR.search(t):
        return "특수문자로만 구성"
    if _DANGLING_CLAUSE_END.search(t):
        return "문장 미완성(연결어/쉼표로 종료)"
    return ""


def is_valid_headline(text: str) -> bool:
    """오늘의 운세 한줄평 가드레일. 길이/인사말·감탄사/특수문자·미완성 문장을 걸러낸다."""
    return headline_invalid_reason(text) == ""


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
