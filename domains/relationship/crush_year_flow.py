"""단독 짝사랑 종합운.

연애운은 가중치 없이 세 요소 중 두 개 이상이 켜진 해만 있다.
요소 하나는 결론이 아니다. 충은 그 자체로 나쁜 해로 두지 않는다.

요소는 기존 계산만 쓴다.
- 배우자궁: branch_relation, 그리고 결혼 10년 창과 같은 일지 삼합
- 배우자성: spouse_star 의 원국 존재, sipsin_of_ganji 로 본 세운 천간·지지
- 도화·홍염: analyze_sinsal. 세운 지지를 같은 함수에 넣어 그해 활성화만 본다.

문장 15개는 이미 쓰인 종합운이다. 여기서 고치거나 새로 만들지 않는다.
같은 유형은 연애 월운과 같이 슬롯을 순환한다.
"""
import re
from typing import Dict, Optional

from core.constants import PA, SAMHAP, YUKHAP
from core.daewoon import GAN_H, JI_H, branch_relation, get_seewoon_list
from core.saju_base import sipsin_of_ganji
from core.sinsal import analyze_sinsal
from core.sipsin import sipsin_group

STAY = "진전"
HOLD = "자중"
OUTWARD = "새인연"

# HEAD 의 2026 종합운. 유형마다 앞 5개. 글자는 그대로다.
_TEXT = {
    STAY: (
        "좋아하는 사람을 향해 마음이 자연스럽게 기울어져서 자꾸만 그쪽으로 시선이 향해요. 오랫동안 마음에 담아둔 그 사람의 작은 행동 하나에도 의미를 두게 돼요. 내 안에서 싹튼 감정이 점점 커져서 숨기려고 해도 숨겨지지 않는 모습이에요.",
        "이미 마음에 둔 사람을 향해 시선이 자꾸만 머물러요. 그 사람 생각으로 가득 차서 마음이 자연스럽게 그쪽으로만 기울어져요. 매일 그 사람을 떠올리며 감정이 더욱 깊어지는 시기예요.",
        "마음에 둔 사람을 향하는 시선에 저절로 힘이 실려요. 깊게 얽히는 작용이 일어나서 마음이 다른 곳으로 흩어지지 않아요. 오랫동안 머물던 곳에 감정이 더 깊게 고정되는 시기예요.",
        "이미 마음에 둔 사람을 향해 자꾸만 시선이 머무는 시기예요. 그 사람의 작은 행동 하나에도 마음이 깊게 흔들려요. 좋아하는 감정이 커져서 숨기려고 해도 자꾸 드러나게 돼요. 혼자서 그 사람을 떠올리는 시간들이 늘어나요.",
        "이미 마음에 둔 사람을 향해 자꾸만 시선이 기울어지는 해예요. 마음속에 품은 그 사람에 대한 생각으로 자연스럽게 발걸음이 움직이게 돼요. 숨길 수 없이 커진 마음이 그 사람에게로 자꾸만 향하고 있어요.",
    ),
    HOLD: (
        "좋아하는 마음이 커져도 앞으로 먼저 다가서지 못하고 멈춰 서게 돼요. 마음속에서 일어나는 생각들이 자꾸 앞서나가는 행동을 붙잡아요. 그래서 상대에게 다가가는 대신 멀리서 바라보며 조용히 마음을 다스리게 돼요.",
        "좋아하는 마음이 자꾸 커지지만 나서지 않고 멈춰 서게 돼요. 마음을 표현하고 싶어도 엇갈릴까 봐 스스로를 단단히 제어하게 돼요. 다가가고 싶은 감정을 꾹 누르며 일정한 거리를 유지하는 중이에요.",
        "마음에 둔 사람을 향하던 시선을 거두고 스스로를 돌아보게 돼요. 관계가 어긋나는 모양새라 먼저 다가가지 못하고 멈춰 서게 돼요. 좋아하는 마음이 남아 있어도 쉽게 앞으로 밀지 않고 숨을 고르게 돼요. 조용히 내 자리를 지키면서 마음을 가라앉히는 시기예요.",
        "마음에 품은 사람을 향해 쉽게 다가서지 못하고 멈춰 서게 돼요. 상황 속에서 괜히 앞서 나가지 않고 조용히 마음을 가라앉히게 돼요. 불필요한 행동을 줄이며 혼자만의 생각을 깊게 정리하는 시기예요.",
        "좋아하는 마음이 자꾸 커지지만 섣불리 다가가지 못하고 멈추게 돼요. 오해를 살 만한 상황이 생길 수 있어서 태도를 조절하게 돼요. 마음을 표현하고 싶은 충동이 일어도 잠시 멈춰 서서 상황을 보게 돼요. 눈에 띄는 행동을 삼키고 속으로만 참는 날들이 이어져요.",
    ),
    OUTWARD: (
        "마음에 둔 사람이 있어도, 그 밖에 새로운 사람이 생길 가능성이 있어요. 그 사람의 말 하나가 귀에 남으면 시선이 잠깐 그쪽으로 갈 수 있어요. 그런 말이 들리지 않으면 마음에 둔 사람은 그대로예요.",
        "좋아하는 사람이 있어도, 마주치는 자리마다 새로운 사람이 생길 가능성은 열려 있어요. 얼굴이 눈에 남으면 마음 한구석이 잠깐 흔들릴 수 있어요. 남는 얼굴이 없으면 시선은 좋아하는 사람에게 있어요.",
        "이미 마음을 둔 사람이 있어도, 다른 자리에서 새로운 사람이 눈에 들어올 가능성이 있어요. 작은 행동이 기억에 남으면 생각이 잠깐 그 사람에게 가요. 기억에 남는 사람이 없으면 원래 마음에 둔 사람이 계속 남아요.",
        "담아 둔 사람이 있어도, 예상 밖의 자리에서 새로운 사람이 생길 가능성이 있어요. 그 사람이 신경 쓰이면 기분이 잠깐 복잡해질 수 있어요. 신경 쓰이는 사람이 없으면 담아 둔 사람은 그대로 마음에 있어요.",
        "가까이에 둔 사람이 있어도, 익숙한 자리 밖에서 새로운 사람이 생길 가능성이 있어요. 낯선 얼굴이 밟히면 설렘이 잠깐 올라올 수 있어요. 밟히는 얼굴이 없으면 가까이에 둔 사람이 계속 마음에 남아요.",
    ),
}


