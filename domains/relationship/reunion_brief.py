"""재회운 화면용 한줄평과 구획.

요청 중에 LLM을 부르지 않는다. 재회 콘텐츠 키와 같은 일간·일지만 본다.
시주, 신강약, 용신은 쓰지 않는다. 재회 점수는 이 도메인에 없으므로 좋고 나쁨 등급을 만들지 않는다.

한줄평의 초점은 운세 등급이 아니다.
- review: 일지에 부딪힘, 쌓임, 감정 자극, 같은 버릇이 보여서 그 패턴을 먼저 볼 때
- talk: 일지가 붙기만 해서, 대화가 열렸을 때 덮인 문제를 말할 수 있는지가 기준일 때
- watch: 붙는 힘과 깨지는 힘이 같이 있거나, 일지에 고정 신호가 없어서 상대의 실제 반응만 볼 때

예시로 거론된 '정리·전환'은 넣지 않는다. 일간·일지만으로 새 인연을 권할 근거가 없고,
내 사주만 볼 때는 새 인연을 말하지 않는다.
"""
from typing import Dict, List, Optional

from core.constants import (
    CHUNG, FIVE_ELEMENT_RELATIONS, GAN_ELEM, HAE, PA, SAMHYEONG,
    SANGHYEONG, SELF_HYEONG, YUKHAP,
)

# 사용자 문장에 십신 이름을 넣지 않는다. 키는 조립용이다.
_ROLE = {
    "비겁": {
        "self_to": "상대와 같은 고집 앞에 서기 쉬워요",
        "other_to": "당신과 같은 고집 앞에 서기 쉬워요",
        "use": "익숙한 방식으로 통하기",
        "burden": "같은 고집을 동시에 세우면 양보가 늦어져요",
    },
    "식상": {
        "self_to": "상대의 막힌 말을 풀어 내는 쪽에 서기 쉬워요",
        "other_to": "당신의 막힌 말을 풀어 내는 쪽에 서기 쉬워요",
        "use": "막힌 이야기를 풀어 주기",
        "burden": "내가 정리를 끝내 버리면 상대의 말이 들어설 자리가 없어요",
    },
    "재성": {
        "self_to": "상대의 현실과 조건을 챙기는 쪽에 서기 쉬워요",
        "other_to": "당신의 현실과 조건을 챙기는 쪽에 서기 쉬워요",
        "use": "감정보다 현실적인 다음 수를 챙기기",
        "burden": "챙겨 주는 말이 상대의 선택을 대신하면 부담이 돼요",
    },
    "관성": {
        "self_to": "상대의 기준에 내 속도를 맞추는 쪽에 서기 쉬워요",
        "other_to": "당신의 기준에 속도를 맞추는 쪽에 서기 쉬워요",
        "use": "상대의 기준을 들으면서도 내 선을 지키기",
        "burden": "맞추느라 내 속도가 사라지면 예전과 같은 답답함으로 돌아가요",
    },
    "인성": {
        "self_to": "상대에게 기대어 버티는 쪽에 서기 쉬워요",
        "other_to": "당신에게 기대어 버티는 쪽에 서기 쉬워요",
        "use": "도움을 받으면서도 내가 지킬 선을 같이 말하기",
        "burden": "돌봄을 당연한 것으로 기대하면 받지 못할 때 서운함이 커져요",
    },
}

