def get_life_stage(age: int) -> str:
    if age <= 19: return "10대 이하 (학업/진로 탐색)"
    elif age <= 29: return "20대 (취업/사회초년/경력 형성)"
    elif age <= 39: return "30대 (자산 형성/성장/커리어 확장)"
    elif age <= 49: return "40대 (안정/중책/투자 책임)"
    elif age <= 59: return "50대 (리더십/자산 관리/은퇴 준비)"
    else: return "60대 이상 (안정/수성/노후 준비)"