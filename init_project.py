# init_project.py
# Moodify Enterprise All-in-One Setup Script (v4.1: Bugfix & Production Mainstream Curation)
# Author: 15-year Senior Python CTO

import os

print("🚀 [Moodify System Setup] 전체 프로젝트 환경 구축을 시작합니다...")

# 1. 필수 디렉토리 구조 생성
DIRECTORIES = [
    os.path.join("templates"),
    os.path.join("static"),
    os.path.join("static", "css"),
    os.path.join("static", "js"),
]

for d in DIRECTORIES:
    os.makedirs(d, exist_ok=True)
    print(f"  📁 디렉토리 검증/생성: {d}")

FILES = {}

# -------------------------------------------------------------
# A. requirements.txt
# -------------------------------------------------------------
FILES["requirements.txt"] = """Flask>=3.0.0,<4.0.0
requests>=2.31.0,<3.0.0
openai>=1.30.0,<2.0.0
google-genai>=0.1.0
python-dotenv>=1.0.0
"""

# -------------------------------------------------------------
# B. .env & .gitignore
# -------------------------------------------------------------
FILES[".env"] = """# Flask 설정
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev-secret-key-change-me-for-production

# LLM API Keys (API 키 미입력 시에도 고품질 메이저 폴백 곡으로 정상 가동)
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
"""

FILES[".gitignore"] = """# Security & Environment Variables
.env
.env.local
*.env

# SQLite & Runtime Databases
*.db
*.sqlite
*.sqlite3
moodify.db

# Python Bytecode & Cache
__pycache__/
*.py[cod]
*$py.class

# Virtual Environments
venv/
.venv/
env/

# OS & IDE
.DS_Store
Thumbs.db
.idea/
.vscode/
"""

# -------------------------------------------------------------
# C. database.py
# -------------------------------------------------------------
FILES["database.py"] = '''from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime
import sqlite3
from typing import Any, Dict, List, Optional

DB_NAME = "moodify.db"

@contextmanager
def get_db_connection():
    """데이터베이스 연결 컨텍스트 매니저"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """테이블 스키마 및 인덱스 초기화"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                mood TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                preview_url TEXT,
                artwork TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diary_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                note TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, friend_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (friend_id) REFERENCES users(id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user_date ON history(user_id, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_diary_user_date ON diary_notes(user_id, date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_friends_user ON friends(user_id)")
        conn.commit()

def create_user(username: str, password_hash: str) -> Optional[int]:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, now_str),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def save_history(user_id: int, user_text: str, songs: List[Dict[str, Any]]) -> None:
    if not songs:
        return
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    records = [
        (
            user_id,
            date_str,
            time_str,
            user_text,
            song.get("title", "Unknown Title"),
            song.get("artist", "Unknown Artist"),
            song.get("preview_url", ""),
            song.get("artwork") or song.get("album_art", ""),
        )
        for song in songs
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO history (user_id, date, time, mood, title, artist, preview_url, artwork)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        conn.commit()

def get_calendar_history(user_id: int, year: int, month: int) -> Dict[str, List[Dict[str, Any]]]:
    month_prefix = f"{year:04d}-{month:02d}"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date, time, mood, title, artist, artwork
            FROM history
            WHERE user_id = ? AND date LIKE ?
            ORDER BY date ASC, time ASC
        """, (user_id, f"{month_prefix}%"))
        rows = [dict(row) for row in cursor.fetchall()]

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["date"], []).append(row)
    return grouped

def upsert_diary_note(user_id: int, date_str: str, note: str) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM diary_notes WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE diary_notes SET note = ?, updated_at = ? WHERE id = ?",
                (note, now_str, row["id"]),
            )
        else:
            cursor.execute(
                "INSERT INTO diary_notes (user_id, date, note, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, date_str, note, now_str),
            )
        conn.commit()

def get_diary_note(user_id: int, date_str: str) -> str:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT note FROM diary_notes WHERE user_id = ? AND date = ?",
            (user_id, date_str),
        )
        row = cursor.fetchone()
        return row["note"] if row and row["note"] else ""

def get_diary_month(user_id: int, year: int, month: int) -> Dict[str, str]:
    month_prefix = f"{year:04d}-{month:02d}"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT date, note FROM diary_notes WHERE user_id = ? AND date LIKE ?",
            (user_id, f"{month_prefix}%"),
        )
        return {row["date"]: (row["note"] or "") for row in cursor.fetchall()}

def add_friend(user_id: int, friend_id: int) -> bool:
    if user_id == friend_id:
        return False
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)",
                (user_id, friend_id, now_str),
            )
            cursor.execute(
                "INSERT INTO friends (user_id, friend_id, created_at) VALUES (?, ?, ?)",
                (friend_id, user_id, now_str),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def get_friends(user_id: int) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id AS id, u.username AS username, f.created_at AS created_at
            FROM friends f
            JOIN users u ON u.id = f.friend_id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def remove_friend(user_id: int, friend_id: int) -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM friends WHERE user_id = ? AND friend_id = ?", (user_id, friend_id))
        cursor.execute("DELETE FROM friends WHERE user_id = ? AND friend_id = ?", (friend_id, user_id))
        conn.commit()
'''

# -------------------------------------------------------------
# D. auth.py
# -------------------------------------------------------------
FILES["auth.py"] = '''from __future__ import annotations
from werkzeug.security import check_password_hash, generate_password_hash

def hash_password(raw_password: str) -> str:
    return generate_password_hash(raw_password)

def verify_password(raw_password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, raw_password)
'''

# -------------------------------------------------------------
# E. analyzer.py (대중성 45% 우선 + 한국어/영어 전용 큐레이터 엔진)
# -------------------------------------------------------------
FILES["analyzer.py"] = '''from __future__ import annotations
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
    return "\\n".join(lines)

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
'''

