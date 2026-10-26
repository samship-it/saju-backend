"""여행운 + 취미운 통합.

사전 생성 문단을 통째로 이어 붙이지 않는다.
전체 흐름은 여가의 공통 기조만 맡고, 여행 방식·시기·취미·동행·수확은 서로 다른 질문만 답한다.
장소·방위·해외·특정 운동 종목처럼 근거 없이 단정된 문장은 통합본에서 뺀다.
"""
import re
from typing import Any, Callable, Dict, List, Optional, Set

from core.constants import CHUNG, SAMHAP, YUKHAP
from core.sipsin import sipsin_group

_YEOKMA = {"寅", "申", "巳", "亥"}

# 전체 흐름 첫 문장. 키는 (이동이 센가, 취미가 센가). 여행 코스나 운동 종목은 넣지 않는다.
_OPENING = {
    (True, True): (
        "올해 여가는 밖으로 나가는 일과 한 가지에 머무는 일이 같이 열려요. "
        "둘을 같은 속도로 채우기보다, 나가는 때와 머무는 때를 나누는 편이 맞아요."
    ),
    (True, False): (
        "올해 여가는 자리를 바꾸며 숨통이 트이는 쪽이에요. "
        "새로운 취미를 여러 개 시작하기보다, 움직이는 사이에 짧게 쉬는 정도가 편해요."
    ),
    (False, True): (
        "올해 여가는 멀리 벌리기보다, 가까운 자리에서 한 가지를 깊게 하는 쪽이에요. "
        "밖은 그 흐름을 환기하는 짧은 외출이면 충분해요."
    ),
    (False, False): (
        "올해 여가는 큰 계획 없이도 굴러가는 해예요. "
        "익숙한 것을 조금 정돈하는 정도면 충분해요."
    ),
}

_CAUTION = {
    (True, True): "나가는 일과 머무는 일을 같은 주에 욕심내면 둘 다 얕아져요. 하나는 다녀오고, 하나는 자리에 앉는 쪽으로 나누는 편이 남아요.",
    (True, False): "일정을 계속 늘리면 다녀와도 남지 않아요. 한 번 움직인 뒤에는 쉬는 시간이 필요해요.",
    (False, True): "취미를 여러 개 동시에 시작하면 어느 것도 손에 남지 않아요. 하나에서 깊이를 보는 편이 맞아요.",
    (False, False): "억지로 판을 키우면 다녀온 기억도 새로 시작한 취미도 금방 흐려져요.",
}

