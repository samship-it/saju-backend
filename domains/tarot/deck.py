"""메이저 아르카나 22장 메타데이터. 이미지: domains/tarot/타로이미지/{id}.jpg"""

BASE_CARDS = [
    {"id": 0, "name_kr": "광대", "name_en": "The Fool"},
    {"id": 1, "name_kr": "마법사", "name_en": "The Magician"},
    {"id": 2, "name_kr": "여사제", "name_en": "The High Priestess"},
    {"id": 3, "name_kr": "여황제", "name_en": "The Empress"},
    {"id": 4, "name_kr": "황제", "name_en": "The Emperor"},
    {"id": 5, "name_kr": "교황", "name_en": "The Hierophant"},
    {"id": 6, "name_kr": "연인", "name_en": "The Lovers"},
    {"id": 7, "name_kr": "전차", "name_en": "The Chariot"},
    {"id": 8, "name_kr": "힘", "name_en": "Strength"},
    {"id": 9, "name_kr": "은둔자", "name_en": "The Hermit"},
    {"id": 10, "name_kr": "운명의 수레바퀴", "name_en": "Wheel of Fortune"},
    {"id": 11, "name_kr": "정의", "name_en": "Justice"},
    {"id": 12, "name_kr": "매달린 사람", "name_en": "The Hanged Man"},
    {"id": 13, "name_kr": "죽음", "name_en": "Death"},
    {"id": 14, "name_kr": "절제", "name_en": "Temperance"},
    {"id": 15, "name_kr": "악마", "name_en": "The Devil"},
    {"id": 16, "name_kr": "탑", "name_en": "The Tower"},
    {"id": 17, "name_kr": "별", "name_en": "The Star"},
    {"id": 18, "name_kr": "달", "name_en": "The Moon"},
    {"id": 19, "name_kr": "태양", "name_en": "The Sun"},
    {"id": 20, "name_kr": "심판", "name_en": "Judgement"},
    {"id": 21, "name_kr": "세계", "name_en": "The World"},
]

CARD_BY_ID = {c["id"]: c for c in BASE_CARDS}


def image_url(card_id: int) -> str:
    return f"/static/tarot_images/{card_id}.jpg"
