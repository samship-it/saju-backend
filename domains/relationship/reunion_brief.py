"""재회운 화면용 한줄평과 구획.

요청 중에 LLM을 부르지 않는다. 재회 콘텐츠 키와 같은 일간·일지만 본다.
시주, 신강약, 용신은 쓰지 않는다. 재회 점수는 이 도메인에 없으므로 좋고 나쁨 등급을 만들지 않는다.

한줄평은 한 문장이다. 근거와 주의는 구획으로 보낸다.
구획은 서로 다른 질문에 답한다.
- 우리는 왜: 두 사주에서 확인되는 강점과 그 근거. 강점이 없으면 만들지 않는다.
- 종합운: 재회를 판단할 때의 기준. 강점 설명을 반복하지 않는다.
- 갈등: 반복될 수 있는 패턴과, 현실에서 확인할 조건. 이별 원인으로 단정하지 않는다.
- 유리한 점과 걸림돌: 재회를 검토할 때 확인할 조건.
- 매력: 관계에서 쓸 수 있는 강점, 표현, 주의.
- 3개월: 확인된 신호에 맞춰 행동·주의·멈춤 기준을 둔다. 신호가 없으면 장면을 만들지 않는다.

두 사람 문장에서 쓰는 근거는 일간 오행 관계와 일지 합·충·파·해·형뿐이다.
일간마다 붙인 속도 형용사는 두 사람 해석에 쓰지 않는다. 내 사주만 볼 때의 습관 설명에만 쓴다.
예시로 거론된 '정리·전환'은 넣지 않는다. 일간·일지만으로 새 인연을 권할 근거가 없다.
"""
from typing import Dict, List, Optional

from core.constants import (
    CHUNG, FIVE_ELEMENT_RELATIONS, GAN_ELEM, HAE, PA, SAMHYEONG,
    SANGHYEONG, SELF_HYEONG, YUKHAP,
)

# 사용자 문장에 십신 이름을 넣지 않는다. 키는 오행 관계 조립용이다.
_ROLE = {
    "비겁": {
        "basis": "두 일간의 기운이 같은 종류라",
        "seat": "당신은 상대와 같은 고집 앞에 서기 쉬워요",
        "use": "익숙한 방식으로 통하는 힘",
        "express": "서로 같은 방식을 먼저 말하고, 양보할 한 가지만 나눠 보세요",
        "caution": "주의할 점은 같은 고집을 상대의 양보로만 풀려고 하지 않는 것이에요.",
        "burden": "같은 고집을 동시에 세우면 양보가 늦어져요.",
        "headline": "같은 고집을 어떻게 나눌지가 재회를 고민할 때의 핵심이에요.",
    },
    "식상": {
        "basis": "당신의 일간 기운이 상대의 일간 기운을 밖으로 꺼내는 쪽이라",
        "seat": "당신은 상대의 막힌 말을 풀어 내는 쪽에 서기 쉬워요",
        "use": "막힌 이야기를 풀어 주는 힘",
        "express": "상대의 이야기를 끝까지 듣고, 서로 다르게 이해한 부분만 정리해 보세요",
        "caution": "주의할 점은 상대의 몫까지 대신 정리하지 않는 것이에요.",
        "burden": "내가 정리를 끝내 버리면 상대의 말이 들어설 자리가 없어요.",
        "headline": "막힌 말을 풀어 주는 자리가 재회를 고민할 때의 핵심이에요.",
    },
    "재성": {
        "basis": "당신의 일간 기운이 상대의 현실 조건을 다루는 쪽이라",
        "seat": "당신은 상대의 현실과 조건을 챙기는 쪽에 서기 쉬워요",
        "use": "현실적인 다음 수를 챙기는 힘",
        "express": "감정 대신, 지금 가능한 조건 한 가지만 말로 꺼내 보세요",
        "caution": "주의할 점은 상대의 선택을 대신 확정하지 않는 것이에요.",
        "burden": "챙겨 주는 말이 상대의 선택을 대신하면 부담이 돼요.",
        "headline": "현실 조건을 누가 챙길지가 재회를 고민할 때의 핵심이에요.",
    },
    "관성": {
        "basis": "상대의 일간 기운이 당신의 속도를 누르는 쪽이라",
        "seat": "당신은 상대의 기준에 내 속도를 맞추는 쪽에 서기 쉬워요",
        "use": "기준을 들으면서도 내 선을 지키는 힘",
        "express": "상대의 기준을 먼저 듣고, 내가 지킬 선 하나를 그 옆에 말하세요",
        "caution": "주의할 점은 맞추는 중에 내 선까지 지우지 않는 것이에요.",
        "burden": "맞추느라 내 속도가 사라지면 예전과 같은 답답함으로 돌아가요.",
        "headline": "상대의 기준과 내 속도를 어떻게 나눌지가 재회를 고민할 때의 핵심이에요.",
    },
    "인성": {
        "basis": "상대의 일간 기운이 당신을 받쳐 주는 쪽이라",
        "seat": "당신은 상대에게 기대어 버티는 쪽에 서기 쉬워요",
        "use": "도움을 받으면서 내 선을 말하는 힘",
        "express": "기대는 부분과 내가 혼자 지킬 부분을 나눠 말해 보세요",
        "caution": "주의할 점은 돌봄을 당연한 약속으로 두지 않는 것이에요.",
        "burden": "돌봄을 당연한 것으로 기대하면 받지 못할 때 서운함이 커져요.",
        "headline": "기대는 마음과 내가 지킬 선을 어떻게 나눌지가 재회를 고민할 때의 핵심이에요.",
    },
}

