import os
import requests

def get_ai_fortune_interpretation(analysis_type: str, engine_data: dict) -> str:
    """Google Gemini 3.5 Flash 모델을 호출하여 2030 맞춤형 사주/재테크 해석 생성"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            return "오류: GEMINI_API_KEY 환경변수가 설정되지 않았습니다."

        # 구글 정책 기준 최신 3.5 모델 고정
        model_name = "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        prompt = f"""
당신은 2030 세대를 위한 트렌디하고 감각적인 AI 라이프/재테크 스페셜리스트입니다.
아래 사주 데이터 결과를 바탕으로 2030 맞춤형 재테크 조언 및 하루 운세 해석을 다정하고 명확하게 작성해 주세요.

[사주 데이터]
{engine_data}

[작성 가이드]
1. "안녕", "AI 스페셜리스트입니다" 같은 자기소개 및 서두 인사말을 절대 작성하지 마세요.
2. 첫 문장부터 바로 핵심 사주/재테크 분석 결과로 즉시 시작하세요.
3. 투자/소비 성향을 직관적으로 짚어줄 것
4. 추천 행동과 주의할 점을 명확히 제시할 것
5. 2030 트렌드 용어(리밸런싱, 추격매수 등)를 자연스럽게 활용할 것
"""

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            # 속도 향상 및 타임아웃 방지를 위해 생성 옵션 추가
            "generationConfig": {
                "maxOutputTokens": 1000,
                "temperature": 0.7
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        # 타임아웃을 60초로 늘려 안정성 확보
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"AI 해석 오류 ({response.status_code}): {response.text}"

    except requests.exceptions.Timeout:
        return "AI 해석 오류: 구글 서버 응답 시간이 초과되었습니다. 다시 시도해 주세요."
    except Exception as e:
        return f"AI 해석 오류: {str(e)}"
