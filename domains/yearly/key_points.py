"""총운 '올해의 핵심 포인트' — 요청 중 LLM 없이 테마에서 세 영역을 고른다.

월별 사건을 예측하지 않는다. 문장은 다른 총운 칸을 복사하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class _Area:
    key: str
    title: str
    markers: Sequence[str]


AREAS: Sequence[_Area] = (
    _Area("career", "커리어와 도전", ("직장", "도전", "커리어", "승진", "프로젝트", "책임", "몰입", "실력", "역할", "업무", "성취", "열정")),
    _Area("wealth", "재물과 자산", ("재물", "수입", "자산", "소비", "저축", "통장", "소득", "지출")),
    _Area("relation", "인간관계와 인연", ("관계", "인연", "소통", "동료", "가족", "오해", "사람")),
    _Area("love", "사랑과 감정", ("사랑", "연애", "설렘", "애정", "연인")),
    _Area("life", "생활과 환경", ("일상", "환경", "생활", "루틴", "동선", "자리")),
    _Area("growth", "자기계발과 성장", ("배움", "성장", "공부", "내면", "내실")),
    _Area("health", "건강과 에너지", ("체력", "컨디션", "에너지", "건강", "휴식", "활력")),
    _Area("expand", "새로운 기회와 확장", ("확장", "시작", "이동", "도약", "새로운", "변화")),
)

_BODIES = {
    "career": (
        "맡은 범위를 문장으로 적고, 그 안의 일을 먼저 닫는 흐름이 일에 힘이 실려요. 역할을 더 받기 전에 지금 열린 건의 마감을 확인하는 편이 낫습니다.",
        "공식적인 자리에서 결론을 먼저 말하면 인상이 남기 쉬운 흐름이에요. 준비되지 않은 약속은 날짜를 보기 전에 수락하지 않는 선이 필요합니다.",
        "실력은 새 간판보다 이미 하고 있는 일의 완성도에서 드러나기 쉬워요. 비교를 늘리기보다 결과물의 기준을 하나 정해 두세요.",
    ),
    "wealth": (
        "들어올 금액과 나갈 금액을 같은 주에 적어 보면 흐름이 보이기 쉬워요. 설명을 충분히 듣지 못한 상품은 서두르지 않는 편이 안전합니다.",
        "고정으로 들어오는 금액과 들쭉날쭉한 금액을 나눠 보는 것이 맞아요. 한 번에 판을 키우기보다 작은 단위로 확인한 뒤 다음을 정하세요.",
        "이름이 불분명한 지출이 반복되면 통장 잔액이 먼저 줄어요. 결제 전에 하루를 두고, 여전히 필요한 것만 남기세요.",
    ),
    "relation": (
        "말의 온도가 관계의 속도를 좌우하기 쉬운 흐름이에요. 여러 사람에게 다른 버전을 전하기보다 같은 내용을 한 번만 전하세요.",
        "도움을 받을 때는 필요한 것과 시점을 같이 말하는 편이 오해를 줄여요. 거절이 와도 바로 다른 사람에게 같은 부탁을 돌리지 마세요.",
        "가까운 사람과의 약속은 횟수보다 지킨 시간이 더 크게 남아요. 모임 수를 늘리기보다 이미 있는 약속을 지키는 쪽이 낫습니다.",
    ),
    "love": (
        "표현은 크게 할수록 좋은 것이 아니라, 상대가 알아듣는 크기로 전할 때 이어지기 쉬워요. 답을 재촉하기보다 서로의 일정을 먼저 맞추세요.",
        "설렘과 편함은 다른 신호예요. 한쪽만 보고 관계를 정하기보다 함께 보낸 하루가 편한지를 보세요.",
        "연락의 간격이 벌어질 때 추측으로 채우면 서로 먼저 지치기 쉬워요. 확인하고 싶은 것은 한 문장으로 물어 보세요.",
    ),
    "life": (
        "사는 곳과 하루의 순서가 컨디션을 좌우하기 쉬워요. 판을 통째로 바꾸기보다 아침 순서 하나만 고정해 보세요.",
        "익숙한 동선이 힘을 아끼게 해 주는 흐름이에요. 이사나 큰 정리는 급하게 날짜를 박지 말고, 체력과 비용을 같이 적고 정하세요.",
        "집안과 일의 경계가 흐리면 둘 다 남아요. 일을 끝내는 자리를 하나로 정해 두면 생활이 덜 섞입니다.",
    ),
    "growth": (
        "배움은 많이 등록할수록 느는 것이 아니라, 이번 주에 쓰는 한 가지를 끝낼 때 남아요. 자료만 모으지 말고 작은 결과물을 먼저 만드세요.",
        "막힌 부분은 검색을 반복하기보다, 그 일을 해 본 사람에게 과정을 물어 보세요. 들은 내용은 다섯 줄로 남겨 두세요.",
        "실력이 느는 구간은 조용히 반복하는 시간에 가까워요. 보여 주기용 계획표보다 오늘 끝낸 분량을 적는 편이 맞습니다.",
    ),
    "health": (
        "체력은 큰 결심보다 잠과 움직이는 시간의 균형에서 갈려요. 아픈 곳을 단정하기보다, 피로가 쌓이는 요일을 적고 그 전날 일정을 줄여 보세요.",
        "기운이 떨어지는 날에는 강도를 높이기보다 걷는 시간과 쉬는 시간을 먼저 지키세요. 몸 상태를 무시하고 일정을 채우면 다음 주가 더 무거워지기 쉽습니다.",
        "몸의 신호는 늦게 알아차리기 쉬워요. 잠이 들쭉날쭉한 주에는 새 운동을 더하기보다 기존 리듬을 먼저 되돌리세요.",
    ),
    "expand": (
        "새 판은 한꺼번에 열기보다, 시험 삼아 작은 범위를 먼저 열어 보는 흐름이 맞아요. 반응이 없으면 바로 키우지 말고 기준을 다시 적으세요.",
        "이동이나 시작이 많아 보여도, 남길 것과 접을 것을 같이 정해야 힘이 남아요. 관심만 있는 제안은 목록에 적고 일주일 뒤에 다시 보세요.",
        "넓히는 일은 속도보다 순서가 중요해요. 다음 단계에 필요한 것 하나를 적고, 그게 준비되기 전에는 판을 넓히지 마세요.",
    ),
}

_BANNED = ("반드시", "무조건", "손실을 피", "투자하면", "여러분", "십신", "신강", "신약", "용신")


def _slot(seed: str, modulo: int) -> int:
    n = 0
    for ch in seed:
        n = (n * 33 + ord(ch)) % 1_000_003
    return n % modulo


def _hits(text: str, markers: Sequence[str]) -> int:
    return sum(1 for marker in markers if marker and marker in text)


def _lead(keyword: str) -> str:
    word = (keyword or "").strip()
    if not word or len(word) > 14 or any(bad in word for bad in _BANNED):
        return ""
    return f"이 해의 결은 ‘{word}’에 가까워요. "


def _overlaps(body: str, others: Iterable[str], size: int = 18) -> bool:
    haystack = "\n".join(text for text in others if text)
    if len(body) < size or not haystack:
        return False
    return any(body[i:i + size] in haystack for i in range(0, len(body) - size + 1))


def _body(area: _Area, seed: str, avoid: Sequence[str]) -> str:
    options = _BODIES[area.key]
    start = _slot(seed + area.key, len(options))
    for shift in range(len(options)):
        text = options[(start + shift) % len(options)]
        if not _overlaps(text, avoid):
            return text
    return options[start]


def build_key_points(
    one_line: str = "",
    keywords: Sequence[str] | None = None,
    overall_flow: str = "",
    seed: str = "",
    avoid: Sequence[str] | None = None,
) -> List[dict]:
    """테마에 맞는 영역 세 개. 항상 01·02·03 카드다."""
    words = [str(word).strip() for word in (keywords or []) if str(word).strip()]
    theme = f"{one_line} {' '.join(words)}"
    flow = overall_flow or ""
    turn = _slot(seed or theme, len(AREAS))
    ranked = []
    for index, area in enumerate(AREAS):
        score = _hits(theme, area.markers) * 4 + min(2, _hits(flow, area.markers))
        ranked.append((-score, (index + turn) % len(AREAS), area))
    ranked.sort()
    chosen = [area for _, _, area in ranked[:3]]
    blocked = list(avoid or [])
    points = []
    for number, area in enumerate(chosen, start=1):
        text = _body(area, seed or theme, blocked)
        if number == 1 and words:
            text = _lead(words[0]) + text
        blocked.append(text)
        points.append({"index": f"{number:02d}", "area": area.title, "body": text})
    return points