# 내 사주만 볼 때. 두 사람 해석에는 이 속도 형용사를 넣지 않는다.
_STEM = {
    "甲": {
        "you": "결론을 서두르기",
        "good": "꼬인 상황을 한 줄로 정리하는 힘",
        "show": "정리하기 전에 상대가 한 말을 한 줄로 받아 적고, 그다음에만 한 줄로 묶으세요",
        "risk": "이유가 적히기 전에 결론부터 말하는 습관",
        "after": "끝난 이유를 적기 전에 다시 시작할 결론부터 나와요",
        "watch": "그 결론이 상대의 대답인지, 내 조급함인지 나눠 보세요",
        "purpose": "확인하려는 것이 내 결론인지 상대의 의사인지 먼저 나누세요.",
        "limit": "거절이나 무응답 뒤에 바로 다시 설득하고 싶어지는 것",
    },
    "乙": {
        "you": "관계를 지키려고 자기 속도를 굽히기",
        "good": "다른 사람의 페이스에 맞춰 대화를 이어 가는 힘",
        "show": "맞추기 전에 상대가 원하는 속도를 듣고, 내가 맞출 수 있는 범위만 말하세요",
        "risk": "맞추는 마음이 다른 사람의 답을 대신해 버리는 습관",
        "after": "상대의 답을 기다리기보다 내가 맞춰서 관계를 유지하려 해요",
        "watch": "그 맞춤이 배려인지, 거절을 받아들이지 못하는 것인지 보세요",
        "purpose": "맞추지 않아도 전할 말이 있는지부터 적으세요.",
        "limit": "거절을 듣고도 더 맞춰서 관계를 붙들고 싶어지는 것",
    },
    "丙": {
        "you": "감정이 올라오면 그 온도로 바로 움직이기",
        "good": "식어 버린 대화를 다시 따뜻하게 여는 힘",
        "show": "온도를 올리기 전에 지난번에 식었던 문장을 먼저 꺼내 보세요",
        "risk": "달아오른 기분을 이미 확인된 답으로 여기는 습관",
        "after": "다시 뜨거워진 기분을 상대의 마음인 것처럼 느끼기 쉬워요",
        "watch": "열기가 식은 뒤에도 같은 말인지 확인하고 보내세요",
        "purpose": "지금 온도가 아니라, 식은 뒤에도 전할 말인지를 기준으로 삼으세요.",
        "limit": "답이 식었다고 느껴질 때 온도를 더 올리게 되는 것",
    },
    "丁": {
        "you": "마음을 오래 묵히고 천천히 드러내기",
        "good": "서두르지 않고 들은 말을 남겨 두는 힘",
        "show": "들은 문장을 그대로 적고, 기다릴 날짜를 옆에 같이 적으세요",
        "risk": "기준 없이 기다리며 미련을 정성으로 여기는 습관",
        "after": "소식이 없는 시간을 견디는 것 자체를 정답으로 여기기 쉬워요",
        "watch": "기다림에 기한이 있는지, 없으면 미련인지 한 줄로 정하세요",
        "purpose": "언제까지 기다릴지 날짜를 적지 못하면 연락의 목적도 비어요.",
        "limit": "답이 없어도 기한 없이 계속 기다리게 되는 것",
    },
    "戊": {
        "you": "흔들리지 않으려고 결정을 미루기",
        "good": "감정의 파도 속에서도 일상을 붙드는 힘",
        "show": "오늘 지킬 일상 한 가지와, 오늘 정하지 않을 것을 나눠 적으세요",
        "risk": "미루는 사이에 다른 사람의 마음을 짐작으로 채우는 습관",
        "after": "결정하지 않은 상태를 신중함으로 여기기 쉬워요",
        "watch": "미룬 이유가 정보가 부족해서인지, 짐작을 사실로 두고 싶어서인지 나누세요",
        "purpose": "오늘 정할 수 있는 내 선택 하나만 적고, 나머지는 상대의 몫으로 두세요.",
        "limit": "답을 듣고도 결정을 또 미루게 되는 것",
    },
    "己": {
        "you": "작은 말과 신호를 오래 되짚기",
        "good": "들은 말을 기억해 챙기는 힘",
        "show": "기억한 문장과 실제로 들은 문장을 다른 줄에 적고, 들은 줄만 대화에 쓰세요",
        "risk": "자기 해석을 실제로 들은 말로 착각하는 습관",
        "after": "작은 기억을 상대의 신호처럼 다시 읽기 쉬워요",
        "watch": "그 말이 실제로 들은 문장인지, 내가 덧붙인 해석인지 구분하세요",
        "purpose": "판단에 쓸 문장은 실제로 들은 것만 남기세요.",
        "limit": "짧은 답을 좋은 신호로 확장해서 읽게 되는 것",
    },
    "庚": {
        "you": "흐린 관계를 빨리 잘라 정리하기",
        "good": "감정에 끌려가지 않고 선을 정하는 힘",
        "show": "끊고 싶은 선과, 아직 확인하지 않은 질문 하나를 같이 적으세요",
        "risk": "확인할 말이 남았는데도 정리부터 해 버리는 습관",
        "after": "남은 확인을 생략한 채 이미 끝난 일로 넘기기 쉬워요",
        "watch": "끊기 전에, 아직 물어보지 않은 한 가지가 있는지만 적고 넘어가세요",
        "purpose": "정리하고 싶은 마음과, 아직 확인하지 않은 문제를 다른 줄에 적으세요.",
        "limit": "불편한 답을 듣기 전에 대화를 닫아 버리게 되는 것",
    },
    "辛": {
        "you": "자존심 때문에 하고 싶은 말을 아끼기",
        "good": "쉽게 무너지지 않고 자기 선을 지키는 힘",
        "show": "지키고 싶은 선 하나를 말하고, 잘 보이려는 문장은 빼세요",
        "risk": "확인할 질문 대신 잘 보이려는 말만 고르는 습관",
        "after": "물어볼 질문 대신 체면을 지키는 침묵을 택하기 쉬워요",
        "watch": "보내지 않는 이유가 존중인지, 자존심인지 한 줄로 구분해 보세요",
        "purpose": "잘 보이려는 문장은 빼고, 확인하고 싶은 질문 하나만 남기세요.",
        "limit": "체면이 상할까 봐 필요한 질문을 빼게 되는 것",
    },
    "壬": {
        "you": "여러 가능성을 재느라 결론을 늦추기",
        "good": "한쪽으로 치우치지 않고 상황을 넓게 보는 힘",
        "show": "가능한 결말을 두 줄만 적고, 그중 감당할 수 있는 답만 남기세요",
        "risk": "감당 못 할 반응을 정하지 않은 채 가능성만 늘리는 습관",
        "after": "여러 결말을 상상하느라 내가 감당할 반응을 정하지 못해요",
        "watch": "이번 주에 감당하지 못할 반응을 한 줄로 정해 두세요",
        "purpose": "가능성을 더 열기 전에, 받아도 되는 답과 아닌 답을 나누세요.",
        "limit": "거절을 또 다른 가능성으로 바꿔 읽게 되는 것",
    },
    "癸": {
        "you": "말하지 않은 마음을 상상으로 채우기",
        "good": "드러나지 않은 감정을 조용히 읽어 내는 힘",
        "show": "읽어 낸 마음과 실제로 받은 말을 다른 줄에 적고, 받은 말만 보내세요",
        "risk": "받은 말보다 상상을 판단의 근거로 쓰는 습관",
        "after": "받지 않은 말을 상상으로 채우고 그 상상을 사실처럼 믿기 쉬워요",
        "watch": "상상은 근거가 아니니, 받은 말만 판단에 쓰세요",
        "purpose": "보내기 전에, 상대가 한 말이 아닌 문장을 지우고 다시 읽으세요.",
        "limit": "답이 없을 때 상상이 그 빈자리를 채우게 되는 것",
    },
}