def pillars() -> list:
    return [GAN_H[i % 10] + JI_H[i % 12] for i in range(60)]


def _phrase(flow: str, day_ganji: str, year: int) -> str:
    options = _TEXT[flow]
    try:
        slot = pillars().index(day_ganji)
    except ValueError:
        slot = 0
    return options[(slot + int(year)) % len(options)]


def _samhap(day_branch: str, sewoon_branch: str) -> bool:
    if not day_branch or not sewoon_branch or day_branch == sewoon_branch:
        return False
    return any(day_branch in group and sewoon_branch in group for group in SAMHAP)


def _charm_on(saju: Dict, sewoon_branch: str) -> Dict[str, bool]:
    """원국에 있는 도화·홍염이 세운 지지에서 켜지는지만 본다."""
    natal = saju.get("sinsal") or {}
    branches = {}
    for key, pillar_key in (
        ("year", "year_ganji"),
        ("month", "month_ganji"),
        ("day", "day_ganji"),
        ("hour", "time_ganji"),
    ):
        pillar = saju.get(pillar_key) or ""
        if len(pillar) > 1:
            branches[key] = pillar[1]
    natal_dohwa = bool(natal.get("has_dohwa"))
    natal_hongyeom = bool(natal.get("has_hongyeom"))
    year_dohwa = False
    year_hongyeom = False
    if sewoon_branch and branches:
        probed = dict(branches)
        probed["sewoon"] = sewoon_branch
        pillars = {
            key: (saju.get(pillar_key) or "")
            for key, pillar_key in (
                ("year", "year_ganji"),
                ("month", "month_ganji"),
                ("day", "day_ganji"),
                ("hour", "time_ganji"),
            )
        }
        found = analyze_sinsal(saju.get("day_master") or "", probed, pillars).get("found") or {}
        year_dohwa = "sewoon" in found.get("도화", [])
        year_hongyeom = "sewoon" in found.get("홍염", [])
    return {
        "natal_dohwa": natal_dohwa,
        "natal_hongyeom": natal_hongyeom,
        "year_dohwa": year_dohwa,
        "year_hongyeom": year_hongyeom,
        "on": (natal_dohwa and year_dohwa) or (natal_hongyeom and year_hongyeom),
    }