# -------------------------------------------------------------
# F. music.py (오염된 URL 복원 + Deezer Rank 인기도 정렬 엔진)
# -------------------------------------------------------------
FILES["music.py"] = '''from __future__ import annotations
import random
from typing import Any, Dict, List, Optional
import urllib.parse
import requests

MINIMUM_POPULARITY_THRESHOLD = 150000

VERIFIED_MAINSTREAM_FALLBACK = [
    {
        "title": "밤편지",
        "artist": "아이유",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music118/v4/b8/b5/0b/b8b50b73-030a-3ecb-665e-bc8e20235940/cover_IU_ThroughTheNight.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music118/v4/b8/b5/0b/b8b50b73-030a-3ecb-665e-bc8e20235940/cover_IU_ThroughTheNight.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview115/v4/b7/c1/9d/b7c19d4e-1282-1cbe-41bf-3df08e9a2be9/mzaf_10526084092497793448.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=%EC%95%84%EC%9D%B4%EC%9C%A0+%EB%B0%A4%ED%8E%B8%EC%A7%80",
        "popularity": 900000
    },
    {
        "title": "Ditto",
        "artist": "NewJeans",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/4c/76/85/4c768571-0847-f32f-b48a-a3a8309df507/cover_NewJeans_OMG.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/4c/76/85/4c768571-0847-f32f-b48a-a3a8309df507/cover_NewJeans_OMG.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview122/v4/e5/22/07/e52207a7-5431-1e96-a836-8cb9622d100a/mzaf_3990812977823908953.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=NewJeans+Ditto",
        "popularity": 950000
    },
    {
        "title": "Square (2017)",
        "artist": "백예린",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/48/80/4f/48804f58-6934-8c70-6644-33827ec32f5d/cover_YerinBaek_Square.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music113/v4/48/80/4f/48804f58-6934-8c70-6644-33827ec32f5d/cover_YerinBaek_Square.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview125/v4/71/bf/20/71bf2092-be29-d055-6b58-e4905d41a7d6/mzaf_4840898517227447814.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=%EB%B0%B1%EC%98%88%EB%A6%B0+Square",
        "popularity": 850000
    },
    {
        "title": "That's What I Like",
        "artist": "Bruno Mars",
        "artwork": "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/c3/84/6b/c3846b0a-f0f5-3006-25f0-6c9fa1ec329f/075679901452.jpg/600x600bb.jpg",
        "album_art": "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/c3/84/6b/c3846b0a-f0f5-3006-25f0-6c9fa1ec329f/075679901452.jpg/600x600bb.jpg",
        "preview_url": "https://audio-ssl.itunes.apple.com/itunes-assets/AudioPreview115/v4/64/43/16/64431697-3a1e-8e47-e234-a0da61f67f6b/mzaf_2089408719056637375.plus.aac.p.m4a",
        "yt_music_url": "https://music.youtube.com/search?q=Bruno+Mars+That%27s+What+I+Like",
        "popularity": 920000
    }
]

def search_deezer_track(title: str, artist: str) -> Optional[Dict[str, Any]]:
    base_url = "https://api.deezer.com/search"
    query = f'track:"{title}" artist:"{artist}"'
    params = {"q": query, "limit": 3, "order": "RANKING"}

    try:
        resp = requests.get(base_url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        
        if not data:
            resp = requests.get(base_url, params={"q": f"{artist} {title}", "limit": 3, "order": "RANKING"}, timeout=5)
            data = resp.json().get("data", [])

        if not data:
            return None

        best_match = max(data, key=lambda x: x.get("rank", 0))
        album = best_match.get("album") or {}
        artwork = album.get("cover_big") or album.get("cover_medium") or ""
        q_enc = urllib.parse.quote(f"{best_match.get('artist', {}).get('name', artist)} {best_match.get('title', title)}")

        return {
            "title": best_match.get("title", title),
            "artist": best_match.get("artist", {}).get("name", artist),
            "artwork": artwork,
            "album_art": artwork,
            "preview_url": best_match.get("preview", ""),
            "yt_music_url": f"https://music.youtube.com/search?q={q_enc}",
            "popularity": best_match.get("rank", 0)
        }
    except Exception as e:
        print(f"[Deezer Match Error] {artist} - {title}: {e}")
        return None

def search_itunes_track(title: str, artist: str) -> Optional[Dict[str, Any]]:
    base_url = "https://itunes.apple.com/search"
    term = f"{artist} {title}"
    params = {"term": term, "media": "music", "entity": "song", "limit": 3, "country": "KR"}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(base_url, params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        track = results[0]
        raw_art = track.get("artworkUrl100", "")
        art = raw_art.replace("100x100bb.jpg", "600x600bb.jpg") if raw_art else ""
        q_enc = urllib.parse.quote(f"{track.get('artistName', artist)} {track.get('trackName', title)}")

        return {
            "title": track.get("trackName", title),
            "artist": track.get("artistName", artist),
            "artwork": art,
            "album_art": art,
            "preview_url": track.get("previewUrl", ""),
            "yt_music_url": f"https://music.youtube.com/search?q={q_enc}",
            "popularity": 500000
        }
    except Exception as e:
        print(f"[iTunes Match Error] {artist} - {title}: {e}")
        return None

def curate_mainstream_songs(candidates: List[Dict[str, str]], limit: int = 4) -> List[Dict[str, Any]]:
    resolved_tracks: List[Dict[str, Any]] = []
    seen_artists = set()

    for item in candidates:
        artist_name = item.get("artist", "").strip()
        song_title = item.get("title", "").strip()
        if not artist_name or not song_title:
            continue

        artist_key = artist_name.lower().replace(" ", "")
        if artist_key in seen_artists:
            continue

        track_data = search_deezer_track(song_title, artist_name)
        if not track_data:
            track_data = search_itunes_track(song_title, artist_name)

        if track_data and track_data.get("artwork"):
            resolved_tracks.append(track_data)
            seen_artists.add(artist_key)

    resolved_tracks.sort(key=lambda x: x.get("popularity", 0), reverse=True)

    if len(resolved_tracks) < limit:
        for fallback in VERIFIED_MAINSTREAM_FALLBACK:
            fb_artist_key = fallback["artist"].lower().replace(" ", "")
            if fb_artist_key not in seen_artists:
                resolved_tracks.append(fallback)
                seen_artists.add(fb_artist_key)
            if len(resolved_tracks) >= limit:
                break

    return resolved_tracks[:limit]
'''

