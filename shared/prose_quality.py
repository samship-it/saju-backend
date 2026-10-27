"""복콩 문장 품질 검사.

조회 경로에서는 뜻을 지우거나 LLM을 부르지 않는다.
고칠 수 있는 것은 닫힌 오타표, 연속 공백, 문장 앞의 호칭 인사뿐이다.
섹션 충돌·문체·중복은 판정만 하고, 카테고리 조립기가 이미 가진 규칙으로만 걸러낸다.
"""
import re
from typing import Any, Iterator, List

# 검수에서 확인된 글자 깨짐만 고친다. 연도나 문장 전체를 여기 넣지 않는다.
TYPO_FIXUPS = {
    "천섀기": "천천히",
    "여미까": "여기니까",
    "제테크": "재테크",
    "숙중하게": "신중하게",
}

_HANGUL = re.compile(r"[가-힣]")
_DOUBLE_SPACE = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,.])")
_GREETING_START = re.compile(r"^(?:안녕하세요|반갑습니다|우와|와우)(?:\s|$|[,!])")
_DANGLING = re.compile(
    r"(?:,|、|~|-|그리고|그래서|하지만|근데|그런데|고|며|는데|지만|어서|아서|니까|거나|든지)\s*$"
)
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]")
_HAEYO = re.compile(r"(?:아요|어요|예요|에요|해요|죠|네요)(?=\s|$|[,.!?…])")
_HAMNIDA = re.compile(r"(?:습니다|입니다|됩니다|십시오)(?=\s|$|[,.!?…])")

# 같은 문단 안에서 둘 다 있으면 관계 설명이 있는지 본다. 설명 없이 같이 있을 때만 남긴다.
_TENSIONS = (
    (("강행군", "무리해서라도"), ("충분히 쉬", "쉬어야 한")),
)
_BRIDGE = ("다만", "대신", "한편", "그러려면", "그 대신")

_SKIP_KEYS = frozenset({
    "nickname", "user_id", "target_person_id", "target_name", "image_url", "name_en",
    "content_type", "status", "code", "day_master", "gender", "love_status", "job_status",
    "orientation", "reading_type", "question", "combo_key", "category", "target_date",
    "session_date", "ganji", "name_kr",
})


def polish_text(text: str) -> str:
    """사용자에게 나가기 직전의 표면만 다듬는다. 문장을 지우거나 덧붙이지 않는다."""
    if not isinstance(text, str) or not text or not _HANGUL.search(text):
        return text
    out = text
    for bad, good in TYPO_FIXUPS.items():
        if bad in out:
            out = out.replace(bad, good)
    from shared.text_format import strip_reader_greeting
    greeted = strip_reader_greeting(out)
    if greeted != out:
        out = greeted
    spaced = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    if spaced != out:
        out = spaced
    collapsed = _DOUBLE_SPACE.sub(" ", out)
    return collapsed


def polish_tree(value: Any, key: str = "") -> Any:
    if key in _SKIP_KEYS:
        return value
    if isinstance(value, str):
        return polish_text(value)
    if isinstance(value, list):
        return [polish_tree(item) for item in value]
    if isinstance(value, dict):
        return {name: polish_tree(item, name) for name, item in value.items()}
    return value


def finish_reading(data: Any, is_fallback: bool = False):
    """운세 응답 딕셔너리를 내보내기 전에 공통 표면 검사를 적용한다."""
    if isinstance(data, dict):
        data = polish_tree(data)
    return data, is_fallback


def walk_strings(value: Any, key: str = "") -> Iterator[str]:
    if key in _SKIP_KEYS:
        return
    if isinstance(value, str):
        if _HANGUL.search(value):
            yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
        return
    if isinstance(value, dict):
        for name, item in value.items():
            yield from walk_strings(item, name)


def hard_surface_reason(text: str) -> str:
    """다듬은 뒤에도 문장으로 끝내지 못한 경우. 인사와 오타는 polish 가 먼저 고친다."""
    if not isinstance(text, str):
        return ""
    polished = polish_text(text).strip()
    if len(polished) < 12 or not _HANGUL.search(polished):
        return ""
    if _DANGLING.search(polished) and not re.search(r"[.!?…。]$", polished):
        return "dangling"
    return ""


def raw_surface_issue(text: str) -> str:
    if not isinstance(text, str) or not _HANGUL.search(text):
        return ""
    for bad in TYPO_FIXUPS:
        if bad in text:
            return "typo"
    if _DOUBLE_SPACE.search(text) or _SPACE_BEFORE_PUNCT.search(text):
        return "spacing"
    if _GREETING_START.match(text.strip()):
        return "greeting"
    return ""


def voice_flag(text: str, expected: str) -> str:
    """expected: haeyo, hamnida, any. 짧은 표식은 문체로 보지 않는다."""
    if not isinstance(text, str) or len(text) < 20:
        return ""
    haeyo = bool(_HAEYO.search(text))
    hamnida = bool(_HAMNIDA.search(text))
    if not haeyo and not hamnida:
        return ""
    if expected == "haeyo" and hamnida and not haeyo:
        return "off_voice"
    if expected == "hamnida" and haeyo and not hamnida:
        return "off_voice"
    if haeyo and hamnida:
        return "voice_mix"
    return ""


def repeated_sentence_count(text: str) -> int:
    if not isinstance(text, str) or len(text) < 24:
        return 0
    parts = []
    for piece in _SENTENCE.findall(text):
        key = re.sub(r"\s+", "", piece)
        if len(key) >= 12:
            parts.append(key)
    return len(parts) - len(set(parts)) if parts else 0


def tension_unbridged(text: str) -> bool:
    """서로 다른 조언이 한 문단에 있는데 둘의 관계를 말하는 말이 없을 때."""
    if not isinstance(text, str):
        return False
    for lefts, rights in _TENSIONS:
        if any(word in text for word in lefts) and any(word in text for word in rights):
            if not any(word in text for word in _BRIDGE):
                return True
    return False


def lead_names_activity(text: str) -> bool:
    """취미 첫 문장이 저장된 활동 이름을 말하거나, 이름이 없어 폴백인 경우."""
    from domains.yearly.travel_hobby import _labels_in, _sentences
    sentences = [sentence for sentence in _sentences(text or "") if sentence.strip()]
    if not sentences:
        return False
    first = sentences[0]
    if "하나에 머무" in first:
        return True
    return bool(_labels_in(first))


def review_text(text: str, voice: str = "any") -> List[str]:
    """한 필드를 공통 규칙으로 본다. 문장을 수정하지 않는다."""
    found = []
    issue = raw_surface_issue(text)
    if issue:
        found.append(issue)
    dangling = hard_surface_reason(text)
    if dangling:
        found.append(dangling)
    voice_hit = voice_flag(text, voice)
    if voice_hit:
        found.append(voice_hit)
    if repeated_sentence_count(text):
        found.append("duplicate")
    if tension_unbridged(text):
        found.append("tension")
    return found
