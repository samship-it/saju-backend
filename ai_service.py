import os
import requests

def get_ai_fortune_interpretation(analysis_type: str, engine_data: dict) -> str:
    """Google Gemini 3.5 모델을 호출하여 2030 맞춤형 사주/재테크 해석 생성"""
    try:
        # Vercel 환경변수에서 GEMINI_API_KEY 불러오기
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            return "오류: GEMINI_API_KEY 환경변수가 설정되지 않았습니다."

        # 구글 Gemini 3.5 Flash 엔드포인트
        model_name = "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        prompt = f"""
당신은 2030 세대를 위한 트렌디하고 감각적인 AI 라이프/재테크 스페셜리스트입니다.
아래 사주 데이터 결과를 바탕으로 2030 맞춤형 재테크 조언 및 하루 운세 해석을 다정하고 명확하게 작성해 주세요.

[사주 데이터]
{engine_data}

[작성 가이드]
1. 인사는 하지말고 투자/소비 성향을 직관적으로 짚어줄 것
2. 추천 행동과 주의할 점을 명확히 제시할 것
3. 2030 트렌드 용어(리밸런싱, 추격매수 등)를 자연스럽게 활용할 것
"""

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        # Google AI Studio 키 사용 시 Content-Type만 지정 (Authorization 헤더 제거)
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"AI 해석 오류 ({response.status_code}): {response.text}"

    except Exception as e:
        return f"AI 해석 오류: {str(e)}"