def _spouse_on(saju: Dict, sewoon: str) -> Dict[str, bool]:
    spouse = saju.get("spouse_star") or {}
    group = spouse.get("spouse_star_group") or ""
    natal = bool(spouse.get("present"))
    se = sipsin_of_ganji(saju.get("day_master") or "", sewoon)
    gan = sipsin_group(se.get("gan") or "")
    ji = sipsin_group(se.get("ji") or "")
    comes = bool(group) and group in {gan, ji}
    return {"natal": natal, "comes": comes, "on": natal and comes}


def _flow(relation: str, samhap: bool, yukhap_and_pa: bool, charm_on: bool) -> Optional[str]:
    """근거가 있는 흐름만 고른다. 없으면 None. 충만으로 자중에 넣지 않는다."""
    if "자형" in relation or relation.startswith(("파", "해", "형")) or yukhap_and_pa:
        return HOLD
    if relation.startswith("육합") or relation.startswith("복음"):
        return STAY
    if relation.startswith("충"):
        return OUTWARD if charm_on else STAY
    if samhap:
        return OUTWARD if charm_on else STAY
    if charm_on:
        return OUTWARD
    return None


_SENTENCE = re.compile(r"[^.!?…]+[.!?…]+|[^.!?…]+$")
_OPENER = re.compile(r"^(하지만|그런데|그래서|그럼에도|다만|오히려|그리고|또)\s*")
_OTHER_ACT = (
    "연락이 오", "연락이 와", "연락을 해", "연락해 올", "연락이 닿", "연락이 올",
    "마주치", "재회를 원", "다가오도록", "해프닝", "구애", "기다리고 있", "반전이 기다",
)
_NEW_PERSON = ("새로운 인연", "새 인연", "다른 인연", "새로운 사람", "새 사람")
_APPROACH = ("그림자", "다가오는 시기", "다가옵니다", "다가오는 때")
_RETURN = (
    "눈앞에 나타", "다시 다가", "다가올", "다시 나타", "손을 내밀",
    "안부를 건네", "먼저 연락",
)


def _sentences(text: str) -> list:
    return [part.strip() for part in _SENTENCE.findall(text or "") if part.strip()]


def _drops_event(sentence: str, flow: Optional[str]) -> bool:
    """상대의 행동이나, 그해 흐름과 반대인 사건 문장만 뺀다."""
    if any(word in sentence for word in _OTHER_ACT):
        return True
    if any(word in sentence for word in _NEW_PERSON):
        return flow != OUTWARD
    if any(word in sentence for word in _APPROACH):
        return flow != STAY
    if flow != STAY and any(word in sentence for word in _RETURN):
        return True
    return False


def _through_close(sentences: list) -> list:
    kept = []
    for sentence in sentences:
        kept.append(sentence)
        if "그뿐" in sentence:
            break
    return kept


_REUNION_CONTACT = {
    STAY: (
        "마음이 그 사람에게 머무는 해\n\n"
        "올해는 마음에 남아 있는 인연에게 먼저 안부를 건네도 괜찮아요. "
        "긴 이야기나 무거운 감정을 전하기보다는 짧고 편안한 한 통의 연락으로 대화를 시작해 보세요. "
        "상대의 반응을 살펴보되, 답이 없다고 해서 같은 말을 반복해서 보내지는 않는 것이 좋아요."
    ),
    HOLD: (
        "마음은 있어도 먼저 당기면 안 되는 해\n\n"
        "올해는 먼저 연락해 관계를 움직이려 하기보다 조금 더 기다려보는 편이 좋아요. "
        "내가 먼저 다가간다고 해서 관계가 원하는 방향으로 흘러가는 것은 아닐 수 있으니, "
        "상대가 먼저 마음을 표현하거나 관계를 이어가려는 움직임이 있는지 살펴보세요."
    ),
    OUTWARD: (
        "그 사람 밖으로도 시선이 갈 수 있는 해\n\n"
        "올해는 지나간 인연에만 마음을 두기보다 조금 다른 방향을 바라보는 것이 좋아요. "
        "굳이 먼저 연락해 관계를 다시 이어가려 애쓰지 않아도 괜찮아요. "
        "지금까지 마음에 두었던 사람 외에도 새로운 가능성을 발견할 수 있는 시기이니, "
        "과거의 인연에 머무르기보다 앞으로의 관계에 여유를 두어 보세요."
    ),
}


