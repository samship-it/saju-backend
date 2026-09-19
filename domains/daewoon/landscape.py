"""10년 대운(DECADE_DAEWOON) — '이 10년의 풍경' 카드.

AI 호출·새 정적 DB 없음. domains/lifelong/landscape.py의 SUBJECT_IMAGE(일간이
상징하는 형상)를 그대로 재수출해 재사용하고, 배경(ENV)은 평생운세와 달리 원국
전체의 elem_power가 아니라 '이 10년 대운 간지의 천간 오행'으로 고른다 — 평생
전체가 아니라 이 10년만의 기운을 보여주는 것이 이 카드의 목적이기 때문.

saju_relation(사주원국-대운 관계 설명)은 lifelong/landscape.py의 build_reason()이
이미 "일간"·"용신" 같은 명리 용어를 문장에 그대로 노출해 온 선례를 이어, 이 10년
대운이 십신 10종(비견/겁재/식신/상관/정재/편재/정관/편관/정인/편인) 중 정확히 어느
것에 해당하고 일간과 어떤 생극 관계를 이루는지 직접 설명한다 — 사용자 요청(더
전문적인 해설을 원하는 유료 모듈, 정/편까지 정확히 구분해달라는 요청)에 따른
의도적 예외이며, content.py의 다른 필드(keywords/domain_analysis 등)는 여전히
십신 용어를 노출하지 않는다.
"""
from typing import Any, Dict, Optional

from core.constants import GAN_ELEM
from domains.lifelong.landscape import ENV_IMAGE, SUBJECT_IMAGE

_DEFAULT_SUBJECT = "고요히 서 있는 존재"
_DEFAULT_ENV = "잔잔한 풍경"

# 십신 10종 → 일간과의 생극 관계 설명. {decade_elem}=이 대운 천간 오행, {day_elem}=
# 원국 일간 오행으로 채워진다. 정/편 쌍(예: 정재/편재)은 오행 생극 방향은 같지만
# 음양 일치 여부가 다르므로(정=음양 다름, 편=음양 같음), 그 차이를 문장에 직접
# 반영해 두 십신이 같은 문구를 내지 않도록 한다.
SAJU_RELATION_TEMPLATE: Dict[str, str] = {
    "비견": (
        "이 10년은 비견운(比肩運)에 해당합니다. 비견은 나(일간)와 같은 오행·같은 음양으로, "
        "대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운과 대등하게 나란히 서는 "
        "형태를 이룹니다. 서로 같은 무게로 협력하며 내실을 다지는 흐름의 10년입니다."
    ),
    "겁재": (
        "이 10년은 겁재운(劫財運)에 해당합니다. 겁재는 나(일간)와 같은 오행이지만 음양이 다른 "
        "기운으로, 대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운과 부딪히듯 "
        "맞서는 형태를 이룹니다. 승부욕과 경쟁 속에서 체질 자체를 바꿔나가는 흐름의 10년입니다."
    ),
    "식신": (
        "이 10년은 식신운(食神運)에 해당합니다. 식신은 나(일간)의 기운이 같은 음양으로 뻗어나가 "
        "만들어내는 오행으로, 원국 일간의 {day_elem} 기운이 대운 천간의 {decade_elem} 기운을 "
        "안정적으로 낳아 흐르는 형태를 이룹니다. 꾸준한 활동과 탐구가 쌓여가는 흐름의 10년입니다."
    ),
    "상관": (
        "이 10년은 상관운(傷官運)에 해당합니다. 상관은 나(일간)의 기운이 다른 음양으로 뻗어나가 "
        "만들어내는 오행으로, 원국 일간의 {day_elem} 기운이 대운 천간의 {decade_elem} 기운을 "
        "거세게 뿜어내는 형태를 이룹니다. 틀을 깨는 창의성과 파격적인 변화가 두드러지는 흐름의 "
        "10년입니다."
    ),
    "정재": (
        "이 10년은 정재운(正財運)에 해당합니다. 정재는 나(일간)의 기운이 다른 음양의 오행을 "
        "다스리는 관계로, 원국 일간의 {day_elem} 기운이 대운 천간의 {decade_elem} 기운을 "
        "차분히 통제하는 형태를 이룹니다. 안정적인 결실과 고정된 수입이 쌓이는 흐름의 10년입니다."
    ),
    "편재": (
        "이 10년은 편재운(偏財運)에 해당합니다. 편재는 나(일간)의 기운이 같은 음양의 오행을 "
        "다스리는 관계로, 원국 일간의 {day_elem} 기운이 대운 천간의 {decade_elem} 기운을 "
        "폭넓게 움직이는 형태를 이룹니다. 영역을 넓히는 큰 기회와 유동적인 흐름이 두드러지는 "
        "10년입니다."
    ),
    "정관": (
        "이 10년은 정관운(正官運)에 해당합니다. 정관은 나(일간)를 다른 음양의 오행이 다스리는 "
        "관계로, 대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운을 가지런히 "
        "다잡는 형태를 이룹니다. 안정적인 조직과 정석적인 신분이 자리잡는 흐름의 10년입니다."
    ),
    "편관": (
        "이 10년은 편관운(偏官運)에 해당합니다. 편관은 나(일간)를 같은 음양의 오행이 강하게 "
        "다스리는 관계로, 대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운을 "
        "거칠게 몰아붙이는 형태를 이룹니다. 특수한 환경 속에서 단련되고 한계를 극복해가는 "
        "흐름의 10년입니다."
    ),
    "정인": (
        "이 10년은 정인운(正印運)에 해당합니다. 정인은 나(일간)를 다른 음양의 오행이 낳아주는 "
        "관계로, 대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운을 순탄하게 "
        "채워주는 형태를 이룹니다. 정통 학문과 순조로운 지원이 뒷받침되는 흐름의 10년입니다."
    ),
    "편인": (
        "이 10년은 편인운(偏印運)에 해당합니다. 편인은 나(일간)를 같은 음양의 오행이 편중되게 "
        "낳아주는 관계로, 대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운을 "
        "한쪽으로 깊게 채워주는 형태를 이룹니다. 전문 기술이나 자격에 깊이 몰입하는 흐름의 "
        "10년입니다."
    ),
}


def build_decade_landscape(day_master_elem: str, ganji: str, sipsin: Optional[str] = None) -> Dict[str, Any]:
    """day_master_elem(saju["day_master_elem"]) + 이 대운 단계의 간지(+십신 10종 중 하나)
    -> {scene, decade_elem, saju_relation}."""
    gan = ganji[0] if ganji else ""
    decade_elem = GAN_ELEM.get(gan, "")
    subject = SUBJECT_IMAGE.get(day_master_elem, _DEFAULT_SUBJECT)
    env = ENV_IMAGE.get(decade_elem, _DEFAULT_ENV)

    saju_relation = None
    if sipsin and day_master_elem and decade_elem:
        template = SAJU_RELATION_TEMPLATE.get(sipsin)
        if template:
            saju_relation = template.format(decade_elem=decade_elem, day_elem=day_master_elem)

    return {
        "scene": f"{env} 아래 {subject}",
        "decade_elem": decade_elem or None,
        "saju_relation": saju_relation,
    }
