# saju_engine.py

from datetime import datetime
from dateutil.relativedelta import relativedelta

class SajuEngine:
    def __init__(self, user_saju):
        """
        user_saju: 사용자의 사주 원국, 출생 연도 및 파생 데이터 전체
        """
        self.saju = user_saju

    def _get_life_stage(self, target_year):
        """
        출생 연도 기준으로 target_year 시점의 생애단계를 산출하는 내부 함수
        """
        birth_year = self.saju.get('birth_year', 1990)
        age = target_year - birth_year
        
        if age < 20:
            return "teen"      # 입시 / 시험 / 성적
        elif age < 30:
            return "20s"       # 취업 / 자격증 / 대학원
        elif age < 50:
            return "30-40s"    # 직무전환 / 승진 / 전문 자격증
        else:
            return "50s+"      # 평생교육 / 자기계발 / 새로운 분야

    def calculate_daily_finance(self, today_data):
        """
        오늘의 일진 데이터와 원국을 결합하여 DAILY_FINANCE 지수를 연산하는 모듈
        """
        ten_stars = self.saju.get('ten_stars_strength', {})
        wealth_base = ten_stars.get('정재', 0) + ten_stars.get('편재', 0)
        
        today_star = today_data.get('today_ten_star', '')
        
        speculation_score = 50
        risk_taking_score = 50
        impulse_buy_score = 50

        if today_star in ['편재', '상관']:
            speculation_score += 30
            risk_taking_score += 25
            impulse_buy_score += 20
        elif today_star == '겁재':
            speculation_score += 20
            impulse_buy_score += 40
        elif today_star in ['정인', '정관']:
            speculation_score -= 20
            risk_taking_score -= 20
            impulse_buy_score -= 30

        speculation_score = max(0, min(100, speculation_score))
        risk_taking_score = max(0, min(100, risk_taking_score))
        impulse_buy_score = max(0, min(100, impulse_buy_score))

        if speculation_score >= 75:
            rec_action = "기존 자산의 비중을 점검하고 분할 매수로 접근하세요."
            avoid_action = "급등하는 종목이나 자산을 홧김에 추격 매수하는 행동"
            caution_level = "WARNING"
            keywords = ["#기회탐색", "#추격매수주의", "#분할매수"]
        else:
            rec_action = "현금 흐름을 확보하고 자산 리밸런싱을 진행하기 좋은 날입니다."
            avoid_action = "무리한 신규 자금 집행"
            caution_level = "SAFE"
            keywords = ["#자산보호", "#원칙매매", "#리스크관리"]

        return {
            "wealth": {
                "wealth_star_strength": wealth_base,
                "wealth_star_activation": "HIGH" if today_star in ['정재', '편재'] else "MEDIUM",
            },
            "investment": {
                "speculation_tendency": speculation_score,
                "risk_taking_tendency": risk_taking_score,
                "financial_caution": caution_level
            },
            "consumption": {
                "impulse_buying_tendency": impulse_buy_score
            },
            "money_action": {
                "recommended": rec_action,
                "avoid": avoid_action,
                "keywords": keywords
            }
        }

    def calculate_personal_relationship(self, target_date_str, partner_saju=None):
        """
        상대방 존재 유무에 따라 개인 애정운 또는 커플 궁합/3개월 전략을 연산하는 모듈
        """
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        
        if partner_saju is None:
            return {
                "mode": "SINGLE",
                "summary": "현재는 나 자신의 매력을 다지고 내실을 기하기 좋은 시기입니다.",
                "reunion_fortune": "과거 인연에 연연하기보다 새로운 환경에서 자연스러운 기운이 들어옵니다.",
                "best_marriage_year": 2027
            }
        
        strategy_3months = []
        for i in range(3):
            future_month = target_date + relativedelta(months=i)
            month_str = future_month.strftime("%Y-%m")
            
            if i == 0:
                guide = "서로의 페이스를 탐색하며 가벼운 소통으로 호감을 쌓는 시기"
            elif i == 1:
                guide = "깊은 대화를 나눌 수 있는 기회가 생기며 관계가 진전되는 시기"
            else:
                guide = "서로에 대한 확신이 생기거나 중요한 관계 결정을 내리기 좋은 시기"
                
            strategy_3months.append({
                "month": month_str,
                "strategy": guide
            })

        return {
            "mode": "COUPLE",
            "compatibility": {
                "score": 86,
                "one_liner": "우린 장기전에 강해요. 💍"
            },
            "strategy_3months": strategy_3months,
            "couple_best_marriage_year": 2029
        }

    def calculate_yearly_fortune(self, target_year):
        """
        대상 연도를 파라미터로 받아 9대 테마 및 12개월 월별 흐름을 생성하는 모듈
        """
        life_stage = self._get_life_stage(target_year)
        
        # 학업운 생애단계별 문구 매칭
        study_guide_map = {
            "teen": "성적 향상과 시험 합격 기운이 높으니 집중적인 마무리가 유리합니다.",
            "20s": "취업, 자격증 취득 및 대학원 진학에 매우 뜻깊은 해입니다.",
            "30-40s": "직무 관련 전문 자격증 취득 및 새로운 영역 도전에 유리한 시기입니다.",
            "50s+": "평생교육 및 시야를 넓히는 교양/학문 탐구에 좋은 기운이 깃듭니다."
        }
        
        # 가상의 1~12월 흐름 점수 생성 (예시 알고리즘)
        monthly_scores = [65, 72, 85, 90, 82, 78, 70, 88, 95, 80, 74, 83]
        
        # 점수를 기준으로 BEST 3월 / 주의 3월 자동 도출
        indexed_scores = list(enumerate(monthly_scores, 1))
        sorted_scores = sorted(indexed_scores, key=lambda x: x[1], reverse=True)
        
        best_months = [f"{m[0]:02d}월" for m in sorted_scores[:3]]
        caution_months = [f"{m[0]:02d}월" for m in sorted_scores[-3:]]

        return {
            "target_year": target_year,
            "life_stage": life_stage,
            "one_liner": f"{target_year}년, 멈춰 있던 일을 다시 움직이기 좋은 해",
            "overall_summary": f"{target_year}년은 새로운 변화의 기운이 과감한 시도를 이끄는 시기입니다.",
            "investment_recommendation": "주식 / 분할 투자 전략",
            "study_fortune": study_guide_map.get(life_stage, ""),
            "hobby_recommendation": "트레킹 및 야외 활동 (역마 기운 활용)",
            "monthly_graph": monthly_scores,
            "best_months": best_months,
            "caution_months": caution_months
        }


# --- 전체 엔진 통합 테스트 ---
if __name__ == "__main__":
    sample_user_saju = {
        'birth_year': 1993,  # 1993년생 (2026년 기준 만 33세 -> 30-40s)
        'ten_stars_strength': {'정재': 20, '편재': 30, '식신': 15}
    }

    engine = SajuEngine(sample_user_saju)

    print("=== YEARLY (2026년 연간 운세 테스트) ===")
    res_yearly = engine.calculate_yearly_fortune(2026)
    print(f"대상 연도: {res_yearly['target_year']}년")
    print(f"생애 단계: {res_yearly['life_stage']}")
    print(f"한 줄 요약: {res_yearly['one_liner']}")
    print(f"학업/자기계발운: {res_yearly['study_fortune']}")
    print(f"BEST 월: {res_yearly['best_months']}")
    print(f"주의 월: {res_yearly['caution_months']}")