_REUNION_CONTACT_WEAK = (
    "올해는 먼저 연락하기보다 조금 더 시간을 두고 상대의 소식을 기다려보는 편이 좋아요. "
    "마음이 앞서 관계를 다시 이어보려 하기보다는, 자연스럽게 연락할 계기가 생길 때까지 여유를 가져보세요. "
    "지금은 서둘러 답을 얻으려 하기보다 잠시 거리를 두고 지난 관계를 돌아보는 것이 더 나은 흐름으로 이어질 수 있어요."
)


def reunion_contact(reading: Optional[Dict]) -> str:
    """단독 재회에서 먼저 연락할지. 연애운이 있으면 세 글, 약하면 기다리는 글이다."""
    if not reading:
        return ""
    if not reading.get("love"):
        return _REUNION_CONTACT_WEAK
    return _REUNION_CONTACT.get(reading.get("flow") or "", "")


def reunion_year_note(reading: Optional[Dict]) -> str:
    """연애운이 있는 해에만 쓰는 앞문장. 약한 해는 빈 문자열이다."""
    if not reading or not reading.get("love"):
        return ""
    if reading.get("flow") == HOLD:
        return "올해는 그 마음이 있어도, 그 관계가 더 분명해지기 어려운 해예요."
    if reading.get("flow") == OUTWARD:
        return (
            "올해는 그 사람 밖으로도 관심이 갈 여지가 있어요. "
            "다른 사람과 사귀게 된다는 뜻은 아니에요."
        )
    return "올해는 그 사람이 다시 마음에 머무는 해예요. 그 사람이 같은 마음인지는 알 수 없어요."


def with_reunion_year(essay: str, reading: Optional[Dict]) -> str:
    """일주 글에서 그해 흐름과 어긋나는 사건만 빼고, 약한 해는 문장을 더하지 않는다."""
    text = (essay or "").strip()
    if not text:
        return text
    flow = reading.get("flow") if reading and reading.get("love") else None
    body = []
    for sentence in _through_close(_sentences(text)):
        if _drops_event(sentence, flow):
            continue
        body.append(sentence)
    if body:
        body[0] = _OPENER.sub("", body[0]).strip()
        if body[0].startswith("이 감정"):
            body[0] = "헤어진 사람이 떠오를 때, 그 감정" + body[0][len("이 감정"):]
        elif body[0].startswith("이 미련"):
            body[0] = "헤어진 사람이 떠오를 때, 그 미련" + body[0][len("이 미련"):]
        elif body[0].startswith("이게"):
            body[0] = "헤어진 사람이 떠오를 때, 그게" + body[0][len("이게"):]
        body = [sentence for sentence in body if sentence]
    kept = " ".join(body).strip()
    note = reunion_year_note(reading)
    if not note:
        return kept or text
    if not kept:
        return note
    return note + " " + kept


def assess(saju: Dict) -> Optional[Dict]:
    """연애운과 문구. 세운이나 일지가 없으면 None."""
    if not isinstance(saju, dict):
        return None
    years = saju.get("seewoon_10years") or []
    sewoon = years[0].get("ganji") if years else ""
    year = saju.get("target_year")
    day = saju.get("day_ganji") or ""
    day_branch = saju.get("day_branch") or (day[1] if len(day) > 1 else "")
    if not year or len(sewoon) < 2 or not day_branch:
        return None

    relation = branch_relation(day_branch, sewoon[1])
    samhap = _samhap(day_branch, sewoon[1])
    pair = frozenset((day_branch, sewoon[1]))
    yukhap_and_pa = pair in YUKHAP and pair in PA
    palace_on = relation != "무관" or samhap
    spouse = _spouse_on(saju, sewoon)
    charm = _charm_on(saju, sewoon[1])
    factors = {
        "배우자궁": palace_on,
        "배우자성": spouse["on"],
        "도화홍염": charm["on"],
    }
    love = sum(factors.values()) >= 2
    flow = _flow(relation, samhap, yukhap_and_pa, charm["on"]) if love else None
    if love and flow is None:
        love = False
    text = _phrase(flow, day, int(year)) if love and flow else None
    return {
        "love": bool(love and text),
        "flow": flow if text else None,
        "text": text,
        "factors": factors,
        "relation": relation,
        "samhap": samhap,
        "yukhap_and_pa": yukhap_and_pa,
        "spouse": spouse,
        "charm": charm,
        "sewoon": sewoon,
        "year": int(year),
        "day_ganji": day,
    }
