"""API 응답에 실을 사주 요약 (프론트/검수용).

용신·격국은 억부법 기반 단순화 구현이므로 반드시 basis(근거)를 함께 노출한다.
나중에 실제 생년월일로 명리 전문가 검수 시 근거를 대조할 수 있도록 하기 위함.
"""
from typing import Dict, Any


def person_summary(saju: Dict[str, Any]) -> Dict[str, Any]:
    st = saju.get("strength", {}) or {}
    gg = saju.get("gyeokguk", {}) or {}
    ss = saju.get("spouse_star", {}) or {}
    return {
        "day_master": saju.get("day_master"),
        "day_branch": saju.get("day_branch"),
        "day_master_elem": saju.get("day_master_elem"),
        "year_ganji": saju.get("year_ganji"),
        "month_ganji": saju.get("month_ganji"),
        "day_ganji": saju.get("day_ganji"),
        "time_ganji": saju.get("time_ganji"),
        "birth_time_known": saju.get("birth_time_known"),
        "five_elements": saju.get("five_elements"),
        "persona_key": f"{saju.get('day_master')}{saju.get('day_branch')}",
        "strength": {
            "verdict": st.get("verdict"),
            "support_ratio": st.get("support_ratio"),
            "deukryeong": st.get("deukryeong"),
            "elem_power": st.get("elem_power"),
            "yongsin": st.get("yongsin"),
            "heesin": st.get("heesin"),
            "gisin": st.get("gisin"),
            "basis": st.get("basis"),
            "method": "억부법(신강약 기반) 단순화 — 명리 전문가 검수 필요 영역",
        },
        "gyeokguk": {
            "name": gg.get("name"),
            "sipsin": gg.get("sipsin"),
            "basis": gg.get("basis"),
            "method": "월지 지장간 정기 기준 (내격) 단순화",
        },
        "spouse_star": {
            "group": ss.get("spouse_star_group"),
            "present": ss.get("present"),
            "palace_branch": ss.get("spouse_palace_branch"),
        },
        "sinsal": saju.get("sinsal", {}).get("names"),
    }
