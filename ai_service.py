# ai_service.py

import os
from google import genai

def get_ai_fortune_interpretation(analysis_type: str, engine_data: dict) -> str:
    """SajuEngine 연산 결과 데이터를 Gemini에 보내 2030 맞춤형 해석 생성"""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "AI 해석 오류: GOOGLE_API_KEY 환경변수가 설정되지 않았습니다."

        # api_key를 명시적으로 지정하여 OAuth 토큰 오인식 방지
        client = genai.Client(api_key=api_key)

        prompt = f"""
당신은 2030 세대를 위한 트렌디하고 감각적인 AI 라이프/재테크 스페셜리스트입니다.
아래 사주 데이터 결과를 바탕으로 2030 맞춤형 재테크 조언 및 하루 운세 해석을 다정하고 명확하게 작성해 주세요.

[사주 데이터]
{engine_data}

[작성 가이드]
1. 투자/소비 성향을 직관적으로 짚어줄 것
2. 추천 행동과 주의할 점을 명확히 제시할 것
3. 2030 트렌드 용어(리밸런싱, 추격매수 등)를 자연스럽게 활용할 것
"""

        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
        )
        return response.text

    except Exception as e:
        return f"AI 해석을 불러오는 중 오류가 발생했습니다: {str(e)}"
