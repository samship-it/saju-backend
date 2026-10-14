"""60갑자 일주 동물 캐릭터 키.

프론트 아바타는 일주 한글 이름(갑자, 신묘 등)으로 `/{이름}.jpg` 를 찾고,
확장자가 다르면 이어서 시도한다. 다른 일주로 대체하지 않는다.
매핑되지 않으면 빈 문자열이다.
"""

_GAN_KO = {
    "甲": "갑", "乙": "을", "丙": "병", "丁": "정", "戊": "무",
    "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계",
}
_JI_KO = {
    "子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사",
    "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해",
}


def ilju_profile_image(day_ganji: str) -> str:
    raw = (day_ganji or "").strip()
    if len(raw) < 2:
        return ""
    stem = _GAN_KO.get(raw[0])
    branch = _JI_KO.get(raw[1])
    if not stem or not branch:
        return ""
    return stem + branch


def ilju_animal_icon(day_ganji: str) -> str:
    """아바타가 받는 60갑자 키. ilju_profile_image 와 같다."""
    return ilju_profile_image(day_ganji)


def target_name(nickname: str | None) -> str | None:
    """헤더에 쓰는 호칭. '민지' → '민지님'. 이미 님이면 한 번만 붙인다."""
    name = (nickname or "").strip()
    if not name:
        return None
    if name.endswith("님"):
        return name
    return f"{name}님"
