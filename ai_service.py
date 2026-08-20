# ai_service.py

from google import genai

GOOGLE_API_KEY = "AQ.Ab8RN6Js0Db450XNUcTeGZG5fwnGQCJ0rRbRMiPz9Nn9FbJB-Q"

client = genai.Client(api_key=GOOGLE_API_KEY)

def get_ai_fortune_interpretation(analysis_type: str, engine_data: dict) -> str:
    """SajuEngine 연산 결과 데이터를 Gemini 3.5 Flash에 보내 2030 맞춤형 해석 생성"""
    
    prompt = f"""
    당신은 2030 세대를 위한 트렌디하고 감각적인 AI 라이프/재테크 스페셜리스트입니다.
    아래의 사주 엔진 연산 결과 데이터를 바탕으로, 사용자에게 직관적이고 세련된 분석과 액션 플랜을 전달하세요.

    [분석 종류]: {analysis_type}
    [엔진 연산 데이터]: {engine_data}

    [필수 작성 규칙]:
    1. "안녕하세요", "병오년의 기운을 받아" 같은 진부한 서두 인사나 템플릿형 인삿말은 절대로 쓰지 마세요.
    2. 시작부터 바로 본론으로 들어가 첫 문장에서 핵심 요약 및 핵심 전략을 던지세요.
    3. 2030 세대가 공감할 수 있는 직관적이고 감각적인 언어(포트폴리오, 리스크 해징, 멘탈 케어, 멘탈 관리, 모멘텀 등)를 적절히 활용하세요.
    4. 한자어나 고전 명리학 용어는 지양하고, 친근하면서도 감각적인 1:1 컨설팅 톤(5~6줄 내외)으로 작성하세요.
    5. 수치가 낮거나 부진한 구간은 무작정 우울하게 말하기보다, 무엇을 피하고 어떤 타이밍을 노려야 하는지 실질적인 가이드를 제공하세요.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return f"AI 해석을 불러오는 중 오류가 발생했습니다: {str(e)}"