_SENTENCE = re.compile(r"(?<=[\.!?])\s+")
_SEASON = ("연초", "초봄", "한여름", "늦여름", "가을", "겨울", "연말", "상반기", "하반기", "봄", "여름", "사계절", "계절이")
_UNGROUNDED = (
    "해외", "동쪽", "서쪽", "남쪽", "북쪽", "방위", "제주", "유럽", "일본", "발리", "비행기",
    "오픈카", "익스트림", "스카이다이빙", "번지",
)
_NARROW_SPORT = ("크로스핏", "웨이트", "헬스")
_SPORTS = _NARROW_SPORT + ("클라이밍", "등산", "수영", "요가", "러닝", "달리기", "서핑")
_STYLE_PILE = ("자연", "도시", "액티비티", "스포츠", "핫플", "액티브", "액션", "축제")
_DENSE = ("여러 곳", "촘촘", "빡빡", "하루에 여러", "빼곡", "꽉 채", "아침부터 밤", "구석구석", "수없이", "발품")
_LONG = ("장기 체류", "일주일 이상", "한 달 이상", "몇 달", "넉넉한 기간")
_BOLD = ("대담", "강렬", "화려", "적극적", "핫플", "액티비티")
_INTENSE = (
    "폭발", "극적", "거침", "미지", "날아", "뛰어들", "과감", "불타",
    "파티", "클럽", "인싸", "모험", "승리", "많이 움직", "세계를 누",
)
_QUIET = ("서두르지", "익숙한 길", "큰 계획", "짧게 다녀", "가까이만")
_FATE = ("운명", "주목", "환영", "알아봐", "시선", "인생 친구", "인연", "당첨", "행운", "대박", "평생")
_RECORD = ("단축", "완등", "근력", "기록을 깨", "기록 경신", "최고 기록")
_BODY_PUSH = ("근육", "중량", "격렬", "심폐", "비명", "체력", "운동")
_HOBBY_TYPES = {
    "body": _SPORTS,
    "make": ("그림", "사진", "글쓰", "공예", "악기", "창작", "펜"),
    "mind": ("독서", "공부", "언어"),
    "watch": ("음악", "영화", "전시", "감상"),
    "social": ("동호회", "모임"),
}
_SPREAD = ("여러 개", "많이 시작", "이것저것", "종목을 많이")
_EXCLUSIVE = ("오직 혼자", "반드시 혼자", "혼자만 하", "혼자만 해", "함께만", "무조건 함께", "반드시 그룹", "단체로만")
_PUSH_ALL = ("모든 에너지", "체력이 소모되어도", "1분 1초", "강행군")
_CHANCE = ("돌발", "우연", "변수", "예측 불허", "뜻밖", "우연히")
_CHANCE_ANCHOR = (
    "맛집", "명소", "사람", "친구", "도움", "사진", "스냅", "카메라", "아카이빙",
    "골목", "찻집", "풍경", "낙엽", "일기", "코스",
)
_STOP = {
    "올해", "여행", "흐름", "취미", "이번", "사람", "시간", "마음", "가장", "정말",
    "아주", "함께", "혼자", "있는", "하는", "되는", "대한", "통해", "위해", "같은",
    "이런", "그런", "하며", "면서", "에서", "으로", "입니다", "이에요", "해요", "합니다",
}

_COMPANY = {
    "solo": "취미는 혼자 두는 시간이 더 잘 맞아요. 사람을 맞추느라 흐름이 끊기면 금방 지칩니다.",
    "together": "취미는 한두 사람과 함께할 때 흥이 살아나요. 혼자 버티기보다 호흡을 맞추는 편이 편합니다.",
    "either": "취미는 혼자 있는 시간과 한두 사람과 있는 시간이 둘 다 필요해요. 어느 한쪽만으로 한 해를 채우면 금방 지칩니다.",
}

# 축이 같아도 스타일이 다르면 마지막 조언이 달라진다. 저장 문장에 그 스타일이 있을 때만 고른다.
_STYLE_CLOSE = {
    "active": "움직이는 양과 회복하는 양을 같이 두세요. 힘을 쓴 뒤에 쉬는 시간이 있어야 성취도 취미의 몰입도 남아요.",
    "rest": "일정을 더 채우기보다, 머무른 자리에서 충분히 쉬는 편이 올해의 여행과 취미에 맞아요.",
    "impulse": "경로가 바뀌는 즉흥은 두되, 이동만 늘리지는 마세요. 한 번 움직인 뒤에는 쉬는 시간이 필요해요.",
}

_FALLBACK_TRAVEL = {
    "one_line": "익숙한 길에서 한 걸음만 벗어나도 숨이 트이는 해",
    "keywords": ["환기"],
    "concept_object": "지도",
    "overall_flow": "올해 이동은 크게 벌리기보다 짧게 다녀오며 기분을 바꾸는 흐름이에요. 먼 일정보다 몸과 마음이 회복되는 거리를 고르면 충분합니다.",
    "travel_style": "도시를 천천히 걷거나, 물가나 숲에서 쉬는 짧은 여행이 잘 맞아요.",
    "travel_luck": "일정 끝을 비워 두면 예상 못 한 골목과 사람이 찾아옵니다.",
    "recommended_spots": "가까운 물가, 바람이 통하는 언덕, 처음 가 보는 동네 골목이 잘 맞아요.",
}
_FALLBACK_HOBBY = {
    "one_line": "손에 잡히는 것 하나가 한 해를 가볍게 만드는 해",
    "keywords": ["몰입"],
    "concept_object": "그림",
    "overall_flow": "올해 취미는 여러 개를 벌리기보다 이미 손이 가는 것 하나를 깊게 하는 흐름이에요. 거창한 시작보다 꾸준히 돌아오는 시간이 남습니다.",
    "active_activities": "걷기, 손그림, 사진, 간단한 악기처럼 바로 시작할 수 있는 활동이 잘 맞아요.",
    "solo_vs_group": "지칠 때는 혼자, 심심할 때는 한두 사람과 함께하는 편이 편해요.",
    "benefits": "꾸준히 돌아온 취미는 마음을 식혀 주고, 다음 계절의 계획을 가볍게 만들어 줍니다.",
}


