import os
import json
import random
import logging
from typing import Dict, Any, List
import docx  # python-docx
from core.gemini_client import generate_gemini_analysis

logger = logging.getLogger(__name__)

# 파일 및 폴더 경로 설정 (실제 경로에 맞춰 확인 필요)
DOCX_PATH = r"C:\운세\타로카드 설명.docx"  # 워드 파일 경로
IMAGE_DIR_PATH = r"C:\운세\타로이미지"     # 타로 이미지 폴더 경로

# 메이저 아르카나 22장 기본 매핑 데이터
BASE_CARDS = [
    {"id": 0, "name_kr": "바보", "name_en": "The Fool", "image_name": "0_fool.png"},
    {"id": 1, "name_kr": "마법사", "name_en": "The Magician", "image_name": "1_magician.png"},
    {"id": 2, "name_kr": "고위 여사제", "name_en": "The High Priestess", "image_name": "2_high_priestess.png"},
    {"id": 3, "name_kr": "여황제", "name_en": "The Empress", "image_name": "3_empress.png"},
    {"id": 4, "name_kr": "황제", "name_en": "The Emperor", "image_name": "4_emperor.png"},
    {"id": 5, "name_kr": "교황", "name_en": "The Hierophant", "image_name": "5_hierophant.png"},
    {"id": 6, "name_kr": "연인", "name_en": "The Lovers", "image_name": "6_lovers.png"},
    {"id": 7, "name_kr": "전차", "name_en": "The Chariot", "image_name": "7_chariot.png"},
    {"id": 8, "name_kr": "힘", "name_en": "Strength", "image_name": "8_strength.png"},
    {"id": 9, "name_kr": "은둔자", "name_en": "The Hermit", "image_name": "9_hermit.png"},
    {"id": 10, "name_kr": "운명의 수레바퀴", "name_en": "Wheel of Fortune", "image_name": "10_wheel_of_fortune.png"},
    {"id": 11, "name_kr": "정의", "name_en": "Justice", "image_name": "11_justice.png"},
    {"id": 12, "name_kr": "매달린 사람", "name_en": "The Hanged Man", "image_name": "12_hanged_man.png"},
    {"id": 13, "name_kr": "죽음", "name_en": "Death", "image_name": "13_death.png"},
    {"id": 14, "name_kr": "절제", "name_en": "Temperance", "image_name": "14_temperance.png"},
    {"id": 15, "name_kr": "악마", "name_en": "The Devil", "image_name": "15_devil.png"},
    {"id": 16, "name_kr": "탑", "name_en": "The Tower", "image_name": "16_tower.png"},
    {"id": 17, "name_kr": "별", "name_en": "The Star", "image_name": "17_star.png"},
    {"id": 18, "name_kr": "달", "name_en": "The Moon", "image_name": "18_moon.png"},
    {"id": 19, "name_kr": "태양", "name_en": "The Sun", "image_name": "19_sun.png"},
    {"id": 20, "name_kr": "심판", "name_en": "Judgement", "image_name": "20_judgement.png"},
    {"id": 21, "name_kr": "세계", "name_en": "The World", "image_name": "21_world.png"}
]

def load_word_descriptions(filepath: str = DOCX_PATH) -> Dict[str, Any]:
    """워드 파일에서 타로 카드 정방향/역방향 텍스트 설명을 읽어오는 함수"""
    if not os.path.exists(filepath):
        logger.warning(f"워드 파일 경로가 존재하지 않습니다: {filepath}")
        return {}

    try:
        doc = docx.Document(filepath)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        return {"raw_text": full_text}
    except Exception as e:
        logger.error(f"docx 읽기 오류: {e}")
        return {}

def draw_random_tarot_cards_with_orientation(count: int = 3) -> List[Dict[str, Any]]:
    """랜덤으로 카드를 뽑으면서 50% 확률로 정방향/역방향(is_reversed)을 결정하는 함수"""
    selected = random.sample(BASE_CARDS, min(count, len(BASE_CARDS)))
    drawn_cards = []

    for card in selected:
        is_reversed = random.choice([True, False])
        card_info = {
            "id": card["id"],
            "name_kr": card["name_kr"],
            "name_en": card["name_en"],
            "image_url": f"/static/tarot_images/{card['image_name']}",
            "is_reversed": is_reversed,
            "orientation": "역방향 (Reversed)" if is_reversed else "정방향 (Upright)"
        }
        drawn_cards.append(card_info)

    return drawn_cards