def _batchim(word: str) -> bool:
    if not word or not ("가" <= word[-1] <= "힣"):
        return False
    return (ord(word[-1]) - ord("가")) % 28 != 0


def _eul(word: str) -> str:
    return word + ("을" if _batchim(word) else "를")


def _iga(word: str) -> str:
    return word + ("이" if _batchim(word) else "가")


def _ieyo(word: str) -> str:
    return word + ("이에요" if _batchim(word) else "예요")


def _stem(ganji: str) -> Dict[str, str]:
    gan = ganji[0] if ganji else ""
    return _STEM.get(gan, _STEM["戊"])


def _pair_flags(branch_a: str, branch_b: str) -> Dict[str, bool]:
    if not branch_a or not branch_b:
        return {"missing": True, "hap": False, "chung": False, "pa": False, "hae": False, "hyung": False, "same": False, "self_hyung": False}
    key = frozenset((branch_a, branch_b))
    hyung = key in SANGHYEONG
    if branch_a != branch_b:
        for group, _name in SAMHYEONG:
            if branch_a in group and branch_b in group:
                hyung = True
    same = branch_a == branch_b
    return {
        "missing": False,
        "hap": key in YUKHAP,
        "chung": key in CHUNG,
        "pa": key in PA,
        "hae": key in HAE,
        "hyung": hyung,
        "same": same,
        "self_hyung": same and branch_a in SELF_HYEONG,
    }