def read_axes(saju: Dict[str, Any], year_ganji: str) -> Dict[str, Any]:
    """이동·취미·동행을 점수로만 가른다. 이 점수는 문장에 나가지 않는다."""
    day_b = saju.get("day_branch") or ""
    year_b = year_ganji[1] if isinstance(year_ganji, str) and len(year_ganji) >= 2 else ""
    sinsal = saju.get("sinsal") if isinstance(saju.get("sinsal"), dict) else {}
    derived = saju.get("derived") if isinstance(saju.get("derived"), dict) else {}
    power = derived.get("group_power") if isinstance(derived.get("group_power"), dict) else {}
    sewoon = saju.get("sewoon_sipsin") if isinstance(saju.get("sewoon_sipsin"), dict) else {}

    def grp(key: str) -> str:
        return sipsin_group(str(sewoon.get(key) or ""))

    move = 0
    if sinsal.get("has_yeokma"):
        move += 2
    if day_b in _YEOKMA or year_b in _YEOKMA:
        move += 2
    if day_b and year_b and frozenset((day_b, year_b)) in CHUNG:
        move += 1

    play = 0
    try:
        sik = float(power.get("식상") or 0)
        peer = float(power.get("비겁") or 0)
    except (TypeError, ValueError):
        sik, peer = 0.0, 0.0
    if sik >= 1.5:
        play += 2
    if grp("gan") == "식상" or grp("ji") == "식상":
        play += 2

    together = 0
    if grp("gan") == "비겁" or grp("ji") == "비겁":
        together += 2
    if peer >= sik and peer >= 1.5:
        together += 1
    paired = frozenset((day_b, year_b))
    if day_b and year_b and (paired in YUKHAP or any(day_b in g and year_b in g for g in SAMHAP)):
        together += 2

    if move >= 3 and together == 0:
        company = "solo"
    elif together >= 2 and move >= 3:
        company = "either"
    elif together >= 2:
        company = "together"
    elif play >= 2 and together == 0:
        company = "solo"
    else:
        company = "either"

    return {
        "move_high": move >= 3,
        "play_high": play >= 2,
        "company": company,
    }


def _tags(keywords) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in keywords or []:
        word = str(raw).strip().lstrip("#").strip()
        if not word or word in seen:
            continue
        seen.add(word)
        out.append(f"#{word}")
    return out


def _body(src: Optional[dict], fallback: dict) -> dict:
    base = dict(fallback)
    if isinstance(src, dict):
        base.update({k: src.get(k) if src.get(k) not in (None, "", []) else base.get(k) for k in fallback})
        if src.get("keywords"):
            base["keywords"] = src.get("keywords")
    return base


def _sentences(text: str) -> List[str]:
    return [part.strip() for part in _SENTENCE.split(text or "") if part.strip()]


def _has(sentence: str, words) -> bool:
    return any(word in sentence for word in words)


def _blocked(sentence: str) -> bool:
    return (
        _has(sentence, _SEASON)
        or _has(sentence, _UNGROUNDED)
        or "치트키" in sentence
        or "그 영상" in sentence
        or "등이 있" in sentence
        or "구체적인 활동으로는" in sentence
    )


