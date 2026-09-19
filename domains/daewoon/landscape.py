"""10년 대운(DECADE_DAEWOON) — '이 10년의 풍경' 카드.

AI 호출·새 정적 DB 없음. domains/lifelong/landscape.py의 SUBJECT_IMAGE(일간이
상징하는 형상)를 그대로 재수출해 재사용하고, 배경(ENV)은 평생운세와 달리 원국
전체의 elem_power가 아니라 '이 10년 대운 간지의 천간 오행'으로 고른다 — 평생
전체가 아니라 이 10년만의 기운을 보여주는 것이 이 카드의 목적이기 때문.

saju_relation(사주원국-대운 관계 설명)은 lifelong/landscape.py의 build_reason()이
이미 "일간"·"용신" 같은 명리 용어를 문장에 그대로 노출해 온 선례를 이어, 이 10년
대운이 어느 십신군(비겁/식상/재성/관성/인성)에 해당하고 일간과 어떤 생극 관계를
이루는지 직접 설명한다 — 사용자 요청(더 전문적인 해설을 원하는 유료 모듈)에 따른
의도적 예외이며, content.py의 다른 필드(keywords/domain_analysis 등)는 여전히
십신 용어를 노출하지 않는다.
"""
from typing import Any, Dict, Optional

from core.constants import GAN_ELEM
from domains.lifelong.landscape import ENV_IMAGE, SUBJECT_IMAGE

_DEFAULT_SUBJECT = "고요히 서 있는 존재"
_DEFAULT_ENV = "잔잔한 풍경"

# 십신군(GROUPS) → 일간과의 생극 관계 설명. {decade_elem}=이 대운 천간 오행,
# {day_elem}=원국 일간 오행으로 채워진다.
SAJU_RELATION_TEMPLATE: Dict[str, str] = {
    "비겁": (
        "이 10년은 비겁운(比劫運)에 해당합니다. 비겁은 나(일간)와 같은 오행으로, 대운 천간의 "
        "{decade_elem} 기운이 원국 일간의 {day_elem} 기운과 같은 세력으로 나란히 서는 형태를 "
        "이룹니다. 원국이 혼자 버티지 않고 같은 편을 얻는 흐름이라, 스스로의 주체성과 추진력이 "
        "크게 강해지는 10년입니다."
    ),
    "식상": (
        "이 10년은 식상운(食傷運)에 해당합니다. 식상은 나(일간)의 기운이 스스로 낳아 밖으로 "
        "뻗어나가는 오행으로, 원국 일간의 {day_elem} 기운이 대운 천간의 {decade_elem} 기운을 "
        "낳아 발산시키는 형태를 이룹니다. 원국 안에 머물던 생각과 재능이 표현과 결과물로 "
        "흘러나오는 흐름입니다."
    ),
    "재성": (
        "이 10년은 재성운(財星運)에 해당합니다. 재성은 나(일간)의 기운이 다스리고 움직이는 "
        "오행으로, 원국 일간의 {day_elem} 기운이 대운 천간의 {decade_elem} 기운을 직접 "
        "통제하는 형태를 이룹니다. 원국의 힘이 현실적인 결과와 실속으로 옮겨가는 흐름입니다."
    ),
    "관성": (
        "이 10년은 관성운(官星運)에 해당합니다. 관성은 나(일간)를 다스리고 통제하는 오행으로, "
        "대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운을 규율 있게 다잡는 "
        "형태를 이룹니다. 원국이 스스로를 절제하며 책임 있는 자리로 나아가는 흐름입니다."
    ),
    "인성": (
        "이 10년은 인성운(印星運)에 해당합니다. 인성은 나(일간)를 낳고 채워주는 오행으로, "
        "대운 천간의 {decade_elem} 기운이 원국 일간의 {day_elem} 기운을 든든하게 밀어주고 "
        "채워주는 형태를 이룹니다. 원국이 안으로 쌓고 배우며 내실을 다지는 흐름입니다."
    ),
}


def build_decade_landscape(day_master_elem: str, ganji: str, group: Optional[str] = None) -> Dict[str, Any]:
    """day_master_elem(saju["day_master_elem"]) + 이 대운 단계의 간지(+지배 십신군)
    -> {scene, decade_elem, saju_relation}."""
    gan = ganji[0] if ganji else ""
    decade_elem = GAN_ELEM.get(gan, "")
    subject = SUBJECT_IMAGE.get(day_master_elem, _DEFAULT_SUBJECT)
    env = ENV_IMAGE.get(decade_elem, _DEFAULT_ENV)

    saju_relation = None
    if group and day_master_elem and decade_elem:
        template = SAJU_RELATION_TEMPLATE.get(group)
        if template:
            saju_relation = template.format(decade_elem=decade_elem, day_elem=day_master_elem)

    return {
        "scene": f"{env} 아래 {subject}",
        "decade_elem": decade_elem or None,
        "saju_relation": saju_relation,
    }