def _friction(flags: Dict[str, bool]) -> bool:
    return bool(flags["chung"] or flags["hae"] or flags["hyung"] or flags["pa"])


def _track(flags: Dict[str, bool]) -> str:
    """한줄평과 전략이 따라갈 일지 신호. 운세 등급이 아니다."""
    if flags.get("missing"):
        return "open"
    if flags["hap"] and _friction(flags):
        return "mixed"
    if flags["chung"] or flags["hyung"] or flags["hae"] or flags["same"]:
        return "review"
    if flags["pa"]:
        return "pa"
    if flags["hap"]:
        return "talk"
    return "open"


def _point(flags: Dict[str, bool]) -> str:
    if flags.get("missing"):
        return "그때 헤어진 장면"
    if flags["hap"] and _friction(flags):
        return "붙었다 깨지는 자리"
    if flags["chung"]:
        return "정면으로 부딪힌 주제"
    if flags["hyung"]:
        return "감정이 먼저 세지는 패턴"
    if flags["hae"]:
        return "작게 쌓인 어긋남"
    if flags["self_hyung"]:
        return "같은 버릇이 서로를 누르는 지점"
    if flags["same"]:
        return "같은 생활 버릇"
    if flags["pa"]:
        return "깨지기 쉬운 합의"
    if flags["hap"]:
        return "편함이 덮어 둔 문제"
    return "그때 헤어진 장면"


def _branch_plain(flags: Dict[str, bool]) -> str:
    if flags.get("missing"):
        return ""
    if flags["hap"] and _friction(flags):
        return "두 일지에 붙는 힘과 깨지는 힘이 같이 있어서"
    if flags["chung"]:
        return "두 일지가 정면으로 부딪히는 관계라"
    if flags["hyung"]:
        return "두 일지가 감정을 먼저 세우는 관계라"
    if flags["hae"]:
        return "두 일지가 작은 어긋남을 쌓는 관계라"
    if flags["self_hyung"]:
        return "두 일지가 같은 버릇으로 서로를 누르는 관계라"
    if flags["same"]:
        return "두 일지가 같은 버릇을 마주하는 관계라"
    if flags["pa"]:
        return "두 일지의 합의가 깨지기 쉬운 관계라"
    if flags["hap"]:
        return "두 일지가 붙는 관계라"
    return ""


def _roles(self_ganji: str, partner_ganji: str):
    mine = GAN_ELEM.get(self_ganji[:1])
    theirs = GAN_ELEM.get(partner_ganji[:1])
    if not mine or not theirs:
        return None
    return _ROLE[FIVE_ELEMENT_RELATIONS[(mine, theirs)]]


def _names(labels: List[str]) -> List[str]:
    names = list(labels[:3])
    while len(names) < 3:
        names.append(f"{len(names) + 1}개월차")
    return names


def _headline_couple(flags: Dict[str, bool], role) -> str:
    if flags.get("missing"):
        return "두 사람의 일주를 특정하지 못해, 재회 여부는 헤어진 이유와 상대의 의사만으로 봐요."
    if flags["hap"] and _friction(flags):
        return "가까워지는 힘과 깨지는 힘이 같이 있는 자리를 어떻게 볼지가 핵심이에요."
    if flags["chung"]:
        return "정면으로 부딪힌 주제가 아직 같은지가 재회를 고민할 때의 핵심이에요."
    if flags["hyung"]:
        return "감정이 먼저 세지는 패턴을 멈출 수 있는지가 재회를 고민할 때의 핵심이에요."
    if flags["hae"]:
        return "작게 쌓인 어긋남을 넘기던 버릇이 줄었는지가 재회를 고민할 때의 핵심이에요."
    if flags["self_hyung"]:
        return "같은 버릇이 서로를 누르는 지점을 멈출 수 있는지가 재회를 고민할 때의 핵심이에요."
    if flags["same"]:
        return "같은 생활 버릇을 다시 견딜 수 있는지가 재회를 고민할 때의 핵심이에요."
    if flags["pa"]:
        return "깨지기 쉬운 합의를 다시 만들 수 있는지가 재회를 고민할 때의 핵심이에요."
    if flags["hap"]:
        return "다시 붙기 쉬운 사이에서는, 덮어 둔 문제를 말할 수 있는지가 핵심이에요."
    if role:
        return role["headline"]
    return "두 사람의 일주를 특정하지 못해, 재회 여부는 헤어진 이유와 상대의 의사만으로 봐요."


def _headline_solo(me: Dict[str, str]) -> str:
    return f"재회를 생각할 때 먼저 볼 것은, {me['you']} 쉬운 내 습관이에요."