def _opposes_move(sentence: str, move_high: bool) -> bool:
    """짧은 해에 대담한 일정을, 움직이는 해에 눌러 앉는 문장을 붙이지 않는다."""
    if _blocked(sentence) or _has(sentence, _FATE) or _has(sentence, _DENSE) or "실천 가이드" in sentence:
        return True
    if sum(word in sentence for word in _SPORTS) >= 2 or sum(word in sentence for word in _STYLE_PILE) >= 2:
        return True
    if move_high:
        return _has(sentence, _QUIET)
    return _has(sentence, _BOLD) or _has(sentence, _INTENSE) or _has(sentence, _LONG)


def _hobby_types(sentence: str) -> List[str]:
    return [name for name, words in _HOBBY_TYPES.items() if _has(sentence, words)]


def _content_tokens(sentence: str) -> Set[str]:
    return {token for token in re.findall(r"[가-힣]{2,}", sentence) if token not in _STOP}


def _similar(left: str, right: str) -> bool:
    """같은 말의 반복만 걸러 낸다. 소재가 다르면 남긴다."""
    if left.strip() == right.strip():
        return True
    a, b = _content_tokens(left), _content_tokens(right)
    if len(a) < 2 or len(b) < 2:
        return False
    return len(a & b) / min(len(a), len(b)) >= 0.72


def _overlaps(sentence: str, seen: Set[str]) -> bool:
    return any(_similar(sentence, prev) for prev in seen)


def _pick_hobby(text: str, used: Set[str], play_high: bool) -> List[str]:
    """같은 유형의 문장을 겹치지 않게 남긴다. 유형을 한꺼번에 늘어놓지 않는다."""
    del play_high  # 유형은 저장 문장의 비중으로 고른다. 운동으로 고정하지 않는다.
    kept: List[str] = []
    for sentence in _sentences(text):
        if sentence in used or _blocked(sentence) or _overlaps(sentence, used):
            continue
        if _has(sentence, _RECORD) or _has(sentence, _SPREAD) or _has(sentence, _NARROW_SPORT):
            continue
        if "보다는" in sentence or _has(sentence, _FATE) or _has(sentence, _INTENSE):
            continue
        kinds = _hobby_types(sentence)
        if sum(word in sentence for word in _SPORTS) >= 2 or len(kinds) >= 2:
            continue
        kept.append(sentence)
    if not kept:
        return []
    preference = ("make", "mind", "watch", "social", "other", "body")
    counts: Dict[str, int] = {}
    for sentence in kept:
        kinds = _hobby_types(sentence)
        name = kinds[0] if kinds else "other"
        counts[name] = counts.get(name, 0) + 1

    def rank(name: str):
        return (counts[name], -preference.index(name) if name in preference else -len(preference))

    chosen = max(counts, key=rank)
    picked: List[str] = []
    for sentence in kept:
        kinds = _hobby_types(sentence)
        name = kinds[0] if kinds else "other"
        if name != chosen or _overlaps(sentence, used) or _overlaps(sentence, set(picked)):
            continue
        used.add(sentence)
        picked.append(sentence)
    return picked


_HYPE = ("완벽하게", "극대화", "압도", "최고의", "최고로", "눈부신", "놀라운", "탁월", "온몸", "짜릿", "전율")
_STYLE_CONFLICT = {
    "rest": ("핫플", "액티비티", "강렬", "대담"),
    "plan": ("발길", "즉흥", "동선 없이"),
    "impulse": ("통제", "스케줄"),
}


def _style_role(sentence: str) -> str:
    if _has(sentence, ("무리하면", "주의할", "지치기", "컨디션이")):
        return "caution"
    if _has(sentence, ("스타일", "형입니다", "형이에요", "여행이 맞", "잘 맞는 여행")):
        return "define"
    if _has(sentence, ("숙소", "호텔", "펜션", "한옥", "독채", "동행", "연인", "가족", "친구", "동반", "일정", "기간", "짐", "준비물", "캐리어", "체력")):
        return "detail"
    return "body"


