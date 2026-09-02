GAN_FIVE_ELEMENTS = {"甲": "목", "乙": "목", "丙": "화", "丁": "화", "戊": "토", "己": "토", "庚": "금", "辛": "금", "壬": "수", "癸": "수"}
JI_FIVE_ELEMENTS = {"子": "수", "丑": "토", "寅": "목", "卯": "목", "辰": "토", "巳": "화", "午": "화", "未": "토", "申": "금", "酉": "금", "戌": "토", "亥": "수"}
GAN_YIN_YANG = {"甲": True, "乙": False, "丙": True, "丁": False, "戊": True, "己": False, "庚": True, "辛": False, "壬": True, "癸": False}
JI_YIN_YANG = {"子": True, "丑": False, "寅": True, "卯": False, "辰": True, "巳": False, "午": True, "未": False, "申": True, "酉": False, "戌": True, "亥": False}

FIVE_ELEMENT_RELATIONS = {
    ("목", "목"): "비겁", ("목", "화"): "식상", ("목", "토"): "재성", ("목", "금"): "관성", ("목", "수"): "인성",
    ("화", "화"): "비겁", ("화", "토"): "식상", ("화", "금"): "재성", ("화", "수"): "관성", ("화", "목"): "인성",
    ("토", "토"): "비겁", ("토", "금"): "식상", ("토", "수"): "재성", ("토", "목"): "관성", ("토", "화"): "인성",
    ("금", "금"): "비겁", ("금", "수"): "식상", ("금", "목"): "재성", ("금", "화"): "관성", ("금", "토"): "인성",
    ("수", "수"): "비겁", ("수", "목"): "식상", ("수", "화"): "재성", ("수", "토"): "관성", ("수", "금"): "인성",
}

def calculate_sipsin(day_master: str, target_char: str, is_gan: bool = True) -> str:
    dm_elem = GAN_FIVE_ELEMENTS.get(day_master, "목")
    dm_yy = GAN_YIN_YANG.get(day_master, True)
    target_elem = GAN_FIVE_ELEMENTS.get(target_char) if is_gan else JI_FIVE_ELEMENTS.get(target_char)
    target_yy = GAN_YIN_YANG.get(target_char) if is_gan else JI_YIN_YANG.get(target_char)

    if not target_elem:
        return "미정"

    group = FIVE_ELEMENT_RELATIONS.get((dm_elem, target_elem), "비겁")
    same_yy = (dm_yy == target_yy)
    mapping = {
        "비겁": ("비견" if same_yy else "겁재"),
        "식상": ("식신" if same_yy else "상관"),
        "재성": ("편재" if same_yy else "정재"),
        "관성": ("편관" if same_yy else "정관"),
        "인성": ("편인" if same_yy else "정인")
    }
    return mapping[group]


def get_sipsin(day_master: str, target_char: str, is_gan: bool = True) -> str:
    """calculate_sipsin 의 호환용 별칭."""
    return calculate_sipsin(day_master, target_char, is_gan=is_gan)