def _why(flags, role) -> str:
    if flags.get("missing"):
        return "일간과 일지를 특정하지 못해, 두 사람의 강점을 만들지 않았어요."
    if flags["hap"] and not _friction(flags):
        return (
            "두 일지가 붙는 관계라, 일상이 다시 이어지기 쉬운 것이 확인되는 강점이에요. "
            "설명이 짧아도 대화의 문이 열릴 수 있어요. "
            "그 강점은 문제가 해결됐다는 뜻이 아니에요."
        )
    if flags["hap"] and _friction(flags):
        return (
            "확인되는 강점은 두 일지가 붙는 쪽, 일상이 다시 이어지기 쉬운 점뿐이에요. "
            "같이 있는 깨지는 힘은 강점이 아니에요."
        )
    if role is None:
        return "일간과 일지를 특정하지 못해, 두 사람의 강점을 만들지 않았어요."
    return (
        "두 일지에서 서로를 붙잡는 강점은 확인되지 않아요. "
        f"확인되는 것은 일간이 맞닿는 방식이에요. {role['basis']}, {role['seat']}. "
        "이건 상대가 지금 그 자리를 원한다는 뜻은 아니에요."
    )


def _overall(flags, point: str) -> str:
    if flags.get("missing"):
        return "일주를 특정하지 못해, 재회를 판단할 기준을 사주로 만들지 않았어요. 헤어진 이유와 상대가 보인 의사만 보세요."
    if flags["hap"] and not _friction(flags):
        return "재회를 판단할 때는 문이 열리는지보다, 열린 뒤에 덮어 둔 문제를 말할 수 있는지를 보세요. 대화가 없으면 재회로 넘어가지 마세요."
    if flags["hap"] and _friction(flags):
        return "붙는 힘과 깨지는 힘이 같이 있어요. 어느 쪽이 재회를 정해 주지는 않으니, 상대가 실제로 보인 반응만 다음 판단에 쓰세요."
    if flags["chung"] or flags["hyung"] or flags["hae"] or flags["same"] or flags["self_hyung"]:
        return f"재회를 판단할 때는 {_iga(point)} 아직 같은지, 그리고 두 사람이 그걸 다르게 다룰 말이 있는지를 보세요."
    if flags["pa"]:
        return "재회를 판단할 때는 깨졌던 합의를 다시 말로 만들 수 있는지를 보세요. 괜찮아 보이던 기억만으로 넘어가지 마세요."
    return "일지에 붙거나 부딪히는 신호가 없어서, 재회는 그 신호로 정해지지 않아요. 헤어진 이유와 상대가 보인 의사만 기준으로 보세요."


def _conflict(flags, role, point: str) -> str:
    if flags.get("missing"):
        return "일주를 특정하지 못해, 반복될 패턴을 사주로 정하지 않았어요. 헤어진 이유가 아직도 같은 말인지만 확인해 보세요."
    if flags["hap"] or flags["chung"] or flags["hyung"] or flags["hae"] or flags["same"] or flags["pa"] or flags["self_hyung"]:
        return (
            f"반복될 수 있는 패턴은 {_ieyo(point)}. "
            f"{_branch_plain(flags)} 이 패턴을 반복 후보로 봐요. "
            "이것이 실제 이별 원인이었는지는 사주가 몰라요. "
            "현실에서 볼 것은, 그 말이 아직도 같은지예요."
        )
    if role is None:
        return "일지가 갈등의 모양을 정해 주지는 않아요. 없는 장면을 만들어 이별의 원인으로 두지 마세요."
    return (
        "일지가 갈등의 모양을 정해 주지는 않아요. "
        f"점검할 수 있는 반복은 당신이 서는 방식이에요. {role['burden']} "
        "이것이 헤어진 원인이었다는 뜻은 아니에요. "
        "다시 만나면 그 방식이 돌아올 수 있는지만 보면 돼요."
    )


def _balance(flags) -> str:
    if flags.get("missing"):
        return "유리한 조건과 걸림돌을 사주로 만들지 않았어요. 상대가 보인 의사만 다음 조건으로 보세요."
    if flags["hap"] and not _friction(flags):
        return (
            "확인할 조건은 두 가지예요. "
            "유리한 조건은 대화의 문이 다시 열리기 쉽다는 점이에요. "
            "걸림돌은 문이 열렸다는 이유로 덮어 둔 문제를 건너뛰는 일이에요. "
            "유리한 조건이 있어도 재회가 되는 것은 아니에요. "
            "그 문제를 두 사람이 인정할 때만 다음을 생각하세요."
        )
    if flags["hap"] and _friction(flags):
        return (
            "확인할 조건은 두 가지예요. "
            "유리한 조건은 가까워질 수 있는 자리가 아직 있다는 점이에요. "
            "걸림돌은 그 자리가 깨지는 힘과 같이 있어서, 어느 쪽인지 기억만으로 고르게 되는 일이에요. "
            "유리한 조건이 있어도 재회가 되는 것은 아니에요. "
            "상대가 보인 반응으로만 다음을 생각하세요."
        )
    if flags["chung"] or flags["hyung"] or flags["self_hyung"]:
        return (
            "확인할 조건은 두 가지예요. "
            "유리한 조건은 문제가 숨지 않아 이름을 붙이기 쉽다는 점이에요. "
            "걸림돌은 그 이름이 그대로인 채 관계만 되돌리는 일이에요. "
            "이름을 붙일 수 있어도 재회가 되는 것은 아니에요. "
            "두 사람이 그 문제를 다르게 다룰 말을 인정할 때만 다음을 생각하세요."
        )
    if flags["hae"] or flags["same"] or flags["pa"]:
        return (
            "확인할 조건은 두 가지예요. "
            "유리한 조건은 작은 차이를 알아챌 수 있다는 점이에요. "
            "걸림돌은 그 차이를 알고도 넘겨 버리는 일이에요. "
            "알아채는 것만으로 재회가 되는 것은 아니에요. "
            "넘기지 않기로 한 문장이 있을 때만 다음을 생각하세요."
        )
    return (
        "일지가 재회에 유리한 조건과 걸림돌을 정해 주지는 않아요. "
        "현실에서 확인할 조건은 두 가지예요. "
        "상대가 그 대화를 받아들이는지, 그리고 헤어진 이유가 아직 같은 말인지예요. "
        "둘 중 하나라도 아니면 다음을 생각하지 마세요."
    )