def _plain_prefer(sentences: List[str]) -> List[str]:
    """같은 내용이면 과장된 문장 대신 담백한 문장을 남긴다."""
    kept: List[str] = []
    for sentence in sentences:
        if _has(sentence, _HYPE) and any(
            not _has(other, _HYPE) and _similar(sentence, other) for other in sentences
        ):
            continue
        kept.append(sentence)
    return kept


def _detail_rank(sentence: str) -> int:
    if _has(sentence, ("숙소", "호텔", "펜션", "한옥", "독채")):
        return 3
    if _has(sentence, ("짐", "준비물", "캐리어", "체력")):
        return 2
    if _has(sentence, ("일정", "기간", "스케줄")):
        return 1
    return 0


def _style_tone(text: str) -> str:
    """보이는 문장에 실제로 있는 스타일만 고른다. 연도를 활동형으로 몰지 않는다."""
    if _has(text, ("즉흥", "탐험", "배낭")):
        return "impulse"
    if _has(text, ("휴양", "힐링", "아늑", "치유")):
        return "rest"
    if _has(text, ("액티브", "액티비티", "한계", "도전", "원정", "열정")):
        return "active"
    return ""


def _chance_keep(sentence: str, state: Dict[str, bool]) -> bool:
    """돌발·우연을 결과 없이 반복하는 문장만 걸러 낸다. 맛집·사진처럼 결과가 있으면 남긴다."""
    if not _has(sentence, _CHANCE):
        return True
    if state.get("used") and not _has(sentence, _CHANCE_ANCHOR):
        return False
    state["used"] = True
    return True


def _keep_style_sentence(sentence: str, move_high: bool, tone: str) -> bool:
    """스타일 이름 자체는 남긴다. 쉴 틈을 없애라는 조언은 뒤에 오는 회복 조언과 부딪혀 뺀다."""
    if _blocked(sentence) or _has(sentence, _FATE) or _has(sentence, _DENSE) or _has(sentence, _PUSH_ALL):
        return False
    role = _style_role(sentence)
    if role != "define" and sum(word in sentence for word in _STYLE_PILE) >= 2:
        return False
    if role == "define":
        return True
    if tone == "active" and role == "body":
        return not _has(sentence, _QUIET)
    if tone == "rest":
        return not _has(sentence, _BOLD) and not _has(sentence, _INTENSE) and not _has(sentence, _LONG)
    if tone == "impulse" and role == "body":
        return not _has(sentence, _QUIET)
    return not _opposes_move(sentence, move_high)


def _arrange_style(sentences: List[str], chance: Dict[str, bool]) -> List[str]:
    """정의 한 문장, 그 스타일의 경험, 동행·일정·준비·숙소 순으로 묶는다."""
    sentences = _plain_prefer(sentences)
    define = [s for s in sentences if _style_role(s) == "define"]
    body = [s for s in sentences if _style_role(s) == "body" and _chance_keep(s, chance)]
    detail = [s for s in sentences if _style_role(s) == "detail"]
    caution = [s for s in sentences if _style_role(s) == "caution"]
    anchor = " ".join(define + body)
    if _has(anchor, ("휴양", "조용", "휴식", "아늑")):
        detail = [s for s in detail if not _has(s, _STYLE_CONFLICT["rest"])]
    elif _has(anchor, ("스케줄", "효율", "동선")) and not _has(anchor, ("즉흥", "발길")):
        detail = [s for s in detail if not _has(s, _STYLE_CONFLICT["plan"])]
    detail = sorted(detail, key=_detail_rank)
    groups: List[List[str]] = []
    if define:
        groups.append(define)
    if body:
        groups.append(body)
    if detail:
        if define or body:
            groups.append(detail)
        else:
            groups.append([s for s in detail if _detail_rank(s) == 0])
            rest = [s for s in detail if _detail_rank(s) > 0]
            if rest:
                groups.append(rest)
    if caution:
        groups.append(caution[:1])
    return [" ".join(group) for group in groups if group]


