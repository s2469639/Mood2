from __future__ import annotations
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