def _charm_couple(role) -> str:
    if role is None:
        return "일간을 특정하지 못해, 이 조합만의 매력을 만들지 않았어요. 상대의 말을 끝까지 듣고, 상대의 몫까지 대신 정하지 않는 선에서만 대화를 이어 보세요."
    return (
        f"이 관계에서 강점으로 보일 수 있는 점은 {_ieyo(role['use'])}. "
        f"표현할 때는 {role['express']}. "
        f"{role['caution']}"
    )


def _charm_solo(me) -> str:
    return (
        f"과거 인연 앞에서 강점으로 보일 수 있는 점은 {me['good']}이에요. "
        f"표현할 때는 {me['show']}. "
        f"주의할 점은 {me['risk']}이 그 강점을 덮지 않게 하는 것이에요."
    )


def _solo_attitude(me) -> str:
    return (
        f"당신의 일간은 {me['you']} 쉬운 쪽이에요. "
        f"이별 뒤에는 {me['after']}. "
        f"다시 그 사람을 떠올릴 때 볼 기준은 이거예요. {me['watch']}."
    )


def _solo_contact(me) -> str:
    return (
        "연락은 상대의 마음을 확인하려는 목적이면 보내지 마세요. "
        f"{me['purpose']} "
        f"감당하지 못할 반응은 {me['limit']}이에요. "
        "그 반응이 시작되면 멈추세요. "
        "상대가 언제 답할지는 내 사주로 알 수 없어요."
    )