# -------------------------------------------------------------
# G. app.py
# -------------------------------------------------------------
FILES["app.py"] = '''from __future__ import annotations
import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

from analyzer import analyze_mood
from auth import hash_password, verify_password
from database import (
    add_friend,
    create_user,
    get_calendar_history,
    get_diary_month,
    get_diary_note,
    get_friends,
    get_user_by_username,
    init_db,
    remove_friend,
    save_history,
    upsert_diary_note,
)
from music import curate_mainstream_songs

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
init_db()

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
        return view_func(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    logged_in = "user_id" in session
    username = session.get("username", "")
    return render_template("index.html", logged_in=logged_in, username=username)

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    invited_by = (data.get("invited_by") or "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "아이디와 비밀번호를 입력해주세요."}), 400
    if len(password) < 4:
        return jsonify({"success": False, "message": "비밀번호는 4자 이상이어야 합니다."}), 400

    user_id = create_user(username, hash_password(password))
    if user_id is None:
        return jsonify({"success": False, "message": "이미 사용 중인 아이디입니다."}), 409

    if invited_by and invited_by != username:
        inviter = get_user_by_username(invited_by)
        if inviter:
            add_friend(user_id, inviter["id"])

    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"success": True, "username": username})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"success": True, "username": user["username"]})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/recommend", methods=["POST"])
@login_required
def recommend():
    try:
        data = request.get_json(silent=True) or {}
        user_text = data.get("text", "").strip()
        favorite_artist = (data.get("favorite_artist") or "").strip()
        favorite_genre = (data.get("favorite_genre") or "").strip()

        if not user_text:
            return jsonify({"success": False, "message": "문장을 입력해주세요."}), 400

        analysis_result = analyze_mood(user_text, favorite_artist, favorite_genre)
        candidates = analysis_result.get("recommended_candidates", [])

        songs = curate_mainstream_songs(candidates, limit=4)
        save_history(session["user_id"], user_text, songs)

        return jsonify({
            "success": True,
            "analysis": analysis_result,
            "songs": songs
        })
    except Exception as e:
        app.logger.error(f"추천 파이프라인 오류: {e}")
        return jsonify({"success": False, "message": "서버 처리 중 오류가 발생했습니다."}), 500

@app.route("/api/calendar", methods=["GET"])
@login_required
def calendar():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "year, month 파라미터가 필요합니다."}), 400

    grouped = get_calendar_history(session["user_id"], year, month)
    return jsonify({"success": True, "calendar": grouped})

@app.route("/api/diary", methods=["GET"])
@login_required
def diary_get():
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"success": False, "message": "date 파라미터가 필요합니다."}), 400
    note = get_diary_note(session["user_id"], date_str)
    return jsonify({"success": True, "date": date_str, "note": note})

@app.route("/api/diary", methods=["POST"])
@login_required
def diary_save():
    data = request.get_json(silent=True) or {}
    date_str = (data.get("date") or "").strip()
    note = (data.get("note") or "").strip()
    if not date_str:
        return jsonify({"success": False, "message": "date가 필요합니다."}), 400
    upsert_diary_note(session["user_id"], date_str, note)
    return jsonify({"success": True})

@app.route("/api/diary/month", methods=["GET"])
@login_required
def diary_month():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "year, month 파라미터가 필요합니다."}), 400

    notes = get_diary_month(session["user_id"], year, month)
    return jsonify({"success": True, "notes": notes})

@app.route("/api/friends", methods=["GET"])
@login_required
def friends_list():
    friends = get_friends(session["user_id"])
    return jsonify({"success": True, "friends": friends})

@app.route("/api/friends/add", methods=["POST"])
@login_required
def friends_add():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()

    if not username:
        return jsonify({"success": False, "message": "친구 아이디를 입력해주세요."}), 400
    if username == session.get("username"):
        return jsonify({"success": False, "message": "자기 자신은 추가할 수 없습니다."}), 400

    target = get_user_by_username(username)
    if not target:
        return jsonify({"success": False, "message": "존재하지 않는 아이디입니다."}), 404

    ok = add_friend(session["user_id"], target["id"])
    if not ok:
        return jsonify({"success": False, "message": "이미 친구로 등록되어 있습니다."}), 409

    return jsonify({"success": True})

@app.route("/api/friends/<int:friend_user_id>", methods=["DELETE"])
@login_required
def friends_remove(friend_user_id):
    remove_friend(session["user_id"], friend_user_id)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
'''

