from typing import Dict, Any, List

def analyze_domain_derived(saju_data: Dict[str, Any]) -> Dict[str, Any]:
    sipsin_map = saju_data.get("sipsin", {})
    sipsin_values = list(sipsin_map.values())

    jaeseong_count = sum(1 for s in sipsin_values if s in ["편재", "정재"])
    gwanseong_count = sum(1 for s in sipsin_values if s in ["편관", "정관"])
    sigsang_count = sum(1 for s in sipsin_values if s in ["식신", "상관"])
    inseong_count = sum(1 for s in sipsin_values if s in ["편인", "정인"])
    bigeob_count = sum(1 for s in sipsin_values if s in ["비견", "겁재"])

    has_sik_jae = (sigsang_count > 0 and jaeseong_count > 0)
    has_gwan_in = (gwanseong_count > 0 and inseong_count > 0)

    finance_score = min(100, 50 + (jaeseong_count * 15) + (10 if has_sik_jae else 0))
    work_score = min(100, 50 + (gwanseong_count * 15) + (10 if has_gwan_in else 0))
    love_score = min(100, 50 + ((gwanseong_count if saju_data.get("gender") == "female" else jaeseong_count) * 15))

    return {
        "counts": {
            "재성": jaeseong_count,
            "관성": gwanseong_count,
            "식상": sigsang_count,
            "인성": inseong_count,
            "비겁": bigeob_count
        },
        "patterns": {
            "식상생재": has_sik_jae,
            "관인상생": has_gwan_in
        },
        "score_components": {
            "finance_base": finance_score,
            "work_base": work_score,
            "love_base": love_score
        }
    }

