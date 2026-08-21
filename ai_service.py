# ai_service.py

import os
import requests

def get_ai_fortune_interpretation(analysis_type: str, engine_data: dict) -> str:
    """SajuEngine 연산 결과 데이터를 Gemini에 보내 2030 맞춤형 해석 생성"""
    try:
        # Render의 고장난 환경변수를 무시하고 새로 발급받은 키를 직접 사용
        api_key = "AIzaSy..."  # <-- 여기에 새로 발급받은 AIzaSy로 시작하는 키 전체를 따옴표 안에 넣으세요.

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"

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

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

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
        return f"AI 해석을 불러오는 중 오류가 발생했습니다: {str(e)}"
