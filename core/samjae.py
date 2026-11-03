"""삼재(三災) 계산 — 년지(띠) 삼합 그룹 기준, 현재 세운이 삼재 3년 중 어디인지 판정.

근거(표준 명리 자료, 2026-09 웹 검색으로 확인):
  해묘미(돼지·토끼·양)띠 -> 사오미(巳午未)년이 삼재
  인오술(호랑이·말·개)띠 -> 신유술(申酉戌)년이 삼재
  사유축(뱀·닭·소)띠    -> 해자축(亥子丑)년이 삼재
  신자진(원숭이·쥐·용)띠 -> 인묘진(寅卯辰)년이 삼재
3년 중 첫 해=입삼재(들삼재), 둘째 해=눌삼재(침삼재), 셋째 해=날삼재(출삼재).
"""
from typing import Dict, Optional

SAMJAE_TABLE = {
    ("亥", "卯", "未"): ("巳", "午", "未"),
    ("寅", "午", "戌"): ("申", "酉", "戌"),
    ("巳", "酉", "丑"): ("亥", "子", "丑"),
    ("申", "子", "辰"): ("寅", "卯", "辰"),
}
_STAGE_LABELS = ("들삼재(입삼재)", "눌삼재(침삼재)", "날삼재(출삼재)")


def check_samjae(year_branch: str, current_year_branch: str) -> Dict[str, Optional[str]]:
    for group, samjae_years in SAMJAE_TABLE.items():
        if year_branch in group:
            if current_year_branch in samjae_years:
                stage = _STAGE_LABELS[samjae_years.index(current_year_branch)]
                return {"is_samjae": True, "stage": stage, "samjae_years": samjae_years, "group": group}
            return {"is_samjae": False, "stage": None, "samjae_years": samjae_years, "group": group}
    return {"is_samjae": False, "stage": None, "samjae_years": (), "group": None}