# -------------------------------------------------------------
# H. templates/index.html (시계 갱신, 리플 전환, 일기 상단배치 UI)
# -------------------------------------------------------------
FILES[os.path.join("templates", "index.html")] = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Moodify - 감성 음악 추천</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet" />

  <style>
    :root {
      --font-display: 'Nunito', sans-serif;
      --font-body: 'Outfit', sans-serif;
      --purple: #8A52F3;
      --pink: #DE359D;
      --deep: #2D1457;
      --muted: #7E6E90;
      --muted-soft: #A396B2;
      --card-bg: rgba(255, 255, 255, 0.72);
      --card-border: rgba(138, 82, 243, 0.15);
    }
    * { box-sizing: border-box; -webkit-font-smoothing: antialiased; margin: 0; padding: 0; }
    ::-webkit-scrollbar { display: none; }
    body {
      font-family: var(--font-body);
      min-height: 100vh;
      display: flex; align-items: center; justify-content: center;
      background: linear-gradient(180deg, #F5E9FF 0%, #FFF4F8 45%, #FFFFFF 75%, #F0FFF4 100%);
      padding: 20px;
    }
    .phone {
      position: relative; width: 390px; height: 844px;
      border-radius: 44px; overflow: hidden;
      box-shadow: 0 32px 80px rgba(124, 111, 239, 0.22), 0 4px 16px rgba(0, 0, 0, 0.08);
      display: flex; flex-direction: column;
      background: #FFFFFF;
    }
    .statusbar {
      position: absolute; top: 0; left: 0; right: 0; z-index: 50;
      display: flex; justify-content: space-between; align-items: center;
      padding: 20px 32px 4px; pointer-events: none;
    }
    .statusbar__time { font-weight: 600; font-size: 14px; color: #5b3d8a; }
    .statusbar__notch { width: 16px; height: 12px; border-radius: 3px; border: 2px solid #5b3d8a; opacity: 0.7; }
    
    .screen {
      position: absolute; inset: 0; display: none; flex-direction: column; padding-top: 44px;
      opacity: 0;
      transition: opacity 0.25s ease;
    }
    .screen.is-active {
      display: flex;
      opacity: 1;
    }

    button, .icon-btn, .mood-chip, .calendar__cell {
      transition: transform 0.12s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.12s ease;
    }
    button:active, .icon-btn:active, .mood-chip:active {
      transform: scale(0.93) !important;
    }

    .screen-transition-overlay {
      position: absolute;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: radial-gradient(circle, var(--pink) 0%, var(--purple) 70%, var(--deep) 100%);
      pointer-events: none;
      z-index: 40;
      transform: translate(-50%, -50%) scale(0);
      opacity: 0.95;
    }
    .screen-transition-overlay.animate {
      animation: rippleExpand 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
    @keyframes rippleExpand {
      0% {
        transform: translate(-50%, -50%) scale(0);
        opacity: 0.95;
      }
      70% {
        opacity: 0.95;
      }
      100% {
        transform: translate(-50%, -50%) scale(90);
        opacity: 0;
      }
    }

    .icon-btn {
      width: 38px; height: 38px; border-radius: 12px;
      background: rgba(138, 82, 243, 0.10); border: 1.5px solid rgba(138, 82, 243, 0.20);
      display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
      font-size: 16px;
    }
    .icon-btn--dark { background: rgba(255, 255, 255, 0.15); border-color: rgba(255, 255, 255, 0.25); }
    .section-label { font-family: var(--font-display); font-weight: 700; font-size: 13px; color: var(--muted); margin: 20px 0 10px; }
    .screen--home { background: linear-gradient(145deg, #f3e8ff 0%, #fce7f3 35%, #fff7ed 70%, #ecfdf5 100%); }
    .home__scroll { flex: 1; overflow-y: auto; padding: 8px 24px 0; }
    .home__header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .home__header-actions { display: flex; gap: 8px; }
    .brand { display: flex; align-items: center; gap: 8px; }
    .brand__logo {
      width: 38px; height: 38px; border-radius: 50%;
      background: linear-gradient(135deg, var(--purple), var(--pink));
      display: flex; align-items: center; justify-content: center;
      color: white; font-size: 18px; box-shadow: 0 4px 14px rgba(138, 82, 243, 0.4);
    }
    .brand__name { font-family: var(--font-display); font-weight: 800; font-size: 22px; color: var(--deep); }
    .home__title { font-family: var(--font-display); font-weight: 800; font-size: 26px; line-height: 1.2; color: var(--deep); }
    .home__subtitle { font-weight: 400; font-size: 14px; color: var(--muted); margin-top: 4px; }
    .textarea-card {
      position: relative; margin-top: 16px;
      background: var(--card-bg); backdrop-filter: blur(12px);
      border: 1.5px solid var(--card-border); border-radius: 22px; padding: 16px; height: 130px;
    }
    .textarea-card textarea {
      width: 100%; height: 100%; border: none; outline: none; resize: none;
      background: transparent; font-family: var(--font-body); font-size: 14.5px; color: var(--deep); line-height: 1.4;
    }
    .textarea-card textarea::placeholder { color: var(--muted-soft); }
    .textarea-card__count { position: absolute; right: 14px; bottom: 10px; font-size: 11px; color: var(--muted-soft); }
    .mood-chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .mood-chip {
      display: flex; align-items: center; gap: 5px; padding: 8px 14px;
      background: var(--card-bg); border: 1.5px solid var(--card-border);
      border-radius: 100px; font-family: var(--font-body); font-weight: 500; font-size: 12.5px;
      color: var(--deep); cursor: pointer;
    }
    .mood-chip.is-selected {
      background: linear-gradient(135deg, var(--purple), var(--pink));
      color: white; border-color: transparent; box-shadow: 0 4px 14px rgba(138, 82, 243, 0.35);
    }
    .home__cta { padding: 12px 24px 24px; }
    .cta-btn {
      width: 100%; height: 54px; display: flex; align-items: center; justify-content: center; gap: 8px;
      background: linear-gradient(135deg, var(--purple), var(--pink)); border: none; border-radius: 20px;
      font-family: var(--font-display); font-weight: 700; font-size: 16px; color: white; cursor: pointer;
      box-shadow: 0 8px 24px rgba(138, 82, 243, 0.35);
    }
    .screen--results { background: linear-gradient(160deg, #3b1f6b 0%, #2d1554 50%, #1e0f3d 100%); padding: 44px 20px 0; }
    .results__header { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
    .results__heading { flex: 1; }
    .results__mood { font-size: 12.5px; color: #c4b5fd; font-weight: 500; }
    .results__title { font-family: var(--font-display); font-weight: 800; font-size: 20px; color: white; margin-top: 2px; }
    .song-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; align-content: start; overflow-y: auto; }
    .song-card { background: none; border: none; padding: 0; text-align: left; }
    .song-card__art { position: relative; width: 100%; aspect-ratio: 1; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3); cursor: pointer; }
    .song-card__art img { width: 100%; height: 100%; object-fit: cover; }
    .song-card__title { font-family: var(--font-display); font-weight: 700; font-size: 13.5px; color: white; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .song-card__artist { font-size: 11.5px; color: #a78bda; margin-top: 1px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .song-card__play {
      position: absolute; right: 8px; bottom: 8px; width: 30px; height: 30px; border-radius: 50%;
      background: rgba(0, 0, 0, 0.55); backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center; cursor: pointer;
    }

    /* ---- 로그인 / 회원가입 ---- */
    .screen--auth { background: linear-gradient(145deg, #f3e8ff 0%, #fce7f3 35%, #fff7ed 70%, #ecfdf5 100%); }
    .auth-scroll { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 24px; overflow-y: auto; }
    .auth-logo { text-align: center; margin-bottom: 28px; }
    .auth-logo .brand__logo { margin: 0 auto 10px; }
    .auth-title { font-family: var(--font-display); font-weight: 800; font-size: 24px; color: var(--deep); text-align: center; }
    .auth-subtitle { font-size: 13px; color: var(--muted); text-align: center; margin-top: 6px; margin-bottom: 24px; }
    .invite-badge { text-align: center; font-size: 12px; color: var(--purple); font-weight: 700; margin: -14px 0 16px; min-height: 16px; }
    .input-card {
      position: relative; margin-bottom: 12px;
      background: var(--card-bg); backdrop-filter: blur(12px);
      border: 1.5px solid var(--card-border); border-radius: 16px; padding: 4px 16px;
    }
    .input-card input {
      width: 100%; height: 48px; border: none; outline: none;
      background: transparent; font-family: var(--font-body); font-size: 14.5px; color: var(--deep);
    }
    .input-card input::placeholder { color: var(--muted-soft); }
    .auth-error { color: #d1224b; font-size: 12.5px; text-align: center; min-height: 16px; margin-bottom: 8px; }
    .auth-switch { text-align: center; font-size: 13px; color: var(--muted); margin-top: 16px; }
    .auth-switch .link { color: var(--purple); font-weight: 700; cursor: pointer; }

    /* ---- 캘린더 / 친구초대 헤더 ---- */
    .screen--calendar { background: linear-gradient(145deg, #f3e8ff 0%, #fce7f3 35%, #fff7ed 70%, #ecfdf5 100%); padding: 44px 20px 0; }
    .calendar__header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
    .calendar__title { flex: 1; text-align: center; font-family: var(--font-display); font-weight: 800; font-size: 16px; color: var(--deep); }
    .calendar__nav { display: flex; gap: 6px; }
    .calendar__weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 11px; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
    .calendar__grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
    .calendar__cell {
      aspect-ratio: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
      border-radius: 12px; font-size: 12.5px; color: var(--deep); background: rgba(255, 255, 255, 0.55); cursor: pointer;
    }
    .calendar__cell.is-empty { background: transparent; cursor: default; }
    .calendar__cell.has-record { background: linear-gradient(135deg, var(--purple), var(--pink)); color: white; font-weight: 700; }
    .calendar__cell.is-selected { box-shadow: 0 0 0 2px var(--deep) inset; }
    .calendar__dot { width: 4px; height: 4px; border-radius: 50%; background: white; margin-top: 2px; }
    .calendar__entries { margin-top: 18px; flex: 1; overflow-y: auto; padding-bottom: 24px; }
    .calendar__entry { display: flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.85); border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; }
    .calendar__entry img { width: 40px; height: 40px; border-radius: 10px; object-fit: cover; flex-shrink: 0; }
    .calendar__entry-info { flex: 1; min-width: 0; }
    .calendar__entry-title { font-weight: 700; font-size: 13px; color: var(--deep); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .calendar__entry-artist { font-size: 11.5px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .calendar__entry-time { font-size: 11px; color: var(--muted-soft); flex-shrink: 0; }
    .calendar__empty { text-align: center; color: var(--muted); font-size: 13px; margin-top: 20px; }
    .diary-card { height: 90px; margin-top: 8px; margin-bottom: 12px; }
    .diary-save-btn { height: 44px; font-size: 14px; margin-bottom: 14px; }

    /* ---- 친구초대 ---- */
    .friends-scroll { padding: 0 0 24px; flex: 1; overflow-y: auto; }
    .friend-item { display: flex; align-items: center; gap: 10px; background: rgba(255, 255, 255, 0.85); border-radius: 14px; padding: 10px 12px; margin-bottom: 8px; }
    .friend-item__avatar {
      width: 36px; height: 36px; border-radius: 50%;
      background: linear-gradient(135deg, var(--purple), var(--pink));
      display: flex; align-items: center; justify-content: center; color: white; font-weight: 700; font-size: 14px; flex-shrink: 0;
    }
    .friend-item__name { flex: 1; font-weight: 700; font-size: 13.5px; color: var(--deep); }
    .friend-item__remove { font-size: 11px; color: var(--muted); cursor: pointer; padding: 4px 8px; }
  </style>
</head>
<body>
  <div class="phone" id="phoneContainer">
    <div class="statusbar">
      <span class="statusbar__time" id="statusClock">9:41</span>
      <span class="statusbar__notch"></span>
    </div>

    <!-- 0-A. 로그인 화면 -->
    <section class="screen screen--auth {{ 'is-active' if not logged_in else '' }}" data-screen="login">
      <div class="auth-scroll">
        <div class="auth-logo">
          <div class="brand__logo">✦</div>
          <p class="auth-title">moodify</p>
          <p class="auth-subtitle">감정을 기록하고 음악으로 기억하세요</p>
        </div>
        <div class="input-card"><input type="text" id="loginUsername" placeholder="아이디" autocomplete="username" /></div>
        <div class="input-card"><input type="password" id="loginPassword" placeholder="비밀번호" autocomplete="current-password" /></div>
        <p class="auth-error" id="loginError"></p>
        <button class="cta-btn" id="loginBtn">로그인</button>
        <p class="auth-switch">계정이 없으신가요? <span class="link" id="goRegister">회원가입</span></p>
      </div>
    </section>

    <!-- 0-B. 회원가입 화면 -->
    <section class="screen screen--auth" data-screen="register">
      <div class="auth-scroll">
        <div class="auth-logo">
          <div class="brand__logo">✦</div>
          <p class="auth-title">회원가입</p>
          <p class="auth-subtitle">나만의 감정 음악 캘린더를 시작해보세요</p>
        </div>
        <p class="invite-badge" id="inviteNotice"></p>
        <div class="input-card"><input type="text" id="registerUsername" placeholder="아이디" autocomplete="username" /></div>
        <div class="input-card"><input type="password" id="registerPassword" placeholder="비밀번호 (4자 이상)" autocomplete="new-password" /></div>
        <div class="input-card"><input type="password" id="registerPassword2" placeholder="비밀번호 확인" autocomplete="new-password" /></div>
        <p class="auth-error" id="registerError"></p>
        <button class="cta-btn" id="registerBtn">가입하고 시작하기</button>
        <p class="auth-switch">이미 계정이 있으신가요? <span class="link" id="goLogin">로그인</span></p>
      </div>
    </section>

    <!-- 1. 메인 홈 화면 -->
    <section class="screen screen--home {{ 'is-active' if logged_in else '' }}" data-screen="home">
      <div class="home__scroll">
        <header class="home__header">
          <div class="brand">
            <span class="brand__logo">✦</span>
            <span class="brand__name">moodify</span>
          </div>
          <div class="home__header-actions">
            <button class="icon-btn" id="friendsBtn" aria-label="친구초대">👥</button>
            <button class="icon-btn" id="calendarBtn" aria-label="캘린더">📅</button>
            <button class="icon-btn" id="logoutBtn" aria-label="로그아웃">🚪</button>
          </div>
        </header>

        <h1 class="home__title">What's your<br />mood now?</h1>
        <p class="home__subtitle">{{ username }}님, 지금 상황이나 기분을 자유롭게 적어보세요</p>

        <div class="textarea-card">
          <textarea id="situation" maxlength="200" placeholder="예) 한강 공원에서 러닝 중! 상쾌하고 신나는 노래"></textarea>
          <span class="textarea-card__count"><span id="charCount">0</span>/200</span>
        </div>

        <p class="section-label">추천 무드 칩</p>
        <div class="mood-chips">
          <button class="mood-chip is-selected" data-text="🏃 러닝 중 에너지 넘치는 신나는 노래">🏃 러닝</button>
          <button class="mood-chip" data-text="🌙 새벽 감성 잔잔하고 차분한 어쿠스틱">🌙 새벽 감성</button>
          <button class="mood-chip" data-text="☕ 여유로운 오후 카페에서 듣는 음악">☕ 카페</button>
          <button class="mood-chip" data-text="🌸 설레는 봄 산책할 때 듣는 기분 좋은 음악">🌸 봄 산책</button>
          <button class="mood-chip" data-text="💫 지친 하루를 위로해주는 힐링 음악">💫 힐링</button>
        </div>

        <p class="section-label">취향 반영 (선택)</p>
        <div class="input-card"><input type="text" id="favArtist" placeholder="좋아하는 가수 (예: 아이유, 아이브)" /></div>
        <div class="input-card"><input type="text" id="favGenre" placeholder="좋아하는 장르 (예: 발라드, 팝, R&B)" /></div>
      </div>

      <div class="home__cta">
        <button class="cta-btn" id="submitBtn">
          음악 찾아보기 →
        </button>
      </div>
    </section>

    <!-- 2. 추천 결과 화면 -->
    <section class="screen screen--results" data-screen="results">
      <header class="results__header">
        <button class="icon-btn icon-btn--dark" id="backBtn" aria-label="뒤로">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="#e9d5ff" stroke-width="1.8" stroke-linecap="round"/></svg>
        </button>
        <div class="results__heading">
          <p class="results__mood" id="resultBadge">#무드추천</p>
          <h2 class="results__title">이런 곡은 어때요?</h2>
        </div>
      </header>

      <div class="song-grid" id="songGrid"></div>
    </section>

    <!-- 3. 캘린더 화면 -->
    <section class="screen screen--calendar" data-screen="calendar">
      <header class="calendar__header">
        <button class="icon-btn" id="calBackBtn" aria-label="뒤로">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="#2D1457" stroke-width="1.8" stroke-linecap="round"/></svg>
        </button>
        <p class="calendar__title" id="calendarTitle">2026년 9월</p>
        <div class="calendar__nav">
          <button class="icon-btn" id="calPrevBtn" aria-label="이전 달">◀</button>
          <button class="icon-btn" id="calNextBtn" aria-label="다음 달">▶</button>
        </div>
      </header>
      <div class="calendar__weekdays">
        <span>일</span><span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span>토</span>
      </div>
      <div class="calendar__grid" id="calendarGrid"></div>
      <div class="calendar__entries" id="calendarEntries"></div>
    </section>

    <!-- 4. 친구 초대 화면 -->
    <section class="screen screen--calendar" data-screen="friends">
      <header class="calendar__header">
        <button class="icon-btn" id="friendsBackBtn" aria-label="뒤로">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M10 3L5 8l5 5" stroke="#2D1457" stroke-width="1.8" stroke-linecap="round"/></svg>
        </button>
        <p class="calendar__title">친구 초대</p>
        <div class="calendar__nav" style="width: 38px;"></div>
      </header>
      <div class="friends-scroll">
        <p class="section-label" style="margin-top: 4px;">내 초대 링크</p>
        <div class="input-card"><input type="text" id="inviteLink" readonly /></div>
        <button class="cta-btn" id="copyInviteBtn" style="margin-bottom: 20px;">링크 복사하기</button>

        <p class="section-label">아이디로 친구 추가</p>
        <div class="input-card"><input type="text" id="addFriendInput" placeholder="친구 아이디 입력" /></div>
        <p class="auth-error" id="friendsError"></p>
        <button class="cta-btn" id="addFriendBtn" style="margin-bottom: 20px;">친구 추가</button>

        <p class="section-label">내 친구 목록</p>
        <div id="friendsListEl"></div>
      </div>
    </section>
  </div>

  <audio id="globalAudio"></audio>

  <script>
    /* 1. 실시간 시계 타이머 */
    function updateClock() {
      const clockEl = document.getElementById("statusClock");
      if (!clockEl) return;
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, "0");
      const minutes = String(now.getMinutes()).padStart(2, "0");
      clockEl.textContent = `${hours}:${minutes}`;
    }
    updateClock();
    setInterval(updateClock, 1000);

    /* 2. 클릭 위치 기반 원형 그라디언트 리플 트랜지션 */
    const phoneContainer = document.getElementById("phoneContainer");
    let isTransitioning = false;

    function transitionToScreen(name, triggerEvent = null) {
      if (isTransitioning) return;
      const targetScreen = document.querySelector(`[data-screen="${name}"]`);
      if (!targetScreen) return;

      if (!triggerEvent) {
        showScreen(name);
        return;
      }

      isTransitioning = true;
      const rect = phoneContainer.getBoundingClientRect();
      const clickX = (triggerEvent.clientX || (rect.left + rect.width / 2)) - rect.left;
      const clickY = (triggerEvent.clientY || (rect.top + rect.height / 2)) - rect.top;

      const ripple = document.createElement("div");
      ripple.className = "screen-transition-overlay";
      ripple.style.left = `${clickX}px`;
      ripple.style.top = `${clickY}px`;
      phoneContainer.appendChild(ripple);

      requestAnimationFrame(() => {
        ripple.classList.add("animate");
      });

      setTimeout(() => {
        showScreen(name);
      }, 180);

      setTimeout(() => {
        if (ripple.parentElement) ripple.remove();
        isTransitioning = false;
      }, 420);
    }

    const IS_LOGGED_IN = {{ 'true' if logged_in else 'false' }};
    const INITIAL_USERNAME = "{{ username }}";
    const urlParams = new URLSearchParams(window.location.search);
    const INVITE_FROM = urlParams.get("invite") || "";

    const situation = document.getElementById("situation");
    const charCount = document.getElementById("charCount");
    const submitBtn = document.getElementById("submitBtn");
    const backBtn = document.getElementById("backBtn");
    const audio = document.getElementById("globalAudio");

    function escapeHtml(str) {
      return String(str == null ? "" : str).replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }

    function showScreen(name) {
      document.querySelectorAll(".screen").forEach(s => s.classList.remove("is-active"));
      const target = document.querySelector(`[data-screen="${name}"]`);
      if (target) target.classList.add("is-active");
      if (name !== "results") { audio.pause(); }
    }

    if (situation) {
      situation.addEventListener("input", () => { charCount.textContent = situation.value.length; });

      document.querySelectorAll(".mood-chip").forEach(chip => {
        chip.addEventListener("click", () => {
          document.querySelectorAll(".mood-chip").forEach(c => c.classList.remove("is-selected"));
          chip.classList.add("is-selected");
          situation.value = chip.dataset.text;
          charCount.textContent = situation.value.length;
        });
      });
    }

    backBtn.addEventListener("click", (e) => transitionToScreen("home", e));

    submitBtn.addEventListener("click", async (e) => {
      const text = situation.value.trim();
      const favoriteArtist = document.getElementById("favArtist").value.trim();
      const favoriteGenre = document.getElementById("favGenre").value.trim();

      if (!text) {
        alert("기분이나 상황을 입력해주세요!");
        return;
      }

      submitBtn.textContent = "명곡 큐레이션 중...";
      submitBtn.disabled = true;

      try {
        const response = await fetch("/api/recommend", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text, favorite_artist: favoriteArtist, favorite_genre: favoriteGenre })
        });

        if (response.status === 401) {
          location.reload();
          return;
        }

        const res = await response.json();

        if (res.success && res.songs && res.songs.length > 0) {
          renderSongs(res.songs, res.analysis);
          transitionToScreen("results", e);
        } else {
          alert(res.message || "음악 추천을 불러오지 못했습니다.");
        }
      } catch (err) {
        alert("서버와의 통신에 실패했습니다.");
      } finally {
        submitBtn.textContent = "음악 찾아보기 →";
        submitBtn.disabled = false;
      }
    });

    let currentSongs = [];

    function renderSongs(songs, analysis) {
      currentSongs = songs;
      const grid = document.getElementById("songGrid");
      const badge = document.getElementById("resultBadge");
      if (analysis) {
        badge.textContent = `#${escapeHtml(analysis.genre || '대중가요')} #${escapeHtml(analysis.mood || '인기곡')}`;
      }
      grid.innerHTML = songs.map((song, idx) => `
        <div class="song-card">
          <div class="song-card__art" data-action="youtube" data-index="${idx}">
            <img src="${song.artwork || song.album_art || 'https://via.placeholder.com/300'}" alt="${escapeHtml(song.title)}" loading="lazy">
            <span class="song-card__play" data-action="preview" data-index="${idx}">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="white"><path d="M5 3.5v9l7-4.5z"/></svg>
            </span>
          </div>
          <p class="song-card__title">${escapeHtml(song.title)}</p>
          <p class="song-card__artist">${escapeHtml(song.artist)}</p>
        </div>
      `).join("");

      grid.querySelectorAll('[data-action="preview"]').forEach(el => {
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          const idx = parseInt(el.getAttribute("data-index"), 10);
          playSong(currentSongs[idx].preview_url);
        });
      });

      grid.querySelectorAll('[data-action="youtube"]').forEach(el => {
        el.addEventListener("click", () => {
          const idx = parseInt(el.getAttribute("data-index"), 10);
          const song = currentSongs[idx];
          if (song && song.yt_music_url) {
            window.open(song.yt_music_url, "_blank", "noopener");
          }
        });
      });
    }

    function playSong(url) {
      if (!url) {
        alert("30초 미리듣기 음원이 제공되지 않는 곡입니다.");
        return;
      }
      if (audio.src === url && !audio.paused) {
        audio.pause();
      } else {
        audio.src = url;
        audio.play();
      }
    }

    /* ---------------- 로그인 / 회원가입 ---------------- */
    const loginBtn = document.getElementById("loginBtn");
    const registerBtn = document.getElementById("registerBtn");
    const logoutBtn = document.getElementById("logoutBtn");
    const goRegister = document.getElementById("goRegister");
    const goLogin = document.getElementById("goLogin");
    const inviteNotice = document.getElementById("inviteNotice");

    if (goRegister) goRegister.addEventListener("click", (e) => transitionToScreen("register", e));
    if (goLogin) goLogin.addEventListener("click", (e) => transitionToScreen("login", e));

    if (!IS_LOGGED_IN && INVITE_FROM) {
      if (inviteNotice) inviteNotice.textContent = `${INVITE_FROM}님의 초대로 가입해요 🎉`;
      showScreen("register");
    }

    if (loginBtn) {
      loginBtn.addEventListener("click", async () => {
        const username = document.getElementById("loginUsername").value.trim();
        const password = document.getElementById("loginPassword").value;
        const errorEl = document.getElementById("loginError");
        errorEl.textContent = "";
        if (!username || !password) { errorEl.textContent = "아이디와 비밀번호를 입력해주세요."; return; }

        try {
          const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
          });
          const data = await res.json();
          if (data.success) {
            location.reload();
          } else {
            errorEl.textContent = data.message || "로그인에 실패했습니다.";
          }
        } catch (e) {
          errorEl.textContent = "서버와의 통신에 실패했습니다.";
        }
      });
    }

    if (registerBtn) {
      registerBtn.addEventListener("click", async () => {
        const username = document.getElementById("registerUsername").value.trim();
        const password = document.getElementById("registerPassword").value;
        const password2 = document.getElementById("registerPassword2").value;
        const errorEl = document.getElementById("registerError");
        errorEl.textContent = "";
        if (!username || !password) { errorEl.textContent = "아이디와 비밀번호를 입력해주세요."; return; }
        if (password !== password2) { errorEl.textContent = "비밀번호가 일치하지 않습니다."; return; }

        try {
          const res = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password, invited_by: INVITE_FROM })
          });
          const data = await res.json();
          if (data.success) {
            location.reload();
          } else {
            errorEl.textContent = data.message || "회원가입에 실패했습니다.";
          }
        } catch (e) {
          errorEl.textContent = "서버와의 통신에 실패했습니다.";
        }
      });
    }

    if (logoutBtn) {
      logoutBtn.addEventListener("click", async () => {
        await fetch("/api/logout", { method: "POST" });
        location.reload();
      });
    }

    /* ---------------- 캘린더 + 일기 메모 ---------------- */
    const calendarBtn = document.getElementById("calendarBtn");
    const calBackBtn = document.getElementById("calBackBtn");
    const calPrevBtn = document.getElementById("calPrevBtn");
    const calNextBtn = document.getElementById("calNextBtn");

    const calState = {
      year: new Date().getFullYear(),
      month: new Date().getMonth() + 1,
      data: {},
      notes: {}
    };

    function pad2(n) { return String(n).padStart(2, "0"); }

    async function loadCalendar() {
      const grid = document.getElementById("calendarGrid");
      const entries = document.getElementById("calendarEntries");
      const title = document.getElementById("calendarTitle");
      title.textContent = `${calState.year}년 ${calState.month}월`;
      grid.innerHTML = "";
      entries.innerHTML = "";

      try {
        const [calRes, diaryRes] = await Promise.all([
          fetch(`/api/calendar?year=${calState.year}&month=${calState.month}`),
          fetch(`/api/diary/month?year=${calState.year}&month=${calState.month}`)
        ]);
        if (calRes.status === 401 || diaryRes.status === 401) { location.reload(); return; }
        const calData = await calRes.json();
        const diaryData = await diaryRes.json();
        calState.data = (calData.success && calData.calendar) ? calData.calendar : {};
        calState.notes = (diaryData.success && diaryData.notes) ? diaryData.notes : {};
      } catch (e) {
        calState.data = {};
        calState.notes = {};
      }

      const firstDay = new Date(calState.year, calState.month - 1, 1).getDay();
      const daysInMonth = new Date(calState.year, calState.month, 0).getDate();

      for (let i = 0; i < firstDay; i++) {
        const empty = document.createElement("div");
        empty.className = "calendar__cell is-empty";
        grid.appendChild(empty);
      }

      for (let d = 1; d <= daysInMonth; d++) {
        const dateKey = `${calState.year}-${pad2(calState.month)}-${pad2(d)}`;
        const cell = document.createElement("div");
        cell.className = "calendar__cell";
        const hasRecord = !!calState.data[dateKey] || !!(calState.notes[dateKey] && calState.notes[dateKey].trim());
        if (hasRecord) cell.classList.add("has-record");
        cell.innerHTML = `${d}` + (hasRecord ? '<span class="calendar__dot"></span>' : "");
        cell.addEventListener("click", () => selectDate(dateKey, cell));
        grid.appendChild(cell);
      }

      entries.innerHTML = '<p class="calendar__empty">날짜를 선택해서 기록을 확인해보세요</p>';
    }

    function selectDate(dateKey, cellEl) {
      document.querySelectorAll(".calendar__cell").forEach(c => c.classList.remove("is-selected"));
      if (cellEl) cellEl.classList.add("is-selected");

      const entries = document.getElementById("calendarEntries");
      const records = calState.data[dateKey] || [];
      const note = calState.notes[dateKey] || "";

      let songsHtml;
      if (records.length > 0) {
        songsHtml = records.map(r => `
          <div class="calendar__entry">
            <img src="${r.artwork || 'https://via.placeholder.com/80'}" alt="${escapeHtml(r.title)}">
            <div class="calendar__entry-info">
              <p class="calendar__entry-title">${escapeHtml(r.title)}</p>
              <p class="calendar__entry-artist">${escapeHtml(r.artist)} · ${escapeHtml(r.mood)}</p>
            </div>
            <span class="calendar__entry-time">${escapeHtml(r.time)}</span>
          </div>
        `).join("");
      } else {
        songsHtml = '<p class="calendar__empty">이 날 들은 음악이 없어요</p>';
      }

      entries.innerHTML = `
        <p class="section-label" style="margin-top: 4px;">이 날의 일기 기록</p>
        <div class="textarea-card diary-card">
          <textarea id="diaryNote" maxlength="300" placeholder="오늘 있었던 일이나 감정을 짧게 남겨보세요">${escapeHtml(note)}</textarea>
        </div>
        <button class="cta-btn diary-save-btn" id="diarySaveBtn">일기 저장</button>
        <p class="auth-error" id="diarySavedMsg" style="color: var(--purple);"></p>
        
        <p class="section-label" style="margin-top: 14px;">청취한 음악</p>
        ${songsHtml}
      `;

      document.getElementById("diarySaveBtn").addEventListener("click", async () => {
        const textEl = document.getElementById("diaryNote");
        const msgEl = document.getElementById("diarySavedMsg");
        try {
          const res = await fetch("/api/diary", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ date: dateKey, note: textEl.value })
          });
          const data = await res.json();
          if (data.success) {
            calState.notes[dateKey] = textEl.value;
            msgEl.style.color = "var(--purple)";
            msgEl.textContent = "저장했어요 ✓";
            if (cellEl && textEl.value.trim()) cellEl.classList.add("has-record");
            setTimeout(() => { msgEl.textContent = ""; }, 1500);
          } else {
            msgEl.style.color = "#d1224b";
            msgEl.textContent = data.message || "저장에 실패했습니다.";
          }
        } catch (e) {
          msgEl.style.color = "#d1224b";
          msgEl.textContent = "서버와의 통신에 실패했습니다.";
        }
      });
    }

    if (calendarBtn) {
      calendarBtn.addEventListener("click", (e) => {
        transitionToScreen("calendar", e);
        loadCalendar();
      });
    }
    if (calBackBtn) calBackBtn.addEventListener("click", (e) => transitionToScreen("home", e));
    if (calPrevBtn) {
      calPrevBtn.addEventListener("click", () => {
        calState.month -= 1;
        if (calState.month < 1) { calState.month = 12; calState.year -= 1; }
        loadCalendar();
      });
    }
    if (calNextBtn) {
      calNextBtn.addEventListener("click", () => {
        calState.month += 1;
        if (calState.month > 12) { calState.month = 1; calState.year += 1; }
        loadCalendar();
      });
    }

    /* ---------------- 친구 초대 ---------------- */
    const friendsBtn = document.getElementById("friendsBtn");
    const friendsBackBtn = document.getElementById("friendsBackBtn");
    const copyInviteBtn = document.getElementById("copyInviteBtn");
    const addFriendBtn = document.getElementById("addFriendBtn");
    const inviteLinkInput = document.getElementById("inviteLink");

    if (inviteLinkInput && IS_LOGGED_IN) {
      inviteLinkInput.value = `${window.location.origin}/?invite=${encodeURIComponent(INITIAL_USERNAME)}`;
    }

    if (friendsBtn) {
      friendsBtn.addEventListener("click", (e) => {
        transitionToScreen("friends", e);
        loadFriends();
      });
    }
    if (friendsBackBtn) friendsBackBtn.addEventListener("click", (e) => transitionToScreen("home", e));

    if (copyInviteBtn) {
      copyInviteBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(inviteLinkInput.value);
        } catch (e) {
          inviteLinkInput.removeAttribute("readonly");
          inviteLinkInput.select();
          document.execCommand("copy");
          inviteLinkInput.setAttribute("readonly", "true");
        }
        const original = copyInviteBtn.textContent;
        copyInviteBtn.textContent = "복사 완료!";
        setTimeout(() => { copyInviteBtn.textContent = original; }, 1500);
      });
    }

    async function loadFriends() {
      const listEl = document.getElementById("friendsListEl");
      listEl.innerHTML = "";
      try {
        const res = await fetch("/api/friends");
        if (res.status === 401) { location.reload(); return; }
        const data = await res.json();
        const friends = (data.success && data.friends) ? data.friends : [];
        if (friends.length === 0) {
          listEl.innerHTML = '<p class="calendar__empty">아직 추가된 친구가 없어요</p>';
          return;
        }
        listEl.innerHTML = friends.map(f => `
          <div class="friend-item">
            <div class="friend-item__avatar">${escapeHtml((f.username || "?").charAt(0).toUpperCase())}</div>
            <span class="friend-item__name">${escapeHtml(f.username)}</span>
            <span class="friend-item__remove" data-remove="${f.id}">삭제</span>
          </div>
        `).join("");

        listEl.querySelectorAll("[data-remove]").forEach(btn => {
          btn.addEventListener("click", async () => {
            const fid = btn.getAttribute("data-remove");
            await fetch(`/api/friends/${fid}`, { method: "DELETE" });
            loadFriends();
          });
        });
      } catch (e) {
        listEl.innerHTML = '<p class="calendar__empty">친구 목록을 불러오지 못했어요</p>';
      }
    }

    if (addFriendBtn) {
      addFriendBtn.addEventListener("click", async () => {
        const input = document.getElementById("addFriendInput");
        const errorEl = document.getElementById("friendsError");
        const username = input.value.trim();
        errorEl.textContent = "";
        if (!username) { errorEl.textContent = "친구 아이디를 입력해주세요."; return; }

        try {
          const res = await fetch("/api/friends/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username })
          });
          const data = await res.json();
          if (data.success) {
            input.value = "";
            loadFriends();
          } else {
            errorEl.textContent = data.message || "친구 추가에 실패했습니다.";
          }
        } catch (e) {
          errorEl.textContent = "서버와의 통신에 실패했습니다.";
        }
      });
    }
  </script>
</body>
</html>
"""

# 3. 디스크에 모든 파일 일괄 배포
for file_path, content in FILES.items():
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"  📄 파일 배포 완료: {file_path}")

print("\n" + "=" * 65)
print("✅ [설치 완료] Moodify 엔터프라이즈 시스템 구축이 완료되었습니다.")
print("=" * 65)
print("▶ [실행 순서]")
print("1. 의존성 설치: pip install -r requirements.txt")
print("2. 서비스 기동: python app.py")
print("3. 웹 브라우저 접속: http://127.0.0.1:5000")