def _arrange_company(sentences: List[str]) -> List[str]:
    """취미를 혼자 둘 때, 함께할 때, 그날 고르는 말 순. 문장 틀은 저장 문장 그대로다."""
    solo: List[str] = []
    together: List[str] = []
    both: List[str] = []
    choice: List[str] = []
    for sentence in sentences:
        if _has(sentence, ("상황에 맞", "상황에 따", "방식을 자유", "방식을 조절", "방식을 바꾸")):
            choice.append(sentence)
            continue
        alone = _has(sentence, ("혼자", "방 안", "조용히 앉아", "사색"))
        shared = _has(sentence, ("함께", "같이", "동호회", "모임", "크루", "사람들"))
        if alone and shared:
            both.append(sentence)
        elif alone:
            solo.append(sentence)
        elif shared:
            together.append(sentence)
        else:
            both.append(sentence)
    if solo:
        return solo + together + both + choice
    # 혼자 두는 상황 문장이 없으면, 혼자와 함께의 차이를 먼저 말한다.
    return both + together + choice


def _one_drive(sentences: List[str]) -> List[str]:
    """성취·열정을 같은 수확 안에서 두 번 말하지 않는다."""
    seen = False
    kept: List[str] = []
    for sentence in sentences:
        if _has(sentence, ("성취", "열정", "돌진")):
            if seen:
                continue
            seen = True
        kept.append(sentence)
    return kept


def _take(text: str, used: Set[str], pred: Optional[Callable[[str], bool]] = None) -> List[str]:
    """걸러진 문장 중 서로 다른 내용만 남긴다. 개수를 미리 자르지 않는다."""
    picked: List[str] = []
    for sentence in _sentences(text):
        if sentence in used or _blocked(sentence) or _overlaps(sentence, used):
            continue
        if pred is not None and not pred(sentence):
            continue
        if _overlaps(sentence, set(picked)):
            continue
        used.add(sentence)
        picked.append(sentence)
    return picked