def generate_tarot_reading(
    question: str,
    reading_type: str = "오늘의 운세",
    selected_card_ids: List[int] = None,
    custom_orientations: List[bool] = None
) -> Dict[str, Any]:
    """정방향/역방향 카드와 운세 유형, 워드 파일 설명을 조합하여 Gemini AI 타로 리딩 생성"""
    # 1. 카드 뽑기 및 정/역방향 설정
    if not selected_card_ids:
        drawn_cards = draw_random_tarot_cards_with_orientation(3)
    else:
        drawn_cards = []
        for idx, c_id in enumerate(selected_card_ids):
            card = next((c for c in BASE_CARDS if c["id"] == c_id), None)
            if card:
                is_rev = custom_orientations[idx] if custom_orientations and idx < len(custom_orientations) else random.choice([True, False])
                drawn_cards.append({
                    "id": card["id"],
                    "name_kr": card["name_kr"],
                    "name_en": card["name_en"],
                    "image_url": f"/static/tarot_images/{card['image_name']}",
                    "is_reversed": is_rev,
                    "orientation": "역방향 (Reversed)" if is_rev else "정방향 (Upright)"
                })

    # 2. 워드 파일 설명 읽어오기
    word_data = load_word_descriptions()
    word_text_context = word_data.get("raw_text", "기본 타로 상징을 바탕으로 해석하세요.")

    system_instruction = """
    당신은 심도 있는 통찰력을 지닌 타로 리더입니다.
    사용자의 질문과 뽑힌 카드들의 정방향/역방향 상태, 그리고 제공된 워드 파일의 카드 설명 자료를 정교하게 반영하여 풀이해야 합니다.
    특히 역방향 카드는 해당 카드의 에너지가 지연되거나, 과해지거나, 내면화되거나, 반대 의미로 나타나는 상태임을 명확히 반영하여 해석해 주세요.
    반드시 유효한 JSON 형식으로만 응답해야 하며, Markdown 형식(```json 등)은 절대 포함하지 마세요.
    """

    prompt = f"""
    [운세 유형]: {reading_type}
    [사용자 질문/고민]: {question}
    
    [뽑힌 카드 배치 및 정/역방향 정보]:
    {json.dumps(drawn_cards, ensure_ascii=False, indent=2)}

    [참고 타로 카드 워드 설명 자료]:
    {word_text_context[:2000]}

    위 카드의 정방향/역방향 특성과 자료를 바탕으로, 특별히 '{reading_type}'의 관점에 맞춰 다음 JSON 스키마 형식으로 반환해 주세요:
    {{
        "reading_type": "{reading_type}",
        "question": "{question}",
        "cards_drawn": {json.dumps(drawn_cards, ensure_ascii=False)},
        "reading_summary": "전체 타로 리딩 한 줄 핵심 요약",
        "detailed_reading": {{
            "past_or_cause": "첫 번째 카드의 정/역방향 상태를 반영한 원인/배경 해석",
            "present_situation": "두 번째 카드의 정/역방향 상태를 반영한 현재 상황 해석",
            "future_and_advice": "세 번째 카드의 정/역방향 상태를 반영한 미래 전망 및 해결책"
        }},
        "actionable_tip": "정/역방향 조언을 반영한 오늘 실천 팁"
    }}
    """

    try:
        raw_response = generate_gemini_analysis(prompt, system_instruction)
        cleaned_json = raw_response.strip().replace("```json", "").replace("```", "").strip()
        analysis_result = json.loads(cleaned_json)
    except Exception as e:
        logger.error(f"Tarot service JSON parsing error: {e}")
        analysis_result = {
            "reading_type": reading_type,
            "question": question,
            "cards_drawn": drawn_cards,
            "reading_summary": f"[{reading_type}] 카드들의 정방향과 역방향 흐름을 신중하게 조율해야 할 시점입니다.",
            "detailed_reading": {
                "past_or_cause": "이전 상황의 영향이 현재까지 이어지며 내부적인 변화를 요구하고 있습니다.",
                "present_situation": "역방향 카드가 있다면 에너지가 다소 막히거나 지연될 수 있으니 신중을 기하세요.",
                "future_and_advice": "문제의 원인을 직면하고 관점을 전환하면 긍정적인 반전이 일어납니다."
            },
            "actionable_tip": "서두르지 말고 자신의 마음과 주변의 상황을 한 번 더 점검해 보세요."
        }

    return {
        "status": "success",
        "tarot_report": analysis_result
    }