def _months_couple(labels: List[str], track: str, point: str) -> List[Dict[str, str]]:
    names = _names(labels)
    quiet = "답이 없는데 같은 말을 반복하지 마세요."
    calendar = "세 달을 채웠다는 이유로 결론을 만들지 마세요."
    if track == "talk":
        return [
            {
                "month": names[0],
                "focus": "덮어 둔 문제를 한 줄로 적는 달",
                "action": "편함이 덮어 둔 문제를 한 문장으로 적으세요.",
                "caution": "다시 만나고 싶은 기분을 문제가 해결된 신호로 바꾸지 마세요.",
                "criterion": "한 문장으로 못 적으면 이번 달에는 대화를 열지 않아요.",
            },
            {
                "month": names[1],
                "focus": "대화가 열린 경우에만 그 문장을 말하는 달",
                "action": "이미 대화가 있는 경우에만, 적어 둔 그 문제를 한 문장으로 말하세요.",
                "caution": quiet,
                "criterion": "대화가 없으면 첫째 달의 기준을 유지해요. 침묵을 호감으로 읽지 않아요.",
            },
            {
                "month": names[2],
                "focus": "그 문제가 말로 다뤄졌는지만 보는 달",
                "action": "들은 말에 그 문제가 다뤄졌는지 비교하세요.",
                "caution": calendar,
                "criterion": "문제가 그대로고 바꿀 합의가 없으면 재회를 다음 단계로 밀지 않아요.",
            },
        ]
    if track == "review":
        topic = _iga(point)
        return [
            {
                "month": names[0],
                "focus": f"{topic} 아직 같은 문장인지 적는 달",
                "action": f"헤어진 이유와 {_eul(point)} 나란히 적고, 같은 문장인지 표시하세요.",
                "caution": "같은 문장으로 보여도, 그것만으로 이별의 원인이었다고 확정하지 마세요.",
                "criterion": "같은지 표시하지 못하면 이번 달에는 대화를 열지 않아요.",
            },
            {
                "month": names[1],
                "focus": "대화가 있는 경우에만 그 패턴이 남았는지 묻는 달",
                "action": f"이미 대화가 있는 경우에만, {topic} 아직 같은지 한 문장으로 물어보세요.",
                "caution": quiet,
                "criterion": "대화가 없으면 첫째 달의 기준을 유지해요. 침묵을 호감으로 읽지 않아요.",
            },
            {
                "month": names[2],
                "focus": "들은 말로 그 패턴을 이어갈지 멈추는 달",
                "action": "들은 말에 그 패턴을 다르게 다룰 합의가 있는지만 보세요.",
                "caution": calendar,
                "criterion": "합의가 없으면 재회를 다음 단계로 밀지 않아요.",
            },
        ]
    if track == "mixed":
        return [
            {
                "month": names[0],
                "focus": "붙는 기억과 깨진 장면을 다른 줄에 적는 달",
                "action": "좋아 보이던 기억과, 실제로 깨졌던 장면을 다른 줄에 적으세요.",
                "caution": "좋아 보이던 기억이 깨진 장면을 지우게 두지 마세요.",
                "criterion": "두 줄을 못 나누면 이번 달에는 대화를 열지 않아요.",
            },
            {
                "month": names[1],
                "focus": "대화가 있는 경우에만 깨진 장면이 남았는지 보는 달",
                "action": "이미 대화가 있는 경우에만, 깨진 장면이 아직 같은지 한 문장으로 물어보세요.",
                "caution": quiet,
                "criterion": "대화가 없으면 어느 쪽 마음인지 정하지 않아요. 침묵을 호감으로 읽지 않아요.",
            },
            {
                "month": names[2],
                "focus": "보인 반응만으로 멈추거나 한 걸음만 정하는 달",
                "action": "들은 반응이 깨진 장면을 다룰 때만 다음을 생각하세요.",
                "caution": "세 달을 채웠다는 이유로 가까워지는 쪽을 고르지 마세요.",
                "criterion": "반응이 없으면 재회를 다음 단계로 밀지 않아요.",
            },
        ]
    if track == "pa":
        return [
            {
                "month": names[0],
                "focus": "깨졌던 합의를 한 문장으로 적는 달",
                "action": "그때 깨진 합의를 한 문장으로 적으세요. 괜찮아 보이던 기억은 다른 줄에 두세요.",
                "caution": "기억 속의 괜찮음을 합의가 복구된 것으로 바꾸지 마세요.",
                "criterion": "합의 문장이 안 나오면 이번 달에는 대화를 열지 않아요.",
            },
            {
                "month": names[1],
                "focus": "대화가 있는 경우에만 그 합의를 다시 말하는지 보는 달",
                "action": "이미 대화가 있는 경우에만, 그 합의를 다시 만들 말인지 한 문장으로 물어보세요.",
                "caution": quiet,
                "criterion": "대화가 없으면 첫째 달의 기준을 유지해요. 침묵을 호감으로 읽지 않아요.",
            },
            {
                "month": names[2],
                "focus": "합의가 말로 돌아왔는지만 보는 달",
                "action": "들은 말에 새 합의가 있을 때만 다음을 생각하세요.",
                "caution": calendar,
                "criterion": "합의가 없으면 재회를 다음 단계로 밀지 않아요.",
            },
        ]
    return [
        {
            "month": names[0],
            "focus": "헤어진 이유를 양쪽 말로 나누는 달",
            "action": "내가 기억하는 이유와, 그때 상대가 실제로 한 말을 다른 줄에 적으세요.",
            "caution": "사주에 없는 갈등 장면을 만들어 빈칸을 채우지 마세요.",
            "criterion": "두 줄이 없으면 이번 달에는 대화를 열지 않아요.",
        },
        {
            "month": names[1],
            "focus": "답이 있는 경우에만 그 두 줄을 비교하는 달",
            "action": "이미 답이 있는 경우에만, 상대가 한 말이 내가 적은 이유와 같은지 보세요.",
            "caution": quiet,
            "criterion": "답이 없으면 비교하지 않아요. 침묵을 호감으로 읽지 않아요.",
        },
        {
            "month": names[2],
            "focus": "오간 말만으로 멈추거나 한 걸음만 정하는 달",
            "action": "오간 말이 없으면 새로 보내지 마세요. 있으면 그 말과 내가 적은 이유가 겹칠 때만 다음을 생각하세요.",
            "caution": calendar,
            "criterion": "겹치는 말이 없으면 재회를 다음 단계로 밀지 않아요.",
        },
    ]


def _months_solo(labels: List[str], me: Dict[str, str]) -> List[Dict[str, str]]:
    names = _names(labels)
    return [
        {
            "month": names[0],
            "focus": f"{me['you']} 습관과 헤어진 이유를 나란히 적는 달",
            "action": f"헤어진 이유 옆에, 내가 {me['you']} 쉬운 태도를 한 줄만 적으세요.",
            "caution": "적는 일에 상대의 마음을 추측해서 채우지 마세요.",
            "criterion": "그 한 줄이 안 나오면 연락 여부를 정하지 않아요.",
        },
        {
            "month": names[1],
            "focus": "보낼 목적과 감당 못 할 반응을 정하는 달",
            "action": me["purpose"],
            "caution": f"감당하지 못할 반응인 {me['limit']}이 보이면 목적을 바꾸지 마세요.",
            "criterion": "목적과 한계가 없으면 보내지 않아요. 상대가 먼저 연락할지는 예측하지 않아요.",
        },
        {
            "month": names[2],
            "focus": "그 한계가 깨지면 멈추는 달",
            "action": f"받은 말만 보고, {me['limit']}이 시작되면 멈추세요. 답이 없으면 새로 보내지 마세요.",
            "caution": "답이 없다는 사실을 좋은 신호나 나쁜 결론으로 확대하지 마세요.",
            "criterion": "세 달이 재회를 만들어 주지는 않아요.",
        },
    ]