def assemble(
    travel: Optional[dict],
    hobby: Optional[dict],
    *,
    move_high: bool,
    play_high: bool,
    company: str,
    timing_months: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """여섯 섹션. travel/hobby 원문 필드는 서로 다른 칸에만 들어간다."""
    t = _body(travel, _FALLBACK_TRAVEL)
    h = _body(hobby, _FALLBACK_HOBBY)
    if company not in _COMPANY:
        company = "either"
    months = [str(m).strip() for m in (timing_months or []) if str(m).strip()]

    lead_travel = move_high or not play_high
    lead_kw = _tags(t["keywords"] if lead_travel else h["keywords"])
    other_kw = _tags(h["keywords"] if lead_travel else t["keywords"])
    keywords: List[str] = []
    for word in lead_kw + other_kw:
        if word not in keywords:
            keywords.append(word)
    keywords = keywords[:3] or ["#환기"]
    used: Set[str] = set()
    axis = (move_high, play_high)
    lead_flow = str(t["overall_flow"] if lead_travel else h["overall_flow"])

    flow = _plain_prefer(_take(lead_flow, used, pred=lambda sentence: not _opposes_move(sentence, move_high)))
    if flow:
        lead_bits = [s for s in flow if _has(s, ("흐름", "방향", "진행", "해입니다", "해예요"))]
        rest_bits = [s for s in flow if s not in lead_bits]
        parts = [" ".join(lead_bits + rest_bits)]
    else:
        parts = [_OPENING[axis]]
        used.add(_OPENING[axis])

    chance: Dict[str, bool] = {}
    style_src = str(t["travel_style"])
    define_for_tone = [
        sentence for sentence in _sentences(style_src)
        if _style_role(sentence) == "define"
        and not _blocked(sentence)
        and not _has(sentence, _FATE)
        and not _has(sentence, _DENSE)
    ]
    tone = _style_tone(" ".join(define_for_tone))
    style = _arrange_style(
        _take(style_src, used, pred=lambda sentence: _keep_style_sentence(sentence, move_high, tone)),
        chance,
    )
    if not style:
        style = [
            "기간은 짧게 잡고, 하루 일정은 비워 두는 편이 맞아요."
            if not move_high
            else "장소를 여러 종류로 늘리기보다, 움직이는 방식 하나를 정하는 편이 맞아요."
        ]
    # 동행 문장에 즉흥이 있어도 스타일 정의가 액티브면 액티브로 둔다.
    tone = _style_tone(style[0]) or tone
    if tone == "active" and _has(" ".join(style), ("에너지", "발산", "온몸")):
        chance["energy"] = True

    def _spot_ok(sentence: str) -> bool:
        if _opposes_move(sentence, move_high):
            return False
        if tone == "impulse" and _has(sentence, ("이동 그 자체", "두루 거치")):
            return False
        if (
            tone == "active"
            and chance.get("energy")
            and _has(sentence, ("에너지", "발산", "온몸"))
            and not _has(sentence, ("동행", "친구", "짐", "숙소", "사람", "명소"))
        ):
            return False
        return _chance_keep(sentence, chance)

    spot = _take(str(t["recommended_spots"]), used, pred=_spot_ok)
    if months:
        when = ", ".join(months[:3])
        spot.insert(0, f"올해 흐름이 더 편한 달은 {when}이에요.")
    elif not spot:
        spot = ["특정한 달이나 방향을 정해 두지는 않았어요. 일정과 체력이 맞는 거리와 분위기를 고르면 충분해요."]

    activity = _pick_hobby(str(h["active_activities"]), used, play_high)
    if not activity:
        activity = ["새로운 것을 여러 개 벌리기보다, 이미 손이 가는 것 하나에 머무는 편이 맞아요."]

    def _company_ok(sentence: str) -> bool:
        # 여행 동행은 스타일 섹션에 있다. 여기에는 취미를 혼자 둘지 함께할지만 남긴다.
        if _has(sentence, ("동행은", "숙소는", "캐리어")):
            return False
        if _has(sentence, _NARROW_SPORT) or _has(sentence, _RECORD) or _has(sentence, _FATE) or _has(sentence, _INTENSE):
            return False
        return not _has(sentence, _EXCLUSIVE)

    company_body = _arrange_company(_take(str(h.get("solo_vs_group") or ""), used, pred=_company_ok))
    company_parts = company_body or [_COMPANY[company]]

    reward: List[str] = []
    travel_gain = _take(
        str(t["travel_luck"]), used,
        pred=lambda sentence: (
            not _has(sentence, _FATE)
            and not _has(sentence, _PUSH_ALL)
            and _chance_keep(sentence, chance)
            and not _opposes_move(sentence, move_high)
        ),
    )
    if tone == "active":
        travel_gain = _one_drive(travel_gain)

    def _hobby_gain_ok(sentence: str) -> bool:
        if _blocked(sentence) or _has(sentence, _RECORD) or _has(sentence, _FATE) or _has(sentence, _BODY_PUSH):
            return False
        if _has(sentence, ("모든 에너지",)):
            return False
        if tone == "active":
            return True
        return not _opposes_move(sentence, move_high)

    hobby_gain = _take(str(h["benefits"]), used, pred=_hobby_gain_ok)
    if travel_gain:
        reward.append("여행에서 얻는 수확")
        reward.extend(travel_gain)
    if hobby_gain:
        reward.append("취미에서 얻는 수확")
        reward.extend(hobby_gain)
    reward.append(_STYLE_CLOSE.get(tone) or _CAUTION[axis])

    headline = str(t["one_line"] if lead_travel else h["one_line"])
    if _opposes_move(headline, move_high):
        headline = _OPENING[axis].split(".")[0].strip() + "."

    return {
        "symbol": {
            "keywords": keywords,
            "object": str(t["concept_object"] if lead_travel else h["concept_object"]),
            "headline": headline,
        },
        "section_1_overall_flow": _join(parts),
        "section_2_travel_style": _join(style),
        "section_3_recommended_spot": _join(spot),
        "section_4_matched_activity": _join(activity),
        "section_5_solo_vs_together": _join(company_parts),
        "section_6_final_reward": _join(reward),
    }


def _join(parts: List[str]) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())
