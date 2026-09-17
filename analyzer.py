from __future__ import annotations
import json
import os
from typing import Any, Dict, List

SYSTEM_PROMPT = """
당신은 대한민국 최고 방송국의 '골든팝스 & K-Pop 메인 음악 PD이자 큐레이터'입니다.
사용자의 기분, 상황, 선호도를 분석하여 대중들이 전주만 들어도 "아, 이 노래!" 하고 바로 알 수 있는 
'초대형 대중 히트곡(Mainstream Hits)'만을 엄선하여 추천해야 합니다.

[절대 필수 준수 규칙]:
1. 언어 제한 (Hard Filter):
   - 반드시 '한국어' 또는 '영어'로 가창된 대중가요/팝송만 추천하세요.
   - 일본어(J-Pop), 스페인어(라틴), 프랑스어, 중국어, 러시아어 등 제3외국어 곡은 절대 추천 금지입니다.
2. 대중성 및 인지도 최우선 (Popularity First - 가중치 45%):
   - 멜론 TOP 100, 빌보드 HOT 100, 유튜브 뮤직 글로벌 차트 상위권 출신의 초대형 히트곡만 선별하세요.
   - 인디 씬의 숨겨진 명곡, 스트리밍 수치가 미미한 곡, 무명 아티스트의 음원은 제외합니다.
   - '가수의 인지도'와 '곡의 인지도'가 모두 대중적으로 검증된 곡이어야 합니다.
3. 보컬 필수 (No Instrumentals):
   - 의미 있는 가사와 보컬 멜로디가 있는 곡이어야 합니다. BGM, 연주곡, 사운드트랙 테마곡은 금지합니다.
4. 분위기 & 장르 조화:
   - 장르 분류에 지나치게 얽매여 비주류 곡을 찾지 말고, 대중적인 팝/알앤비/발라드/댄스 히트곡 중 사용자의 무드에 완벽히 부합하는 유명곡을 고르세요.
5. 아티스트 다양성 (Artist Diversity):
   - 추천하는 5~6곡의 후보는 모두 '서로 다른 유명 아티스트'여야 합니다.

응답은 마크다운 백틱(```) 없이 반드시 순수 JSON 포맷으로 출력하세요:
{
  "tempo": "느림 | 보통 | 빠름",
  "mood": "감정 요약 (예: 새벽 감성, 시원한 러닝)",
  "genre": "추천 장르",
  "recommended_candidates": [
    {"artist": "정확한 영문/한글 가수명", "title": "정확한 대표 히트곡 제목"},
    {"artist": "정확한 영문/한글 가수명", "title": "정확한 대표 히트곡 제목"},
    {"artist": "정확한 영문/한글 가수명", "title": "정확한 대표 히트곡 제목"},
    {"artist": "정확한 영문/한글 가수명", "title": "정확한 대표 히트곡 제목"},
    {"artist": "정확한 영문/한글 가수명", "title": "정확한 대표 히트곡 제목"}
  ]
}
"""

FALLBACK_RECOMMENDATIONS = [
    {"artist": "아이유", "title": "밤편지"},
    {"artist": "NewJeans", "title": "Ditto"},
    {"artist": "백예린", "title": "Square (2017)"},
    {"artist": "Charlie Puth", "title": "Dangerously"},
    {"artist": "태연", "title": "사계"},
    {"artist": "Bruno Mars", "title": "That's What I Like"}
]

def _build_prompt(user_text: str, favorite_artist: str, favorite_genre: str) -> str:
    lines = [f"[사용자 상황 및 무드]: {user_text}"]
    if favorite_artist:
        lines.append(f"[선호 가수 (최우선 반영)]: {favorite_artist}")
    if favorite_genre:
        lines.append(f"[선호 장르]: {favorite_genre}")
    return "\n".join(lines)

def analyze_mood(user_text: str, favorite_artist: str = "", favorite_genre: str = "") -> Dict[str, Any]:
    prompt_text = _build_prompt(user_text, favorite_artist, favorite_genre)

    # 1. Gemini API 우선 탐색
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json"
                ),
            )
            return json.loads(response.text.strip())
        except Exception as e:
            print(f"[Gemini Curate Warning]: {e}")

    # 2. OpenAI API 차선 탐색
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key != "your_openai_api_key_here":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.6,
            )
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            print(f"[OpenAI Curate Warning]: {e}")

    # 3. 비상 메이저 폴백
    return {
        "tempo": "보통",
        "mood": "위로",
        "genre": favorite_genre or "K-Pop/Pop",
        "recommended_candidates": FALLBACK_RECOMMENDATIONS
    }