def _strategy_couple(labels: List[str], track: str, point: str) -> Dict[str, object]:
    if track == "talk":
        intro = (
            "세 달은 재회가 성사되는 기한이 아니에요. "
            "일지가 붙는 관계라, 이 기간에 볼 것은 편함이 덮어 둔 문제예요. "
            "대화가 없으면 연락을 반복하지 않아요."
        )
    elif track == "review":
        intro = (
            "세 달은 재회가 성사되는 기한이 아니에요. "
            f"일지에서 보이는 반복 후보는 {_ieyo(point)}. "
            "이 기간에는 그 패턴이 아직 같은지만 보고, 대화가 없으면 연락을 반복하지 않아요. "
            "이 패턴이 실제 이별 원인이었다고 단정하지는 않아요."
        )
    elif track == "mixed":
        intro = (
            "세 달은 재회가 성사되는 기한이 아니에요. "
            "일지에 가까워지는 힘과 깨지는 힘이 같이 있어서, 이 기간에는 어느 쪽이 더 큰지 정하지 않아요. "
            "대화가 없으면 연락을 반복하지 않아요."
        )
    elif track == "pa":
        intro = (
            "세 달은 재회가 성사되는 기한이 아니에요. "
            "일지의 합의가 깨지기 쉬운 관계라, 이 기간에는 그 합의를 다시 말로 만들 수 있는지만 봐요. "
            "대화가 없으면 연락을 반복하지 않아요."
        )
    else:
        intro = (
            "세 달은 재회가 성사되는 기한이 아니에요. "
            "일지에 붙거나 부딪히는 고정 장면이 없어서, 사주가 정해 준 갈등으로 이번 달의 행동을 만들지 않아요. "
            "대화가 없으면 연락을 반복하지 않아요."
        )
    return {"title": "앞으로 3개월 전략", "intro": intro, "months": _months_couple(labels, track, point)}


def _strategy_solo(labels: List[str], me: Dict[str, str]) -> Dict[str, object]:
    return {
        "title": "앞으로 3개월 동안의 행동 전략",
        "intro": (
            "세 달은 상대가 연락할 시점을 세는 기간이 아니에요. "
            f"당신의 일간에서 먼저 볼 습관은 {me['you']} 쉬운 쪽이에요. "
            "첫 달은 그 습관과 헤어진 이유를 적고, 둘째 달은 보낼 목적과 한계를 정하고, 셋째 달은 그 한계가 깨지면 멈춰요."
        ),
        "months": _months_solo(labels, me),
    }


def build_reunion_brief(self_ganji: str, partner_ganji: Optional[str], month_labels: List[str]) -> Dict[str, object]:
    """재회운 화면에 올릴 한줄평과 구획. 저장된 종합운 문장은 바꾸지 않는다."""
    me = _stem(self_ganji or "")
    if not partner_ganji:
        return {
            "headline": _headline_solo(me),
            "frame": {
                "title": "나의 연애 성향",
                "subtitle": "상대의 사주는 몰라서, 상대의 마음이나 연락 시점은 말하지 않아요. 과거 인연을 내가 어떻게 대하는지만 봤어요.",
            },
            "sections": [
                {"title": "나의 연애 성향과 과거 인연에 대한 태도", "text": _solo_attitude(me)},
                {"title": "먼저 연락할지 판단할 때 고려할 기준", "text": _solo_contact(me)},
                {"title": "상대에게 어필할 나의 매력", "text": _charm_solo(me)},
            ],
            "strategy": _strategy_solo(month_labels, me),
        }

    branches = (
        self_ganji[1:2] if len(self_ganji) >= 2 else "",
        partner_ganji[1:2] if len(partner_ganji) >= 2 else "",
    )
    flags = _pair_flags(branches[0], branches[1])
    point = _point(flags)
    role = _roles(self_ganji or "", partner_ganji or "")
    track = _track(flags)
    return {
        "headline": _headline_couple(flags, role),
        "frame": {
            "title": "두 사람의 관계 분석",
            "subtitle": "확인되는 강점과, 재회를 판단할 기준을 나눴어요. 재회가 되는 날로 읽지 마세요.",
        },
        "sections": [
            {"title": "우리는 왜", "text": _why(flags, role)},
            {"title": "종합운", "text": _overall(flags, point)},
            {"title": "갈등이 생기는 원인과 반복될 수 있는 패턴", "text": _conflict(flags, role, point)},
            {"title": "재회를 고려할 때 유리한 점과 걸림돌", "text": _balance(flags)},
            {"title": "상대에게 어필할 당신의 매력", "text": _charm_couple(role)},
        ],
        "strategy": _strategy_couple(month_labels, track, point),
    }