_STEM = {
    "甲": {
        "you": "결론을 서두르기",
        "good": "꼬인 상황을 한 줄로 정리하는 힘",
        "risk": "이유가 적히기 전에 결론부터 말하는 습관",
        "after": "끝난 이유를 적기 전에 다시 시작할 결론부터 나와요",
        "watch": "그 결론이 상대의 대답인지, 내 조급함인지 나눠 보세요",
        "purpose": "확인하려는 것이 내 결론인지 상대의 의사인지 먼저 나누세요.",
        "limit": "거절이나 무응답 뒤에 바로 다시 설득하고 싶어지는 것",
    },
    "乙": {
        "you": "관계를 지키려고 자기 속도를 굽히기",
        "good": "다른 사람의 페이스에 맞춰 대화를 이어 가는 유연함",
        "risk": "맞추는 마음이 다른 사람의 답을 대신해 버리는 습관",
        "after": "상대의 답을 기다리기보다 내가 맞춰서 관계를 유지하려 해요",
        "watch": "그 맞춤이 배려인지, 거절을 받아들이지 못하는 것인지 보세요",
        "purpose": "맞추지 않아도 전할 말이 있는지부터 적으세요.",
        "limit": "거절을 듣고도 더 맞춰서 관계를 붙들고 싶어지는 것",
    },
    "丙": {
        "you": "감정이 올라오면 그 온도로 바로 움직이기",
        "good": "식어 버린 대화를 다시 따뜻하게 여는 힘",
        "risk": "달아오른 기분을 이미 확인된 답으로 여기는 습관",
        "after": "다시 뜨거워진 기분을 상대의 마음인 것처럼 느끼기 쉬워요",
        "watch": "열기가 식은 뒤에도 같은 말인지 확인하고 보내세요",
        "purpose": "지금 온도가 아니라, 식은 뒤에도 전할 말인지를 기준으로 삼으세요.",
        "limit": "답이 식었다고 느껴질 때 온도를 더 올리게 되는 것",
    },
    "丁": {
        "you": "마음을 오래 묵히고 천천히 드러내기",
        "good": "서두르지 않고 들은 말을 남겨 두는 힘",
        "risk": "기준 없이 기다리며 미련을 정성으로 여기는 습관",
        "after": "소식이 없는 시간을 견디는 것 자체를 정답으로 여기기 쉬워요",
        "watch": "기다림에 기한이 있는지, 없으면 미련인지 한 줄로 정하세요",
        "purpose": "언제까지 기다릴지 날짜를 적지 못하면 연락의 목적도 비어요.",
        "limit": "답이 없어도 기한 없이 계속 기다리게 되는 것",
    },
    "戊": {
        "you": "흔들리지 않으려고 결정을 미루기",
        "good": "감정의 파도 속에서도 일상을 붙드는 힘",
        "risk": "미루는 사이에 다른 사람의 마음을 짐작으로 채우는 습관",
        "after": "결정하지 않은 상태를 신중함으로 여기기 쉬워요",
        "watch": "미룬 이유가 정보가 부족해서인지, 짐작을 사실로 두고 싶어서인지 나누세요",
        "purpose": "오늘 정할 수 있는 내 선택 하나만 적고, 나머지는 상대의 몫으로 두세요.",
        "limit": "답을 듣고도 결정을 또 미루게 되는 것",
    },
    "己": {
        "you": "작은 말과 신호를 오래 되짚기",
        "good": "무심코 나온 말을 기억해 챙기는 세심함",
        "risk": "자기 해석을 실제로 들은 말로 착각하는 습관",
        "after": "작은 기억을 상대의 신호처럼 다시 읽기 쉬워요",
        "watch": "그 말이 실제로 들은 문장인지, 내가 덧붙인 해석인지 구분하세요",
        "purpose": "판단에 쓸 문장은 실제로 들은 것만 남기세요.",
        "limit": "짧은 답을 좋은 신호로 확장해서 읽게 되는 것",
    },
    "庚": {
        "you": "흐린 관계를 빨리 잘라 정리하기",
        "good": "감정에 끌려가지 않고 선을 정하는 힘",
        "risk": "확인할 말이 남았는데도 정리부터 해 버리는 습관",
        "after": "남은 확인을 생략한 채 이미 끝난 일로 넘기기 쉬워요",
        "watch": "끊기 전에, 아직 물어보지 않은 한 가지가 있는지만 적고 넘어가세요",
        "purpose": "정리하고 싶은 마음과, 아직 확인하지 않은 문제를 다른 줄에 적으세요.",
        "limit": "불편한 답을 듣기 전에 대화를 닫아 버리게 되는 것",
    },
    "辛": {
        "you": "자존심 때문에 하고 싶은 말을 아끼기",
        "good": "쉽게 무너지지 않고 자기 선을 지키는 힘",
        "risk": "확인할 질문 대신 잘 보이려는 말만 고르는 습관",
        "after": "물어볼 질문 대신 체면을 지키는 침묵을 택하기 쉬워요",
        "watch": "보내지 않는 이유가 존중인지, 자존심인지 한 줄로 구분해 보세요",
        "purpose": "잘 보이려는 문장은 빼고, 확인하고 싶은 질문 하나만 남기세요.",
        "limit": "체면이 상할까 봐 필요한 질문을 빼게 되는 것",
    },
    "壬": {
        "you": "여러 가능성을 재느라 결론을 늦추기",
        "good": "한쪽으로 치우치지 않고 상황을 넓게 보는 힘",
        "risk": "감당 못 할 반응을 정하지 않은 채 가능성만 늘리는 습관",
        "after": "여러 결말을 상상하느라 내가 감당할 반응을 정하지 못해요",
        "watch": "이번 주에 감당하지 못할 반응을 한 줄로 정해 두세요",
        "purpose": "가능성을 더 열기 전에, 받아도 되는 답과 아닌 답을 나누세요.",
        "limit": "거절을 또 다른 가능성으로 바꿔 읽게 되는 것",
    },
    "癸": {
        "you": "말하지 않은 마음을 상상으로 채우기",
        "good": "드러나지 않은 감정을 조용히 읽어 내는 힘",
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


def _wa(word: str) -> str:
    return word + ("과" if _batchim(word) else "와")


def _topic(who: str) -> str:
    return who + ("은" if _batchim(who) else "는")


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


def _focus(flags: Dict[str, bool]) -> str:
    """등급이 아니라 한줄평이 먼저 말할 판단 초점."""
    if flags.get("missing"):
        return "watch"
    friction = flags["chung"] or flags["hae"] or flags["hyung"] or flags["pa"]
    if flags["hap"] and friction:
        return "watch"
    if flags["chung"] or flags["hyung"] or flags["hae"] or flags["same"]:
        return "review"
    if flags["pa"]:
        return "watch"
    if flags["hap"]:
        return "talk"
    return "watch"


def _point(flags: Dict[str, bool]) -> str:
    if flags.get("missing"):
        return "그때 헤어진 장면"
    if flags["hap"] and (flags["pa"] or flags["chung"] or flags["hae"] or flags["hyung"]):
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


def _roles(self_ganji: str, partner_ganji: str):
    mine = GAN_ELEM.get(self_ganji[:1])
    theirs = GAN_ELEM.get(partner_ganji[:1])
    if not mine or not theirs:
        return None
    return (
        _ROLE[FIVE_ELEMENT_RELATIONS[(mine, theirs)]],
        _ROLE[FIVE_ELEMENT_RELATIONS[(theirs, mine)]],
    )


def _headline_couple(me: Dict[str, str], other: Dict[str, str], flags: Dict[str, bool], point: str) -> str:
    pair = f"{_topic('당신')} {me['you']} 쉽고, {_topic('상대')} {other['you']} 쉬워요."
    if flags.get("missing"):
        return "두 사람의 일주를 특정하지 못해서, 재회가 될지는 이 결과로 정하지 않아요. 헤어진 이유와 상대의 의사를 기준으로 보세요."
    if flags["hap"] and (flags["pa"] or flags["chung"] or flags["hae"] or flags["hyung"]):
        return f"{pair} 가까워지는 힘과 깨지는 힘이 같이 있어서, 어느 쪽 마음인지 단정하지 말고 상대가 실제로 보인 반응만 다음 판단에 쓰세요."
    if flags["chung"]:
        return f"{pair} {_iga(point)} 다시 커질 수 있으니, 다시 만나기 전에 그 주제가 아직 그대로인지부터 보세요."
    if flags["hyung"] or flags["self_hyung"]:
        return f"{pair} {_iga(point)} 되살아나기 쉬우니, 다시 만나고 싶은 마음보다 그 패턴을 멈출 수 있는지를 먼저 보세요."
    if flags["hae"]:
        return f"{pair} {_iga(point)} 관계를 다시 상하게 할 수 있으니, 작은 어긋남을 넘기는 버릇이 줄었는지를 기준으로 보세요."
    if flags["same"]:
        return f"{pair} {point} 때문에 헤어진 이유도 같은 모양으로 돌아올 수 있어요. 같은 하루를 다시 견딜 준비인지를 먼저 보세요."
    if flags["pa"]:
        return f"{pair} {_iga(point)} 반복되기 쉬우니, 괜찮아 보이던 기억만으로 넘어가지 말고 상대의 실제 반응을 보세요."
    if flags["hap"]:
        return f"{pair} 일상은 붙기 쉽지만 {_iga(point)} 그대로면 같은 자리로 돌아가요. 대화가 열리면 그 문제를 한 가지 말할 수 있는지를 기준으로 보세요."
    return f"{pair} 일지에서 붙거나 정면으로 부딪히는 고정 신호는 없어요. 재회는 사주가 정해 주지 않으니, 헤어진 이유와 상대의 의사를 기준으로 보세요."


def _headline_solo(me: Dict[str, str]) -> str:
    return (
        f"{_topic('당신')} {me['you']} 쉬워요. "
        f"재회를 생각할 때는 상대의 마음 대신, {_eul(me['risk'])} 먼저 멈추세요."
    )


def _signaled(flags) -> bool:
    return bool(flags["hap"] or flags["chung"] or flags["pa"] or flags["hae"] or flags["hyung"] or flags["same"])


def _why(me, other, flags, roles) -> str:
    if me["good"] == other["good"]:
        goods = f"두 사람 모두 {_eul(me['good'])} 가지고 있을 때"
    else:
        goods = f"당신이 가진 {_wa(me['good'])}, 상대 사주에서 보이는 {_iga(other['good'])} 같이 있을 때"
    if flags["hap"] and not (flags["pa"] or flags["chung"] or flags["hae"] or flags["hyung"]):
        return (
            f"{goods} 일상 리듬이 붙는 것이 이 조합의 강점이에요. "
            "설명이 짧아도 통할 수 있지만, 그 강점은 문제가 해결됐다는 뜻이 아니에요. "
            "대화의 문을 열기 쉽다는 뜻에 가깝고, 문을 열어도 덮어 둔 문제는 따로 말해야 해요."
        )
    if flags["chung"]:
        return (
            f"{goods} 다른 점이 숨지 않고 드러나는 것이 강점이에요. "
            "어디가 다른지 이름을 붙이기 쉬워서, 다툼으로 커지기 전에 그 이름을 쓸 수 있어요. "
            "분명함 자체가 재회의 이유는 아니에요."
        )
    if flags["hyung"] or flags["self_hyung"]:
        return (
            f"{goods} 감정을 숨기지 않고 드러내는 힘은 있어요. "
            "그 힘이 강점이 되려면, 세진 감정 앞에서 한 박자 멈춰 사실을 말하는 합의가 있어야 해요. "
            "뜨거움만으로는 강점이라고 보기 어려워요."
        )
    if flags["hae"] or flags["pa"] or flags["same"]:
        return (
            f"{goods} 작은 차이를 알아채는 데 쓸 수 있어요. "
            "알아챈 차이를 넘겨 버리지 않을 때만 강점이고, 넘기면 같은 쌓임이 반복돼요."
        )
    seat = ""
    if roles:
        seat = f" 일간만 보면 당신은 {roles[0]['self_to']}. 이건 오늘의 마음이 아니라 두 사주가 맞닿는 방식이에요."
    return (
        f"{goods} 서로를 붙잡는 일지 신호는 없어요. "
        f"강점으로 말할 수 있는 것은 그 두 가지 힘뿐이에요.{seat} "
        "일지에 궁합처럼 붙는 이유가 있다고 바꾸어 읽지 마세요."
    )


def _overall(me, other, flags, roles, point: str) -> str:
    if roles:
        seat = (
            f"일간이 맞닿는 자리만 보면, 당신은 {roles[0]['self_to']}. "
            f"상대의 일간은 {roles[1]['other_to']}. "
            "이것은 지금 상대의 감정이 아니에요. "
        )
    else:
        seat = "일간끼리의 자리는 특정하지 못했어요. "
    if me["you"] == other["you"]:
        pace = f"두 사람 모두 {me['you']} 쉬워서, 같은 속도가 한쪽으로 몰리기 쉬워요. "
    else:
        pace = f"당신은 {me['you']} 쉽고, 상대는 {other['you']} 쉬워서 같은 장면에서 속도가 달라질 수 있어요. "
    if flags["hap"] and not (flags["chung"] or flags["pa"] or flags["hae"] or flags["hyung"]):
        decision = f"대화에서 {_eul(point)} 말할 수 있을 때만 다음을 생각하세요. 대화가 없으면 재회로 넘어가지 마세요."
    elif flags["chung"] or flags["hyung"] or flags["hae"] or flags["same"] or flags["self_hyung"]:
        decision = f"{_iga(point)} 이번에도 같은지, 그리고 두 사람이 그걸 다르게 다룰 말이 있는지를 보세요."
    else:
        decision = "상대가 실제로 보인 반응과 헤어진 이유만 놓고 보세요. 사주가 재회를 대신 정해 주지는 않아요."
    return f"{seat}{pace}{decision}"


def _conflict(me, other, flags, point: str) -> str:
    if _signaled(flags):
        meet = f"두 습관이 만나면 {_eul(point)} 키울 수 있어요. "
    else:
        meet = "두 습관이 만나도 일지가 충돌의 모양을 정해 주지는 않아요. "
    return (
        f"당신이 되풀이하기 쉬운 점은 {me['risk']}이에요. "
        f"상대 사주에서 보이기 쉬운 점은 {other['risk']}이에요. "
        f"{meet}"
        "헤어진 원인이 이것인지는 사주가 알지 못해요. "
        "다만 다시 만나면 이 모양이 돌아올 수 있으니, 그 원인이 아직도 같은 문장인지만 확인해 보세요."
    )


def _balance(flags, point: str, roles) -> str:
    if flags["hap"] and not (flags["pa"] or flags["chung"] or flags["hae"] or flags["hyung"]):
        adv = "일상이 붙어 대화를 다시 열기 쉬운 점"
    elif flags["chung"] or flags["hyung"]:
        adv = "다른 점이 숨지 않아, 문제를 두루뭉술하게 넘기기 어려운 점"
    elif roles:
        adv = f"당신이 {roles[0]['use']} 쉬운 점"
    else:
        adv = "기대를 사주에 맡기지 않고 상대의 답을 직접 볼 수 있는 점"
    return (
        f"유리한 점은 {adv}이에요. "
        f"걸림돌은 {_eul(point)} 그대로 둔 채 관계만 되돌리는 일이에요. "
        "유리한 점이 있다고 재회가 되는 것은 아니에요. "
        "걸림돌을 두 사람이 인정하고, 상대가 그 대화를 받아들일 때만 다음을 생각하세요."
    )


def _charm_couple(me, roles, point: str) -> str:
    if roles:
        use = f"이 조합에서 그 점은 {roles[0]['use']} 쉬운 쪽으로 작용해요. {roles[0]['burden']}."
    else:
        use = "어느 쪽으로 들릴지는 상대의 반응이 오기 전에는 알 수 없어요."
    if point == "그때 헤어진 장면":
        risk_line = f"반대로 {me['risk']}이 나오면, 없는 신호를 관계의 답으로 채우게 돼요. "
    else:
        risk_line = f"반대로 {me['risk']}이 나오면 {_eul(point)} 더 키워요. "
    return (
        f"다시 대화할 일이 생기면, {me['good']}을 먼저 보여 주세요. {use} "
        f"{risk_line}"
        "상대가 무엇을 그리워하는지는 이 사주로 말하지 않아요. "
        "한 가지 질문을 던진 뒤 답을 듣고, 그 다음에 마음을 정하세요."
    )


def _charm_solo(me) -> str:
    return (
        f"다시 보여줄 수 있는 점은 {me['good']}이에요. "
        "과거 인연 앞에서 그 점은 신뢰로 보일 수 있어요. "
        f"다만 {me['risk']}은 같은 관계에서 이미 문제가 됐을 수 있으니, 말을 건넨다면 그 습관부터 한 단계 낮추세요. "
        "상대가 어떻게 받아들일지는 상대의 사주를 모르니 단정하지 않아요."
    )


def _solo_attitude(me) -> str:
    return (
        f"{_topic('당신')} {me['you']} 쉬운 쪽으로 과거 인연을 대해요. "
        f"이별 뒤에는 {me['after']}. "
        f"다시 그 사람을 떠올리는 순간에는 {me['watch']}."
    )


def _solo_contact(me) -> str:
    return (
        "연락의 목적을 상대의 마음을 확인하는 것으로 두면, 어떤 답이 와도 부족해져요. "
        f"{me['purpose']} "
        f"감당하지 못할 반응은 {me['limit']}이에요. "
        "그 반응을 감당하지 못하면 보내지 마세요. "
        "상대가 답을 할지, 언제 할지는 내 사주로 알 수 없어요."
    )


def _months(labels: List[str], point: str, partner: bool) -> List[Dict[str, str]]:
    names = list(labels[:3])
    while len(names) < 3:
        names.append(f"{len(names) + 1}개월차")
    topic = _eul(point)
    if partner and point == "그때 헤어진 장면":
        ask = "이미 대화가 있는 경우에만, 그때 오간 말이 아직 같은지 한 문장으로 물어보세요."
        note = "사주가 정해 준 갈등 장면은 없어요. 그때 오간 말과 내가 기억하는 이유가 같은지만 적으세요."
    else:
        ask = f"이미 대화가 있는 경우에만 {topic} 한 문장으로 물어보세요."
        note = f"연락으로 마음을 확인하지 말고, {_wa(point)} 헤어진 이유가 겹치는지 적으세요."
    if partner:
        return [
            {
                "month": names[0],
                "focus": "헤어진 이유를 한 줄로 적는 달",
                "action": note,
                "caution": "다시 만나고 싶은 기분을 상대의 신호로 바꾸지 마세요.",
                "criterion": "이유를 한 줄로 못 적으면 이번 달에는 대화를 열지 않아요.",
            },
            {
                "month": names[1],
                "focus": "대화가 실제로 열렸을 때만 한 가지를 확인하는 달",
                "action": ask,
                "caution": "답이 없는데 같은 말을 반복하지 마세요.",
                "criterion": "대화가 없으면 첫째 달의 기준을 유지해요. 침묵을 호감으로 읽지 않아요.",
            },
            {
                "month": names[2],
                "focus": "들은 내용으로 이어갈지 멈출지 정하는 달",
                "action": "실제로 들은 말과, 내가 적은 이유가 겹치는지 비교하세요.",
                "caution": "세 달을 채웠다는 이유로 결론을 만들지 마세요.",
                "criterion": "이유가 그대로고 바꿀 합의가 없으면 재회를 다음 단계로 밀지 않아요.",
            },
        ]
    return [
        {
            "month": names[0],
            "focus": "내가 되풀이하는 태도와 헤어진 이유를 같이 적는 달",
            "action": "헤어진 이유 옆에, 내가 그때 반복한 태도를 한 줄만 적으세요.",
            "caution": "적는 일에 상대의 마음을 추측해서 채우지 마세요.",
            "criterion": "한 줄이 안 나오면, 연락 여부를 정하지 않아요.",
        },
        {
            "month": names[1],
            "focus": "보낼 목적과 감당 못 할 반응을 정하는 달",
            "action": "목적은 한 가지, 감당 못 할 반응도 한 가지로 적으세요.",
            "caution": "마음을 확인하려는 목적은 빼세요. 그 목적은 어떤 답에도 부족해져요.",
            "criterion": "목적과 한계가 없으면 보내지 않아요. 상대가 먼저 쓸지는 예측하지 않아요.",
        },
        {
            "month": names[2],
            "focus": "이미 한 말만으로 내 선택을 정리하는 달",
            "action": "이미 연락했다면 받은 답만 보고, 하지 않았다면 적어 둔 한계를 지키세요.",
            "caution": "답이 없다는 사실을 좋은 신호나 나쁜 결론으로 확대하지 마세요.",
            "criterion": "받은 말이 없으면 관계는 내가 적어 둔 한계에 머물러요. 세 달이 재회를 만들어 주지는 않아요.",
        },
    ]


def _strategy(labels: List[str], point: str, partner: bool) -> Dict[str, object]:
    if partner:
        intro = (
            "세 달은 재회가 성사되는 기한이 아니에요. "
            "첫 달은 이유를 적고, 둘째 달은 대화가 실제로 열렸을 때만 확인하고, "
            "셋째 달은 들은 말로 이어갈지 멈출지를 정하는 흐름이에요."
        )
        title = "앞으로 3개월 전략"
    else:
        intro = (
            "세 달은 상대가 연락할 시점을 세는 기간이 아니에요. "
            "첫 달은 내 태도와 이유를 적고, 둘째 달은 보낼 목적과 한계를 정하고, "
            "셋째 달은 이미 오간 말만으로 내 선택을 정리해요."
        )
        title = "앞으로 3개월 동안의 행동 전략"
    return {"title": title, "intro": intro, "months": _months(labels, point, partner)}


def build_reunion_brief(self_ganji: str, partner_ganji: Optional[str], month_labels: List[str]) -> Dict[str, object]:
    """재회운 화면에 올릴 한줄평과 구획. 저장된 종합운 문장은 바꾸지 않는다."""
    me = _stem(self_ganji or "")
    partner = bool(partner_ganji)
    if not partner:
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
            "strategy": _strategy(month_labels, "내가 되풀이하는 태도", False),
        }

    other = _stem(partner_ganji or "")
    branches = (self_ganji[1:2] if len(self_ganji) >= 2 else "", partner_ganji[1:2] if partner_ganji and len(partner_ganji) >= 2 else "")
    flags = _pair_flags(branches[0], branches[1])
    point = _point(flags)
    roles = _roles(self_ganji or "", partner_ganji or "")
    return {
        "headline": _headline_couple(me, other, flags, point),
        "frame": {
            "title": "두 사람의 관계 분석",
            "subtitle": "두 사람 사이에서 통하는 지점과 다시 부딪힐 수 있는 지점을 나눴어요. 재회가 되는 날로 읽지 말고, 다시 만날지를 고를 때의 기준으로 보세요.",
        },
        "sections": [
            {"title": "우리는 왜", "text": _why(me, other, flags, roles)},
            {"title": "종합운", "text": _overall(me, other, flags, roles, point)},
            {"title": "갈등이 생기는 원인과 반복될 수 있는 패턴", "text": _conflict(me, other, flags, point)},
            {"title": "재회를 고려할 때 유리한 점과 걸림돌", "text": _balance(flags, point, roles)},
            {"title": "상대에게 어필할 당신의 매력", "text": _charm_couple(me, roles, point)},
        ],
        "strategy": _strategy(month_labels, point, True),
    }
