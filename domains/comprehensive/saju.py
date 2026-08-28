# -*- coding: utf-8 -*-
from google import genai
import json

# 1. 제미나이 클라이언트 설정 (본인의 키 입력)
MY_API_KEY = ""
client = genai.Client(api_key="GEMINI_API_KEY")

# 2. 테스트할 일주와 일진 설정
user_p = "무인"
today_p = "을사"

# 3. 화면 레이아웃 맞춤형 프롬프트 (이모지 제거 버전)
prompt = f"""
너는 Z세대와 2030 직장인의 마음을 사로잡는 전문 사주 앱의 수석 명리학 마스터야.

[사주 정보]
- 유저 타고난 일주: {user_p}
- 오늘 들어온 일진 기운: {today_p}

보여주신 운세 앱 화면(총운 점수, 타이틀, 본문 단락, 애정운, 금전운 등)의 레이아웃에 완벽히 들어맞도록, 풍부하고 깊이 있는 오늘의 운세를 작성해줘.

반드시 아래 JSON 구조로만 응답해야 해. Markdown 펜스(```json)나 다른 설명 없이 오직 순수 JSON만 출력해.

{{
    "score": 78,
    "one_liner": "호랑이 기운에 뱀의 날카로움이 얹힌 날, 포커페이스가 생명!",
    "main_title": "나 이런 사람이야 ~ 오늘 하루 당당하게",
    "total_analysis": "힘들고 어려웠던 일이 있었다면 조금만 참고 기다리는 것이 좋습니다. 안좋았던 기운이 좋은 기세로 넘어가는 과도기에 서있기 때문에 약간 불안한 모습을 보일 수 있습니다. 하지만 조금만 인내한다면 어려웠던 일이 해결되며 대박을 향한 첫 걸음으로 바뀔 수 있습니다. 작은 비난을 들을 여지가 있었으나, 훨씬 더 큰 긍정적인 사건이 일어나 작은 풍파는 금세 잊히게 되며 오후에는 큰 운이 기대됩니다.",
    "love_relation": "굳이 말하지 않아도 자신이 어떤 생각을 하고 있는지, 무엇을 싫어하는지 다 파악하는 상대방입니다. 상대방에 그만큼 익숙해져 있다는 의미입니다. 또한 상대방의 눈으로 상대방의 마음을 그대로 느낄 수 있기 때문에 그만큼 자신의 감정에 대해서 조심해야 할 필요성이 있습니다. 그만큼 안 좋은 운은 좋은 운에서는 안 좋은 다는 것이지요. 자신이 상대방에 대해 진심으로 사랑하는 마음을 가지고 솔직하고 진솔하게 한다면 더 많이 아름다운 시간이 만들어질 것입니다.",
    "money_wealth": "오전에는 아닌 밤중 홍두깨와 같은 일이 있었으나, 훗날 다른 금전적인 사건이 일어나 작은 풍파는 금세 잊히는 금세 잊혀지게 되며 오후에 금운이 기대됩니다.",
    "work_study": "주변의 잔소리나 억지 피드백에 휘둘리지 말고 내 페이스를 지키는 것이 중요합니다. 묵직한 태산처럼 흔들리지 않으면 오후부터 네가 주도권을 잡게 됩니다.",
    "health_mental": "신경이 예민해져 두통이나 소화 불량이 올 수 있으니, 따뜻한 차를 마시며 멘탈을 다잡으세요.",
    "golden_time": "오후 2시 ~ 오후 5시",
    "lucky_items": {{
        "color": "딥 그린",
        "food": "따뜻한 허브티",
        "number": "5"
    }},
    "avoid_action": "오전에 기분 나쁘다고 충동적으로 홧김 소비 하거나 메신저로 예민하게 반응하기"
}}
"""

# 4. API 호출
response = client.models.generate_content(
    model='gemini-3.5-flash',
    contents=prompt
)

raw_text = response.text.strip()
if raw_text.startswith("```json"):
    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

# 5. 결과 출력
data = json.loads(raw_text)
print("=== [앱 화면 적용 테스트 결과] ===")
print(f"점수: {data['score']}점")
print(f"한 줄 카피: {data['one_liner']}")
print(f"\n[총운: {data['main_title']}]")
print(data['total_analysis'])
print(f"\n[애정운]")
print(data['love_relation'])
print(f"\n[금전운]")
print(data['money_wealth'])
print(f"\n[직장/학업운]")
print(data['work_study'])
print(f"\n[골든타임] {data['golden_time']}")
print(f"[액땜 방지] {data['avoid_action']}")
