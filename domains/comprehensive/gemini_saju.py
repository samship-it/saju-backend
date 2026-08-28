from google import genai
from sajupy import SajuCalculator
from datetime import datetime

# 1. 제미나이 API 연결
client = genai.Client(api_key="GEMINI_API_KEY")

# 2. 만세력 연산 실행
today = datetime.today()
calculator = SajuCalculator()

# 유저 생년월일시 (1995년 8월 15일 14시 30분)
user_saju = calculator.calculate_saju(year=1995, month=8, day=15, hour=14, minute=30)
today_saju = calculator.calculate_saju(year=today.year, month=today.month, day=today.day, hour=today.hour, minute=today.minute)

user_day_pillar = user_saju['day_pillar']   # 유저의 일주 (나)
today_day_pillar = today_saju['day_pillar']  # 오늘의 일진

print(f"🔮 유저 일주: {user_day_pillar} / 오늘 일진: {today_day_pillar}")
print("제미나이 AI가 오늘의 족집게 운세를 작성 중입니다...\n")

# 3. AI에게 전달할 운세 지시서(프롬프트) 작성
prompt_text = f"""
너는 Z세대 감성을 200% 이해하는 힙하고 속 시원한 족집게 사주 마스터야.

[유저 사주 정보]
- 유저 본체의 일주: {user_day_pillar}
- 오늘 들어온 일진: {today_day_pillar}

위 사주 조합을 바탕으로 Z세대 직장인/취준생이 공감할 만한 오늘 하루 운세를 아래 양식에 맞춰 작성해줘.

[출력 양식]
1. 오늘 운세 점수 (10~100점 사이):
2. 한 줄 족집게 카피 (이모지 포함):
3. 오늘의 현실 조언 (3문장 이내, 힙한 반말 톤):
4. 오늘 피해야 할 액땜 행동 1가지:
"""

# 4. 제미나이 모델 불러와서 답변 받기
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt_text,
)

# 5. 결과 출력
print("====================================")
print(response.text)
print("====================================")
